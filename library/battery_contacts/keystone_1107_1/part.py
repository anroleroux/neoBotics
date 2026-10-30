"""Keystone 1107-1 battery clip.

A tin-nickel plated spring-steel battery clip: a flat plate with a solder lug
cut from its middle and bent out at an angle to one side, with a solder hole
in it, and at the top a jog that folds the sheet 180 degrees back down on the
other side: the spring leaf the cell presses on. From the catalogue drawing:
6.35 mm (0.250 in) wide, 13.7 mm (0.538 in) tall, the lug reaching 4.0 mm
(0.156 in) from the plate's back with its end 7.6 mm (0.300 in) below the
top, and a 1.8 mm (0.070 in) solder hole.

The spring is drawn deformed, as it is with a cell in place: folded the full
180 degrees, its leaf parallel to the plate.

Assumptions where the drawing is silent:
- 0.3 mm sheet;
- the lug is 3.0 mm wide, cut from a window with a 0.4 mm gap each side that
  runs from 1.5 mm above the plate's bottom to 9.6 mm, the lug's root;
- the lug bends out of the plate at its root (a rounded bend on the sheet's
  centreline) and runs straight towards the point 4.0 mm out and 7.6 mm below
  the top; it ends square across where its outer corner reaches 4.0 mm, so its
  end's centre is about 0.05 mm lower than that point;
- the solder hole is through the lug, halfway along its straight run;
- the 13.7 mm height is overall, over the fold; the fold has an inner radius
  of 0.5 mm, so the leaf is 1.0 mm off the plate: it hooks over a 1 mm wall
  (a holder's end wall) with the plate on one side and the leaf on the
  other; the leaf runs the plate's full width down to z = 0;
- the width is the drawing's 0.250 in exactly (6.35 mm; the drawing rounds
  it to 6.4 mm);
- the drawing's notches at the plate's foot are left out;
- modelled standing on z = 0, centred across y: the plate between x = 0 and
  the sheet's thickness, the solder lug towards +x (out through the holder's
  wall), the spring leaf on -x (towards the cell).
"""
import math

import cadquery as cq

# parameters, in mm
thickness = 0.3  # the sheet
width = 0.250 * 25.4  # 6.35 mm
height = 13.7  # 0.538 in
depth = 4.0  # 0.156 in: the plate's back to the lug's farthest corner
lug_end_below_top = 7.6  # 0.300 in
hole_diameter = 1.8  # 0.070 in

lug_width = 3.0
lug_gap = 0.4  # each side of the lug, in the window
window_bottom = 1.5
lug_root = 9.6  # the window's top, where the lug bends out
fold_radius = 0.5  # inside the 180 degree jog at the top: a 1 mm gap

fold_outer = fold_radius + thickness
plate_top = height - fold_outer  # where the plate's straight part ends and the fold starts
fold_x = -fold_radius  # the fold's axis, along y, between the plate and the leaf
leaf_x = 2 * fold_x - thickness  # the leaf's outer face, towards the cell

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

plate = cq.Workplane("XY").box(thickness, width, plate_top, centered=(False, True, False))
# the jog: a half ring over the plate's top, then the leaf back down on -x
fold = (
    cq.Workplane("XZ", origin=(0, width / 2, 0))
    .center(fold_x, plate_top)
    .circle(fold_outer)
    .circle(fold_radius)
    .extrude(width)
    .intersect(cq.Workplane("XY", origin=(0, 0, plate_top))
               .box(2 * fold_outer + 1, width, fold_outer, centered=(True, True, False)))
)
leaf = cq.Workplane("XY", origin=(leaf_x, 0, 0)).box(
    thickness, width, plate_top, centered=(False, True, False))
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
result = (plate.cut(window).union(lug).cut(cq.Workplane("XY").add(hole))
          .union(fold).union(leaf))

regions = {
    "spring": result.faces("<X"),  # the leaf's face, on the cell's end
    "solder_hole": result.faces("%CYLINDER").filter(  # not the fold: hole_diameter across y
        lambda f: abs(f.BoundingBox().ylen - hole_diameter) < 1e-3),
    "lug_end": result.faces(">X"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
