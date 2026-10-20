"""Shaded pictures of CAD output as PNG, with no OpenGL: ``python -m neobotics.cadview``.

Adapted from topocombo's ``cadview``: it reads what the pipeline exported — a
part's BREP or STL — never the script that built it.  Shapes are tessellated
into triangles and rasterized with a small numpy z-buffer (back-face culling,
Lambert shading, supersampled for antialiasing), then saved through
matplotlib's Agg backend, so it runs on a headless CI box with no OpenGL.  A
z-buffer rather than topocombo's painter's algorithm: machined parts put
small faces right behind large ones, which a depth sort gets wrong.

Parts are modelled with z up (they stand on the z = 0 plane), so the camera
keeps z up; the default view is an axonometric one from the front (-y), right
(+x) and above.  :data:`VIEWS` adds the opposite corner from below, so a
reviewer sees every face between the two.  Sharp edges (a crease of more than
30 degrees, or an open boundary) are drawn as lines.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

#: Camera azimuth about z (from -y towards +x) and elevation, in degrees.
VIEW_AZIMUTH = 35.0
VIEW_ELEVATION = 25.0
#: Named (azimuth, elevation) views: the default corner and its opposite, from below.
VIEWS = {"iso": (VIEW_AZIMUTH, VIEW_ELEVATION), "rear_below": (VIEW_AZIMUTH + 180.0, -VIEW_ELEVATION)}
#: Crease angle above which an edge is drawn as a line.
FEATURE_ANGLE = 30.0

_FACE_RGB = np.array([0.36, 0.56, 0.78])  # a mid steel blue, legible on light and dark pages
#: One colour per component of an assembly, in order; the first is _FACE_RGB.
COMPONENT_RGB = np.array([
    [0.36, 0.56, 0.78],  # steel blue
    [0.88, 0.56, 0.24],  # amber
    [0.40, 0.68, 0.45],  # green
    [0.62, 0.48, 0.78],  # violet
    [0.80, 0.40, 0.45],  # brick
    [0.45, 0.70, 0.72],  # teal
])
_EDGE_RGBA = (0.10, 0.14, 0.20, 0.9)
_LIGHT = np.array([0.35, 0.8, 0.5])


def _camera(azimuth: float, elevation: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(screen right, screen up, towards the viewer) unit vectors, z up."""
    az, el = np.radians(azimuth), np.radians(elevation)
    toward = np.array([np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)])
    right = np.cross([0.0, 0.0, 1.0], toward)
    right /= np.linalg.norm(right)
    up = np.cross(toward, right)
    return right, up, toward


