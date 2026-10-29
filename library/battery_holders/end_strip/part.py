"""End strip for six single 18650 holders.

A flat strip that bolts across the end faces of single 18650 holders: three
holders side by side, in two rows bottom to bottom (one row upside down on
the other), held together by twelve M1.2 x 6 countersunk screws, one into
each bottom triangle's threaded hole. The holes are placed from the holder
body's width and screw positions, and the countersinks sized from the screw,
both through load_library, so the strip follows a change to either.

Two tabs come off the strip's top edge and turn 90 degrees to stick out
forward, like bent sheet-metal ears in plastic: one in line with each of the
two middle screw clusters (where neighbouring holders meet), each as wide as
the strip and long enough for an M1.2 countersunk head, with two side by
side; their countersinks are on the inside of the bend, the tabs'
undersides.

Assumptions where the description is silent:
- 1.5 mm thick: the 6 mm screw, flush in its countersink, then reaches
  4.5 mm into the holder's 5 mm deep hole, 0.5 mm short of its bottom;
- 10 mm wide (across the two rows), centred on the joint between them: the
  screw rows sit 1.83 mm either side of the joint, and the strip stays
  clear of the clips' solder lugs, which start about 9 mm from the joint;
- 0.05 mm radial clearance round the screw head in the countersink, which
  matches the head (90 degrees, with its short cylindrical edge) so the head
  sits flush; 1.3 mm clearance holes through (ISO 273 fine, M1.2);
- the tabs are on the top edge (z = width), the strip's thickness thick,
  their tops flush with the strip's top, running forward from the strip's
  back; each is the strip's width (10 mm) along y, centred on a joint
  between neighbouring holders; they stay clear of the countersinks below
  them (0.47 mm) and of the clips' solder lugs, which come out at the
  holders' centres;
- each tab reaches 3.4 mm out past the strip's front: its holes' centres
  1.7 mm from the strip's front and from the tab's end, so each 2.4 mm
  countersink keeps 0.5 mm of material to both; its two holes are a quarter
  and three quarters across it; they go down through the tab, along z, and
  the countersinks open on its underside;
- square corners, no fillets;
- modelled as it is bolted on: its back on x = 0 against the holders' end
  faces, the countersinks opening on +x, centred across y, standing on z = 0
  with the joint between the rows at z = width / 2.
"""
import cadquery as cq

holder = load_library("battery_holders/single_18650_holder/body")  # width, screw_y, screw_inset
screw = load_library("fasteners/m1_2x6_countersunk")  # head and length

# parameters, in mm
columns = 3  # holders side by side, along y
rows = 2  # bottom to bottom, along z
width = 10.0  # along z, across the rows
clearance_hole = 1.3  # M1.2, ISO 273 fine
head_clearance = 0.05  # radial, round the head in its countersink
engagement = 4.5  # of each screw in the holder's hole
thickness = screw.length - engagement

length = columns * holder.width  # along y
joint = width / 2  # the plane where the two rows' bottoms meet

tab_margin = 0.5  # round each tab countersink, to the strip's front and to the tab's end

countersink_radius = screw.head_diameter / 2 + head_clearance
cone_height = countersink_radius - clearance_hole / 2  # 90 degrees: as deep as it narrows
tab_reach = 2 * (countersink_radius + tab_margin)  # out past the strip's front, along x
tab_width = width  # along y
tab_thickness = thickness  # along z
tab_ys = [side * holder.width / 2 for side in (1, -1)]  # the middle joints, with three columns
tab_underside = width - tab_thickness
tab_hole_x = thickness + tab_reach / 2
tab_hole_offsets = [-tab_width / 4, tab_width / 4]  # along y, from each tab's centre
points = [
    (column_y + side * holder.screw_y, joint + row * holder.screw_inset)
    for column_y in ((c - (columns - 1) / 2) * holder.width for c in range(columns))
    for side in (1, -1)
    for row in (1, -1)
]



def countersunk_hole(face_point, out, depth):
    """A clearance hole through ``depth`` of material, countersunk for the
    screw's head where it opens at ``face_point``, facing along ``out``: the
    head's short cylindrical edge at the face, then its 90 degree cone."""
    at, out = cq.Vector(*face_point), cq.Vector(*out)
    return [
        cq.Solid.makeCylinder(clearance_hole / 2, depth, at - out * depth, out),
        cq.Solid.makeCylinder(countersink_radius, screw.edge_height,
                              at - out * screw.edge_height, out),
        cq.Solid.makeCone(clearance_hole / 2, countersink_radius, cone_height,
                          at - out * (screw.edge_height + cone_height), out),
    ]


plate = cq.Workplane("XY").box(thickness, length, width, centered=(False, True, False))
tabs = [
    cq.Workplane("XY", origin=(0, y, tab_underside)).box(
        thickness + tab_reach, tab_width, tab_thickness, centered=(False, True, False))
    for y in tab_ys
]
cuts = [c for y, z in points for c in countersunk_hole((thickness, y, z), (1, 0, 0), thickness)]
# the tabs' countersinks open on their undersides, inside the bend
cuts += [c for y in tab_ys for dy in tab_hole_offsets
         for c in countersunk_hole((tab_hole_x, y + dy, tab_underside), (0, 0, -1), tab_thickness)]
result = plate
for tab in tabs:
    result = result.union(tab)
for cut in cuts:
    result = result.cut(cq.Workplane("XY").add(cut))

regions = {
    "back": result.faces("<X"),  # against the holders' end faces
    "front": result.faces("|X").filter(  # where the screw heads sit flush
        lambda f: abs(f.Center().x - thickness) < 1e-6),
    "countersinks": result.faces("%CONE").filter(  # into the holders, along x
        lambda f: f.BoundingBox().xlen < thickness and f.BoundingBox().zlen > thickness),
    "tab_countersinks": result.faces("%CONE").filter(  # on the tabs' undersides
        lambda f: f.BoundingBox().zlen < tab_thickness),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
