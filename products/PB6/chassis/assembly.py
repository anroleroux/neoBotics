"""Chassis base with the six-cell 18650 pack.

The base with the six-cell 18650 pack from the parts library
(battery_holders/pack_3x2) on its floor: three holders side by side across
the breadth, in two rows, their length along x, its back end against the
base's back end wall (-x) and its front end just behind the front mini wall.
Two IP6505 USB fast-charge boards sit side by side on the floor in front of
the pack, their USB ports against the front wall, each behind one of the
wall's USB-A holes, and a CN3302 2S charger board sits beside them at +y,
its USB-C port behind the wall's USB-C hole. The 2S BMS stands on edge
against the front face of the front mini wall, its components facing the
front.

The base and the boards come from their own scripts through load_part and
the pack through load_library, so the assembly follows any change to them.

Assumptions where the description is silent:
- the pack is centred across the breadth and stands on the floor, its back
  end (the tips of its back end strip's tabs) against the back wall;
- the cells are wired as two groups of three in parallel, in series (2S3P,
  8.4 V full), to suit the 2S BMS and charger; the wiring is not modelled.
"""
import cadquery as cq

base = load_part("base")  # floor and end walls at +-x, standing on z = 0
pack = load_library("battery_holders/pack_3x2")  # the six-cell pack, standing on z = 0
ip6505 = load_part("ip6505_charger")  # USB-A port at +x, underside on z = 0
cn3302 = load_part("cn3302_charger")  # USB-C port at +x, underside on z = 0
bms = load_part("bms_2s")  # lying flat, components up, length along y, underside on z = 0

# move the pack's back end onto the inside of the back wall, centre it across
# the breadth and stand it on the floor
pack_box = pack.result.toCompound().BoundingBox()
pack_loc = cq.Location((base.pack_back - pack_box.xmin, -pack_box.center.y, base.wall - pack_box.zmin))

result = (
    cq.Assembly(name="chassis")
    .add(base.result, name="base", color=cq.Color(0.36, 0.56, 0.78))
    .add(pack.result, name="pack_3x2", loc=pack_loc)
)

# the USB boards where the base's plug holes expect them
board_green = cq.Color(0.15, 0.45, 0.30)
for i, y in enumerate(base.ip6505_ys):
    result.add(
        ip6505.result,
        name=f"ip6505_charger_{i + 1}",
        loc=cq.Location((base.ip6505_x, y, base.ip6505_z)),
        color=board_green,
    )
result.add(
    cn3302.result,
    name="cn3302_charger",
    loc=cq.Location((base.cn3302_x, base.cn3302_y, base.cn3302_z)),
    color=board_green,
)

# stand the BMS up: a quarter turn about y takes its component side (+z) to the
# front (+x) and its width (x) to the vertical; its back then lies on the
# mini wall's front face
result.add(
    bms.result,
    name="bms_2s",
    loc=cq.Location(cq.Vector(base.bms_x, base.bms_y, base.bms_z), cq.Vector(0, 1, 0), 90),
    color=cq.Color(0.20, 0.30, 0.55),  # board blue
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="chassis")
