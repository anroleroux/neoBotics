"""The static site: built run directories in, a page with every part out."""

from __future__ import annotations

from pathlib import Path

import pytest

from neobotics.pipeline import run_script
from neobotics.site import DOWNLOADS, build_site, read_part

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "motor_mount" / "part.py"


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("runs") / "motor_mount"
    assert run_script(EXAMPLE, out).ok
    return out


def test_cad_run_keeps_the_description_next_to_the_script(run_dir):
    assert (run_dir / "description.md").read_text() == (EXAMPLE.parent / "description.md").read_text()
    assert (run_dir / "part.py").read_text() == EXAMPLE.read_text()


def test_site_has_the_part_its_files_and_the_viewer(run_dir, tmp_path):
    part = read_part(run_dir)
    assert part.title == "An L-bracket that holds a NEMA 17 stepper motor"
    index = build_site([part], tmp_path / "site")
    page = index.read_text()
    assert 'id="motor_mount"' in page
    assert 'data-stl="parts/motor_mount/part.stl"' in page
    assert "three@0.160.0" in page
    assert "NEMA 17 31 mm square pattern" in page  # the description
    assert "50 × 40 × 50 mm" in page  # the measured size
    assert "regions = {" in page  # the script, escaped into the page
    for filename, *_ in DOWNLOADS:
        assert (tmp_path / "site" / "parts" / "motor_mount" / filename).exists()
        assert f'href="parts/motor_mount/{filename}"' in page
    assert (tmp_path / "site" / ".nojekyll").exists()


def test_site_escapes_what_it_shows(run_dir, tmp_path):
    part = read_part(run_dir)
    part.description = "<script>alert(1)</script> & more"
    page = build_site([part], tmp_path / "site").read_text()
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in page


def test_site_refuses_unbuilt_runs_and_duplicate_names(run_dir, tmp_path):
    with pytest.raises(FileNotFoundError):
        read_part(tmp_path)
    part = read_part(run_dir)
    with pytest.raises(ValueError, match="unique"):
        build_site([part, part], tmp_path / "site")
