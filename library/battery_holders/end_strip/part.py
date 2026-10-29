"""End strip for six single 18650 holders.

A flat strip that bolts across the end faces of single 18650 holders: three
holders side by side, in two rows bottom to bottom (one row upside down on
the other), held together by twelve M1.2 x 6 countersunk screws, one into
each bottom triangle's threaded hole. The holes are placed from the holder
body's width and screw positions, and the countersinks sized from the screw,
both through load_library, so the strip follows a change to either.

Two flanges stand out at 90 degrees from the strip's front, one on each of
the two middle screw clusters (where neighbouring holders meet), each as
wide as the strip and just long enough for an M1.2 countersunk head, with
two side by side; their countersinks are on the flanges' inner faces, which
face each other.

Assumptions where the description is silent:
- 1.5 mm thick: the 6 mm screw, flush in its countersink, then reaches
  4.5 mm into the holder's 5 mm deep hole, 0.5 mm short of its bottom;
- 10 mm wide (across the two rows), centred on the joint between them: the
  screw rows sit 1.83 mm either side of the joint, and the strip stays
  clear of the clips' solder lugs, which start about 9 mm from the joint;
- 0.05 mm radial clearance round the screw head in the countersink, which
  matches the head (90 degrees, with its short cylindrical edge) so the head
  sits flush; 1.3 mm clearance holes through (ISO 273 fine, M1.2);
- the flanges stand on the front (the side with the countersinks), centred
  on the joints between neighbouring holders; they are 1.0 mm thick, not the
  strip's 1.5 mm, because only about 1.25 mm of face is left between the
  countersinks either side of a joint: 1.0 mm leaves 0.13 mm to each head;
- each flange reaches 3.4 mm out: its holes' centres 1.7 mm from the strip's
  front and from the flange's end, so each 2.4 mm countersink keeps 0.5 mm of
  material to both; its two holes are a quarter and three quarters across;
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

flange_thickness = 1.0  # across y: fits between the countersinks at a joint
flange_margin = 0.5  # round each flange countersink, to the strip and to the flange's end

countersink_radius = screw.head_diameter / 2 + head_clearance
cone_height = countersink_radius - clearance_hole / 2  # 90 degrees: as deep as it narrows
flange_length = 2 * (countersink_radius + flange_margin)  # out from the strip's front, along x
flange_ys = [side * holder.width / 2 for side in (1, -1)]  # the middle joints, with three columns
flange_hole_x = thickness + flange_length / 2
flange_hole_zs = [width / 4, 3 * width / 4]
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
flanges = [
    cq.Workplane("XY", origin=(thickness, y, 0)).box(
        flange_length, flange_thickness, width, centered=(False, True, False))
    for y in flange_ys
]
cuts = [c for y, z in points for c in countersunk_hole((thickness, y, z), (1, 0, 0), thickness)]
# the flanges' countersinks open on their inner faces, towards y = 0
for y in flange_ys:
    inward = -1 if y > 0 else 1
    for z in flange_hole_zs:
        cuts += countersunk_hole((flange_hole_x, y + inward * flange_thickness / 2, z),
                                 (0, inward, 0), flange_thickness)
result = plate
for flange in flanges:
    result = result.union(flange)
for cut in cuts:
    result = result.cut(cq.Workplane("XY").add(cut))

regions = {
    "back": result.faces("<X"),  # against the holders' end faces
    "front": result.faces("|X").filter(  # where the screw heads sit flush
        lambda f: abs(f.Center().x - thickness) < 1e-6),
    "countersinks": result.faces("%CONE").filter(  # into the holders, along x
        lambda f: f.BoundingBox().xlen < thickness),
    "flange_countersinks": result.faces("%CONE").filter(  # on the flanges' inner faces
        lambda f: f.BoundingBox().ylen < flange_thickness),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
