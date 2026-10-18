"""An L-bracket that holds a NEMA 17 stepper motor.

The hand-written reference for the CAD stage: the same contract a generated
script follows (see neobotics.nl2cad.SYSTEM_PROMPT), so `neobotics cad` and the
tests run without a model.

Assumptions where the description is silent:
- the vertical plate is the front (y = 0 .. thickness), the base runs back
  along +y, and the motor sits in front of the plate (-y), its shaft along -y;
- the bore and the motor holes are centred on the plate's width and on the
  height of the motor body above the base (so a 42.3 mm motor clears the base);
- gussets are right triangles 20 mm along each leg, flush with the outer edges.
"""
import cadquery as cq

# parameters, in mm
width = 50.0  # along x, both plates
plate_height = 50.0  # vertical plate, along z
base_depth = 40.0  # base plate, along y
thickness = 3.0  # both plates and the gussets
inner_fillet = 3.0  # where the plates meet
motor_body = 42.3  # NEMA 17 square body
bore = 22.5  # pilot-boss clearance
hole_spacing = 31.0  # NEMA 17 square bolt pattern
m3_clearance = 3.4
m4_clearance = 4.5
base_hole_spacing = 30.0  # the two M4 holes, along x
base_hole_offset = 25.0  # behind the vertical plate's front face, along y
gusset_leg = 20.0

motor_z = thickness + motor_body / 2  # bore centre height

vertical = cq.Workplane("XY").box(width, thickness, plate_height, centered=(True, False, False))
base = cq.Workplane("XY").box(width, base_depth, thickness, centered=(True, False, False))
result = vertical.union(base)
result = result.edges("|X").edges(cq.selectors.NearestToPointSelector((0, thickness, thickness))) \
    .fillet(inner_fillet)

for side in (-1, 1):
    x = side * (width / 2 - thickness / 2)
    gusset = (
        cq.Workplane("YZ", origin=(x - thickness / 2, 0, 0))
        .polyline([(thickness, thickness), (thickness + gusset_leg, thickness),
                   (thickness, thickness + gusset_leg)])
        .close()
        .extrude(thickness)
    )
    result = result.union(gusset)

motor_face = cq.Workplane("XZ", origin=(0, 0, motor_z))
result = result.cut(motor_face.circle(bore / 2).extrude(-thickness))
result = result.cut(
    motor_face.rect(hole_spacing, hole_spacing, forConstruction=True).vertices()
    .circle(m3_clearance / 2).extrude(-thickness)
)
result = result.cut(
    cq.Workplane("XY").pushPoints([(-base_hole_spacing / 2, base_hole_offset),
                                   (base_hole_spacing / 2, base_hole_offset)])
    .circle(m4_clearance / 2).extrude(thickness)
)

regions = {
    "motor_face": result.faces("<Y"),  # the motor's flange bears on it
    "pilot_bore": result.faces("%CYLINDER").faces(
        cq.selectors.NearestToPointSelector((0, thickness / 2, motor_z))),
    "base_bottom": result.faces("<Z"),  # screwed down to the frame
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
