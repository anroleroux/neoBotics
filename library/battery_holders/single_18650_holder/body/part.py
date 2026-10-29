"""Single 18650 holder body.

A plastic frame for one 18650 cell: a hollow rectangular prism, open at the
top and the bottom, with walls wall thick (1 mm by default). Two ribs across
the inside, spaced along the cell's length, each have a semicircular cradle
the cell lies in. Outside each end wall a second wall stands off by the
battery clip's thickness, making a slot, open at the top and the bottom, that
the clip's plate slides into. Change wall and the outside grows with it; the
cavity keeps the cell's size, which comes from the battery part, and the
slots the clip's thickness, so the body follows a change to either.

Assumptions where the description is silent:
- the cavity is sized for the battery part (an 18650, 18.4 mm across and
  65.0 mm long) lying along x, with 0.5 mm clearance at each end and 0.3 mm
  each side;
- the walls are 20 mm tall (as before, when the body had a floor), so the cell
  sits about flush with the rim;
- each rib is 2 mm thick along x, spans the inside wall to wall, and runs from
  the bottom up to the cell's axis, so its cut-out is a full half circle;
- each cradle is 0.1 mm larger in radius than the cell, with 1 mm of rib below
  it; near the walls the rib narrows to 0.2 mm at its top;
- the ribs sit at the cell's quarter points, half its length apart, centred;
- the outer end walls are wall thick and the body's full height and width:
  the side walls run on past the end walls to meet them, so each slot spans
  the cavity's width, inner_width;
- the slots are exactly the clip's sheet thickness (0.3 mm), with no
  clearance, as asked;
- no fillets or holes yet, and no opening in the outer walls for the clip's
  solder lug;
- x is the cell's axis, centred on the origin; the body stands on z = 0.
"""
import cadquery as cq

cell = load_part("../battery")  # the cell this body holds: diameter, length
clip = load_library("battery_contacts/keystone_1107_1")  # the terminal: its sheet thickness

# parameters, in mm
wall = 1.0  # side and end walls
cell_diameter = cell.diameter
cell_length = cell.length
end_clearance = 0.5  # at each end, along x
side_clearance = 0.3  # each side, across y
height = 20.0  # overall: the walls

rib_thickness = 2.0  # along x
rib_spacing = cell_length / 2  # centre to centre, along x
cradle_clearance = 0.1  # on the radius, round the cell
rib_base = 1.0  # rib material under the cradle
slot = clip.thickness  # between each end wall and its outer wall

inner_length = cell_length + 2 * end_clearance
inner_width = cell_diameter + 2 * side_clearance
end_wall_outside = inner_length / 2 + wall  # each end wall's outer face, from the centre
length = inner_length + 2 * (wall + slot + wall)  # overall, over the outer walls
width = inner_width + 2 * wall
cradle_radius = cell_diameter / 2 + cradle_clearance
axis_height = rib_base + cradle_radius  # the cradles' centre, and the ribs' top

frame = (
    cq.Workplane("XY")
    .rect(length, width)
    .rect(inner_length, inner_width)  # the inner loop is the opening, top to bottom
    .extrude(height)
)
slots = (
    cq.Workplane("XY")
    .pushPoints([(-(end_wall_outside + slot / 2), 0), (end_wall_outside + slot / 2, 0)])
    .rect(slot, inner_width)
    .extrude(height)
)
ribs = (
    cq.Workplane("XY")
    .pushPoints([(-rib_spacing / 2, 0), (rib_spacing / 2, 0)])
    .rect(rib_thickness, inner_width)
    .extrude(axis_height)
)
cradle = (
    cq.Workplane("YZ", origin=(-length / 2, 0, axis_height))
    .circle(cradle_radius)
    .extrude(length)
)
result = frame.cut(slots).union(ribs.cut(cradle))

regions = {
    "bottom": result.faces("<Z"),  # the walls' and ribs' feet: the mounting face
    "rim": result.faces(">Z"),  # the open top's edge
    "cradles": result.faces("%CYLINDER"),  # where the cell lies
    "clip_slots": result.faces("|X").filter(  # each slot's two faces, at the end walls' outsides
        lambda f: abs(abs(f.Center().x) - end_wall_outside) < 1e-6
        or abs(abs(f.Center().x) - (end_wall_outside + slot)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="part")
