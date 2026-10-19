"""Chassis base plate.

A flat plate the PB4 chassis is built on: corner bolt holes to the standoffs,
a central cable slot, and an M3 motor-mount pattern on each long side.

Assumptions where the description is silent:
- the plate's length runs along x and its width along y, centred on the
  origin, standing on z = 0;
- every hole and the slot go straight through the plate;
- the slot's 40 mm length is overall, end to end, including the rounded ends.
"""
import math

import cadquery as cq

# parameters, in mm
length = 160.0  # along x
width = 120.0  # along y
thickness = 4.0  # along z
corner_radius = 10.0
m4_clearance = 4.5  # corner bolt holes to the standoffs
corner_inset = 10.0  # hole centres from both edges
slot_length = 40.0  # overall, along x
slot_width = 12.0
m3_clearance = 3.4  # motor-mount holes
motor_hole_pitch = 20.0  # between the two holes of a pattern, along x
motor_edge_inset = 12.0  # hole centres from the long edge

corner_holes = [
    (sx * (length / 2 - corner_inset), sy * (width / 2 - corner_inset))
    for sx in (-1, 1) for sy in (-1, 1)
]
motor_holes = [
    (sx * motor_hole_pitch / 2, sy * (width / 2 - motor_edge_inset))
    for sx in (-1, 1) for sy in (-1, 1)
]

result = (
    cq.Workplane("XY")
    .rect(length, width)
    .extrude(thickness)
    .edges("|Z")
    .fillet(corner_radius)
)
top = result.faces(">Z").workplane(origin=(0, 0, thickness))
result = (
    top.pushPoints(corner_holes).hole(m4_clearance)
    .faces(">Z").workplane(origin=(0, 0, thickness))
    .pushPoints(motor_holes).hole(m3_clearance)
    .faces(">Z").workplane(origin=(0, 0, thickness))
    .slot2D(slot_length, slot_width).cutThruAll()
)


def holes(diameter):
    """The through-hole walls of one size: cylinders of area pi * d * thickness."""
    wall = math.pi * diameter * thickness
    return result.faces("%CYLINDER").filter(lambda f: abs(f.Area() - wall) < 1e-3)


regions = {
    "top_face": result.faces(">Z"),  # what mounts on the plate
    "bottom_face": result.faces("<Z"),
    "standoff_holes": holes(m4_clearance),  # the four corner bolts
    "motor_holes": holes(m3_clearance),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
