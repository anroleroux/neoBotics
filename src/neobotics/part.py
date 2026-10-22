"""The CAD stage: run a CadQuery part script, check it, export it.

A part is a CadQuery script, the same contract as topocombo's ``part.py``.  It
assigns the part to ``result`` and may name places on it in ``regions``:

  result   the part — a ``cq.Workplane`` or ``cq.Shape`` holding one or more
           solids, modelled in millimetres with z up, standing on z = 0
  regions  optional dict of named places on the part (mounting faces, bores,
           a shaft axis): vertices, edges or faces, picked with selectors or
           built on their own — what a later stage (a study, an assembly)
           refers to by name

Two names are provided to every script:

  load_part(path)  runs the part (or assembly) script in the directory ``path``
                   names, relative to the calling script's directory, and
                   returns its top-level names as attributes — so a lid can be
                   sized from its box (``box = load_part("../base")`` then
                   ``box.l``), and an assembly can place its parts.

An assembly directory may hold an ``assembly.py`` whose ``result`` is a
``cq.Assembly``: the parts placed together.  It is checked shape by
shape, and its components (what was added to it directly: a part, or a whole
sub-assembly as one) are tested pairwise for interference (shared volume) and
contact (shared surface: a lid resting on a rim).  Its STEP keeps one named
body per shape, and its PNG views and per-shape STLs colour each shape in the
``color`` it was added with (or its parent's), else from a palette.

The script is the B-rep code: running it builds the boundary representation,
which is written out as BREP (the exact OpenCascade shape), STEP (for other
CAD tools), STL (for slicers and renderers) and shaded PNG views.  The script
itself is copied next to them, so what went into CadQuery is never implicit,
and it opens as-is in CQ-editor.

Scripts may come from a language model, so they are never run in this
process: :func:`build_part` starts ``python -m neobotics.part`` in a child
process with a timeout, and reads back a JSON summary.  The child does the
checking — ``result`` exists and holds valid solids with volume, every region
selects something — and either exports everything or reports the first
problem as a message a person (or the model) can act on.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

#: Wall-clock limit for building one part, in seconds.
BUILD_TIMEOUT = 180.0
#: How much of a failing script's traceback is kept (the tail is what matters).
TRACEBACK_CHARS = 3000

#: Exported file names, by kind, inside the CAD directory.
FILES = {
    "script": "part.py",
    "brep": "part.brep",
    "step": "part.step",
    "stl": "part.stl",
    "png": "part.png",
    "png_rear": "part_rear_below.png",
    "summary": "summary.json",
}


class PartError(ValueError):
    """A part script that does not build into a usable part."""


@dataclass
class BuildResult:
    """What came of building one part script."""

    ok: bool
    error: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    files: dict[str, Path] = field(default_factory=dict)


# --------------------------------------------------------------------------
# in the child process
# --------------------------------------------------------------------------
SCRIPT_NAMES = ("part.py", "assembly.py")


def script_in(directory: Path) -> Path | None:
    """The part or assembly script a catalogue directory holds, if any."""
    for name in SCRIPT_NAMES:
        if (Path(directory) / name).is_file():
            return Path(directory) / name
    return None


class _Loader:
    """``load_part(path)`` inside a script: run the part (or assembly) script in
    the directory ``path`` names, relative to the calling script's directory,
    and return its top-level names (``result``, ``regions`` and every parameter)
    as attributes.  Each script runs once per build; a cycle is an error."""

    def __init__(self) -> None:
        self.cache: dict[Path, SimpleNamespace] = {}
        self.stack: list[Path] = []

    def bind(self, directory: Path):
        def load_part(path: str) -> SimpleNamespace:
            target = (Path(directory) / path).resolve()
            script = script_in(target)
            if script is None:
                raise PartError(f"load_part({path!r}): no part.py or assembly.py in {target}")
            if script in self.stack:
                chain = " -> ".join(p.parent.name for p in [*self.stack, script])
                raise PartError(f"load_part cycle: {chain}")
            if script not in self.cache:
                self.stack.append(script)
                try:
                    namespace = self.run(script.read_text(), script)
                finally:
                    self.stack.pop()
                self.cache[script] = SimpleNamespace(
                    **{k: v for k, v in namespace.items() if not k.startswith("__")})
            return self.cache[script]
        return load_part

    def run(self, source: str, script: Path) -> dict[str, Any]:
        namespace: dict[str, Any] = {"__name__": "__cadquery_script__",
                                     "load_part": self.bind(script.parent)}
        exec(compile(source, str(script.name), "exec"), namespace)
        return namespace


def _exec_script(source: str, script: Path) -> dict[str, Any]:
    loader = _Loader()
    loader.stack.append(script.resolve())
    return loader.run(source, script.resolve())


def _as_shape(value, what: str):
    """A single cq.Shape from a Workplane, a Shape or a list of shapes."""
    import cadquery as cq

    if isinstance(value, cq.Workplane):
        shapes = [v for v in value.vals() if isinstance(v, cq.Shape)]
    elif isinstance(value, cq.Shape):
        shapes = [value]
    elif isinstance(value, (list, tuple)) and all(isinstance(v, cq.Shape) for v in value):
        shapes = list(value)
    else:
        raise PartError(f"{what} must be a cq.Workplane or cq.Shape, got {type(value).__name__}")
    if not shapes:
        raise PartError(f"{what} selects nothing")
    return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)


def check_part(namespace: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """(the part as one shape, its regions as shapes) from a script's namespace.

    Raises :class:`PartError` naming the first problem.
    """
    if "result" not in namespace:
        raise PartError("the script must assign the part to `result`")
    shape = _as_shape(namespace["result"], "`result`")
    return _check_solids(shape), _check_regions(namespace)


def _check_solids(shape):
    """``shape`` if it holds valid solids with volume; PartError otherwise."""
    solids = shape.Solids()
    if not solids:
        raise PartError(f"`result` holds no solid (it is a {shape.ShapeType()}); "
                        "extrude, revolve or loft the sketch into a solid")
    for i, solid in enumerate(solids):
        if not solid.isValid():
            raise PartError(f"solid {i} of `result` is not a valid B-rep "
                            "(self-intersecting or degenerate geometry)")
        if solid.Volume() <= 0:
            raise PartError(f"solid {i} of `result` has no volume")
    return shape


def _check_regions(namespace: dict[str, Any]) -> dict[str, Any]:
    regions = namespace.get("regions", {}) or {}
    if not isinstance(regions, dict):
        raise PartError("`regions` must be a dict of name -> selection")
    checked = {}
    for name, value in regions.items():
        if not isinstance(name, str) or not name:
            raise PartError(f"region names must be non-empty strings, got {name!r}")
        region = _as_shape(value, f"region {name!r}")
        if region.ShapeType() == "Solid":
            raise PartError(f"region {name!r} is a solid; regions are vertices, edges or faces")
        checked[name] = region
    return checked


def components(assembly) -> list[tuple[str, Any]]:
    """(path name, shape in place) for every shape in a cq.Assembly, nested ones
    included: what is drawn, one mesh each."""
    import cadquery as cq

    out = []

    def visit(node, loc, prefix):
        here = loc * node.loc
        name = f"{prefix}/{node.name}" if prefix else node.name
        if node.obj is not None:
            out.append((name, _as_shape(node.obj, f"component {name!r}").moved(here)))
        for child in node.children:
            visit(child, here, name)

    visit(assembly, cq.Location(), "")
    return out


def top_level(assembly) -> list[tuple[str, list[int]]]:
    """(name, indices into components()) for each thing added to the assembly
    directly: a part is one shape, a sub-assembly all the shapes inside it.
    A shape on the assembly's own node counts as a component of its own."""
    out: list[tuple[str, list[int]]] = []
    count = 0

    def visit(node, group):
        nonlocal count
        if node.obj is not None:
            out[group][1].append(count)
            count += 1
        for child in node.children:
            visit(child, group)

    if assembly.obj is not None:
        out.append((assembly.name, [count]))
        count += 1
    for child in assembly.children:
        out.append((f"{assembly.name}/{child.name}", []))
        visit(child, len(out) - 1)
    return [(name, shapes) for name, shapes in out if shapes]


