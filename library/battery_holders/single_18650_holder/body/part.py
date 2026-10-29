"""Single 18650 holder body.

A plastic frame for one 18650 cell: a hollow rectangular prism, open at the
top and the bottom, with walls wall thick (1 mm by default). Two ribs across
the inside, spaced along the cell's length, each have a semicircular cradle
the cell lies in. Outside each end wall a second wall stands off by the
battery clip's thickness, making a slot, open at the top and the bottom, that
the clip's plate slides into, and each outer wall has a slot from its top
down past where the clip's solder lug passes through it. A notch 0.25 in
wide and 4 mm deep in the top of each end wall takes the clip's fold, which
hooks over the wall with its spring leaf on the cell's side. Change wall and the outside grows with it; the
cavity keeps the cell's size, which comes from the battery part, and the
slots the clip's thickness, so the body follows a change to either.

Assumptions where the description is silent:
- the cavity is sized for the battery part (an 18650, 18.4 mm across and
  65.0 mm long) lying along x, with 0.5 mm clearance at each end and 0.3 mm
  each side;
- the walls are 20 mm tall (as before, when the body had a floor), so the cell
  sits about flush with the rim;
- each rib is 2 mm thick along x, spans the inside wall to wall, and runs from
  the bottom up to the cell's axis, so its cut-out is a full half circle;
- each cradle is 0.1 mm larger in radius than the cell, with 1 mm of rib below
  it; near the walls the rib narrows to 0.2 mm at its top;
- the ribs sit at the cell's quarter points, half its length apart, centred;
- the outer end walls are wall thick and the body's full height and width:
  the side walls run on past the end walls to meet them, so each slot spans
  the cavity's width, inner_width;
- the slots are exactly the clip's sheet thickness (0.3 mm), with no
  clearance, as asked;
- each notch is centred across y and exactly the clip's width (0.250 in),
  with no clearance;
- the clip goes in from the top and hangs on its fold: the fold's inner
  curve (1 mm across, the end wall's thickness) rests on the notch's two top
  edges, which puts the clip's foot clip_base above z = 0;
- each lug slot runs from the outer wall's top down to 0.2 mm below the lug's
  underside where it leaves the wall, and is 0.2 mm wider than the lug each
  side;
- no fillets or holes yet;
- x is the cell's axis, centred on the origin; the body stands on z = 0.
"""
import cadquery as cq

cell = load_part("../battery")  # the cell this body holds: diameter, length
clip = load_library("battery_contacts/keystone_1107_1")  # the terminal: its sheet thickness

# parameters, in mm
wall = 1.0  # side and end walls
cell_diameter = cell.diameter
cell_length = cell.length
end_clearance = 0.5  # at each end, along x
side_clearance = 0.3  # each side, across y
height = 20.0  # overall: the walls

rib_thickness = 2.0  # along x
rib_spacing = cell_length / 2  # centre to centre, along x
cradle_clearance = 0.1  # on the radius, round the cell
rib_base = 1.0  # rib material under the cradle
slot = clip.thickness  # between each end wall and its outer wall
lug_clearance = 0.2  # round the clip's solder lug, in the outer walls
notch_width = 0.250 * 25.4  # in the end walls' tops, across y: the clip's width
notch_depth = 4.0  # from the end walls' tops

inner_length = cell_length + 2 * end_clearance
inner_width = cell_diameter + 2 * side_clearance
end_wall_outside = inner_length / 2 + wall  # each end wall's outer face, from the centre
length = inner_length + 2 * (wall + slot + wall)  # overall, over the outer walls
width = inner_width + 2 * wall
cradle_radius = cell_diameter / 2 + cradle_clearance
notch_bottom = height - notch_depth
# the clip hangs on the notch: its fold's straight legs end, and its inner
# curve starts, at the clip's plate_top, level with the notch's bottom edges
clip_base = notch_bottom - clip.plate_top
# the clip's lug runs down and out from its root; its underside is lowest where
# it leaves the outer wall, slot + wall out from the clip's back (on the
# clip's own centreline, at x = half; the underside is half / dx below it)
lug_exit = slot + wall
lug_underside = clip_base + (clip.lug_root + (lug_exit - clip.half) * clip.dz / clip.dx
                             - clip.half / clip.dx)
lug_slot_bottom = lug_underside - lug_clearance
lug_slot_width = clip.lug_width + 2 * lug_clearance
axis_height = rib_base + cradle_radius  # the cradles' centre, and the ribs' top

frame = (
    cq.Workplane("XY")
    .rect(length, width)
    .rect(inner_length, inner_width)  # the inner loop is the opening, top to bottom
    .extrude(height)
)
slots = (
    cq.Workplane("XY")
    .pushPoints([(-(end_wall_outside + slot / 2), 0), (end_wall_outside + slot / 2, 0)])
    .rect(slot, inner_width)
    .extrude(height)
)
ribs = (
    cq.Workplane("XY")
    .pushPoints([(-rib_spacing / 2, 0), (rib_spacing / 2, 0)])
    .rect(rib_thickness, inner_width)
    .extrude(axis_height)
)
cradle = (
    cq.Workplane("YZ", origin=(-length / 2, 0, axis_height))
    .circle(cradle_radius)
    .extrude(length)
)
lug_slots = (
    cq.Workplane("XY", origin=(0, 0, lug_slot_bottom))
    .pushPoints([(-(end_wall_outside + slot + wall / 2), 0),
                 (end_wall_outside + slot + wall / 2, 0)])
    .rect(wall, lug_slot_width)
    .extrude(height - lug_slot_bottom)
)
notches = (
    cq.Workplane("XY", origin=(0, 0, notch_bottom))
    .pushPoints([(-(inner_length + wall) / 2, 0), ((inner_length + wall) / 2, 0)])
    .rect(wall, notch_width)
    .extrude(notch_depth)
)
result = frame.cut(slots).cut(lug_slots).cut(notches).union(ribs.cut(cradle))

regions = {
    "bottom": result.faces("<Z"),  # the walls' and ribs' feet: the mounting face
    "rim": result.faces(">Z"),  # the open top's edge
    "cradles": result.faces("%CYLINDER"),  # where the cell lies
    "clip_slots": result.faces("|X").filter(  # each slot's two faces, at the end walls' outsides
        lambda f: abs(abs(f.Center().x) - end_wall_outside) < 1e-6
        or abs(abs(f.Center().x) - (end_wall_outside + slot)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="part")
