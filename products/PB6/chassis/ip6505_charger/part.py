"""IP6505 USB fast-charge board.

A single-port IP6505 fast-charge module: a printed circuit board with a USB-A
receptacle at one end, the IP6505 chip, and the buck converter's inductor.

Assumptions where the description is silent:
- the board is 34.3 x 17 mm and the module 10 mm high overall, as a seller
  lists it (robu.in; sellers ship either an IP6505 or an MH-KC24 board, with
  the same outline); the parts' sizes and places below are typical, not
  measured;
- a 1.6 mm FR-4 board, its parts all on top (no through-hole pins below);
- the USB-A receptacle is the standard one: a 13.1 x 5.7 mm steel shell, 14 mm
  deep, with a 12 x 4.5 mm mouth and an 11 x 1.8 mm tongue 0.6 mm below the
  mouth's top, centred across the board with its mouth flush with the board's
  end;
- an 8 x 8 x 8.4 mm shielded inductor near the other end, the tallest part,
  setting the 10 mm overall height; the IP6505 is an ESOP-8 package,
  5 x 4 x 1.5 mm, between them;
- x runs along the board with the USB mouth at +x, y across it, z up; the
  board is centred on x and y and its underside is on z = 0.
"""
import cadquery as cq

# the board, in mm
length = 34.3  # along x
width = 17.0  # along y
pcb_t = 1.6  # board thickness

# the USB-A receptacle, at +x
usb_w = 13.1  # shell width, along y
usb_h = 5.7  # shell height, along z
usb_d = 14.0  # shell depth, along x
mouth_w = 12.0  # opening width
mouth_h = 4.5  # opening height
mouth_d = 12.0  # opening depth into the shell
tongue_w = 11.0  # the contact tongue's width
tongue_t = 1.8  # its thickness
tongue_d = 10.0  # how far it reaches out of the back of the opening
tongue_gap = 0.6  # between the tongue and the top of the opening, for the plug's shell

# the other parts
inductor = 8.0  # inductor footprint, square
inductor_h = 8.4  # inductor height
inductor_margin = 1.5  # from the board's -x end
chip = (5.0, 4.0, 1.5)  # IP6505, ESOP-8: length, width, height

usb_x1 = length / 2  # the mouth, flush with the board's +x end
usb_x0 = usb_x1 - usb_d
usb_z0 = pcb_t  # the shell sits on the board
usb_axis_z = usb_z0 + usb_h / 2  # the mouth's centre height above the board's underside
height = pcb_t + inductor_h  # overall

board = cq.Workplane("XY").box(length, width, pcb_t, centered=(True, True, False))

shell = (
    cq.Workplane("XY", origin=((usb_x0 + usb_x1) / 2, 0, usb_z0))
    .box(usb_d, usb_w, usb_h, centered=(True, True, False))
)
mouth = (
    cq.Workplane("YZ", origin=(usb_x1, 0, usb_axis_z))
    .rect(mouth_w, mouth_h)
    .extrude(-mouth_d)
)
tongue = (
    cq.Workplane("YZ", origin=(usb_x1 - mouth_d, 0, usb_axis_z + mouth_h / 2 - tongue_gap - tongue_t / 2))
    .rect(tongue_w, tongue_t)
    .extrude(tongue_d)
)
usb = shell.cut(mouth).union(tongue)

coil = (
    cq.Workplane("XY", origin=(-length / 2 + inductor_margin + inductor / 2, 0, pcb_t))
    .box(inductor, inductor, inductor_h, centered=(True, True, False))
)
ic_x = (-length / 2 + inductor_margin + inductor + usb_x0) / 2  # midway between coil and port
ic = (
    cq.Workplane("XY", origin=(ic_x, 0, pcb_t))
    .box(*chip, centered=(True, True, False))
)

result = board.union(usb).union(coil).union(ic)

regions = {
    "usb_mouth": result.faces(">X").faces(  # the receptacle's front rim, around the opening
        cq.selectors.BoxSelector((usb_x1 - 0.01, -usb_w, usb_z0), (usb_x1 + 0.01, usb_w, usb_z0 + usb_h))),
    "bottom": result.faces("<Z"),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
