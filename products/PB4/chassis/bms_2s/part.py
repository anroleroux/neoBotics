"""2S 8A BMS (battery protection board).

Robofactory's 2S 7.4V 8A 18650 lithium battery protection board: a long,
narrow printed circuit board with the protection IC and its two MOSFETs on
top, and solder pads for the pack (B-, BM, B+) and the load (P-, P+).

Assumptions where the description is silent:
- 38 x 8 mm and 2.6 mm thick overall, as Robofactory lists it; the parts'
  sizes and places below are typical, not measured;
- a 1.0 mm board, its parts all on top: two SOP-8 MOSFETs, 5 x 4 x 1.6 mm
  (the tallest parts, setting the 2.6 mm), and a SOT-23-6 protection IC,
  3 x 1.6 x 1.1 mm, beside the -y MOSFET;
- five 3 x 2.5 mm pads on top, 0.1 mm proud: B- and P- at the -y end, BM
  past the +y MOSFET, P+ and B+ at the +y end;
- modelled lying flat with its components up: the board's length along y,
  its width along x, centred on x and y, its underside on z = 0; an assembly
  stands it on edge as needed.
"""
import cadquery as cq

# the board, in mm
length = 38.0  # along y
width = 8.0  # along x
pcb_t = 1.0  # board thickness
height = 2.6  # overall, with the parts

# the parts on top, placed along the board (y) from -y to +y
mosfet = (4.0, 5.0, height - pcb_t)  # SOP-8: along x, along y, height
mosfet_y = [-4.5, 2.5]  # the two MOSFETs' centres
ic = (1.6, 3.0, 1.1)  # SOT-23-6: along x, along y, height
ic_y = -10.5  # the protection IC's centre, beside the -y MOSFET
pad = (3.0, 2.5, 0.1)  # along x, along y, thickness
pad_y = {"B-": -17.25, "P-": -14.25, "BM": 8.0, "P+": 14.25, "B+": 17.25}  # pad centres

board = cq.Workplane("XY").box(width, length, pcb_t, centered=(True, True, False))
mosfets = (
    cq.Workplane("XY", origin=(0, 0, pcb_t))
    .pushPoints([(0, y) for y in mosfet_y])
    .box(*mosfet, centered=(True, True, False))
)
chip = cq.Workplane("XY", origin=(0, ic_y, pcb_t)).box(*ic, centered=(True, True, False))
pads = (
    cq.Workplane("XY", origin=(0, 0, pcb_t))
    .pushPoints([(0, y) for y in pad_y.values()])
    .rect(pad[0], pad[1])
    .extrude(pad[2])
)

result = board.union(mosfets).union(chip).union(pads)

regions = {
    "bottom": result.faces("<Z"),  # the plain back, which mounts against a wall
    "pads": result.faces("+Z").filter(  # B-, P-, BM, P+, B+ from -y to +y
        lambda f: abs(f.Center().z - (pcb_t + pad[2])) < 1e-6),
}

if "show_object" in globals():  # CQ-editor
    show_object(result, name="part")
