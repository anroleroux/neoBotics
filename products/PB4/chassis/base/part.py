"""Chassis base box.

An open-top rectangular box with its side walls at +-y removed: a floor and
the two end walls at +-x, all one wall thickness, open at the top and along
both long sides. Four variables drive it: l, b, h and wall. Five ribs on
the floor run along x: three battery separators between the four 18650 cells
and two side battery retainers along the open sides. A front mini wall, as
high as the ribs, stands across the breadth just in front of the cells. The
side retainers run from the back wall to the mini wall, the centre separator
from 1 mm in front of the back wall to the mini wall, and the other two
separators from 1 mm in front of the back wall to the cells' front faces.
The front wall has two holes for USB-A plugs, in line with the ports of the
two IP6505 fast-charge boards that sit side by side on the floor behind it,
and a hole for a USB-C plug, in line with the port of the CN3302 battery
charger beside them.

Assumptions where the description is silent:
- l, b and h are the outside dimensions; the space between the end walls is
  l - 2 wall long and h - wall deep, and runs the full breadth b;
- the floor is as thick as the walls;
- l = 120, b = 80, h = 50 and wall = 3 mm until real sizes are given;
- the box is centred on the z axis and stands on z = 0, with l along x and b
  along y; corners are sharp;
- the ribs are 1 mm thick and 12 mm tall above the floor (the first 8 mm
  plus the requested 4 mm);
- the cells lie with their negative ends against the back wall (-x), so
  their front faces, positive buttons included, are a cell length in front
  of it;
- the front mini wall is 2 mm thick, 12 mm tall like the ribs, and runs the
  full breadth b, flush with the side retainers' outer faces; its back face
  is 1 mm in front of the cells' front faces;
- the side retainers' outer faces are flush with the box's sides, at +-b/2,
  and the five ribs are evenly spaced, so the four cell slots share what is
  left of the breadth equally (18.75 mm each, 0.35 mm wider than a cell);
- the cells' diameter and length come from battery_18650 through load_part;
- the first IP6505 board sits on the floor, centred across the breadth, its
  USB port's mouth against the inside of the front wall (+x); the second sits
  beside it on the -y side, 3 mm away, the same way round; each plug hole is
  the USB-A plug's 12 x 4.5 mm metal shell with 0.5 mm clearance all round
  (13 x 5.5 mm), square-cornered, centred on its port, so the plug's moulded
  body stays outside; the board's size and port height come from
  ip6505_charger through load_part;
- the CN3302 charger board sits on the floor beside the first IP6505, on the
  +y side with a 3 mm gap between the boards, its USB-C port's mouth against the inside of
  the front wall too; its plug hole is the USB-C plug's 8.25 x 2.4 mm shell
  with 0.5 mm clearance all round (9.25 x 3.4 mm), with fully rounded ends
  like the plug, centred on the port; the board's size and port height come
  from cn3302_charger through load_part.
"""
import cadquery as cq

cell = load_part("../battery_18650")  # the cells the ribs hold: diameter, length
ip6505 = load_part("../ip6505_charger")  # the USB-A output board behind the front wall
cn3302 = load_part("../cn3302_charger")  # the USB-C battery charger beside it

# the driving variables, in mm
l = 120.0  # length, outside, along x
b = 80.0  # breadth, outside, along y
h = 50.0  # height, outside, along z
wall = 3.0  # thickness of the walls and the floor

# the battery ribs on the floor
cell_count = 4  # cells side by side across the breadth
rib_t = 1.0  # rib thickness, along y
rib_h = 12.0  # rib height above the floor
rib_back_gap = 1.0  # between the inner ribs' back ends and the back wall
front_gap = 1.0  # between the cells' front faces and the front mini wall
front_t = 2.0  # front mini wall thickness, along x
rib_count = cell_count + 1  # three separators and two side retainers
pitch = (b - rib_t) / cell_count  # rib centre to rib centre
slot = pitch - rib_t  # clear width of a cell slot between two ribs
rib_y = [(i - cell_count / 2) * pitch for i in range(rib_count)]  # rib centres
slot_y = [(i - (cell_count - 1) / 2) * pitch for i in range(cell_count)]  # cell centres
assert slot > cell.diameter, "the cells do not fit between the ribs"
cell_back = -l / 2 + wall  # the cells' negative ends, against the back wall
cell_front = cell_back + cell.length  # the cells' front faces, buttons included
front_x0 = cell_front + front_gap  # the front mini wall's back face
# each rib's back and front ends, from -y to +y: the side retainers run from
# the back wall to the mini wall, the centre separator from just off the back
# wall to the mini wall, the other two from just off the back wall to the cells
gapped = cell_back + rib_back_gap
rib_x = [(cell_back, front_x0), (gapped, cell_front), (gapped, front_x0),
         (gapped, cell_front), (cell_back, front_x0)]

