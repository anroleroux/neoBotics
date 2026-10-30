"""Six-cell 18650 pack.

Six single 18650 holders, each with its cell and its two clips: three side by
side along y, in two rows bottom to bottom, the lower row turned upside down
about x. An end strip across each end face joins them, with twelve M1.2 x 6
countersunk screws at each end, flush in the strip, into the holders' tap
holes. Every piece comes from the parts library through load_library, so the
pack follows any change to the holder, the strip or the screw.

The summary's interference lists each screw against its holder: that is the
screw's 1.2 mm shank forming its thread in the 0.95 mm tap hole, as intended.

Assumptions where the description is silent:
- the pack stands on z = 0 on the lower row's open tops, the joint between
  the rows at the holders' height; centred along x and y;
- the strip at -x is the +x strip turned half a turn about z, so its tabs
  stay at the bottom and stick out away from the holders at both ends;
- the screws in the strips' tabs (which fix the pack to something else) are
  left out.
"""
import cadquery as cq

holder = load_library("battery_holders/single_18650_holder")  # body, cell and clips
body = load_library("battery_holders/single_18650_holder/body")  # length, width, height
strip = load_library("battery_holders/end_strip")  # points, thickness, joint
screw = load_library("fasteners/m1_2x6_countersunk")  # standing up: tip on z = 0

joint = body.height  # where the two rows' bottoms meet
end = body.length / 2  # each end face, from the centre

result = cq.Assembly(name="pack_3x2")
for c, y in enumerate(strip.column_ys):
    result.add(holder.result, name=f"upper_{c + 1}", loc=cq.Location((0, y, joint)))
    result.add(holder.result, name=f"lower_{c + 1}",
               loc=cq.Location(cq.Vector(0, y, joint), cq.Vector(1, 0, 0), 180))

strip_color = cq.Color(0.30, 0.33, 0.38)
screw_color = cq.Color(0.70, 0.70, 0.72)
strip_z = joint - strip.joint  # the strip's own z = 0
for side, label in ((1, "front"), (-1, "back")):
    turn = 0 if side == 1 else 180  # about z: the back strip faces -x
    result.add(strip.result, name=f"strip_{label}",
               loc=cq.Location(cq.Vector(side * end, 0, strip_z), cq.Vector(0, 0, 1), turn),
               color=strip_color)
    # each screw: head flush with the strip's front, along x into the holders
    head = side * (end + strip.thickness)
    for i, (y, z) in enumerate(strip.points, start=1):
        result.add(screw.result, name=f"screw_{label}_{i:02d}",
                   loc=cq.Location(cq.Vector(head - side * screw.length, side * y, strip_z + z),
                                   cq.Vector(0, 1, 0), side * 90),
                   color=screw_color)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="pack_3x2")
