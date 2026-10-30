"""M1.2 x 6 countersunk screw.

A slotted countersunk (flat head) machine screw, DIN 963, M1.2 x 0.25,
6 mm long overall: a countersunk screw's length is measured from the top of
its head. Nominal dimensions from the standard; the thread is not modelled.

Assumptions where the description is silent:
- DIN 963 M1.2: head diameter dk 2.3 mm, head height k 0.72 mm (to the
  theoretical sharp edge of the 90 degree cone; the real head's edge is a
  short cylinder at dk), slot 0.3 mm wide and 0.32 mm deep; check these
  against the supplier's drawing;
- the shank is a plain cylinder at the nominal 1.2 mm, with a 0.15 mm 45
  degree chamfer at the tip;
- modelled standing up: tip on z = 0, head on top, its top face at z = length.
"""
import math

import cadquery as cq

# parameters, in mm
diameter = 1.2  # nominal, M1.2
pitch = 0.25  # coarse thread (not modelled)
length = 6.0  # overall, head included
head_diameter = 2.3  # dk
head_height = 0.72  # k
countersink_angle = 90.0  # included, degrees
slot_width = 0.3
slot_depth = 0.32
tip_chamfer = 0.15

half_angle = math.radians(countersink_angle / 2)
cone_height = (head_diameter - diameter) / 2 / math.tan(half_angle)  # shank to dk
edge_height = head_height - cone_height  # the short cylinder at dk, on top
shank_length = length - head_height

shank = (
    cq.Workplane("XY")
    .circle(diameter / 2)
    .extrude(shank_length)
    .faces("<Z").edges().chamfer(tip_chamfer)
)
cone = cq.Solid.makeCone(diameter / 2, head_diameter / 2, cone_height,
                         cq.Vector(0, 0, shank_length))
edge = cq.Workplane("XY", origin=(0, 0, shank_length + cone_height)).circle(
    head_diameter / 2).extrude(edge_height)
slot = cq.Workplane("XY", origin=(0, 0, length - slot_depth)).rect(
    head_diameter * 1.2, slot_width).extrude(slot_depth)
result = shank.union(cq.Workplane("XY").add(cone)).union(edge).cut(slot)

regions = {
    "head_top": result.faces(">Z"),  # flush with the countersunk surface
    "tip": result.faces("<Z"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
