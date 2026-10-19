"""Chassis box with its lid.

The base box with the lid seated on top: the lid's plate rests on the rims
of the box's side walls, its skirts cover the walls' outsides down to the
base's bottom, and its lip drops between the walls.  Both parts come from their own
scripts through load_part, so the assembly follows any change to the box's
l, b, h or wall.
"""
import cadquery as cq

base = load_part("base")  # the open-top box, standing on z = 0
lid = load_part("lid")  # modelled as installed: skirts stand on z = 0

# the lid's plate underside is seat_height above its own z = 0; lifting the lid
# by h - seat_height puts that underside on the box rim at z = h (today 0: the
# skirts reach the base's bottom)
lid_seat = base.h - lid.seat_height

result = (
    cq.Assembly(name="chassis")
    .add(base.result, name="base", color=cq.Color(0.36, 0.56, 0.78))
    .add(lid.result, name="lid", loc=cq.Location((0, 0, lid_seat)), color=cq.Color(0.85, 0.55, 0.25))
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="chassis")
