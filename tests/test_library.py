"""The parts library: reusable parts and assemblies, by category, placed with load_library."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neobotics.catalog import build_catalog, discover_all, find, used_in
from neobotics.part import build_part

LIBRARY = Path(__file__).resolve().parents[1] / "library"
HOLDER = LIBRARY / "battery_holders" / "holder_18650"

PLATE = """\
\"\"\"Plate.\"\"\"
import cadquery as cq

l, b, t = 20.0, 10.0, 2.0
result = cq.Workplane("XY").box(l, b, t, centered=(True, True, False))
"""
PIN = """\
\"\"\"Pin.\"\"\"
import cadquery as cq

plate = load_part("../plate")
result = cq.Workplane("XY").circle(1.0).extrude(5.0)
"""
CLIP = """\
\"\"\"Clip.\"\"\"
import cadquery as cq

plate, pin = load_part("plate"), load_part("pin")
result = (cq.Assembly(name="clip")
          .add(plate.result, name="plate")
          .add(pin.result, name="pin", loc=cq.Location((0, 0, plate.t))))
"""
# a product part, two levels down, that stands a library assembly on itself
USER = """\
\"\"\"Bracket with a clip.\"\"\"
import cadquery as cq

clip = load_library("fasteners/clip")
plate = load_library("fasteners/clip/plate")
result = cq.Workplane("XY").box(plate.l, plate.b, 3.0, centered=(True, True, False))
"""


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _tree(root: Path) -> Path:
    """A products tree and a library beside it; returns the products root."""
    clip = root / "library" / "fasteners" / "clip"
    _write(clip / "plate" / "part.py", PLATE)
    _write(clip / "pin" / "part.py", PIN)
    _write(clip / "assembly.py", CLIP)
    _write(root / "library" / "fasteners" / "category.md", "# Fasteners\n\nClips and pins.\n")
    _write(root / "products" / "P1" / "frame" / "bracket" / "part.py", USER)
    return root / "products"


def _summary(result):
    assert result.ok, result.error
    return json.loads(result.files["summary"].read_text())


def test_load_library_finds_the_library_above_the_script(tmp_path):
    products = _tree(tmp_path)
    summary = _summary(build_part(products / "P1/frame/bracket/part.py", tmp_path / "out"))
    assert summary["bounding_box"]["size"] == pytest.approx([20, 10, 3])


def test_load_library_names_what_is_missing(tmp_path, monkeypatch):
    products = _tree(tmp_path / "repo")
    _write(products / "P1" / "frame" / "other" / "part.py", 'x = load_library("fasteners/nut")\n')
    result = build_part(products / "P1/frame/other/part.py", tmp_path / "out")
    assert not result.ok and "load_library('fasteners/nut'): no part.py or assembly.py" in result.error
    # no library/ above the script, and none named: say how to point at one
    _write(tmp_path / "loose" / "part.py", 'x = load_library("fasteners/clip")\n')
    monkeypatch.delenv("NEOBOTICS_LIBRARY", raising=False)
    result = build_part(tmp_path / "loose" / "part.py", tmp_path / "out2")
    assert not result.ok and "NEOBOTICS_LIBRARY" in result.error


def test_the_library_can_live_anywhere(tmp_path, monkeypatch):
    _tree(tmp_path / "repo")
    _write(tmp_path / "elsewhere" / "part.py", USER)
    monkeypatch.setenv("NEOBOTICS_LIBRARY", str(tmp_path / "repo" / "library"))
    assert build_part(tmp_path / "elsewhere" / "part.py", tmp_path / "out").ok


def test_catalog_reads_the_library_beside_the_products(tmp_path):
    products = _tree(tmp_path)
    entries = discover_all(products)
    assert [e.address for e in entries] == [
        "P1/frame/bracket",
        "library/fasteners/clip", "library/fasteners/clip/pin", "library/fasteners/clip/plate"]
    entry = find(products, "library/fasteners/clip/pin")
    assert entry.designation == "fasteners/clip/pin"
    assert entry.out_dir(tmp_path / "r") == tmp_path / "r/library/fasteners/clip/pin"
    assert find(products, "library/fasteners/clip").out_dir(tmp_path / "r") == \
        tmp_path / "r/library/fasteners/clip/_assembly"
    assert used_in(entries) == {"fasteners/clip": ["P1/frame/bracket"],
                                "fasteners/clip/plate": ["P1/frame/bracket"]}


def test_site_publishes_the_library_with_its_uses(tmp_path):
    products = _tree(tmp_path)
    index, failures = build_catalog(products, tmp_path / "results", tmp_path / "site",
                                    log=lambda _: None)
    assert not failures
    site = tmp_path / "site"
    overview = index.read_text()
    assert "Parts library" in overview and 'href="library/fasteners/index.html"' in overview
    library = (site / "library/index.html").read_text()
    assert 'href="../library/fasteners/index.html"' in library and "Fasteners" in library
    category = (site / "library/fasteners/index.html").read_text()
    assert "Category" in category and 'href="clip/index.html"' in category
    assert 'href="../../library/index.html">Parts library</a>' in category  # the breadcrumb
    clip = (site / "library/fasteners/clip/index.html").read_text()
    assert "Library assembly" in clip and "Assembled model" in clip
    assert "load_library(&quot;fasteners/clip&quot;)" in clip
    # who places it, linked from the site root
    assert 'href="../../../products/P1/frame/bracket/index.html"' in clip
    pin = (site / "library/fasteners/clip/pin/index.html").read_text()
    assert "Library part" in pin and "Not placed in any product yet" in pin
    assert (site / "products/P1/frame/bracket/index.html").exists()


def test_the_18650_holder_takes_a_terminal_at_each_end(tmp_path):
    """The real holder: both terminals sit in their slots without interference,
    each touching the holder, with their bumps' tips one cell length apart."""
    summary = _summary(build_part(HOLDER / "assembly.py", tmp_path / "out"))
    assert summary["interference"] == []
    names = [c["name"] for c in summary["components"]]
    assert names == ["holder_18650/holder", "holder_18650/terminal_negative",
                     "holder_18650/terminal_positive"]
    assert [(c["a"], c["b"]) for c in summary["contacts"]] == [
        ("holder_18650/holder", "holder_18650/terminal_negative"),
        ("holder_18650/holder", "holder_18650/terminal_positive")]
    negative, positive = summary["components"][1:]
    # each terminal's inner extent is its bump's tip: one 18650 (65 mm) apart
    assert negative["bounding_box_max"][0] == pytest.approx(-32.5)
    assert positive["bounding_box_min"][0] == pytest.approx(32.5)
    # their feet stand on the holder's floor, their tabs above its top
    assert negative["bounding_box_min"][2] == pytest.approx(1.5)
    assert negative["bounding_box_max"][2] > summary["components"][0]["bounding_box_max"][2]


