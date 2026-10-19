"""The product catalogue: a product breakdown under ``products/``.

    products/
      PB4/                              a product; the directory name is its designation
        product.md                      "# Title", then a paragraph or two about it
        chassis/                        an assembly
          assembly.md                   "# Title", then a short blurb
          lid/                          a part: any directory holding a part.py
            description.md              the natural-language description
            part.py                     the CadQuery script (B-rep code)
        drive/                          an assembly with sub-assemblies
          assembly.md
          left_wheel/                   a sub-assembly (a leaf: it holds parts)
            assembly.md
            hub/
              description.md
              part.py

A product holds assemblies; an assembly holds either sub-assemblies or parts,
never both, so the leaves of the breakdown are assemblies of parts.  An
assembly may also hold an ``assembly.py``: its parts (or sub-assemblies)
placed together as a ``cq.Assembly`` with ``load_part`` — the assembled
model, built and shown with the assembly.  Every
directory name is a slug and a part's *designation* is the path to it:
``PB4/chassis/lid``.  ``product.md`` and ``assembly.md`` give the
display title (their ``#`` heading) and blurb; without them the slug is the
title.  Directories starting with ``.`` or ``_`` are ignored, and everything
appears in alphabetical order of its slug.

:func:`build_catalog` builds every part with :func:`neobotics.pipeline.run_script`
into ``results/<designation>/`` and renders the site from them.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .pipeline import run_script
from .site import Assembly, Product, build_site, read_part

PART_SCRIPT = "part.py"
ASSEMBLY_SCRIPT = "assembly.py"
#: Where an assembly model is built and published, inside its assembly's
#: directory; the leading underscore keeps it clear of every slug.
ASSEMBLY_DIR = "_assembly"


@dataclass
class Entry:
    """One script in the tree, before it is built: a part, or an assembly's
    ``assembly.py`` (``part`` is None)."""

    product: str
    assemblies: tuple[str, ...]
    part: str | None
    script: Path

    @property
    def is_assembly(self) -> bool:
        return self.part is None

    @property
    def designation(self) -> str:
        return "/".join([self.product, *self.assemblies, *([self.part] if self.part else [])])

    def out_dir(self, results: Path) -> Path:
        """Where this script is built: ``results/<designation>`` for a part,
        ``results/<designation>/_assembly`` for an assembly model."""
        base = Path(results).joinpath(self.product, *self.assemblies)
        return base / ASSEMBLY_DIR if self.is_assembly else base / self.part


def read_heading(path: Path, fallback: str) -> tuple[str, str]:
    """(title, blurb) from a markdown file: its ``#`` heading and the text after it."""
    if not path.exists():
        return fallback, ""
    lines = path.read_text().strip().splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).strip()
    return fallback, "\n".join(lines).strip()


def _children(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_")))


def _is_part(directory: Path) -> bool:
    return (directory / PART_SCRIPT).is_file()


def discover(root: Path) -> list[Entry]:
    """Every part and assembly script under ``root``, depth first in slug order
    (an assembly's ``assembly.py`` comes before its own parts).

    Raises ValueError for a breakdown that breaks the rules: a part directly
    under a product, or an assembly holding both parts and sub-assemblies.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"{root}: no such catalogue directory")
    entries: list[Entry] = []

    def visit(product: str, chain: tuple[str, ...], directory: Path) -> None:
        children = _children(directory)
        parts = [c for c in children if _is_part(c)]
        subs = [c for c in children if not _is_part(c)]
        where = "/".join([product, *chain])
        if parts and subs:
            raise ValueError(
                f"{where}: an assembly holds either parts or sub-assemblies, not both "
                f"(parts: {', '.join(p.name for p in parts)}; "
                f"sub-assemblies: {', '.join(s.name for s in subs)})")
        for sub in subs:
            visit(product, chain + (sub.name,), sub)
        if (directory / ASSEMBLY_SCRIPT).is_file():
            entries.append(Entry(product, chain, None, directory / ASSEMBLY_SCRIPT))
        for part in parts:
            stray = [c.name for c in _children(part)]  # _-prefixed build output is fine
            if stray:
                raise ValueError(f"{where}/{part.name}: a part holds no directories, "
                                 f"found {', '.join(stray)}")
            entries.append(Entry(product, chain, part.name, part / PART_SCRIPT))

    for product in _children(root):
        for top in _children(product):
            if _is_part(top):
                raise ValueError(f"{product.name}/{top.name}: a part must sit inside an "
                                 "assembly, not directly under the product")
            visit(product.name, (top.name,), top)
    return entries


def find(root: Path, designation: str) -> Entry:
    """The part (``PB4/chassis/lid``) or assembly model (``PB4/chassis``) a
    designation names."""
    wanted = designation.strip().strip("/")
    for entry in discover(root):
        if entry.designation == wanted:
            return entry
    raise KeyError(f"no part or assembly model {wanted!r} under {root} (a part is a directory "
                   f"with a {PART_SCRIPT}; an assembly model is an {ASSEMBLY_SCRIPT})")


def _assemble(root: Path, built: list[tuple[Entry, object]]) -> list[Product]:
    """The product tree from built parts, with titles and blurbs from the markdown files."""
    products: dict[str, Product] = {}
    nodes: dict[tuple[str, ...], Assembly] = {}
    for entry, part in built:
        product = products.get(entry.product)
        if product is None:
            title, blurb = read_heading(root / entry.product / "product.md", entry.product)
            product = products[entry.product] = Product(entry.product, title, blurb)
        siblings, node = product.assemblies, None
        for depth in range(1, len(entry.assemblies) + 1):
            key = (entry.product, *entry.assemblies[:depth])
            node = nodes.get(key)
            if node is None:
                slug = entry.assemblies[depth - 1]
                title, blurb = read_heading(root.joinpath(*key) / "assembly.md",
                                            slug.replace("_", " ").capitalize())
                node = nodes[key] = Assembly(slug, title, blurb)
                siblings.append(node)
            siblings = node.assemblies
        if entry.is_assembly:
            node.model = part
        else:
            node.parts.append(part)
    return list(products.values())


def build_catalog(root: Path, results: Path, site_dir: Path,
                  log=print) -> tuple[Path, list[str]]:
    """Build every part under ``root`` and render the site.

    Returns (the index page, the parts that failed to build, as messages).
    Failed parts are left off the site; the caller decides whether that fails
    the run.
    """
    root, results = Path(root), Path(results)
    built, failures = [], []
    for entry in discover(root):
        out = entry.out_dir(results)
        result = run_script(entry.script, out)
        if not result.ok:
            failures.append(f"{entry.designation}: {result.error}")
            log(f"FAILED {entry.designation}: {result.error.strip().splitlines()[-1]}")
            continue
        log(f"built {entry.designation}")
        built.append((entry, read_part(out, entry.part or entry.assemblies[-1])))
    index = build_site(_assemble(root, built), site_dir)
    return index, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="neobotics site",
        description="Build every part in a products/ tree and render the catalogue site.",
    )
    parser.add_argument("root", type=Path, nargs="?", default=Path("products"),
                        help="the catalogue: <product>/<assembly>/.../<part>/part.py "
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
