"""The catalogue site: a products/ tree in, one page grouped by product and subcategory out."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from neobotics.catalog import build_catalog, discover, read_heading
from neobotics.pipeline import run_script
from neobotics.site import DOWNLOADS, Category, Product, build_site, read_part

PRODUCTS = Path(__file__).resolve().parents[1] / "products"
BRACKET = PRODUCTS / "B4" / "motor_mounts" / "nema17_bracket"

PLATE = """\
\"\"\"A 30 x 30 x 4 mm plate.\"\"\"
import cadquery as cq

result = cq.Workplane("XY").box(30, 30, 4, centered=(True, True, False))
regions = {}
"""


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory):
    """The real B4 bracket plus a second product with a part of its own."""
    root = tmp_path_factory.mktemp("products")
    shutil.copytree(PRODUCTS / "B4", root / "B4")
    plate = root / "Z9" / "plates" / "square_plate"
    plate.mkdir(parents=True)
    (plate / "part.py").write_text(PLATE)
    (root / "Z9" / "product.md").write_text("# Z9 <beta>\n\nA second product & line.\n")
    out = tmp_path_factory.mktemp("build")
    index, failures = build_catalog(root, out / "results", out / "site", log=lambda _: None)
    return {"root": root, "out": out, "index": index, "failures": failures,
            "page": index.read_text()}


def test_discover_walks_product_subcategory_part():
    entries = discover(PRODUCTS)
    assert [(e.product, e.category, e.part) for e in entries] == [
        ("B4", "motor_mounts", "nema17_bracket")]


def test_discover_refuses_scripts_outside_the_three_levels(tmp_path):
    (tmp_path / "B4" / "loose").mkdir(parents=True)
    (tmp_path / "B4" / "loose" / "part.py").write_text(PLATE)
    with pytest.raises(ValueError, match="B4/loose/part.py"):
        discover(tmp_path)


def test_read_heading(tmp_path):
    md = tmp_path / "product.md"
    md.write_text("# B4\n\nThe B4 line.\n")
    assert read_heading(md, "x") == ("B4", "The B4 line.")
    assert read_heading(tmp_path / "missing.md", "fallback") == ("fallback", "")


def test_cad_run_keeps_the_description_next_to_the_script(tmp_path):
    assert run_script(BRACKET / "part.py", tmp_path / "run").ok
    assert (tmp_path / "run" / "description.md").read_text() == (BRACKET / "description.md").read_text()


def _product_page(catalogue, slug):
    return (catalogue["out"] / "site" / "products" / slug / "index.html").read_text()


def test_overview_has_a_card_per_product(catalogue):
    page = catalogue["page"]
    assert not catalogue["failures"]
    assert page.index('href="products/B4/index.html"') < page.index('href="products/Z9/index.html"')
    assert "Motor mounts" in page and "Plates" in page  # subcategories listed on the cards
    assert 'src="products/B4/motor_mounts/nema17_bracket/part.png"' in page  # thumbnail
    assert "2 products · 2 parts" in page
    assert "three.module.js" not in page  # no viewer on the overview


def test_each_product_has_its_own_page(catalogue):
    b4 = _product_page(catalogue, "B4")
    assert "<title>B4 · neoBotics</title>" in b4
    assert b4.index('id="motor_mounts"') < b4.index('id="motor_mounts--nema17_bracket"')
    assert "Motor mounts" in b4  # the title from category.md
    assert "An L-bracket that holds a NEMA 17 stepper motor" in b4
    assert "NEMA 17 31 mm square pattern" in b4  # the description
    assert "50 × 40 × 50 mm" in b4  # the measured size
    assert "square_plate" not in b4  # another product's part stays on its own page
    z9 = _product_page(catalogue, "Z9")
    assert 'id="plates--square_plate"' in z9
    assert "Plates" in z9  # no category.md: the slug, capitalised


def test_product_pages_link_back(catalogue):
    b4, z9 = _product_page(catalogue, "B4"), _product_page(catalogue, "Z9")
    for page in (b4, z9):
        assert page.count('href="../../index.html"') >= 3  # breadcrumb, sidebar, pager
        assert "All products" in page
    assert 'href="../Z9/index.html"' in b4 and "../B4/index.html" not in b4
    assert 'href="../B4/index.html"' in z9 and "../Z9/index.html" not in z9


def test_every_part_publishes_its_files(catalogue):
    site = catalogue["out"] / "site"
    for product, rest in (("B4", "motor_mounts/nema17_bracket"), ("Z9", "plates/square_plate")):
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
    good = root / "A1" / "plates" / "good"
    bad = root / "A1" / "plates" / "bad"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    (good / "part.py").write_text(PLATE)
    (bad / "part.py").write_text("result = 42\n")
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
    twice = Product("B4", "B4", categories=[Category("mounts", "Mounts", parts=[part, part])])
    with pytest.raises(ValueError, match="unique"):
        build_site([twice], tmp_path / "site")
