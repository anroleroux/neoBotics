"""Chassis base box.

An open-top rectangular box with its side walls at +-y removed: a floor and
the two end walls at +-x, all one wall thickness, open at the top and along
both long sides. Four variables drive it: l, b, h and wall. Five ribs on
the floor run along x, from 1 mm in front of the back wall to the cells' front
faces: three battery separators between the four 18650 cells and two side
battery retainers along the open sides.

Assumptions where the description is silent:
- l, b and h are the outside dimensions; the space between the end walls is
  l - 2 wall long and h - wall deep, and runs the full breadth b;
- the floor is as thick as the walls;
- l = 120, b = 80, h = 50 and wall = 3 mm until real sizes are given;
- the box is centred on the z axis and stands on z = 0, with l along x and b
  along y; corners are sharp;
- the ribs are 1 mm thick and 12 mm tall above the floor (the first 8 mm
  plus the requested 4 mm); they stand free of both end walls;
- the cells lie with their negative ends against the back wall (-x), so
  their front faces, positive buttons included, are a cell length in front
  of it; the ribs end there;
- the side retainers' outer faces are flush with the box's sides, at +-b/2,
  and the five ribs are evenly spaced, so the four cell slots share what is
  left of the breadth equally (18.75 mm each, 0.35 mm wider than a cell);
- the cells' diameter and length come from battery_18650 through load_part.
"""
import cadquery as cq

cell = load_part("../battery_18650")  # the cells the ribs hold: diameter, length

# the driving variables, in mm
l = 120.0  # length, outside, along x
b = 80.0  # breadth, outside, along y
h = 50.0  # height, outside, along z
wall = 3.0  # thickness of the walls and the floor

# the battery ribs on the floor
cell_count = 4  # cells side by side across the breadth
rib_t = 1.0  # rib thickness, along y
rib_h = 12.0  # rib height above the floor
rib_back_gap = 1.0  # between the ribs' back ends and the back wall
rib_count = cell_count + 1  # three separators and two side retainers
pitch = (b - rib_t) / cell_count  # rib centre to rib centre
slot = pitch - rib_t  # clear width of a cell slot between two ribs
rib_y = [(i - cell_count / 2) * pitch for i in range(rib_count)]  # rib centres
slot_y = [(i - (cell_count - 1) / 2) * pitch for i in range(cell_count)]  # cell centres
assert slot > cell.diameter, "the cells do not fit between the ribs"
cell_back = -l / 2 + wall  # the cells' negative ends, against the back wall
rib_x0 = cell_back + rib_back_gap  # the ribs' back ends
rib_x1 = cell_back + cell.length  # the ribs' front ends: the cells' front faces
rib_len = rib_x1 - rib_x0

# the space between the end walls, above the floor, through both long sides
channel = (
    cq.Workplane("XY", origin=(0, 0, wall))
    .box(l - 2 * wall, b, h - wall, centered=(True, True, False))
)
result = cq.Workplane("XY").box(l, b, h, centered=(True, True, False)).cut(channel)

# the ribs: on the floor, from just in front of the back wall to the cells' fronts
ribs = (
    cq.Workplane("XY", origin=((rib_x0 + rib_x1) / 2, 0, wall))
    .pushPoints([(0, y) for y in rib_y])
    .rect(rib_len, rib_t)
    .extrude(rib_h)
)
result = result.union(ribs)

regions = {
    "rim": result.faces(">Z"),  # the tops of the two end walls, where the lid sits
    "sides": result.faces(">Y or <Y"),  # the open long sides' edges, where the lid's skirts meet
    "bottom": result.faces("<Z"),
    "rib_tops": result.faces("+Z").filter(  # the tops of the five ribs
        lambda f: abs(f.Center().z - (wall + rib_h)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
