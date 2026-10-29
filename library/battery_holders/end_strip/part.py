"""End strip for six single 18650 holders.

A flat strip that bolts across the end faces of single 18650 holders: three
holders side by side, in two rows bottom to bottom (one row upside down on
the other), held together by twelve M1.2 x 6 countersunk screws, one into
each bottom triangle's threaded hole. The holes are placed from the holder
body's width and screw positions, and the countersinks sized from the screw,
both through load_library, so the strip follows a change to either.

Assumptions where the description is silent:
- 1.5 mm thick: the 6 mm screw, flush in its countersink, then reaches
  4.5 mm into the holder's 5 mm deep hole, 0.5 mm short of its bottom;
- 10 mm wide (across the two rows), centred on the joint between them: the
  screw rows sit 1.83 mm either side of the joint, and the strip stays
  clear of the clips' solder lugs, which start about 9 mm from the joint;
- 0.05 mm radial clearance round the screw head in the countersink, which
  matches the head (90 degrees, with its short cylindrical edge) so the head
  sits flush; 1.3 mm clearance holes through (ISO 273 fine, M1.2);
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

countersink_radius = screw.head_diameter / 2 + head_clearance
cone_height = countersink_radius - clearance_hole / 2  # 90 degrees: as deep as it narrows
points = [
    (column_y + side * holder.screw_y, joint + row * holder.screw_inset)
    for column_y in ((c - (columns - 1) / 2) * holder.width for c in range(columns))
    for side in (1, -1)
    for row in (1, -1)
]

plate = cq.Workplane("XY").box(thickness, length, width, centered=(False, True, False))
holes = (
    cq.Workplane("YZ")
    .pushPoints(points)
    .circle(clearance_hole / 2)
    .extrude(thickness)
)
# each countersink: the head's short cylindrical edge at the face, then its 90 degree cone
countersinks = []
for y, z in points:
    edge = cq.Solid.makeCylinder(countersink_radius, screw.edge_height,
                                 cq.Vector(thickness - screw.edge_height, y, z), cq.Vector(1, 0, 0))
    cone = cq.Solid.makeCone(clearance_hole / 2, countersink_radius, cone_height,
                             cq.Vector(thickness - screw.edge_height - cone_height, y, z),
                             cq.Vector(1, 0, 0))
    countersinks += [edge, cone]
result = plate.cut(holes)
for cut in countersinks:
    result = result.cut(cq.Workplane("XY").add(cut))

regions = {
    "back": result.faces("<X"),  # against the holders' end faces
    "front": result.faces(">X"),  # where the screw heads sit flush
    "countersinks": result.faces("%CONE"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
