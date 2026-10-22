"""The catalogue site: a products/ breakdown in, an overview and one page per product out."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from neobotics.catalog import build_catalog, discover, find, read_heading
from neobotics.cli import main as cli_main
from neobotics.pipeline import run_script
from neobotics.site import DOWNLOADS, Assembly, Product, build_site, read_part

PRODUCTS = Path(__file__).resolve().parents[1] / "products"
BRACKET = Path(__file__).resolve().parent / "fixtures" / "nema17_bracket"

PLATE = """\
\"\"\"A 30 x 30 x 4 mm plate.\"\"\"
import cadquery as cq

result = cq.Workplane("XY").box(30, 30, 4, centered=(True, True, False))
regions = {}
"""


def _part(directory: Path, script: str = PLATE) -> None:
    directory.mkdir(parents=True)
    (directory / "part.py").write_text(script)


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory):
    """The reference bracket in a B4 product, plus a product with a sub-assembly two levels down."""
    root = tmp_path_factory.mktemp("products")
    shutil.copytree(BRACKET, root / "B4" / "motor_mounts" / "nema17_bracket")
    (root / "B4" / "product.md").write_text("# B4\n\nThe B4 line.\n")
    _part(root / "Z9" / "drive" / "left_wheel" / "hub")
    _part(root / "Z9" / "cover")  # a part of the product itself
    (root / "Z9" / "product.md").write_text("# Z9 <beta>\n\nA second product & line.\n")
    (root / "Z9" / "drive" / "assembly.md").write_text("# Drive train\n\nWheels and motors.\n")
    out = tmp_path_factory.mktemp("build")
    index, failures = build_catalog(root, out / "results", out / "site", log=lambda _: None)
    return {"root": root, "out": out, "index": index, "failures": failures,
            "page": index.read_text()}


def _page(catalogue, *path):
    """A page of the built site, by its directory under products/."""
    return (catalogue["out"] / "site" / "products" / Path(*path) / "index.html").read_text()


# ---- the breakdown -----------------------------------------------------------
def test_discover_walks_the_real_catalogue():
    designations = [e.designation for e in discover(PRODUCTS)]
    assert designations == ["PB4/chassis", "PB4/chassis/base", "PB4/chassis/battery_18650",
                            "PB4/chassis/bms_2s",
                            "PB4/chassis/cn3302_charger", "PB4/chassis/ip6505_charger",
                            "PB4", "PB4/lid", "RA6/base/base_plate"]


def test_discover_follows_sub_assemblies(tmp_path):
    _part(tmp_path / "P1" / "drive" / "left" / "hub")
    _part(tmp_path / "P1" / "drive" / "right" / "hub")
    _part(tmp_path / "P1" / "frame" / "plate")
    (tmp_path / "P1" / "_drafts").mkdir()  # ignored
    entries = discover(tmp_path)
    assert [e.designation for e in entries] == [
        "P1/drive/left/hub", "P1/drive/right/hub", "P1/frame/plate"]
    assert entries[0].assemblies == ("drive", "left") and entries[0].part == "hub"


def test_a_product_may_hold_parts_and_assemblies(tmp_path):
    _part(tmp_path / "P1" / "lid")
    _part(tmp_path / "P1" / "frame" / "plate")
    assert [e.designation for e in discover(tmp_path)] == ["P1/frame/plate", "P1/lid"]


@pytest.mark.parametrize("layout, message", [
    (["P1/frame/plate", "P1/frame/sub/bolt"], "either parts or sub-assemblies, not both"),
])
def test_discover_enforces_the_rules(tmp_path, layout, message):
    for path in layout:
        _part(tmp_path / path)
    with pytest.raises(ValueError, match=message):
        discover(tmp_path)


def test_a_part_holds_no_directories(tmp_path):
    _part(tmp_path / "P1" / "frame" / "plate")
    (tmp_path / "P1" / "frame" / "plate" / "extra").mkdir()
    with pytest.raises(ValueError, match="a part holds no directories"):
        discover(tmp_path)


def test_find_by_designation():
    assert find(PRODUCTS, "PB4/chassis/base/").script.name == "part.py"
    assert find(PRODUCTS, "PB4/chassis").script.name == "assembly.py"
    assert find(PRODUCTS, "PB4").script.name == "assembly.py"  # the product's own model
    assert find(PRODUCTS, "PB4/lid").part == "lid"
    with pytest.raises(KeyError):
        find(PRODUCTS, "PB4/chassis/nope")


@pytest.mark.parametrize("script, title", [
    ('"""Wheel hub."""\nimport cadquery as cq\n', "Wheel hub"),
    ('"""A plate.\n\nMore words.\n"""\n', "A plate"),
    ("import cadquery as cq\n", "base plate"),
])
def test_part_title_is_the_first_docstring_line(script, title):
    from neobotics.site import _title

    assert _title(script, "base_plate") == title


def test_read_heading(tmp_path):
    md = tmp_path / "product.md"
    md.write_text("# B4\n\nThe B4 line.\n")
    assert read_heading(md, "x") == ("B4", "The B4 line.")
    assert read_heading(tmp_path / "missing.md", "fallback") == ("fallback", "")


def test_build_command_builds_one_part_by_designation(tmp_path, capsys):
    assert cli_main(["build", "PB4/chassis/base", "--out", str(tmp_path)]) == 0
    cad = tmp_path / "PB4" / "chassis" / "base" / "cad"
    assert (cad / "part.step").exists()
    assert "built PB4/chassis/base" in capsys.readouterr().out


def test_cad_run_keeps_the_description_next_to_the_script(tmp_path):
    assert run_script(BRACKET / "part.py", tmp_path / "run").ok
    assert (tmp_path / "run" / "description.md").read_text() == (BRACKET / "description.md").read_text()


# ---- the pages ---------------------------------------------------------------
def test_overview_has_a_card_per_product(catalogue):
    page = catalogue["page"]
    assert not catalogue["failures"]
    assert page.index('href="products/B4/index.html"') < page.index('href="products/Z9/index.html"')
    assert 'src="products/B4/motor_mounts/nema17_bracket/part.png"' in page  # first part, deep
    assert "2 products · 3 parts" in page
    assert "three.module.js" not in page  # no viewer on the overview


def test_each_level_lists_only_its_own_contents(catalogue):
    z9 = _page(catalogue, "Z9")
    # the product: its assembly and its own part, as cards that drill down
    assert 'href="drive/index.html"' in z9 and 'href="cover/index.html"' in z9
    assert "Drive train" in z9  # the assembly's title from assembly.md
    assert "1 assembly · 1 part" in z9
    # nothing from further down: no card or link for the sub-assembly or its part
    # (the drive card's picture may come from deeper down)
    assert 'href="drive/left_wheel' not in z9 and "Z9/drive/left_wheel" not in z9
    drive = _page(catalogue, "Z9", "drive")
    assert 'href="left_wheel/index.html"' in drive and "Sub-assembly" in drive
    assert "Left wheel" in drive  # no assembly.md: the slug, capitalised
    assert "hub/index.html" not in drive and "Z9/drive/left_wheel/hub" not in drive
    wheel = _page(catalogue, "Z9", "drive", "left_wheel")
    assert 'href="hub/index.html"' in wheel and 'src="hub/part.png"' in wheel
    assert "Z9/drive/left_wheel/hub" in wheel  # the card shows the designation


def test_a_part_has_its_own_page(catalogue):
    hub = _page(catalogue, "Z9", "drive", "left_wheel", "hub")
    assert "Z9/drive/left_wheel/hub" in hub and 'data-stl="part.stl"' in hub
    bracket = _page(catalogue, "B4", "motor_mounts", "nema17_bracket")
    assert "An L-bracket that holds a NEMA 17 stepper motor" in bracket
    assert "NEMA 17 31 mm square pattern" in bracket  # the description
    assert "50 × 40 × 50 mm" in bracket  # the measured size


def test_every_page_links_back_up(catalogue):
    hub = _page(catalogue, "Z9", "drive", "left_wheel", "hub")
    root = "../" * 5  # products/Z9/drive/left_wheel/hub/
    for href in (f"{root}index.html", f"{root}products/Z9/index.html",
                 f"{root}products/Z9/drive/index.html",
                 f"{root}products/Z9/drive/left_wheel/index.html"):
        assert f'href="{href}"' in hub  # the breadcrumb, one link per level above
    assert "← Back to Left wheel" in hub
    z9 = _page(catalogue, "Z9")
    assert 'href="../../index.html"' in z9 and "← Back to all products" in z9


def test_every_part_publishes_its_files(catalogue):
    site = catalogue["out"] / "site" / "products"
    for path in ("B4/motor_mounts/nema17_bracket", "Z9/drive/left_wheel/hub", "Z9/cover"):
        page = (site / path / "index.html").read_text()
        for filename, *_ in DOWNLOADS:
            assert (site / path / filename).exists()
            assert f'href="{filename}"' in page
    assert (catalogue["out"] / "site" / ".nojekyll").exists()


def test_pages_escape_titles_and_blurbs(catalogue):
    for page in (catalogue["page"], _page(catalogue, "Z9")):
        assert "Z9 <beta>" not in page and "Z9 &lt;beta&gt;" in page
    assert "A second product &amp; line." in _page(catalogue, "Z9")


def test_a_part_that_does_not_build_is_reported_and_left_off(tmp_path):
    root = tmp_path / "products"
    _part(root / "A1" / "plates" / "good")
    _part(root / "A1" / "plates" / "bad", "result = 42\n")
    index, failures = build_catalog(root, tmp_path / "results", tmp_path / "site",
                                    log=lambda _: None)
    assert len(failures) == 1 and failures[0].startswith("A1/plates/bad:")
    page = (tmp_path / "site" / "products" / "A1" / "plates" / "index.html").read_text()
    assert 'href="good/index.html"' in page and "bad" not in page


def test_site_refuses_empty_catalogues_and_duplicate_slugs(tmp_path):
    run = tmp_path / "run"
    assert run_script(BRACKET / "part.py", run).ok
    part = read_part(run, "bracket")
    with pytest.raises(ValueError, match="no parts"):
        build_site([Product("B4", "B4")], tmp_path / "site")
    twice = Product("B4", "B4", assemblies=[Assembly("mounts", "Mounts", parts=[part, part])])
    with pytest.raises(ValueError, match="unique"):
        build_site([twice], tmp_path / "site")
