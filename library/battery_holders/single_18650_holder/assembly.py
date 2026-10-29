"""Single 18650 holder with its cell.

The holder body with an 18650 cell lying in its two rib cradles: along x,
positive terminal towards +x, centred along the length and across the
breadth, resting on the bottoms of the cradles. Both parts come from their
own scripts through load_part, so the assembly follows any change to the
body or the cell.
"""
import cadquery as cq

body = load_part("body")  # open frame, centred, standing on z = 0
cell = load_part("battery")  # standing up: axis along z, negative end on z = 0

# lay the cell down along +x: a quarter turn about y takes its +z axis to +x,
# putting its negative end at x = 0; then centre it along the length, and lower
# it onto the cradles: its underside on their bottoms, rib_base above z = 0
axis_height = body.rib_base + cell.diameter / 2

result = (
    cq.Assembly(name="single_18650_holder")
    .add(body.result, name="body", color=cq.Color(0.22, 0.22, 0.24))
    .add(cell.result, name="battery",
         loc=cq.Location(cq.Vector(-cell.length / 2, 0, axis_height), cq.Vector(0, 1, 0), 90),
         color=cq.Color(0.88, 0.56, 0.24))
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="single_18650_holder")
