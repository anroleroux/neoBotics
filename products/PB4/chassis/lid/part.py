"""Chassis lid.

A flat lid that sits on the rim of the base box, with a locating lip that
drops into the opening so it cannot slide off. It is sized from the box: its
footprint is the box's l x b, and the lip follows the opening, so the lid
still fits when the box's variables change.

Assumptions where the description is silent:
- the lid's plate is as thick as the box's wall and covers the box's full
  outside footprint;
- the lip is one wall thick, 6 mm deep, with 0.2 mm clearance per side to the
  inside of the box walls;
- modelled as installed: lip down, standing on z = 0, centred like the box.
"""
import cadquery as cq

box = load_part("../base")  # the box this lid fits: l, b, h, wall

# parameters, in mm
plate = box.wall  # plate thickness
lip_depth = 6.0  # how far the lip drops into the box
lip_wall = box.wall  # lip thickness
clearance = 0.2  # per side, between the lip and the box's inner walls

opening_l = box.l - 2 * box.wall  # the box's opening
opening_b = box.b - 2 * box.wall
lip_l = opening_l - 2 * clearance  # the lip's outside
lip_b = opening_b - 2 * clearance

lip = (
    cq.Workplane("XY")
    .rect(lip_l, lip_b)
    .rect(lip_l - 2 * lip_wall, lip_b - 2 * lip_wall)
    .extrude(lip_depth)
)
top = (
    cq.Workplane("XY", origin=(0, 0, lip_depth))
    .rect(box.l, box.b)
    .extrude(plate)
)
result = top.union(lip)

regions = {
    "top": result.faces(">Z"),
    "seat": result.faces("<Z[1]"),  # the plate's underside that rests on the box rim
    "lip_bottom": result.faces("<Z"),  # the end of the locating lip, inside the box
}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="part")
