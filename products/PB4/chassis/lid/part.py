"""Chassis lid.

A cover that sits on the rim of the base box and wraps down its two long
sides: a top plate with a skirt down each side, past the box's breadth by the
lid's thickness and down to the bottom of the base, overhanging the box by
a = 5 mm at both ends. A locating lip under the plate drops between the box's
side walls. It is sized from the box, so it still fits when the box's
variables change.

Assumptions where the description is silent:
- the lid's thickness (plate and skirts) is the box's wall thickness;
- the skirts touch the outside of the box's side walls (no clearance), and run
  the lid's full length, l + 2a;
- the lip stays as before: one wall thick, 6 mm deep, 0.2 mm clearance per
  side to the inside of the box walls, its length still l - 2 wall;
- modelled as installed, centred like the box: the skirt bottoms stand on
  z = 0, level with the bottom of the base, and the plate's underside is at
  seat_height = the box's h.
"""
import cadquery as cq

box = load_part("../base")  # the box this lid fits: l, b, h, wall

# parameters, in mm
t = box.wall  # lid thickness: plate and skirts
a = 5.0  # overhang past the box at each end, along the length
lip_depth = 6.0  # how far the lip drops between the box's side walls
lip_wall = box.wall  # lip thickness
clearance = 0.2  # per side, between the lip and the box's inner walls

length = box.l + 2 * a  # overall, along x
breadth = box.b + 2 * t  # overall, along y: the box plus a skirt each side
seat_height = box.h  # the plate's underside, on the box rim
height = seat_height + t  # overall, skirt bottom to top of plate

lip_l = box.l - 2 * box.wall - 2 * clearance  # the lip's outside
lip_b = box.b - 2 * box.wall - 2 * clearance

# the plate and skirts: an inverted U in the y-z plane, run along the length
cover = (
    cq.Workplane("XY")
    .box(length, breadth, height, centered=(True, True, False))
    .cut(cq.Workplane("XY").box(length, box.b, seat_height, centered=(True, True, False)))
)
lip = (
    cq.Workplane("XY", origin=(0, 0, seat_height - lip_depth))
    .rect(lip_l, lip_b)
    .rect(lip_l - 2 * lip_wall, lip_b - 2 * lip_wall)
    .extrude(lip_depth)
)
result = cover.union(lip)

regions = {
    "top": result.faces(">Z"),
    "skirts_inside": result.faces("%PLANE").filter(  # against the box's side walls
        lambda f: abs(f.normalAt().y) > 0.999 and abs(abs(f.Center().y) - box.b / 2) < 1e-6),
    "lip_bottom": result.faces(cq.selectors.NearestToPointSelector((0, lip_b / 2, seat_height - lip_depth))),
}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="part")
