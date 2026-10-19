"""Parts sized from other parts (load_part), and assembled models (assembly.py)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from neobotics.catalog import build_catalog, discover, find
from neobotics.cli import main as cli_main
from neobotics.part import build_part

PRODUCTS = Path(__file__).resolve().parents[1] / "products"
CHASSIS = PRODUCTS / "PB4" / "chassis"

BOX = """\
\"\"\"Box.\"\"\"
import cadquery as cq

l, b, h = 40.0, 30.0, 20.0
result = cq.Workplane("XY").box(l, b, h, centered=(True, True, False))
"""
SLAB_ON_BOX = """\
\"\"\"Slab.\"\"\"
import cadquery as cq

box = load_part("../box")
result = cq.Workplane("XY").box(box.l, box.b, 2.0, centered=(True, True, False))
"""
ASSEMBLY = """\
\"\"\"Box and slab.\"\"\"
import cadquery as cq

box, slab = load_part("box"), load_part("slab")
result = (cq.Assembly(name="stack")
          .add(box.result, name="box")
          .add(slab.result, name="slab", loc=cq.Location((0, 0, box.h - {sink}))))
"""


def _tree(root: Path, sink: float = 0.0) -> Path:
    for name, source in (("box", BOX), ("slab", SLAB_ON_BOX)):
        (root / "P1" / "stack" / name).mkdir(parents=True)
        (root / "P1" / "stack" / name / "part.py").write_text(source)
    (root / "P1" / "stack" / "assembly.py").write_text(ASSEMBLY.format(sink=sink))
    return root


def _summary(result):
    assert result.ok, result.error
    return json.loads(result.files["summary"].read_text())


def test_load_part_sizes_one_part_from_another(tmp_path):
    root = _tree(tmp_path)
    summary = _summary(build_part(root / "P1/stack/slab/part.py", tmp_path / "out"))
    assert summary["bounding_box"]["size"] == pytest.approx([40, 30, 2])


def test_load_part_reports_missing_and_cyclic_parts(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "part.py").write_text('x = load_part("../b")\n')
    (tmp_path / "b" / "part.py").write_text('y = load_part("../a")\n')
    result = build_part(tmp_path / "a" / "part.py", tmp_path / "out")
    assert not result.ok and "load_part cycle: a -> b -> a" in result.error
    (tmp_path / "b" / "part.py").write_text('y = load_part("../nowhere")\n')
    result = build_part(tmp_path / "a" / "part.py", tmp_path / "out")
    assert not result.ok and "no part.py or assembly.py" in result.error


def test_seated_assembly_touches_without_interference(tmp_path):
    root = _tree(tmp_path)
    summary = _summary(build_part(root / "P1/stack/assembly.py", tmp_path / "out"))
    assert summary["kind"] == "assembly" and summary["script"] == "assembly.py"
    assert [c["name"] for c in summary["components"]] == ["stack/box", "stack/slab"]
    assert summary["bounding_box"]["size"] == pytest.approx([40, 30, 22])
    assert summary["interference"] == []
    assert summary["contacts"] == [{"a": "stack/box", "b": "stack/slab", "area_mm2": 1200.0}]
    cad = tmp_path / "out"
    assert (cad / "assembly.py").exists() and (cad / "part.step").exists()


def test_overlapping_components_are_a_clash(tmp_path):
    root = _tree(tmp_path, sink=1.5)  # the slab sinks 1.5 mm into the box
    summary = _summary(build_part(root / "P1/stack/assembly.py", tmp_path / "out"))
    assert summary["interference"] == [
        {"a": "stack/box", "b": "stack/slab", "volume_mm3": pytest.approx(40 * 30 * 1.5)}]


def test_catalog_finds_assembly_models(tmp_path):
    root = _tree(tmp_path)
    entries = discover(root)
    assert [(e.designation, e.is_assembly) for e in entries] == [
        ("P1/stack", True), ("P1/stack/box", False), ("P1/stack/slab", False)]
    assert find(root, "P1/stack").out_dir(tmp_path / "r") == tmp_path / "r/P1/stack/_assembly"


def test_the_pb4_chassis_lid_fits_its_box(tmp_path):
    """The real chassis: lid seated on the box rim, lip clear of the walls."""
    summary = _summary(build_part(CHASSIS / "assembly.py", tmp_path / "out"))
    box = _summary(build_part(CHASSIS / "base" / "part.py", tmp_path / "box"))
    assert summary["interference"] == []
    (contact,) = summary["contacts"]
    rim = 120 * 80 - (120 - 6) * (80 - 6)  # outside minus opening, for l, b = 120, 80 and wall 3
    assert contact["area_mm2"] == pytest.approx(rim)
    assert summary["bounding_box"]["size"][2] == pytest.approx(box["bounding_box"]["size"][2] + 3)


def test_build_command_takes_an_assembly_designation(tmp_path, capsys):
    assert cli_main(["build", "PB4/chassis", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "PB4/chassis/_assembly/cad/part.step").exists()
    assert "built PB4/chassis" in capsys.readouterr().out


def test_site_shows_the_assembled_model_with_its_fit(tmp_path):
    root = _tree(tmp_path / "products")
    index, failures = build_catalog(root, tmp_path / "results", tmp_path / "site",
                                    log=lambda _: None)
    assert not failures
    page = (tmp_path / "site/products/P1/index.html").read_text()
    assert page.index('id="stack"') < page.index('id="stack--assembled"') \
        < page.index('id="stack--box"')
    assert "Assembled model" in page and "No interference" in page and "touch over" in page
    # one STL per component, so the viewer colours them like the PNG views
    assert 'data-stl="stack/_assembly/component_01.stl stack/_assembly/component_02.stl"' in page
    assert (tmp_path / "site/products/P1/stack/_assembly/component_02.stl").exists()
    assert 'href="stack/_assembly/assembly.py"' in page
    assert (tmp_path / "site/products/P1/stack/_assembly/assembly.py").exists()
    assert 'src="products/P1/stack/_assembly/part.png"' in index.read_text()  # card thumbnail
