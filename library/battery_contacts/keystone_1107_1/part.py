"""Keystone 1107-1 battery clip.

A tin-nickel plated spring-steel battery clip: a flat plate with a solder lug
cut from its middle and bent out at an angle, with a solder hole in it. From
the catalogue drawing: 6.4 mm (0.250 in) wide, 13.7 mm (0.538 in) tall, the
lug reaching 4.0 mm (0.156 in) from the plate's back with its end 7.6 mm
(0.300 in) below the top, and a 1.8 mm (0.070 in) solder hole. The spring
that presses on the cell is still to come.

Assumptions where the drawing is silent:
- 0.3 mm sheet;
- the lug is 3.0 mm wide, cut from a window with a 0.4 mm gap each side that
  runs from 1.5 mm above the plate's bottom to 9.6 mm, the lug's root;
- the lug bends out of the plate at its root (a rounded bend on the sheet's
  centreline) and runs straight towards the point 4.0 mm out and 7.6 mm below
  the top; it ends square across where its outer corner reaches 4.0 mm, so its
  end's centre is about 0.05 mm lower than that point;
- the solder hole is through the lug, halfway along its straight run;
- the drawing's notches at the plate's foot are left out;
- modelled standing on z = 0, the plate's back on x = 0 and the lug towards
  +x (the cell), centred across y.
"""
import math

import cadquery as cq

# parameters, in mm
thickness = 0.3  # the sheet
width = 6.4  # 0.250 in
height = 13.7  # 0.538 in
depth = 4.0  # 0.156 in: the plate's back to the lug's farthest corner
lug_end_below_top = 7.6  # 0.300 in
hole_diameter = 1.8  # 0.070 in

lug_width = 3.0
lug_gap = 0.4  # each side of the lug, in the window
window_bottom = 1.5
lug_root = 9.6  # the window's top, where the lug bends out

half = thickness / 2
lug_end_height = height - lug_end_below_top
# the lug's direction, root to end, in the x-z plane, and its outward normal
run_x, run_z = depth - thickness, lug_end_height - lug_root
run = math.hypot(run_x, run_z)
dx, dz = run_x / run, run_z / run
nx = -dz  # the normal's x component: the end's outer corner sits half a sheet past the centreline
# length along the centreline that puts the end's outer corner on the 4.0 mm reach
lug_length = (depth - half * nx - half) / dx
end_x, end_z = half + lug_length * dx, lug_root + lug_length * dz

plate = cq.Workplane("XY").box(thickness, width, height, centered=(False, True, False))
window = (
    cq.Workplane("YZ")
    .center(0, (window_bottom + lug_root) / 2)
    .rect(lug_width + 2 * lug_gap, lug_root - window_bottom)
    .extrude(thickness)
)

# the lug: its centreline in the x-z plane, swept with the sheet's section; it
# starts a sheet's thickness up inside the plate, so the two fuse at the root
path = cq.Workplane("XZ").polyline([
    (half, lug_root + thickness),
    (half, lug_root),
    (end_x, end_z),
])
lug = (
    cq.Workplane("XY", origin=(half, 0, lug_root + thickness))
    .rect(thickness, lug_width)
    .sweep(path, transition="round")
)
# the solder hole: through the lug, square to it, halfway along its run
mid_x, mid_z = half + lug_length / 2 * dx, lug_root + lug_length / 2 * dz
normal = cq.Vector(nx, 0, dx)
hole = cq.Solid.makeCylinder(
    hole_diameter / 2, 2 * thickness,
    cq.Vector(mid_x, 0, mid_z) - normal * thickness, normal)
result = plate.cut(window).union(lug).cut(cq.Workplane("XY").add(hole))

regions = {
    "back": result.faces("<X"),  # the plate's back, against the holder's wall
    "solder_hole": result.faces("%CYLINDER"),
    "lug_end": result.faces(">X"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