def group(placed: list[tuple[str, Any]], groups: list[tuple[str, list[int]]]
          ) -> list[tuple[str, Any]]:
    """(name, one shape) per top-level component: a sub-assembly's shapes as a compound."""
    import cadquery as cq

    return [(name, placed[shapes[0]][1] if len(shapes) == 1
             else cq.Compound.makeCompound([placed[i][1] for i in shapes]))
            for name, shapes in groups]


def component_colors(assembly) -> list[str]:
    """The colour of every shape in a cq.Assembly, as #rrggbb, in components() order:
    the colour its node was added with, else its nearest parent's, else the
    palette colour for its place in the list."""
    import cadquery as cq

    from .cadview import COMPONENT_RGB

    out = []

    def visit(node, inherited):
        color = node.color.toTuple()[:3] if node.color is not None else inherited
        if node.obj is not None:
            out.append(color)
        for child in node.children:
            visit(child, color)

    visit(assembly, None)
    rgb = [c if c is not None else COMPONENT_RGB[i % len(COMPONENT_RGB)] for i, c in enumerate(out)]
    return ["#" + "".join(f"{round(float(v) * 255):02x}" for v in c) for c in rgb]


def check_assembly(namespace: dict[str, Any]) -> tuple[Any, list[tuple[str, Any]], dict[str, Any]]:
    """(the assembly as one compound, its placed components, its regions)."""
    import cadquery as cq

    placed = components(namespace["result"])
    if not placed:
        raise PartError("the assembly in `result` holds no shapes")
    for name, shape in placed:
        try:
            _check_solids(shape)
        except PartError as exc:
            raise PartError(f"component {name!r}: {exc}") from None
    compound = cq.Compound.makeCompound([s for _, s in placed])
    return compound, placed, _check_regions(namespace)


