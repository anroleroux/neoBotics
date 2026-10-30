"""Single 18650 holder body.

A plastic frame for one 18650 cell: a hollow rectangular prism, open at the
top and the bottom, with walls wall thick (1 mm by default). Two ribs across
the inside, spaced along the cell's length, each have a semicircular cradle
the cell lies in. Outside each end wall a second wall stands off by the
battery clip's thickness, making a slot, open at the top and the bottom, that
the clip's plate slides into, and each outer wall has a slot from its top
down past where the clip's solder lug passes through it. A notch 0.25 in
wide and 4 mm deep in the top of each end wall takes the clip's fold, which
hooks over the wall with its spring leaf on the cell's side. Along the
bottom, a triangular extrusion on each side runs the full length: flush with
the bottom, up the side wall, and down at 45 degrees towards the centre,
about 1 mm outside the cradles' arcs. Each triangle has an M1.2 threaded
hole in from both end faces, for the screws of a strip bolted on across the
end. A filleted cut-out in the top edge of both side walls, symmetric about
the middle, saves material. Change wall and the outside grows with it; the
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
- each triangle's profile spans from its 45 degree face to the body's outer
  side face (merging with the side wall), and its 45 degree face is exactly
  1 mm from the cradles' arcs, measured square to the face; so it meets the
  bottom 4.3 mm from the centre and the side wall's inside 5.2 mm up;
- the triangles run the body's whole length, through the end walls, the clip
  slots and the outer walls, so they partly close the slots' bottoms at the
  sides (clear of the clips, which are 6.35 mm wide);
- the M1.2 holes are tap drill size, 0.95 mm, plain (the thread is formed
  by the screw), 5 mm deep from the end face, along x; each sits at the
  triangle's incentre (1.83 mm from its side, its bottom and its 45 degree
  face), so a 2.3 mm countersunk head (DIN 963) on it stays 0.68 mm inside
  the body's side and bottom;
- the side cut-out starts 20 % of the body's overall length in from each
  end (where the rim starts to curve down), drops to 40 % of the height
  below the rim, and comes up again; its bottom corners have 4 mm fillets
  and its top corners, where it meets the rim, 2 mm; it goes through both
  side walls and stays above the ribs and clear of the end walls;
- no other fillets;
- x is the cell's axis, centred on the origin; the body stands on z = 0.
"""
import math

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
gusset_offset = 1.0  # from the cradles' arcs to the triangles' 45 degree faces
screw_tap_drill = 0.95  # M1.2 x 0.25
screw_hole_depth = 5.0  # from each end face, along x
side_cut_start = 0.20  # of the overall length, in from each end
side_cut_depth = 0.40  # of the height, down from the rim
side_cut_bottom_fillet = 4.0
side_cut_top_fillet = 2.0

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
# the triangles along the bottom: a 45 degree face gusset_offset outside the
# cradle's circle (centre on the axis, axis_height up) meets z = 0 at
# gusset_foot from the centre: |axis_height + gusset_foot| / sqrt(2) = radius + offset
gusset_foot = math.sqrt(2) * (cradle_radius + gusset_offset) - axis_height
gusset_rise = width / 2 - gusset_foot  # up the body's outer side face
gussets = [
    cq.Workplane("YZ", origin=(-length / 2, 0, 0))
    .polyline([(side * gusset_foot, 0), (side * width / 2, 0), (side * width / 2, gusset_rise)])
    .close()
    .extrude(length)
    for side in (1, -1)
]
# the screw holes: at each triangle's incentre, the point farthest from its
# three faces; a right isosceles triangle with legs gusset_rise has inradius
# gusset_rise * (2 - sqrt(2)) / 2
screw_inset = gusset_rise * (2 - math.sqrt(2)) / 2  # from the side face and the bottom
screw_y = width / 2 - screw_inset
screw_holes = [
    cq.Workplane("YZ", origin=(end * length / 2, 0, 0))
    .pushPoints([(screw_y, screw_inset), (-screw_y, screw_inset)])
    .circle(screw_tap_drill / 2)
    .extrude(-end * screw_hole_depth)  # into the body from that end
    for end in (1, -1)
]
# the side cut-out, in the x-z plane through both side walls: a notch with
# rounded bottom corners whose top corners round over into the rim
cut_half = length / 2 - side_cut_start * length  # where the rim starts to curve down
cut_bottom = height - side_cut_depth * height
r1, r2 = side_cut_bottom_fillet, side_cut_top_fillet
a = cut_half - r2  # the notch's straight sides
k = math.sqrt(0.5)  # cos 45 = sin 45, for the arcs' midpoints
side_cut = (
    cq.Workplane("XZ")
    .moveTo(-cut_half, height)
    .threePointArc((-cut_half + r2 * k, height - r2 + r2 * k), (-a, height - r2))
    .lineTo(-a, cut_bottom + r1)
    .threePointArc((-a + r1 - r1 * k, cut_bottom + r1 - r1 * k), (-a + r1, cut_bottom))
    .lineTo(a - r1, cut_bottom)
    .threePointArc((a - r1 + r1 * k, cut_bottom + r1 - r1 * k), (a, cut_bottom + r1))
    .lineTo(a, height - r2)
    .threePointArc((cut_half - r2 * k, height - r2 + r2 * k), (cut_half, height))
    .lineTo(cut_half, height + 1)
    .lineTo(-cut_half, height + 1)
    .close()
    .extrude(width / 2 + 1, both=True)
)
result = (frame.cut(slots).cut(lug_slots).cut(notches).cut(side_cut)
          .union(ribs.cut(cradle)))
for gusset in gussets:
    result = result.union(gusset)
for holes in screw_holes:
    result = result.cut(holes)

regions = {
    "bottom": result.faces("<Z"),  # the walls' and ribs' feet: the mounting face
    "rim": result.faces(">Z"),  # the open top's edge
    "cradles": result.faces("%CYLINDER").filter(  # where the cell lies: the half circles
        lambda f: abs(f.BoundingBox().ylen - 2 * cradle_radius) < 1e-3),
    "screw_holes": result.faces("%CYLINDER").filter(  # the M1.2 tap holes, at the ends
        lambda f: abs(f.BoundingBox().ylen - screw_tap_drill) < 1e-3),
    "clip_slots": result.faces("|X").filter(  # each slot's two faces, at the end walls' outsides
        lambda f: abs(abs(f.Center().x) - end_wall_outside) < 1e-6
        or abs(abs(f.Center().x) - (end_wall_outside + slot)) < 1e-6),
}

if "show_object" in globals():  # CQ-editor (load_part runs under neobotics only)
    show_object(result, name="part")
