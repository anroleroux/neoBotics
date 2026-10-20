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
The front wall has a hole for a USB-A plug, in line with the port of the
IP6505 charger board that sits on the floor behind it.

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
- the IP6505 charger board sits on the floor, centred across the breadth,
  its USB port's mouth against the inside of the front wall (+x); the plug
  hole is the USB-A plug's 12 x 4.5 mm metal shell with 0.5 mm clearance all
  round (13 x 5.5 mm), square-cornered, centred on the port, so the plug's
  moulded body stays outside; the board's size and port height come from
  ip6505_charger through load_part.
"""
import cadquery as cq

cell = load_part("../battery_18650")  # the cells the ribs hold: diameter, length
charger = load_part("../ip6505_charger")  # the USB board behind the front wall: length, port

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

# the USB charger board and the hole for its plug in the front wall
plug_w = 12.0  # USB-A plug shell width
plug_h = 4.5  # USB-A plug shell height
plug_clearance = 0.5  # all round the plug, in the hole
charger_x = l / 2 - wall - charger.length / 2  # board centre: its port against the front wall
charger_y = 0.0  # centred across the breadth
charger_z = wall  # on the floor
plug_z = charger_z + charger.usb_axis_z  # the hole's centre height
assert charger_x - charger.length / 2 > front_x0 + front_t, "the charger does not fit in front of the mini wall"

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

plug_hole = (
    cq.Workplane("YZ", origin=(l / 2 - wall, charger_y, plug_z))
    .rect(plug_w + 2 * plug_clearance, plug_h + 2 * plug_clearance)
    .extrude(wall)
)
result = result.cut(plug_hole)

regions = {
    "rim": result.faces(">Z"),  # the tops of the two end walls, where the lid sits
    "sides": result.faces(">Y or <Y"),  # the open long sides' edges, where the lid's skirts meet
    "bottom": result.faces("<Z"),
    "plug_hole": result.faces("+Y or -Y or +Z or -Z").filter(  # the hole's four sides
        lambda f: f.Center().x > l / 2 - wall + 1e-6 and abs(f.Center().y - charger_y) < plug_w
        and abs(f.Center().z - plug_z) < plug_h),
    "rib_tops": result.faces("+Z").filter(  # the tops of the ribs and the front mini wall
        lambda f: abs(f.Center().z - (wall + rib_h)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
