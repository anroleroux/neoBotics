"""RA6 base plate.

A base plate with a circular cylinder at its centre holding a circular
cavity, four feet extending out from the cylinder, and vertical ribs running
from the feet up to the cylinder.

Assumptions where the description is silent:
- the cylinder is 80 mm across and 60 mm tall overall, with a 5 mm wall, so
  the cavity is 70 mm across; the cavity is open at the top and blind, its
  floor the plate itself;
- the plate is 6 mm thick: a disc under the cylinder plus the four feet,
  one solid, standing on z = 0 and centred on the z axis;
- the feet lie along +-x and +-y, are 24 mm wide and reach 110 mm from the
  axis, with fully rounded ends, and each has an M5 clearance hole 12 mm in
  from its tip to screw the base down;
- one rib per foot, 5 mm thick, on the foot's centreline: a right triangle
  rising from the foot's top face to the cylinder's full height at the
  cylinder wall, stopping 8 mm short of the foot hole so a screw head and
  washer clear it;
- edges are sharp.
"""
import cadquery as cq

# parameters, in mm
cyl_d = 80.0  # cylinder outside diameter
cyl_h = 60.0  # cylinder overall height, from z = 0
cyl_wall = 5.0  # cylinder wall thickness
plate_t = 6.0  # plate and feet thickness; also the cavity floor
foot_w = 24.0  # foot width
foot_reach = 110.0  # from the axis to the foot tip
foot_hole_inset = 12.0  # foot hole centre, in from the tip
m5_clearance = 5.5
rib_t = 5.0  # rib thickness
rib_hole_gap = 8.0  # rib end to the foot hole centre

cavity_d = cyl_d - 2 * cyl_wall
hole_r = foot_reach - foot_hole_inset  # foot hole centre, from the axis
rib_start = cyl_d / 2 - cyl_wall / 2  # inside the wall, clear of the cavity
rib_end = hole_r - rib_hole_gap

# the plate: a disc under the cylinder and four feet, rounded at the tips
foot = (
    cq.Workplane("XY")
    .center(foot_reach / 2, 0)
    .slot2D(foot_reach, foot_w)
    .extrude(plate_t)
)
result = cq.Workplane("XY").circle(cyl_d / 2).extrude(plate_t)
for angle in (0, 90, 180, 270):
    result = result.union(foot.rotate((0, 0, 0), (0, 0, 1), angle))

# the centre cylinder and its cavity
result = result.union(cq.Workplane("XY").circle(cyl_d / 2).extrude(cyl_h))
result = result.cut(
    cq.Workplane("XY", origin=(0, 0, plate_t)).circle(cavity_d / 2).extrude(cyl_h - plate_t)
)

# the ribs, one per foot, from the foot to the cylinder
rib = (
    cq.Workplane("XZ", origin=(0, rib_t / 2, 0))
    .polyline([(rib_start, plate_t), (rib_end, plate_t), (rib_start, cyl_h)])
    .close()
    .extrude(rib_t)
)
for angle in (0, 90, 180, 270):
    result = result.union(rib.rotate((0, 0, 0), (0, 0, 1), angle))

# the foot holes
result = result.cut(
    cq.Workplane("XY")
    .pushPoints([(hole_r, 0), (0, hole_r), (-hole_r, 0), (0, -hole_r)])
    .circle(m5_clearance / 2)
    .extrude(plate_t)
)

regions = {
    "bottom": result.faces("<Z"),  # stands on and is screwed down to the floor
    "cavity": result.faces("%CYLINDER").faces(
        cq.selectors.NearestToPointSelector((cavity_d / 2, 0, cyl_h / 2))),
    "cavity_floor": result.faces(">Z[-2]").faces(
        cq.selectors.NearestToPointSelector((0, 0, plate_t))),
    "top_rim": result.faces(">Z"),  # the cylinder's top face
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
