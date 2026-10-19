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
BRACKET = PRODUCTS / "B4" / "motor_mounts" / "nema17_bracket"

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
    """The real B4 bracket, plus a product with a sub-assembly two levels down."""
    root = tmp_path_factory.mktemp("products")
    shutil.copytree(PRODUCTS / "B4", root / "B4")
    _part(root / "Z9" / "drive" / "left_wheel" / "hub")
    (root / "Z9" / "product.md").write_text("# Z9 <beta>\n\nA second product & line.\n")
    (root / "Z9" / "drive" / "assembly.md").write_text("# Drive train\n\nWheels and motors.\n")
    out = tmp_path_factory.mktemp("build")
    index, failures = build_catalog(root, out / "results", out / "site", log=lambda _: None)
    return {"root": root, "out": out, "index": index, "failures": failures,
            "page": index.read_text()}


def _product_page(catalogue, slug):
    return (catalogue["out"] / "site" / "products" / slug / "index.html").read_text()


# ---- the breakdown -----------------------------------------------------------
def test_discover_walks_the_real_catalogue():
    designations = [e.designation for e in discover(PRODUCTS)]
    assert designations == ["B4/motor_mounts/nema17_bracket",
                            "PB4/chassis", "PB4/chassis/base", "PB4/chassis/lid"]


def test_discover_follows_sub_assemblies(tmp_path):
    _part(tmp_path / "P1" / "drive" / "left" / "hub")
    _part(tmp_path / "P1" / "drive" / "right" / "hub")
    _part(tmp_path / "P1" / "frame" / "plate")
    (tmp_path / "P1" / "_drafts").mkdir()  # ignored
    entries = discover(tmp_path)
    assert [e.designation for e in entries] == [
        "P1/drive/left/hub", "P1/drive/right/hub", "P1/frame/plate"]
    assert entries[0].assemblies == ("drive", "left") and entries[0].part == "hub"


@pytest.mark.parametrize("layout, message", [
    (["P1/loose"], "must sit inside an assembly"),
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
    assert "Motor mounts" in page and "Drive train" in page  # top-level assemblies on the cards
    assert 'src="products/B4/motor_mounts/nema17_bracket/part.png"' in page
    assert 'src="products/Z9/drive/left_wheel/hub/part.png"' in page  # first part, however deep
    assert "2 products · 2 parts" in page
    assert "three.module.js" not in page  # no viewer on the overview


def test_product_page_nests_assemblies_and_shows_designations(catalogue):
    z9 = _product_page(catalogue, "Z9")
    assert z9.index('id="drive"') < z9.index('id="drive--left_wheel"') \
        < z9.index('id="drive--left_wheel--hub"')
    assert "Drive train" in z9  # the title from assembly.md
    assert "Left wheel" in z9  # no assembly.md: the slug, capitalised
    assert "Sub-assembly" in z9
    assert "Z9/drive/left_wheel/hub" in z9  # the part's designation
    b4 = _product_page(catalogue, "B4")
    assert "B4/motor_mounts/nema17_bracket" in b4
    assert "NEMA 17 31 mm square pattern" in b4  # the description
    assert "50 × 40 × 50 mm" in b4  # the measured size
    assert "left_wheel" not in b4  # another product's parts stay on their own page


def test_product_pages_link_back(catalogue):
    b4, z9 = _product_page(catalogue, "B4"), _product_page(catalogue, "Z9")
    for page in (b4, z9):
        assert page.count('href="../../index.html"') >= 3  # breadcrumb, sidebar, pager
        assert "All products" in page
    assert 'href="../Z9/index.html"' in b4 and "../B4/index.html" not in b4
    assert 'href="../B4/index.html"' in z9 and "../Z9/index.html" not in z9


def test_every_part_publishes_its_files(catalogue):
    site = catalogue["out"] / "site"
    for product, rest in (("B4", "motor_mounts/nema17_bracket"), ("Z9", "drive/left_wheel/hub")):
        page = _product_page(catalogue, product)
        assert f'data-stl="{rest}/part.stl"' in page
        for filename, *_ in DOWNLOADS:
            assert (site / "products" / product / rest / filename).exists()
            assert f'href="{rest}/{filename}"' in page
    assert (site / ".nojekyll").exists()


def test_pages_escape_titles_and_blurbs(catalogue):
    for page in (catalogue["page"], _product_page(catalogue, "Z9")):
        assert "Z9 <beta>" not in page and "Z9 &lt;beta&gt;" in page
        assert "A second product &amp; line." in page


def test_a_part_that_does_not_build_is_reported_and_left_off(tmp_path):
    root = tmp_path / "products"
    _part(root / "A1" / "plates" / "good")
    _part(root / "A1" / "plates" / "bad", "result = 42\n")
    index, failures = build_catalog(root, tmp_path / "results", tmp_path / "site",
                                    log=lambda _: None)
    assert len(failures) == 1 and failures[0].startswith("A1/plates/bad:")
    page = (tmp_path / "site" / "products" / "A1" / "index.html").read_text()
    assert 'id="plates--good"' in page and "plates--bad" not in page


def test_site_refuses_empty_catalogues_and_duplicate_slugs(tmp_path):
    run = tmp_path / "run"
    assert run_script(BRACKET / "part.py", run).ok
    part = read_part(run, "bracket")
    with pytest.raises(ValueError, match="no parts"):
        build_site([Product("B4", "B4")], tmp_path / "site")
    twice = Product("B4", "B4", assemblies=[Assembly("mounts", "Mounts", parts=[part, part])])
    with pytest.raises(ValueError, match="unique"):
        build_site([twice], tmp_path / "site")
