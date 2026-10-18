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


def test_page_groups_parts_by_product_and_subcategory(catalogue):
    page = catalogue["page"]
    assert not catalogue["failures"]
    # products in order, each with its subcategories and parts
    assert page.index('id="B4"') < page.index('id="B4--motor_mounts"') \
        < page.index('id="B4--motor_mounts--nema17_bracket"') < page.index('id="Z9"') \
        < page.index('id="Z9--plates"') < page.index('id="Z9--plates--square_plate"')
    assert "Motor mounts" in page  # the title from category.md
    assert "Plates" in page  # no category.md: the slug, capitalised
    assert "An L-bracket that holds a NEMA 17 stepper motor" in page
    assert "NEMA 17 31 mm square pattern" in page  # the description
    assert "50 × 40 × 50 mm" in page  # the measured size
    assert 'href="#B4--motor_mounts"' in page  # the subcategory card and the tree


def test_every_part_publishes_its_files(catalogue):
    page = catalogue["page"]
    site = catalogue["out"] / "site"
    for path in ("B4/motor_mounts/nema17_bracket", "Z9/plates/square_plate"):
        assert f'data-stl="parts/{path}/part.stl"' in page
        for filename, *_ in DOWNLOADS:
            assert (site / "parts" / path / filename).exists()
            assert f'href="parts/{path}/{filename}"' in page
    assert (site / ".nojekyll").exists()


def test_page_escapes_titles_and_blurbs(catalogue):
    page = catalogue["page"]
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
    page = index.read_text()
    assert 'id="A1--plates--good"' in page and "A1--plates--bad" not in page


def test_site_refuses_empty_catalogues_and_duplicate_slugs(tmp_path):
    run = tmp_path / "run"
    assert run_script(BRACKET / "part.py", run).ok
    part = read_part(run, "bracket")
    with pytest.raises(ValueError, match="no parts"):
        build_site([Product("B4", "B4")], tmp_path / "site")
    twice = Product("B4", "B4", categories=[Category("mounts", "Mounts", parts=[part, part])])
    with pytest.raises(ValueError, match="unique"):
        build_site([twice], tmp_path / "site")
