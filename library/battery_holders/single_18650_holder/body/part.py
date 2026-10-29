"""Single 18650 holder body.

A plastic box for one 18650 cell: a hollow rectangular prism, open at the top,
with walls and floor wall thick (1 mm by default). Change wall and the outside
grows with it; the cavity keeps the cell's size.

Assumptions where the description is silent:
- the cavity is sized for one 18650 lying along x: the cell is 18.4 mm across
  and 65.0 mm long, with 0.5 mm clearance at each end and 0.3 mm each side,
  and as deep as it is wide, so the cell sits flush with the rim;
- the floor is the same thickness as the walls;
- no fillets, holes or terminal features yet;
- x is the cell's axis, centred on the origin; the body stands on z = 0.
"""
import cadquery as cq

# parameters, in mm
wall = 1.0  # walls and floor
cell_diameter = 18.4
cell_length = 65.0
end_clearance = 0.5  # at each end, along x
side_clearance = 0.3  # each side, across y and above the cell

inner_length = cell_length + 2 * end_clearance
inner_width = cell_diameter + 2 * side_clearance
inner_depth = inner_width  # the cell sits flush with the rim
length = inner_length + 2 * wall
width = inner_width + 2 * wall
height = inner_depth + wall

block = cq.Workplane("XY").box(length, width, height, centered=(True, True, False))
cavity = (
    cq.Workplane("XY", origin=(0, 0, wall))
    .rect(inner_length, inner_width)
    .extrude(inner_depth)
)
result = block.cut(cavity)

regions = {
    "bottom": result.faces("<Z"),  # the mounting face
    "rim": result.faces(">Z"),  # the open top's edge
    "inner_floor": result.faces(">Z[1]"),  # where the cell rests
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
