"""PB6, assembled.

The chassis (the base with its six-cell pack) with the lid seated on top: the
lid's plate rests on the base's end walls, its skirts close the open long
sides down to the base's bottom, and its lips drop just inside the end walls.
Both come from their own scripts through load_part, so the model follows any
change to the base.
"""
import cadquery as cq

chassis = load_part("chassis")  # the chassis assembly: base and pack, base on z = 0
base = load_part("chassis/base")
lid = load_part("lid")  # modelled as installed: skirts stand on z = 0

# the lid's plate underside is seat_height above its own z = 0; lifting the lid
# by h - seat_height puts that underside on the base's rim at z = h (today 0:
# the skirts reach the base's bottom)
lid_seat = base.h - lid.seat_height

result = (
    cq.Assembly(name="PB6")
    .add(chassis.result, name="chassis")
    .add(lid.result, name="lid", loc=cq.Location((0, 0, lid_seat)), color=cq.Color(0.40, 0.68, 0.45))
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="PB6")