def _boxes_overlap(a, b, tolerance: float) -> bool:
    """Whether two shapes' bounding boxes meet, touching included (a cheap pre-check)."""
    p, q = a.BoundingBox(), b.BoundingBox()
    return (p.xmin <= q.xmax + tolerance and q.xmin <= p.xmax + tolerance
            and p.ymin <= q.ymax + tolerance and q.ymin <= p.ymax + tolerance
            and p.zmin <= q.zmax + tolerance and q.zmin <= p.zmax + tolerance)


def contact_area(a, b, gap: float = 1e-4) -> float:
    """The area over which two solids touch, through planar faces: pairs that
    face each other (opposite normals) in the same plane (within ``gap``),
    summed over the region the two faces share.

    Face by face rather than from the solids' intersection, which OpenCascade
    returns empty when two faces coincide exactly (a slab on a box of the same
    footprint).
    """
    planar_b = [(f, f.normalAt(), f.BoundingBox()) for f in b.Faces() if f.geomType() == "PLANE"]
    area = 0.0
    for fa in a.Faces():
        if fa.geomType() != "PLANE":
            continue
        na, ca, bba = fa.normalAt(), fa.Center(), fa.BoundingBox()
        for fb, nb, bbb in planar_b:
            if na.dot(nb) > -0.9999 or abs((fb.Center() - ca).dot(na)) > gap:
                continue
            if (bba.xmin > bbb.xmax + gap or bbb.xmin > bba.xmax + gap or bba.ymin > bbb.ymax + gap
                    or bbb.ymin > bba.ymax + gap or bba.zmin > bbb.zmax + gap
                    or bbb.zmin > bba.zmax + gap):
                continue
            area += sum(f.Area() for f in fa.intersect(fb).Faces())
    return area


