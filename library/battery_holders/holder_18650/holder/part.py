"""18650 holder body.

A snap-in cradle for one 18650 cell lying along x, with a slot in each end wall
for a contact terminal and two M3 mounting holes through the floor. The holder
owns the terminal's interface (its sheet thickness, contact bump and slot), so
the terminal script sizes itself from these variables.

Assumptions where the description is silent:
- the cell is 18.4 mm across and 65.0 mm long, button included (the measured
  size of an 18650), with 0.2 mm radial clearance in the trough;
- the trough's walls rise to 65 % of the trough's diameter, so its opening
  (about 17.9 mm) is narrower than the cell: it snaps in from above;
- the terminals are 0.5 mm sheet with a 1.0 mm contact bump; each slot is
  0.1 mm thicker than the sheet and 0.4 mm wider than the plate, and runs from
  the top down to the floor;
- the cavity between the slots is sized so the two bumps' tips are exactly
  one cell length apart;
- 1.5 mm floor under the trough, 1.6 mm side walls, 2.5 mm end walls;
- M3 clearance holes (3.4 mm) on the axis, a quarter of the cavity length
  either side of the centre;
- x is the cell's axis (+x the positive end), centred on the origin; the
  holder stands on z = 0.
"""
import cadquery as cq

# the cell, in mm
cell_diameter = 18.4
cell_length = 65.0  # overall, button included
radial_clearance = 0.2

# the terminals this holder takes
terminal_thickness = 0.5  # sheet
terminal_width = 10.0  # plate, across y
bump_height = 1.0  # how far the contact bump stands off the plate
slot_clearance = 0.1  # extra slot thickness, along x
slot_side_clearance = 0.2  # each side of the plate, along y

# the body
floor = 1.5  # under the trough
side_wall = 1.6
end_wall = 2.5  # beyond each slot
wrap = 0.65  # wall height, as a fraction of the trough diameter
hole_diameter = 3.4  # M3 clearance

trough_diameter = cell_diameter + 2 * radial_clearance
axis_height = floor + trough_diameter / 2  # the cell's axis above z = 0
height = floor + wrap * trough_diameter
# the plates sit against the slots' outer faces; their bumps reach in to the cell
cavity_length = cell_length + 2 * (bump_height - slot_clearance)
slot_thickness = terminal_thickness + slot_clearance
slot_width = terminal_width + 2 * slot_side_clearance
length = cavity_length + 2 * (slot_thickness + end_wall)
width = trough_diameter + 2 * side_wall
hole_spacing = cavity_length / 2

block = cq.Workplane("XY").box(length, width, height, centered=(True, True, False))
trough = (
    cq.Workplane("YZ", origin=(-cavity_length / 2, 0, axis_height))
    .circle(trough_diameter / 2)
    .extrude(cavity_length)
)
slots = (
    cq.Workplane("XY", origin=(0, 0, floor))
    .pushPoints([(-(cavity_length + slot_thickness) / 2, 0),
                 ((cavity_length + slot_thickness) / 2, 0)])
    .rect(slot_thickness, slot_width)
    .extrude(height - floor)
)
holes = (
    cq.Workplane("XY")
    .pushPoints([(-hole_spacing / 2, 0), (hole_spacing / 2, 0)])
    .circle(hole_diameter / 2)
    .extrude(floor)
)
result = block.cut(trough).cut(slots).cut(holes)

regions = {
    "bottom": result.faces("<Z"),  # the mounting face
    "mounting_holes": result.faces("%CYLINDER").filter(  # the bores: hole_diameter across
        lambda f: abs(f.BoundingBox().ylen - hole_diameter) < 1e-3),
    "trough": result.faces("%CYLINDER").filter(  # where the cell lies: the cavity's length
        lambda f: abs(f.BoundingBox().xlen - cavity_length) < 1e-3),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
