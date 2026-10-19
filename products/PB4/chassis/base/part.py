"""Chassis base box.

An open-top rectangular box with its end walls removed: a floor and the two
long side walls, all one wall thickness, open at the top and at both ends.
Four variables drive it: l, b, h and wall.

Assumptions where the description is silent:
- l, b and h are the outside dimensions; the space between the side walls is
  b - 2 wall wide and h - wall deep, and runs the full length l;
- "the sides along the breadth" are the two end walls, which span the
  breadth b at x = +-l/2; the long side walls along l stay;
- the floor is as thick as the walls;
- l = 120, b = 80, h = 50 and wall = 3 mm until real sizes are given;
- the box is centred on the z axis and stands on z = 0, with l along x and b
  along y; corners are sharp.
"""
import cadquery as cq

# the driving variables, in mm
l = 120.0  # length, outside, along x
b = 80.0  # breadth, outside, along y
h = 50.0  # height, outside, along z
wall = 3.0  # thickness of the walls and the floor

# the space between the side walls, above the floor, through both ends
channel = (
    cq.Workplane("XY", origin=(0, 0, wall))
    .box(l, b - 2 * wall, h - wall, centered=(True, True, False))
)
result = cq.Workplane("XY").box(l, b, h, centered=(True, True, False)).cut(channel)

regions = {
    "rim": result.faces(">Z"),  # the tops of the two side walls, where the lid sits
    "side_walls_outside": result.faces("|Y").faces(">Y or <Y"),  # what the lid's skirts cover
    "bottom": result.faces("<Z"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
