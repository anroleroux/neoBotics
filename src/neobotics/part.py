"""The CAD stage: run a CadQuery part script, check it, export it.

A part is a CadQuery script, the same contract as topocombo's ``part.py``.  It
assigns the part to ``result`` and may name places on it in ``regions``:

  result   the part — a ``cq.Workplane`` or ``cq.Shape`` holding one or more
           solids, modelled in millimetres with z up, standing on z = 0
  regions  optional dict of named places on the part (mounting faces, bores,
           a shaft axis): vertices, edges or faces, picked with selectors or
           built on their own — what a later stage (a study, an assembly)
           refers to by name

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
def _exec_script(source: str, filename: str) -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "__cadquery_script__"}
    exec(compile(source, filename, "exec"), namespace)
    return namespace


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
    return shape, checked


def summarize(shape, regions: dict[str, Any]) -> dict[str, Any]:
    """Facts a reviewer checks the part against: size, volume, topology, regions."""
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


def export_part(shape, source: str, out_dir: Path) -> dict[str, Path]:
    """Write the script, BREP, STEP, STL and PNG views of a built part."""
    import cadquery as cq

    from .cadview import render_shape

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {kind: out_dir / name for kind, name in FILES.items() if kind != "summary"}
    files["script"].write_text(source)
    shape.exportBrep(str(files["brep"]))
    workplane = cq.Workplane("XY").add(shape)
    cq.exporters.export(workplane, str(files["step"]))
    diag = max(shape.BoundingBox().DiagonalLength, 1e-9)
    cq.exporters.export(workplane, str(files["stl"]), tolerance=diag * 1e-3, angularTolerance=0.2)
    render_shape(shape, files["png"], view="iso")
    render_shape(shape, files["png_rear"], view="rear_below")
    return files


def _build_here(script: Path, out_dir: Path) -> dict[str, Any]:
    """Build, check and export one script in this process; a JSON-able report."""
    source = script.read_text()
    try:
        namespace = _exec_script(source, str(script.name))
    except Exception:  # the script's own error, with its line numbers
        tb = traceback.format_exc()
        return {"ok": False, "error": "the script raised an error:\n" + tb[-TRACEBACK_CHARS:]}
    try:
        shape, regions = check_part(namespace)
        summary = summarize(shape, regions)
        files = export_part(shape, source, out_dir)
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
