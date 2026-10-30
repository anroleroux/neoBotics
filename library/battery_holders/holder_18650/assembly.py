"""18650 battery holder.

The holder body with a terminal in each end wall's slot: each plate's back on
the slot's outer face and its foot on the slot's bottom, its bump facing the
cell. Both parts come from their own scripts through load_part, so the
assembly follows any change to the holder.
"""
import cadquery as cq

holder = load_part("holder")  # trough along x, centred, standing on z = 0
terminal = load_part("terminal")  # back on x = 0, bump towards +x, foot on z = 0

# a slot's outer face, from the centre, along x
slot_outer = holder.cavity_length / 2 + holder.slot_thickness

result = (
    cq.Assembly(name="holder_18650")
    .add(holder.result, name="holder", color=cq.Color(0.22, 0.22, 0.24))
    # negative end (-x): the plate as modelled, back on the slot's outer face
    .add(terminal.result, name="terminal_negative",
         loc=cq.Location((-slot_outer, 0, holder.floor)),
         color=cq.Color(0.80, 0.80, 0.82))
    # positive end (+x): turned half a turn about z, so its bump faces -x
    .add(terminal.result, name="terminal_positive",
         loc=cq.Location(cq.Vector(slot_outer, 0, holder.floor), cq.Vector(0, 0, 1), 180),
         color=cq.Color(0.80, 0.80, 0.82))
)

regions = {}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="holder_18650")
