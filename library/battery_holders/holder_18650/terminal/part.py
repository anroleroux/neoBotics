"""18650 holder terminal.

A sheet-metal contact plate for the 18650 holder: it slides into a slot in the
holder's end wall, presses a round bump onto the cell's end, and has a solder
tab with a hole above the holder. It is sized from the holder, so it follows
any change to the holder's slot or trough. One part serves both ends.

Assumptions where the description is silent:
- the plate is the holder's terminal sheet (0.5 mm) and terminal width
  (10 mm), and reaches from the slot's bottom (the holder's floor) to the
  holder's top;
- the bump is a 4 mm cylinder, 1.0 mm proud (the holder's bump height),
  centred on the cell's axis;
- the solder tab is 4 mm wide and stands 4 mm above the plate, with a 1.5 mm
  hole 2 mm above the plate's top;
- modelled standing on z = 0 with its back on x = 0 and the bump on +x;
  the assembly turns it to face the cell at each end.
"""
import cadquery as cq

holder = load_part("../holder")  # the slot and the cell's axis it fits

# parameters, in mm
thickness = holder.terminal_thickness
width = holder.terminal_width
plate_height = holder.height - holder.floor  # slot bottom to holder top
contact_height = holder.axis_height - holder.floor  # the cell's axis, above the plate's bottom
bump_diameter = 4.0
bump_height = holder.bump_height
tab_width = 4.0
tab_height = 4.0  # above the plate
tab_hole_diameter = 1.5
tab_hole_height = 2.0  # hole centre, above the plate's top

plate = cq.Workplane("XY").box(thickness, width, plate_height + tab_height,
                               centered=(False, True, False))
# narrow the top tab_height to the tab: cut the plate away either side of it
shoulder = (width - tab_width) / 2
shoulders = (
    cq.Workplane("XY", origin=(thickness / 2, 0, plate_height))
    .pushPoints([(0, (tab_width + shoulder) / 2), (0, -(tab_width + shoulder) / 2)])
    .rect(thickness, shoulder)
    .extrude(tab_height)
)
tab_hole = (
    cq.Workplane("YZ")
    .center(0, plate_height + tab_hole_height)
    .circle(tab_hole_diameter / 2)
    .extrude(thickness)
)
bump = (
    cq.Workplane("YZ", origin=(thickness, 0, 0))
    .center(0, contact_height)
    .circle(bump_diameter / 2)
    .extrude(bump_height)
)
result = plate.cut(shoulders).cut(tab_hole).union(bump)

regions = {
    "contact": result.faces(">X"),  # the bump's face, on the cell's end
    "back": result.faces("<X"),  # against the slot's outer face
    "solder_hole": result.faces("%CYLINDER").filter(  # tab_hole_diameter across
        lambda f: abs(f.BoundingBox().ylen - tab_hole_diameter) < 1e-3),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
