"""Parts sized from other parts (load_part), and assembled models (assembly.py)."""

from __future__ import annotations

import json
import math
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


def test_the_pb4_chassis_carries_four_cells_against_the_back_wall(tmp_path):
    """The real chassis: four 18650 cells on the floor, pointing along x, each
    with its negative end against the back (-x) wall, none overlapping."""
    summary = _summary(build_part(CHASSIS / "assembly.py", tmp_path / "out"))
    base = _summary(build_part(CHASSIS / "base" / "part.py", tmp_path / "base"))
    assert summary["interference"] == []
    cells = [c for c in summary["components"] if "battery" in c["name"]]
    assert len(cells) == 4
    l, wall = base["bounding_box"]["size"][0], 3.0
    for cell in cells:
        assert cell["bounding_box_min"][0] == pytest.approx(-l / 2 + wall)  # against the back wall
        assert cell["bounding_box_max"][0] - cell["bounding_box_min"][0] == pytest.approx(65.0)
        assert cell["bounding_box_min"][2] == pytest.approx(wall)  # on the floor
    # each cell touches the base over exactly its negative end
    assert [c["area_mm2"] for c in summary["contacts"]] == pytest.approx([math.pi * 9.2 ** 2] * 4)


def test_the_pb4_lid_fits_the_base(tmp_path):
    """The product model: the lid sits on the end walls' rims (+-x), its skirts
    close the open long sides (+-y), and its lips stay clear of the end walls
    and of the cells."""
    summary = _summary(build_part(PRODUCTS / "PB4" / "assembly.py", tmp_path / "out"))
    box = _summary(build_part(CHASSIS / "base" / "part.py", tmp_path / "box"))
    assert summary["interference"] == []
    (lid,) = [c for c in summary["contacts"] if c["b"].endswith("/lid")]
    l, b, h = box["bounding_box"]["size"]
    wall = 3.0
    rims = 2 * b * wall  # the two end walls' tops
    sides = 2 * (l * wall + 2 * wall * (h - wall))  # the floor's and end walls' edges at +-y
    retainers = 2 * (65.0 - 1.0) * 12.0  # the side retainers' outer faces, flush at +-y:
    # a cell length less the 1 mm gap at the back wall, 12 mm tall
    assert lid["a"].endswith("/base") and lid["area_mm2"] == pytest.approx(rims + sides + retainers)
    # the lid overhangs a = 5 mm at each end, adds its thickness each side and on top,
    # and reaches the base's bottom
    assert summary["bounding_box"]["size"] == pytest.approx([l + 10, b + 2 * wall, h + wall])
    assert summary["bounding_box"]["min"][2] == pytest.approx(0)


def test_build_command_takes_an_assembly_designation(tmp_path, capsys):
    assert cli_main(["build", "PB4/chassis", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "PB4/chassis/_assembly/cad/part.step").exists()
    assert "built PB4/chassis" in capsys.readouterr().out


def test_site_shows_the_assembled_model_with_its_fit(tmp_path):
    root = _tree(tmp_path / "products")
    index, failures = build_catalog(root, tmp_path / "results", tmp_path / "site",
                                    log=lambda _: None)
    assert not failures
    page = (tmp_path / "site/products/P1/stack/index.html").read_text()
    # the assembly's own page: its model first, then its contents
    assert page.index("Contents") < page.index("Assembled model")
    assert "No interference" in page and "touch over" in page
    assert "2 components · no interference · 1 contact" in page  # the folded summary
    assert 'href="box/index.html"' in page and 'href="slab/index.html"' in page
    # one STL per component, so the viewer colours them like the PNG views
    assert 'data-stl="_assembly/component_01.stl _assembly/component_02.stl"' in page
    assert (tmp_path / "site/products/P1/stack/_assembly/component_02.stl").exists()
    assert 'href="_assembly/assembly.py"' in page
    assert (tmp_path / "site/products/P1/stack/_assembly/assembly.py").exists()
    # the assembly's card on the product page uses the model as its picture
    product = (tmp_path / "site/products/P1/index.html").read_text()
    assert 'src="stack/_assembly/part.png"' in product
    assert 'src="products/P1/stack/_assembly/part.png"' in index.read_text()


def test_a_product_level_model_and_part_reach_the_site(tmp_path):
    """A product's own part, and an assembly.py on the product itself."""
    root = _tree(tmp_path / "products")
    (root / "P1" / "cap").mkdir()
    (root / "P1" / "cap" / "part.py").write_text(SLAB_ON_BOX.replace('"../box"', '"../stack/box"'))
    (root / "P1" / "assembly.py").write_text(
        'import cadquery as cq\n'
        'stack, cap = load_part("stack"), load_part("cap")\n'
        'result = (cq.Assembly(name="P1").add(stack.result, name="stack")\n'
        '          .add(cap.result, name="cap", loc=cq.Location((0, 0, 40))))\n')
    assert [e.designation for e in discover(root)][-2:] == ["P1", "P1/cap"]
    index, failures = build_catalog(root, tmp_path / "results", tmp_path / "site",
                                    log=lambda _: None)
    assert not failures
    page = (tmp_path / "site/products/P1/index.html").read_text()
    assert page.index("Contents") < page.index("Assembled model")
    assert 'href="stack/index.html"' in page and 'href="cap/index.html"' in page
    assert "1 assembly · 1 part" in page
    assert (tmp_path / "site/products/P1/_assembly/part.stl").exists()
    assert (tmp_path / "site/products/P1/cap/index.html").exists()
