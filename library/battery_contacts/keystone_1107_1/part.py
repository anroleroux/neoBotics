"""Keystone 1107-1 battery clip.

A tin-nickel plated spring-steel battery clip with a solder lug: a flat plate
with a solder hole near its top and a spring leaf cut from its middle, bent
out into a V that presses on the cell's end. From the catalogue drawing:
6.4 mm (0.250 in) wide, 13.7 mm (0.538 in) tall, 4.0 mm (0.156 in) deep over
the leaf, the leaf's apex 7.6 mm (0.300 in) below the top, and a 1.8 mm
(0.070 in) solder hole.

Assumptions where the drawing is silent:
- 0.3 mm sheet;
- the leaf is 3.0 mm wide, in a window with a 0.4 mm gap each side, from
  1.5 mm above the plate's bottom to just below the solder hole (its root,
  at 9.6 mm);
- the leaf runs from its root down and out to the apex, then back in towards
  the plate, its free tip 1.2 mm off the plate and 2.5 mm above the bottom,
  clear of the window's edge; the bends are rounded, on the sheet's centreline;
- the solder hole is centred 11.7 mm up, 2 mm below the top;
- the drawing's notches at the plate's foot are left out;
- modelled standing on z = 0, the plate's back on x = 0 and the leaf towards
  +x (the cell), centred across y.
"""
import cadquery as cq

# parameters, in mm
thickness = 0.3  # the sheet
width = 6.4  # 0.250 in
height = 13.7  # 0.538 in
depth = 4.0  # 0.156 in: the plate's back to the leaf's apex
apex_below_top = 7.6  # 0.300 in
hole_diameter = 1.8  # 0.070 in
hole_height = height - 2.0  # the hole's centre

leaf_width = 3.0
leaf_gap = 0.4  # each side of the leaf, in the window
window_bottom = 1.5
leaf_root = hole_height - hole_diameter / 2 - 1.2  # the window's top, under the hole
tip_offset = 1.2  # the free tip's distance from the plate, along x
tip_height = 2.5

apex_height = height - apex_below_top

plate = cq.Workplane("XY").box(thickness, width, height, centered=(False, True, False))
window = (
    cq.Workplane("YZ")
    .center(0, (window_bottom + leaf_root) / 2)
    .rect(leaf_width + 2 * leaf_gap, leaf_root - window_bottom)
    .extrude(thickness)
)
hole = cq.Workplane("YZ").center(0, hole_height).circle(hole_diameter / 2).extrude(thickness)

# the leaf: its centreline in the x-z plane, swept with the sheet's section;
# it starts a sheet's thickness up inside the plate, so the two fuse at the root
half = thickness / 2
path = cq.Workplane("XZ").polyline([
    (half, leaf_root + thickness),
    (half, leaf_root),
    (depth - half, apex_height),
    (tip_offset + half, tip_height),
])
leaf = (
    cq.Workplane("XY", origin=(half, 0, leaf_root + thickness))
    .rect(thickness, leaf_width)
    .sweep(path, transition="round")
)
result = plate.cut(window).cut(hole).union(leaf)

regions = {
    "back": result.faces("<X"),  # the plate's back, against the holder's wall
    "contact": result.faces(">X"),  # the leaf's apex, on the cell's end
    "solder_hole": result.faces("%CYLINDER"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
