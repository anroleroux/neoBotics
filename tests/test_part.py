"""The CAD stage: part scripts in, checked B-rep and its exports out."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from neobotics.cadview import stl_triangles
from neobotics.part import build_part

EXAMPLE = (Path(__file__).resolve().parents[1] / "products" / "B4" / "motor_mounts"
           / "nema17_bracket" / "part.py")


@pytest.fixture(scope="module")
def example_build(tmp_path_factory):
    return build_part(EXAMPLE, tmp_path_factory.mktemp("motor_mount"))


def test_example_builds_and_exports_everything(example_build):
    assert example_build.ok, example_build.error
    for kind in ("script", "brep", "step", "stl", "png", "png_rear", "summary"):
        path = example_build.files[kind]
        assert path.exists() and path.stat().st_size > 0, kind
    assert example_build.files["script"].read_text() == EXAMPLE.read_text()


def test_example_summary_matches_the_description(example_build):
    summary = example_build.summary
    assert summary["bounding_box"]["size"] == pytest.approx([50.0, 40.0, 50.0])
    assert summary["bounding_box"]["min"][2] == pytest.approx(0.0)  # stands on z = 0
    assert summary["n_solids"] == 1
    # bore + 4 x M3 + 2 x M4 + the inside fillet
    assert summary["face_types"]["CYLINDER"] == 8
    assert set(summary["regions"]) == {"motor_face", "pilot_bore", "base_bottom"}
    on_disk = json.loads(example_build.files["summary"].read_text())
    assert on_disk == summary


def test_stl_is_a_closed_surface_of_the_part(example_build):
    points, triangles = stl_triangles(example_build.files["stl"])
    tri = points[triangles]
    # divergence theorem: the enclosed volume matches the B-rep's
    volume = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6
    assert volume == pytest.approx(example_build.summary["volume_mm3"], rel=2e-3)


def _build(tmp_path, source):
    script = tmp_path / "part.py"
    script.write_text(source)
    return build_part(script, tmp_path / "out", timeout=120)


@pytest.mark.parametrize("source, message", [
    ("import cadquery as cq\nbox = cq.Workplane().box(1, 1, 1)\n", "assign the part to `result`"),
    ("import cadquery as cq\nresult = cq.Workplane().rect(4, 4)\n", "holds no solid (it is a Wire)"),
    ("import cadquery as cq\nresult = cq.Workplane().rect(4, 4).extrude(0.0)\n", "raised an error"),
    ("import cadquery as cq\nresult = cq.Face.makePlane(4, 4)\n", "holds no solid"),
    ("result = 42\n", "must be a cq.Workplane or cq.Shape"),
    ("import cadquery as cq\nresult = cq.Workplane().box(2, 2, 2)\nregions = {'all': result}\n",
     "is a solid"),
    ("import cadquery as cq\nresult = cq.Workplane().box(2, 2, 2)\n"
     "regions = {'none': result.faces('%CYLINDER')}\n", "selects nothing"),
    ("def broken(:\n", "raised an error"),
])
def test_bad_scripts_are_reported_not_raised(tmp_path, source, message):
    result = _build(tmp_path, source)
    assert not result.ok
    assert message in result.error


def test_script_errors_carry_the_failing_line(tmp_path):
    result = _build(tmp_path, "import cadquery as cq\n\nresult = cq.Workplane().box(1, 1, 1)\n"
                              "result = result.faces('>Z').hole(5).fillet(-1)\n")
    assert not result.ok
    assert 'File "part.py", line 4' in result.error


def test_a_hanging_script_times_out(tmp_path):
    script = tmp_path / "part.py"
    script.write_text("while True:\n    pass\n")
    result = build_part(script, tmp_path / "out", timeout=5)
    assert not result.ok and "longer than 5 s" in result.error
