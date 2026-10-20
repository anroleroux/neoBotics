"""Chassis base with four 18650 cells.

The base with four 18650 cells lying on its floor along x, side by side
across the breadth, each between the base's back end wall (-x) and the cells'
front line. The two cells at -y (battery_1 and battery_2) are turned round:
their positive terminals point to the back and their negative ends to the
front. The other two point their positive terminals to the front (+x) and
have their negative ends against the back wall. All four are a faded pink.
An IP6505 USB fast-charge board sits on the floor in front of the cells, its
USB port against the front wall, behind the wall's plug hole.
Both parts come from their own
scripts through load_part, so the assembly follows any change to the base's
l, b, h or wall.

Assumptions where the description is silent:
- each cell is centred in its slot between two of the base's ribs (the
  base's slot_y), so no cell touches a rib or its neighbour;
- each cell rests on the floor;
- a turned-round cell fills the same length of its slot, its positive button
  against the back wall.
"""
import cadquery as cq

base = load_part("base")  # floor and end walls at +-x, standing on z = 0
cell = load_part("battery_18650")  # standing up: axis along z, negative end on z = 0
charger = load_part("ip6505_charger")  # port at +x, underside on z = 0

# lay each cell down along x: a quarter turn about y takes its +z axis to +x,
# putting its negative end at x = 0; then move that end onto the inside of the
# back wall, and lift the cell onto the floor.  A turned-round cell takes the
# opposite quarter turn (+z to -x) and has its negative end at the front line.
back_wall_inside = base.cell_back
front_line = base.cell_back + cell.length  # the cells' front faces
axis_height = base.wall + cell.diameter / 2
turned = {1, 2}  # battery_1 and battery_2, at -y: positive terminal to the back
cell_color = cq.Color(0.93, 0.73, 0.79)  # a faded pink

result = cq.Assembly(name="chassis").add(base.result, name="base", color=cq.Color(0.36, 0.56, 0.78))
for i, y in enumerate(base.slot_y):
    n = i + 1
    x, turn = (front_line, -90) if n in turned else (back_wall_inside, 90)
    result.add(
        cell.result,
        name=f"battery_{n}",
        loc=cq.Location(cq.Vector(x, y, axis_height), cq.Vector(0, 1, 0), turn),
        color=cell_color,
    )

# the charger where the base's plug hole expects it
result.add(
    charger.result,
    name="ip6505_charger",
    loc=cq.Location((base.charger_x, base.charger_y, base.charger_z)),
    color=cq.Color(0.15, 0.45, 0.30),  # board green
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="chassis")