# the two USB boards, ports against the front wall, and the holes for their plugs
plug_clearance = 0.5  # all round a plug, in its hole
board_gap = 3.0  # between the two boards, across the breadth
front_inside = l / 2 - wall  # the front wall's inner face

plug_w = 12.0  # USB-A plug shell width
plug_h = 4.5  # USB-A plug shell height
ip6505_x = front_inside - ip6505.length / 2  # board centre: its port against the front wall
ip6505_ys = [0.0, -(ip6505.width + board_gap)]  # the first centred, the second beside it at -y
ip6505_z = wall  # on the floor
plug_z = ip6505_z + ip6505.usb_axis_z  # the USB-A hole's centre height

usbc_w = 8.25  # USB-C plug shell width
usbc_h = 2.4  # USB-C plug shell height
cn3302_x = front_inside - cn3302.length / 2
cn3302_y = ip6505_ys[0] + ip6505.width / 2 + board_gap + cn3302.width / 2  # beside the first, at +y
cn3302_z = wall
usbc_z = cn3302_z + cn3302.usb_axis_z  # the USB-C hole's centre height

for board, x in ((ip6505, ip6505_x), (cn3302, cn3302_x)):
    assert x - board.length / 2 > front_x0 + front_t, "a USB board does not fit in front of the mini wall"
assert cn3302_y + cn3302.width / 2 < b / 2 - rib_t, "the CN3302 board does not fit inside the side retainer"
assert min(ip6505_ys) - ip6505.width / 2 > -b / 2 + rib_t, "an IP6505 board does not fit inside the side retainer"

# the space between the end walls, above the floor, through both long sides
channel = (
    cq.Workplane("XY", origin=(0, 0, wall))
    .box(l - 2 * wall, b, h - wall, centered=(True, True, False))
)
result = cq.Workplane("XY").box(l, b, h, centered=(True, True, False)).cut(channel)

# the ribs and the front mini wall, on the floor
for (x0, x1), y in zip(rib_x, rib_y):
    rib = (
        cq.Workplane("XY", origin=((x0 + x1) / 2, y, wall))
        .rect(x1 - x0, rib_t)
        .extrude(rib_h)
    )
    result = result.union(rib)
front_wall = (
    cq.Workplane("XY", origin=(front_x0 + front_t / 2, 0, wall))
    .rect(front_t, b)
    .extrude(rib_h)
)
result = result.union(front_wall)

plug_holes = (
    cq.Workplane("YZ", origin=(front_inside, 0, plug_z))
    .pushPoints([(y, 0) for y in ip6505_ys])
    .rect(plug_w + 2 * plug_clearance, plug_h + 2 * plug_clearance)
    .extrude(wall)
)
usbc_hole = (
    cq.Workplane("YZ", origin=(front_inside, cn3302_y, usbc_z))
    .slot2D(usbc_w + 2 * plug_clearance, usbc_h + 2 * plug_clearance)
    .extrude(wall)
)
result = result.cut(plug_holes).cut(usbc_hole)

regions = {
    "rim": result.faces(">Z"),  # the tops of the two end walls, where the lid sits
    "sides": result.faces(">Y or <Y"),  # the open long sides' edges, where the lid's skirts meet
    "bottom": result.faces("<Z"),
    "plug_holes": result.faces("+Y or -Y or +Z or -Z").filter(  # the two USB-A holes' sides
        lambda f: f.Center().x > front_inside + 1e-6
        and min(abs(f.Center().y - y) for y in ip6505_ys) < plug_w
        and abs(f.Center().z - plug_z) < plug_h),
    "usbc_hole": result.faces().filter(  # the USB-C hole's sides: two flats, two rounded ends
        lambda f: f.Center().x > front_inside + 1e-6 and f.Center().x < l / 2 - 1e-6
        and abs(f.Center().y - cn3302_y) < usbc_w and abs(f.Center().z - usbc_z) < usbc_h),
    "rib_tops": result.faces("+Z").filter(  # the tops of the ribs and the front mini wall
        lambda f: abs(f.Center().z - (wall + rib_h)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
