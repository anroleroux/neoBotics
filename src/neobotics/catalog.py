"""The product catalogue: ``products/<product>/<subcategory>/<part>/``.

    products/
      B4/
        product.md                 "# B4", then a paragraph or two about it
        motor_mounts/
          category.md              "# Motor mounts", then a short blurb
          nema17_bracket/
            description.md         the natural-language description
            part.py                the CadQuery script (B-rep code)

Every directory name is a slug: it names the URL anchor and the folder the
part's files are published under.  ``product.md`` and ``category.md`` give the
display title (their ``#`` heading) and blurb; without them the slug is the
title.  A part is any directory holding a ``part.py``.  Products, subcategories
and parts appear in alphabetical order of their slugs.

:func:`build_catalog` builds every part with :func:`neobotics.pipeline.run_script`
into ``results/<product>/<subcategory>/<part>/`` and renders the site from them.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .pipeline import run_script
from .site import Category, Product, build_site, read_part


@dataclass
class Entry:
    """One part script in the tree, before it is built."""

    product: str
    category: str
    part: str
    script: Path


def read_heading(path: Path, fallback: str) -> tuple[str, str]:
    """(title, blurb) from a markdown file: its ``#`` heading and the text after it."""
    if not path.exists():
        return fallback, ""
    lines = path.read_text().strip().splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).strip()
    return fallback, "\n".join(lines).strip()


def discover(root: Path) -> list[Entry]:
    """Every ``<product>/<subcategory>/<part>/part.py`` under ``root``, sorted."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"{root}: no such catalogue directory")
    entries = []
    for script in sorted(root.glob("*/*/*/part.py")):
        part_dir = script.parent
        entries.append(Entry(part_dir.parent.parent.name, part_dir.parent.name, part_dir.name,
                             script))
    stray = sorted(set(root.rglob("part.py")) - {e.script for e in entries})
    if stray:
        raise ValueError("part scripts must sit at <product>/<subcategory>/<part>/part.py; "
                         f"found {', '.join(str(p.relative_to(root)) for p in stray)}")
    return entries


def build_catalog(root: Path, results: Path, site_dir: Path,
                  log=print) -> tuple[Path, list[str]]:
    """Build every part under ``root`` and render the site.

    Returns (the index page, the parts that failed to build, as messages).
    Failed parts are left off the page; the caller decides whether that fails
    the run.
    """
    root, results = Path(root), Path(results)
    products: dict[str, Product] = {}
    failures = []
    for entry in discover(root):
        label = f"{entry.product}/{entry.category}/{entry.part}"
        out = results / entry.product / entry.category / entry.part
        result = run_script(entry.script, out)
        if not result.ok:
            failures.append(f"{label}: {result.error}")
            log(f"FAILED {label}: {result.error.strip().splitlines()[-1]}")
            continue
        log(f"built {label}")
        product = products.get(entry.product)
        if product is None:
            title, blurb = read_heading(root / entry.product / "product.md", entry.product)
            product = products[entry.product] = Product(entry.product, title, blurb)
        if not product.categories or product.categories[-1].slug != entry.category:
            title, blurb = read_heading(root / entry.product / entry.category / "category.md",
                                        entry.category.replace("_", " ").capitalize())
            product.categories.append(Category(entry.category, title, blurb))
        product.categories[-1].parts.append(read_part(out, entry.part))
    index = build_site(list(products.values()), site_dir)
    return index, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="neobotics site",
        description="Build every part in a products/ tree and render the catalogue site.",
    )
    parser.add_argument("root", type=Path, nargs="?", default=Path("products"),
                        help="the catalogue: <product>/<subcategory>/<part>/part.py "
                             "(default: products)")
    parser.add_argument("--out", type=Path, default=Path("results"),
                        help="where the parts are built (default: results)")
    parser.add_argument("--site", type=Path, default=Path("site"))
    args = parser.parse_args(argv)
    try:
        index, failures = build_catalog(args.root, args.out, args.site)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"site: {index}")
    if failures:
        print(f"{len(failures)} part(s) failed to build:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
