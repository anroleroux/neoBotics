"""Chassis base box.

An open-top rectangular box: four walls and a floor, all one wall thickness.
Four variables drive it: l, b, h and wall.

Assumptions where the description is silent:
- l, b and h are the outside dimensions; the opening is (l - 2 wall) x
  (b - 2 wall) and the inside depth is h - wall;
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

result = (
    cq.Workplane("XY")
    .box(l, b, h, centered=(True, True, False))
    .faces(">Z")
    .shell(-wall)  # hollow it from the top face inwards: open top, walls and floor of `wall`
)

regions = {
    "rim": result.faces(">Z"),  # the top edge of the walls, where the lid sits
    "bottom": result.faces("<Z"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