def interference(placed: list[tuple[str, Any]], tolerance: float = 1e-6
                 ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(clashes, contacts) between the placed components, pair by pair.

    A clash is shared volume: solids in the intersection, in mm^3 (a lip too
    wide for its opening).  A contact is shared surface with no shared volume:
    faces in the intersection, in mm^2 (a lid resting on a rim).  Only solids
    count as volume: OpenCascade reports a face-only intersection's "volume"
    as its area, which would make every seated part look like a clash.
    """
    clashes, contacts = [], []
    for i, (name_a, a) in enumerate(placed):
        for name_b, b in placed[i + 1:]:
            if not _boxes_overlap(a, b, tolerance):
                continue
            common = a.intersect(b)
            volume = sum(s.Volume() for s in common.Solids())
            if volume > tolerance:
                clashes.append({"a": name_a, "b": name_b, "volume_mm3": round(volume, 4)})
                continue
            area = contact_area(a, b)
            if area > tolerance:
                contacts.append({"a": name_a, "b": name_b, "area_mm2": round(area, 4)})
    return clashes, contacts


def summarize(shape, regions: dict[str, Any], script: str = "part.py",
              placed: list[tuple[str, Any]] | None = None,
              colors: list[str] | None = None,
              groups: list[tuple[str, list[int]]] | None = None) -> dict[str, Any]:
    """Facts a reviewer checks the part against: size, volume, topology, regions;
    for an assembly also its components and any interference between them.

    An assembly's components are what was added to it directly (``groups``,
    from top_level; by default every shape on its own).  Each lists its meshes:
    the STL and colour of every shape inside it, as drawn."""
    summary = _summarize_shape(shape, regions)
    summary = {"kind": "assembly" if placed is not None else "part", "script": script, **summary}
    if placed is not None:
        groups = groups or [(name, [i]) for i, (name, _) in enumerate(placed)]
        grouped = group(placed, groups)
        summary["components"] = [
            {"name": name,
             "volume_mm3": round(sum(x.Volume() for x in s.Solids()), 4),
             "bounding_box_min": [round(v, 4) for v in _corner(s, "min")],
             "bounding_box_max": [round(v, 4) for v in _corner(s, "max")],
             "meshes": [{"name": placed[i][0], "stl": f"component_{i + 1:02d}.stl",
                         **({"color": colors[i]} if colors else {})} for i in shapes]}
            for (name, s), (_, shapes) in zip(grouped, groups)
        ]
        summary["interference"], summary["contacts"] = interference(grouped)
    return summary


def _corner(shape, which: str) -> tuple[float, float, float]:
    bb = shape.BoundingBox()
    return (bb.xmin, bb.ymin, bb.zmin) if which == "min" else (bb.xmax, bb.ymax, bb.zmax)


def _summarize_shape(shape, regions: dict[str, Any]) -> dict[str, Any]:
    bb = shape.BoundingBox()
    solids = shape.Solids()
    return {
        "bounding_box": {
            "min": [round(bb.xmin, 4), round(bb.ymin, 4), round(bb.zmin, 4)],
            "max": [round(bb.xmax, 4), round(bb.ymax, 4), round(bb.zmax, 4)],
            "size": [round(bb.xlen, 4), round(bb.ylen, 4), round(bb.zlen, 4)],
        },
        "volume_mm3": round(sum(s.Volume() for s in solids), 4),
        "surface_area_mm2": round(shape.Area(), 4),
        "n_solids": len(solids),
        "n_faces": len(shape.Faces()),
        "n_edges": len(shape.Edges()),
        "face_types": _count(f.geomType() for f in shape.Faces()),
        "regions": {
            name: {"type": region.ShapeType(), "count": _region_count(region)}
            for name, region in regions.items()
        },
    }


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return dict(sorted(out.items()))


def _region_count(region) -> int:
    kind = region.ShapeType()
    if kind == "Compound":
        return len(region.Faces()) or len(region.Edges()) or len(region.Vertices())
    return 1


def export_part(shape, source: str, out_dir: Path, script_name: str = "part.py",
                assembly=None, placed: list[tuple[str, Any]] | None = None,
                colors: list[str] | None = None) -> dict[str, Path]:
    """Write the script, BREP, STEP, STL and PNG views of a built part.

    For an assembly the STEP keeps its structure: one named, placed body per
    component.  The other files show the assembly as one compound.
    """
    import cadquery as cq

    from .cadview import render_components, render_shape

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {kind: out_dir / name for kind, name in FILES.items() if kind != "summary"}
    files["script"] = out_dir / script_name
    files["script"].write_text(source)
    shape.exportBrep(str(files["brep"]))
    workplane = cq.Workplane("XY").add(shape)
    if assembly is not None:
        assembly.export(str(files["step"]), "STEP")
    else:
        cq.exporters.export(workplane, str(files["step"]))
    diag = max(shape.BoundingBox().DiagonalLength, 1e-9)
    cq.exporters.export(workplane, str(files["stl"]), tolerance=diag * 1e-3, angularTolerance=0.2)
    if placed:  # an assembly: one colour (``colors``) and one STL per shape
        shapes = [s for _, s in placed]
        for i, component in enumerate(shapes, start=1):
            files[f"component_{i:02d}"] = out_dir / f"component_{i:02d}.stl"
            cq.exporters.export(cq.Workplane("XY").add(component), str(files[f"component_{i:02d}"]),
                                tolerance=diag * 1e-3, angularTolerance=0.2)
        render_components(shapes, files["png"], view="iso", colors=colors)
        render_components(shapes, files["png_rear"], view="rear_below", colors=colors)
    else:
        render_shape(shape, files["png"], view="iso")
        render_shape(shape, files["png_rear"], view="rear_below")
    return files


def _build_here(script: Path, out_dir: Path) -> dict[str, Any]:
    """Build, check and export one script in this process; a JSON-able report."""
    import cadquery as cq

    source = script.read_text()
    try:
        namespace = _exec_script(source, script)
    except PartError as exc:  # load_part trouble, already explained
        return {"ok": False, "error": str(exc)}
    except Exception:  # the script's own error, with its line numbers
        tb = traceback.format_exc()
        return {"ok": False, "error": "the script raised an error:\n" + tb[-TRACEBACK_CHARS:]}
    try:
        if isinstance(namespace.get("result"), cq.Assembly):
            shape, placed, regions = check_assembly(namespace)
            colors = component_colors(namespace["result"])
            summary = summarize(shape, regions, script.name, placed, colors,
                                top_level(namespace["result"]))
            files = export_part(shape, source, out_dir, script.name, namespace["result"], placed,
                                colors)
        else:
            shape, regions = check_part(namespace)
            summary = summarize(shape, regions, script.name)
            files = export_part(shape, source, out_dir, script.name)
    except PartError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        tb = traceback.format_exc()
        return {"ok": False, "error": "exporting the part failed:\n" + tb[-TRACEBACK_CHARS:]}
    summary_path = Path(out_dir) / FILES["summary"]
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    files["summary"] = summary_path
    return {"ok": True, "summary": summary, "files": {k: str(v) for k, v in files.items()}}


# --------------------------------------------------------------------------
# in the parent process
# --------------------------------------------------------------------------
def build_part(script: Path, out_dir: Path, timeout: float = BUILD_TIMEOUT) -> BuildResult:
    """Build a part script in a child process and export it to ``out_dir``."""
    script, out_dir = Path(script).resolve(), Path(out_dir).resolve()
    report_path = out_dir / ".build.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.unlink(missing_ok=True)
    env = {**os.environ, "MPLBACKEND": "Agg"}
    try:
        done = subprocess.run(
            [sys.executable, "-m", "neobotics.part", str(script), "--out", str(out_dir),
             "--report", str(report_path)],
            capture_output=True, text=True, timeout=timeout, env=env, cwd=out_dir,
        )
    except subprocess.TimeoutExpired:
        return BuildResult(False, f"building the part took longer than {timeout:g} s")
    if not report_path.exists():
        tail = (done.stderr or done.stdout or "")[-TRACEBACK_CHARS:]
        return BuildResult(False, f"the build process died (exit {done.returncode}):\n{tail}")
    report = json.loads(report_path.read_text())
    report_path.unlink()
    if not report["ok"]:
        return BuildResult(False, report["error"])
    return BuildResult(True, None, report["summary"],
                       {k: Path(v) for k, v in report["files"].items()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m neobotics.part",
        description="Build one CadQuery part script in this process (the child side of build_part).",
    )
    parser.add_argument("script", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True, help="JSON report to write")
    args = parser.parse_args(argv)
    report = _build_here(args.script, args.out)
    args.report.write_text(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
