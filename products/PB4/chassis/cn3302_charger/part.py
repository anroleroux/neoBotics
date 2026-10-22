"""CN3302 2S USB-C charger board.

A two-cell (2S, 8.4 V) boost charger module built on the CN3302: a printed
circuit board with a USB-C input receptacle at one end, the CN3302 chip, its
inductor, and the battery output pads at the other end.

Assumptions where the description is silent:
- the board is 25 x 18 mm and the module 6 mm high overall, as a seller lists
  the common Type-C 2S 8.4 V charger board (robu.in, 1 A and 2 A versions);
  the parts' sizes and places below are typical, not measured;
- a 1.6 mm FR-4 board, its parts all on top (no through-hole pins below);
- the USB-C receptacle is a top-mount one: an 8.94 x 3.26 mm shell, 7.35 mm
  deep, with rounded ends and an 8.34 x 2.66 mm mouth around a 6.7 x 0.7 mm
  tongue, centred across the board with its mouth flush with the board's end;
- a 6 x 6 x 4.4 mm shielded inductor, the tallest part, setting the 6 mm
  overall height; the CN3302 is an SOP-8 package, 5 x 4 x 1.5 mm;
- two 3 x 2.5 mm output pads (B+ and B-) on top at the board's far end;
- x runs along the board with the USB-C mouth at +x, y across it, z up; the
  board is centred on x and y and its underside is on z = 0.
"""
import cadquery as cq

# the board, in mm
length = 25.0  # along x
width = 18.0  # along y
pcb_t = 1.6  # board thickness

# the USB-C receptacle, at +x
usb_w = 8.94  # shell width, along y
usb_h = 3.26  # shell height, along z
usb_d = 7.35  # shell depth, along x
mouth_w = 8.34  # opening width
mouth_h = 2.66  # opening height
mouth_d = 6.5  # opening depth into the shell
tongue_w = 6.7  # the contact tongue's width
tongue_t = 0.7  # its thickness
tongue_d = 5.0  # how far it reaches out of the back of the opening

# the other parts
inductor = 6.0  # inductor footprint, square
inductor_h = 4.4  # inductor height
chip = (5.0, 4.0, 1.5)  # CN3302, SOP-8: length, width, height
pad = (2.5, 3.0, 0.1)  # an output pad: length, width, thickness
pad_margin = 1.0  # from the board's -x end
pad_pitch = 8.0  # B+ to B-, centre to centre, across the board

usb_x1 = length / 2  # the mouth, flush with the board's +x end
usb_x0 = usb_x1 - usb_d
usb_z0 = pcb_t  # the shell sits on the board
usb_axis_z = usb_z0 + usb_h / 2  # the mouth's centre height above the board's underside
height = pcb_t + inductor_h  # overall

board = cq.Workplane("XY").box(length, width, pcb_t, centered=(True, True, False))

shell = (
    cq.Workplane("YZ", origin=(usb_x0, 0, usb_axis_z))
    .slot2D(usb_w, usb_h)
    .extrude(usb_d)
)
mouth = (
    cq.Workplane("YZ", origin=(usb_x1, 0, usb_axis_z))
    .slot2D(mouth_w, mouth_h)
    .extrude(-mouth_d)
)
tongue = (
    cq.Workplane("YZ", origin=(usb_x1 - mouth_d, 0, usb_axis_z))
    .rect(tongue_w, tongue_t)
    .extrude(tongue_d)
)
usb = shell.cut(mouth).union(tongue)

pads_x = -length / 2 + pad_margin + pad[0] / 2
pads = (
    cq.Workplane("XY", origin=(pads_x, 0, pcb_t))
    .pushPoints([(0, -pad_pitch / 2), (0, pad_pitch / 2)])
    .rect(pad[0], pad[1])
    .extrude(pad[2])
)
coil_x = pads_x + pad[0] / 2 + 1.0 + inductor / 2  # just inside the pads
coil = (
    cq.Workplane("XY", origin=(coil_x, 0, pcb_t))
    .box(inductor, inductor, inductor_h, centered=(True, True, False))
)
ic_x = (coil_x + inductor / 2 + usb_x0) / 2  # midway between coil and port
ic = (
    cq.Workplane("XY", origin=(ic_x, 0, pcb_t))
    .box(*chip, centered=(True, True, False))
)

result = board.union(usb).union(coil).union(ic).union(pads)

regions = {
    "usb_end": result.faces("+X").filter(  # the board's +x end and the receptacle's rim, flush
        lambda f: abs(f.Center().x - usb_x1) < 1e-6),
    "output_pads": result.faces("+Z").filter(  # B+ and B-, where the pack's leads solder on
        lambda f: abs(f.Center().z - (pcb_t + pad[2])) < 1e-6),
    "bottom": result.faces("<Z"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
