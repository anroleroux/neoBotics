"""18650 battery cell.

A cylindrical 18650 lithium-ion cell: a can with a raised positive terminal
button at one end and a flat negative end at the other. The holder body takes
its cavity and cradles from this cell's diameter and length.

Assumptions where the description is silent:
- 18.4 mm diameter and 65.0 mm overall length, button included: the typical
  measured size of an 18650 (18 x 65 is the nominal size class);
- the positive button is 7 mm across and stands 1 mm proud of the can;
- modelled standing up: axis along z, negative end on z = 0, positive
  terminal on top; the assembly lays it down in the holder.
"""
import math

import cadquery as cq

# parameters, in mm
diameter = 18.4
length = 65.0  # overall, negative end to the top of the positive button
button_diameter = 7.0
button_height = 1.0

can_length = length - button_height

can = cq.Workplane("XY").circle(diameter / 2).extrude(can_length)
button = (
    cq.Workplane("XY", origin=(0, 0, can_length))
    .circle(button_diameter / 2)
    .extrude(button_height)
)
result = can.union(button)

regions = {
    "positive_terminal": result.faces(">Z"),  # the top of the button
    "negative_end": result.faces("<Z"),
    "wrap": result.faces("%CYLINDER").filter(  # the can's side: area pi * d * can_length
        lambda f: abs(f.Area() - math.pi * diameter * can_length) < 1e-3),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