def test_the_single_18650_holder_cradles_its_cell(tmp_path):
    """The cell lies along x in the body's two rib cradles, inside the open
    frame, clear of every wall."""
    summary = _summary(build_part(LIBRARY / "battery_holders/single_18650_holder/assembly.py",
                                  tmp_path / "out"))
    assert summary["interference"] == []
    body, cell, positive, negative = summary["components"]
    # a clip at each end, from the library, its spring leaf just off the cell's end
    assert [positive["name"], negative["name"]] == [
        "single_18650_holder/clip_positive", "single_18650_holder/clip_negative"]
    assert positive["bounding_box_min"][0] == pytest.approx(32.7)
    assert negative["bounding_box_max"][0] == pytest.approx(-32.7)
    assert positive["bounding_box_max"][2] < body["bounding_box_max"][2]  # below the rim
    assert {c["b"] for c in summary["contacts"]} == {positive["name"], negative["name"]}
    assert cell["name"].endswith("/battery")
    assert [cell["bounding_box_max"][i] - cell["bounding_box_min"][i] for i in range(3)] == \
        pytest.approx([65.0, 18.4, 18.4])
    assert cell["bounding_box_min"][2] == pytest.approx(1.0)  # on the cradles' bottoms
    for i in range(3):  # inside the body
        assert body["bounding_box_min"][i] <= cell["bounding_box_min"][i]
        assert cell["bounding_box_max"][i] <= body["bounding_box_max"][i]


def test_the_single_18650_holder_takes_m12_screws_in_its_triangles(tmp_path):
    """Four M1.2 tap holes, one in each bottom triangle at each end, entirely in
    material, far enough in that a 2.3 mm countersunk head clears the side and
    the bottom."""
    import math

    summary = _summary(build_part(LIBRARY / "battery_holders/single_18650_holder/body/part.py",
                                  tmp_path / "out"))
    assert summary["regions"]["screw_holes"]["count"] == 4
    width = summary["bounding_box"]["size"][1]
    foot = math.sqrt(2) * (18.4 / 2 + 0.1 + 1.0) - (1.0 + 18.4 / 2 + 0.1)  # the 45 face meets z = 0
    inset = (width / 2 - foot) * (2 - math.sqrt(2)) / 2  # the triangle's inradius
    assert inset - 2.3 / 2 == pytest.approx(0.676, abs=1e-3)  # head clear of side and bottom
