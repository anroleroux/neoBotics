"""Single 18650 holder with its cell and clips.

The holder body with an 18650 cell lying in its two rib cradles, and a
Keystone 1107-1 battery clip at each end. The cell lies along x, positive
terminal towards +x, centred along the length and across the breadth,
resting on the bottoms of the cradles. Each clip's plate stands in the slot
outside its end wall, its fold hung in the end wall's notch, its spring leaf
on the cell's side, and its solder lug out through the outer wall.

The body and the cell come from their own scripts through load_part, the
clip from the parts library through load_library, so the assembly follows
any change to them.
"""
import cadquery as cq

body = load_part("body")  # open frame, centred, standing on z = 0
cell = load_part("battery")  # standing up: axis along z, negative end on z = 0
clip = load_library("battery_contacts/keystone_1107_1")  # plate's back on x = 0, lug on +x

# lay the cell down along +x: a quarter turn about y takes its +z axis to +x,
# putting its negative end at x = 0; then centre it along the length, and lower
# it onto the cradles: its underside on their bottoms, rib_base above z = 0
axis_height = body.rib_base + cell.diameter / 2

# each clip's plate back on its slot's inner face (the end wall's outside),
# lifted to hang on the notch; the -x clip turned half a turn about z so its
# lug points out at that end too
clip_x = body.end_wall_outside
clip_color = cq.Color(0.80, 0.80, 0.82)

result = (
    cq.Assembly(name="single_18650_holder")
    .add(body.result, name="body", color=cq.Color(0.22, 0.22, 0.24))
    .add(cell.result, name="battery",
         loc=cq.Location(cq.Vector(-cell.length / 2, 0, axis_height), cq.Vector(0, 1, 0), 90),
         color=cq.Color(0.88, 0.56, 0.24))
    .add(clip.result, name="clip_positive",
         loc=cq.Location((clip_x, 0, body.clip_base)), color=clip_color)
    .add(clip.result, name="clip_negative",
         loc=cq.Location(cq.Vector(-clip_x, 0, body.clip_base), cq.Vector(0, 0, 1), 180),
         color=clip_color)
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="single_18650_holder")
