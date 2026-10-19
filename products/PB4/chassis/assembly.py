"""Chassis box with its lid.

The base box with the lid seated on top: the lid's plate rests on the box's
rim and its lip drops into the opening.  Both parts come from their own
scripts through load_part, so the assembly follows any change to the box's
l, b, h or wall.
"""
import cadquery as cq

base = load_part("base")  # the open-top box, standing on z = 0
lid = load_part("lid")  # modelled as installed, lip down, standing on z = 0

# the lid's plate underside sits lip_depth above its own z = 0; lifting the lid
# by h - lip_depth puts that underside on the box rim at z = h
lid_seat = base.h - lid.lip_depth

result = (
    cq.Assembly(name="chassis")
    .add(base.result, name="base", color=cq.Color(0.36, 0.56, 0.78))
    .add(lid.result, name="lid", loc=cq.Location((0, 0, lid_seat)), color=cq.Color(0.85, 0.55, 0.25))
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="chassis")
