"""Chassis lid.

A cover that sits on the rim of the base box and wraps down its two long
sides: a top plate with a skirt down each side, past the box's breadth by the
lid's thickness and down to the bottom of the base, overhanging the box by
a = 5 mm at both ends. Two lips under the plate run along the length (x), one
at +y and one at -y, and drop between the box's end walls. It is sized from
the box, so it still fits when the box's variables change.

Assumptions where the description is silent:
- the lid's thickness (plate and skirts) is the box's wall thickness;
- the skirts touch the outside of the box's side walls (no clearance), and run
  the lid's full length, l + 2a;
- x is the length, y the breadth, z the height;
- each lip is one wall thick and 6 mm deep, and sits where the long sides of
  the earlier lip ring were: its outside face wall + 0.2 mm in from the box's
  breadth, so the lips' outer faces are b - 2 wall - 0.4 mm apart;
- the lips run between the box's end walls, with 0.2 mm clearance at each end:
  l - 2 wall - 0.4 mm long;
- modelled as installed, centred like the box: the skirt bottoms stand on
  z = 0, level with the bottom of the base, and the plate's underside is at
  seat_height = the box's h.
"""
import cadquery as cq

box = load_part("../base")  # the box this lid fits: l, b, h, wall

# parameters, in mm
t = box.wall  # lid thickness: plate and skirts
a = 5.0  # overhang past the box at each end, along the length
lip_depth = 6.0  # how far the lips drop below the plate
lip_wall = box.wall  # lip thickness, along y
clearance = 0.2  # between the lips' ends and the box's end walls; and the lips' inset

length = box.l + 2 * a  # overall, along x
breadth = box.b + 2 * t  # overall, along y: the box plus a skirt each side
seat_height = box.h  # the plate's underside, on the box rim
height = seat_height + t  # overall, skirt bottom to top of plate

lip_l = box.l - 2 * box.wall - 2 * clearance  # each lip's length, between the end walls
lip_b = box.b - 2 * box.wall - 2 * clearance  # across the two lips' outer faces

# the plate and skirts: an inverted U in the y-z plane, run along the length
cover = (
    cq.Workplane("XY")
    .box(length, breadth, height, centered=(True, True, False))
    .cut(cq.Workplane("XY").box(length, box.b, seat_height, centered=(True, True, False)))
)
# two lips along x, one each side in y; none across the ends
lip_y = lip_b / 2 - lip_wall / 2  # each lip's centre line
lips = (
    cq.Workplane("XY", origin=(0, 0, seat_height - lip_depth))
    .pushPoints([(0, lip_y), (0, -lip_y)])
    .rect(lip_l, lip_wall)
    .extrude(lip_depth)
)
result = cover.union(lips)

regions = {
    "top": result.faces(">Z"),
    "skirts_inside": result.faces("%PLANE").filter(  # against the box's side walls
        lambda f: abs(f.normalAt().y) > 0.999 and abs(abs(f.Center().y) - box.b / 2) < 1e-6),
    "lip_bottoms": result.faces("%PLANE").filter(  # the two lips' lower ends
        lambda f: f.normalAt().z < -0.999 and abs(f.Center().z - (seat_height - lip_depth)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="part")