def _weld(points: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Merge coincident points so neighbouring triangles share their edges."""
    scale = max(float(np.ptp(points, axis=0).max()), 1e-12)
    keys = np.round(points / scale, 9)
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    welded = np.zeros((unique.shape[0], 3))
    welded[inverse.ravel()] = points
    return welded, inverse.ravel()[triangles]


def feature_edges(
    points: np.ndarray, triangles: np.ndarray, angle: float = FEATURE_ANGLE
) -> tuple[np.ndarray, np.ndarray]:
    """(edges as point-index pairs, the triangles on each side, -1 for none).

    An edge is kept when it bounds only one triangle or when the normals of its
    two triangles differ by more than ``angle`` degrees.
    """
    normals = _normals(points, triangles)
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    owner = np.tile(np.arange(triangles.shape[0]), 3)
    keys = np.sort(edges, axis=1)
    order = np.lexsort((keys[:, 1], keys[:, 0]))
    keys, owner = keys[order], owner[order]
    starts = np.flatnonzero(np.r_[True, np.any(keys[1:] != keys[:-1], axis=1)])
    counts = np.diff(np.r_[starts, keys.shape[0]])

    first = owner[starts]
    second = np.where(counts == 2, owner[np.minimum(starts + 1, owner.size - 1)], -1)
    cos = np.einsum("ij,ij->i", normals[first], normals[np.maximum(second, 0)])
    sharp = (second < 0) | (cos < np.cos(np.radians(angle)))
    return keys[starts][sharp], np.column_stack([first, second])[sharp]


def _normals(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    tri = points[triangles]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-300)


def _rasterize(screen: np.ndarray, depth: np.ndarray, triangles: np.ndarray,
               shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Z-buffer the triangles: (nearest depth, triangle index or -1) per pixel.

    ``screen`` is in pixel coordinates (x right, y down); larger depth is nearer.
    """
    height, width = shape
    zbuf = np.full(shape, -np.inf)
    ids = np.full(shape, -1, dtype=np.int64)
    tri_xy, tri_z = screen[triangles], depth[triangles]
    lo = np.floor(tri_xy.min(axis=1)).astype(int).clip(0, [width - 1, height - 1])
    hi = np.ceil(tri_xy.max(axis=1)).astype(int).clip(0, [width - 1, height - 1])
    for t in range(triangles.shape[0]):
        (x0, y0), (x1, y1) = lo[t], hi[t]
        (ax, ay), (bx, by), (cx, cy) = tri_xy[t]
        area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(area) < 1e-12:
            continue
        px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / area
        w1 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not inside.any():
            continue
        z = w0 * tri_z[t, 0] + w1 * tri_z[t, 1] + w2 * tri_z[t, 2]
        window = zbuf[y0:y1 + 1, x0:x1 + 1]
        nearer = inside & (z > window)
        window[nearer] = z[nearer]
        ids[y0:y1 + 1, x0:x1 + 1][nearer] = t
    return zbuf, ids


def render_triangles(
    points: np.ndarray,
    triangles: np.ndarray,
    png_path: Path,
    *,
    title: str | None = None,
    two_sided: bool = False,
    width_px: int = 1400,
    azimuth: float = VIEW_AZIMUTH,
    elevation: float = VIEW_ELEVATION,
    supersample: int = 2,
    colors: np.ndarray | None = None,
) -> Path:
    """Draw a triangle surface to a transparent PNG and return its path.

    Hidden surfaces are resolved per pixel with a z-buffer, rendered at
    ``supersample`` times the size and averaged down for antialiasing.
    ``two_sided`` shades every triangle whichever way it faces (an open
    surface); otherwise triangles facing away from the camera are culled,
    which assumes a closed, outward-oriented surface.  Feature edges are drawn
    where the z-buffer shows them unoccluded.  ``colors`` gives each triangle
    its own RGB (an assembly's components); by default all are steel blue.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    points, triangles = _weld(np.asarray(points, float), np.asarray(triangles, int))
    right, up, toward = _camera(azimuth, elevation)
    normals = _normals(points, triangles)
    facing = normals @ toward
    if two_sided:
        normals = np.where(facing[:, None] < 0, -normals, normals)
        facing = np.abs(facing)
    visible = facing > 1e-9

    view_xy = np.column_stack([points @ right, points @ up])
    depth = points @ toward
    lo, hi = view_xy.min(axis=0), view_xy.max(axis=0)
    span = np.maximum(hi - lo, 1e-9)
    margin = 0.08 * span.max()
    aspect = (span[1] + 2 * margin) / (span[0] + 2 * margin)
    dpi = 150
    fig_w = width_px / dpi
    fig_h = min(max(fig_w * aspect, 1.6), fig_w * 1.2)

    # pixel grid over the view box, at the figure's aspect ratio
    px_w, px_h = int(round(fig_w * dpi)) * supersample, int(round(fig_h * dpi)) * supersample
    scale = min(px_w / (span[0] + 2 * margin), px_h / (span[1] + 2 * margin))
    centre = (lo + hi) / 2
    view_lo = centre - np.array([px_w, px_h]) / (2 * scale)
    screen = np.column_stack([(view_xy[:, 0] - view_lo[0]) * scale,
                              px_h - (view_xy[:, 1] - view_lo[1]) * scale])

    tri_idx = np.flatnonzero(visible)
    zbuf, ids = _rasterize(screen, depth, triangles[tri_idx], (px_h, px_w))

    light = _LIGHT / np.linalg.norm(_LIGHT)
    shade = 0.45 + 0.55 * np.clip(normals[tri_idx] @ light, 0.0, 1.0)
    base_rgb = (np.broadcast_to(_FACE_RGB, (len(triangles), 3)) if colors is None
                else np.asarray(colors, float))[tri_idx]
    face_rgb = np.clip(shade[:, None] * base_rgb, 0, 1)
    image = np.zeros((px_h, px_w, 4))
    hit = ids >= 0
    image[hit, :3] = face_rgb[ids[hit]]
    image[hit, 3] = 1.0

    # feature edges: sample each at sub-pixel steps, keep the samples no
    # deeper than the nearest surface there (within a small tolerance)
    edges, sides = feature_edges(points, triangles)
    side_vis = np.where(sides >= 0, visible[np.maximum(sides, 0)], False)
    edges = edges[side_vis.any(axis=1)]
    tol = 2e-3 * max(float(np.ptp(depth)), 1e-9) + 1.5 / scale
    for a, b in edges:
        n = int(np.ceil(np.linalg.norm(screen[b] - screen[a]) * 2)) + 1
        f = np.linspace(0.0, 1.0, n)[:, None]
        xy = screen[a] + f * (screen[b] - screen[a])
        z = depth[a] + f[:, 0] * (depth[b] - depth[a])
        col = np.clip(xy[:, 0].astype(int), 0, px_w - 1)
        row = np.clip(xy[:, 1].astype(int), 0, px_h - 1)
        shown = z >= zbuf[row, col] - tol
        for dr in range(-supersample // 2, supersample - supersample // 2):
            for dc in range(-supersample // 2, supersample - supersample // 2):
                r = np.clip(row[shown] + dr, 0, px_h - 1)
                c = np.clip(col[shown] + dc, 0, px_w - 1)
                image[r, c] = _EDGE_RGBA

    if supersample > 1:
        image = image.reshape(px_h // supersample, supersample, px_w // supersample, supersample, 4)
        alpha = image[..., 3].mean(axis=(1, 3))
        rgb = (image[..., :3] * image[..., 3:]).sum(axis=(1, 3)) / np.maximum(
            image[..., 3].sum(axis=(1, 3)), 1e-12)[..., None]
        image = np.concatenate([rgb, alpha[..., None]], axis=-1)

    view_hi = view_lo + np.array([px_w, px_h]) / scale
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ax.imshow(image, extent=(view_lo[0], view_hi[0], view_lo[1], view_hi[1]),
              interpolation="nearest")
    ax.set_xlim(view_lo[0], view_hi[0])
    ax.set_ylim(view_lo[1], view_hi[1])
    _axis_triad(ax, right, up, lo, span, margin)
    if title:
        ax.text(lo[0] - margin * 0.6, hi[1] + margin * 0.4, title, fontsize=9,
                color="#6b7684", va="top")

    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=dpi, transparent=True)
    plt.close(fig)
    return png_path


def _axis_triad(ax, right, up, lo, span, margin) -> None:
    """x / y / z arrows in the lower-left corner, so the orientation reads."""
    size = 0.06 * span.max()
    origin = np.array([lo[0] - margin, lo[1] - margin]) + 0.9 * margin
    for axis, name in enumerate("xyz"):
        vec = np.eye(3)[axis]
        d = np.array([vec @ right, vec @ up]) * size
        ax.annotate(
            "", xy=origin + d, xytext=origin,
            arrowprops={"arrowstyle": "-|>", "color": "#8a94a0", "lw": 0.9},
        )
        ax.text(*(origin + d * 1.25), name, color="#8a94a0", fontsize=7, ha="center", va="center")


# --------------------------------------------------------------------------
# sources: a CadQuery shape, a BREP or an STL
# --------------------------------------------------------------------------
def shape_triangles(shape, tolerance: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Tessellate a CadQuery shape into (points, triangles)."""
    bb = shape.BoundingBox()
    tol = tolerance or max(bb.DiagonalLength, 1e-9) * 1e-3
    vertices, triangles = shape.tessellate(tol, 0.2)
    points = np.array([v.toTuple() for v in vertices], dtype=float)
    return points, np.asarray(triangles, dtype=int).reshape(-1, 3)


def render_shape(shape, png_path: Path, title: str | None = None, view: str = "iso") -> Path:
    """Render a CadQuery shape (a face or a solid) to PNG from one of :data:`VIEWS`."""
    points, triangles = shape_triangles(shape)
    has_volume = shape.ShapeType() in ("Solid", "CompSolid", "Compound") and shape.Volume() > 0
    azimuth, elevation = VIEWS[view]
    return render_triangles(points, triangles, png_path, title=title, two_sided=not has_volume,
                            azimuth=azimuth, elevation=elevation)


def render_components(shapes: list, png_path: Path, title: str | None = None,
                      view: str = "iso") -> Path:
    """Render an assembly's placed components to PNG, each in its own colour."""
    points, triangles, colors, offset = [], [], [], 0
    for i, shape in enumerate(shapes):
        p, t = shape_triangles(shape)
        points.append(p)
        triangles.append(t + offset)
        colors.append(np.tile(COMPONENT_RGB[i % len(COMPONENT_RGB)], (len(t), 1)))
        offset += len(p)
    azimuth, elevation = VIEWS[view]
    return render_triangles(np.vstack(points), np.vstack(triangles), png_path, title=title,
                            azimuth=azimuth, elevation=elevation, colors=np.vstack(colors))


def render_brep(brep_path: Path, png_path: Path, title: str | None = None, view: str = "iso") -> Path:
    """Render an exported CadQuery BREP to PNG."""
    import cadquery as cq

    return render_shape(cq.importers.importBrep(str(brep_path)).val(), png_path, title, view)


def stl_triangles(stl_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read an ASCII or binary STL into (points, triangles) with OCP's reader."""
    from OCP.RWStl import RWStl

    tri = RWStl.ReadFile_s(str(stl_path))
    if tri is None:
        raise ValueError(f"cannot read {stl_path} as STL")
    points = np.array([tri.Node(i).Coord() for i in range(1, tri.NbNodes() + 1)], dtype=float)
    triangles = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)], dtype=int)
    return points, triangles - 1


def render_stl(stl_path: Path, png_path: Path, title: str | None = None, view: str = "iso") -> Path:
    """Render a closed STL surface to PNG."""
    points, triangles = stl_triangles(stl_path)
    azimuth, elevation = VIEWS[view]
    return render_triangles(points, triangles, png_path, title=title,
                            azimuth=azimuth, elevation=elevation)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m neobotics.cadview",
        description="Render a BREP or STL (from a neobotics run) to a shaded PNG.",
    )
    parser.add_argument("source", type=Path, help=".brep or .stl file")
    parser.add_argument("--out", type=Path, help="PNG to write (default: next to the source)")
    parser.add_argument("--view", choices=sorted(VIEWS), default="iso")
    args = parser.parse_args(argv)

    out = args.out or args.source.with_suffix(".png")
    suffix = args.source.suffix.lower()
    if suffix == ".brep":
        render_brep(args.source, out, view=args.view)
    elif suffix == ".stl":
        render_stl(args.source, out, view=args.view)
    else:
        parser.error(f"cannot render {args.source.name}: expected a .brep or .stl file")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
