"""Chassis base with four 18650 cells.

The base with four 18650 cells lying on its floor, pointing along x (positive
terminal towards the front, +x), side by side across the breadth, with their
negative ends against the back end wall (-x). Both parts come from their own
scripts through load_part, so the assembly follows any change to the base's
l, b, h or wall.

Assumptions where the description is silent:
- the cells are centred across the breadth with a 0.5 mm gap between
  neighbours, so no two cells touch;
- each cell rests on the floor.
"""
import cadquery as cq

base = load_part("base")  # floor and end walls at +-x, standing on z = 0
cell = load_part("battery_18650")  # standing up: axis along z, negative end on z = 0

count = 4
gap = 0.5  # between neighbouring cells, across the breadth
pitch = cell.diameter + gap

# lay each cell down along +x: a quarter turn about y takes its +z axis to +x,
# putting its negative end at x = 0; then move that end onto the inside of the
# back wall, and lift the cell onto the floor
back_wall_inside = -base.l / 2 + base.wall
axis_height = base.wall + cell.diameter / 2

result = cq.Assembly(name="chassis").add(base.result, name="base", color=cq.Color(0.36, 0.56, 0.78))
for i in range(count):
    y = (i - (count - 1) / 2) * pitch
    result.add(
        cell.result,
        name=f"battery_{i + 1}",
        loc=cq.Location(cq.Vector(back_wall_inside, y, axis_height), cq.Vector(0, 1, 0), 90),
        color=cq.Color(0.88, 0.56, 0.24),
    )

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="chassis")
