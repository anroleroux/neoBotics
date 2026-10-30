"""The product catalogue: a product breakdown under ``products/``.

    products/
      PB6/                              a product; the directory name is its designation
        product.md                      "# Title", then a paragraph or two about it
        assembly.py                     optional: the whole product, assembled
        lid/                            a part of the product itself
          description.md                the natural-language description
          part.py                       the CadQuery script (B-rep code)
        chassis/                        an assembly
          assembly.md                   "# Title", then a short blurb
          assembly.py                   optional: its parts placed together
          base/                         a part: any directory holding a part.py
            description.md
            part.py
        drive/                          an assembly with sub-assemblies
          assembly.md
          left_wheel/                   a sub-assembly (a leaf: it holds parts)
            assembly.md
            hub/
              part.py

Next to it, ``library/`` is the parts library: parts and assemblies kept for
reuse in any product, filed by category::

    library/
      battery_holders/                  a category
        category.md                     "# Title", then a short blurb
        keystone_1107_1/                a reusable part: a battery clip
          part.py
        single_18650_holder/            a reusable assembly: a body, its cell and two clips
          assembly.md
          assembly.py
          body/
            part.py
          battery/
            part.py

A category follows a product's rules: it holds parts and assemblies.  Any
script places a library item with ``load_library("battery_holders/single_18650_holder")``
(see :mod:`neobotics.part`); the site lists, on each library item's page,
the products that use it.

A product holds assemblies and parts of its own (``PB6/lid``).  An assembly
holds either sub-assemblies or parts, never both, so the leaves of the
breakdown are assemblies of parts.  The product, and any assembly, may also
hold an ``assembly.py``: its contents placed together as a ``cq.Assembly``
with ``load_part``, built and shown as that level's assembled model.

Every directory name is a slug, and a part's *designation* is the path to it:
``PB6/chassis/base``.  ``product.md`` and ``assembly.md`` give the display
title (their ``#`` heading) and blurb; without them the slug is the title.
Directories starting with ``.`` or ``_`` are ignored, and everything appears
in alphabetical order of its slug.

:func:`build_catalog` builds every part with :func:`neobotics.pipeline.run_script`
into ``results/<designation>/`` and renders the site from them.
"""

from __future__ import annotations

import argparse
import sys
import re
from dataclasses import dataclass
from pathlib import Path

from .part import LIBRARY_DIR
from .pipeline import run_script
from .site import Assembly, Product, build_site, read_part

PART_SCRIPT = "part.py"
ASSEMBLY_SCRIPT = "assembly.py"
#: The two sections of the catalogue, and the file naming each one's top levels.
PRODUCTS, LIBRARY = "products", LIBRARY_DIR
TOP_FILE = {PRODUCTS: "product.md", LIBRARY: "category.md"}
#: A script's use of a library item: ``load_library("battery_holders/single_18650_holder")``.
_USES_LIBRARY = re.compile(r"""load_library\(\s*["']([^"']+)["']""")
#: Where an assembly model is built and published, inside its assembly's
#: directory; the leading underscore keeps it clear of every slug.
ASSEMBLY_DIR = "_assembly"


@dataclass
class Entry:
    """One script in the tree, before it is built: a part, or an assembly's
    ``assembly.py`` (``part`` is None).  In the library, ``product`` is the
    category."""

    product: str
    assemblies: tuple[str, ...]
    part: str | None
    script: Path
    section: str = PRODUCTS

    @property
    def is_assembly(self) -> bool:
        return self.part is None

    @property
    def designation(self) -> str:
        """``PB6/chassis/lid``; in the library, what ``load_library`` takes:
        ``battery_holders/single_18650_holder``."""
        return "/".join([self.product, *self.assemblies, *([self.part] if self.part else [])])

    @property
    def address(self) -> str:
        """The designation with its section, as ``neobotics build`` takes it:
        ``PB6/chassis/lid``, ``library/battery_holders/single_18650_holder``."""
        return self.designation if self.section == PRODUCTS else f"{self.section}/{self.designation}"

    def out_dir(self, results: Path) -> Path:
        """Where this script is built: ``results/<address>`` for a part,
        ``results/<address>/_assembly`` for an assembly model."""
        base = Path(results) if self.section == PRODUCTS else Path(results) / self.section
        base = base.joinpath(self.product, *self.assemblies)
        return base / ASSEMBLY_DIR if self.is_assembly else base / self.part

    def uses(self) -> list[str]:
        """The library items this script places, by designation, in order."""
        return [d.strip("/") for d in _USES_LIBRARY.findall(self.script.read_text())]


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


def discover(root: Path, section: str = PRODUCTS) -> list[Entry]:
    """Every part and assembly script under ``root``, depth first in slug order
    (an assembly's ``assembly.py`` comes before its own parts).

    Raises ValueError for a breakdown that breaks the rules: an assembly
    holding both parts and sub-assemblies, or a part holding directories.  A
    product (or a library category) may hold both: its own parts and its
    assemblies.
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
        if chain and parts and subs:  # the product itself may hold both
            raise ValueError(
                f"{where}: an assembly holds either parts or sub-assemblies, not both "
                f"(parts: {', '.join(p.name for p in parts)}; "
                f"sub-assemblies: {', '.join(s.name for s in subs)})")
        for sub in subs:
            visit(product, chain + (sub.name,), sub)
        if (directory / ASSEMBLY_SCRIPT).is_file():
            entries.append(Entry(product, chain, None, directory / ASSEMBLY_SCRIPT, section))
        for part in parts:
            stray = [c.name for c in _children(part)]  # _-prefixed build output is fine
            if stray:
                raise ValueError(f"{where}/{part.name}: a part holds no directories, "
                                 f"found {', '.join(stray)}")
            entries.append(Entry(product, chain, part.name, part / PART_SCRIPT, section))

    for product in _children(root):
        visit(product.name, (), product)
    return entries


def library_for(root: Path) -> Path:
    """The parts library that goes with a products tree: ``library/`` beside it."""
    return Path(root).parent / LIBRARY_DIR


def discover_all(root: Path, library: Path | None = None) -> list[Entry]:
    """The products under ``root``, then the parts library (if there is one)."""
    library = library_for(root) if library is None else Path(library)
    entries = discover(root)
    if library.is_dir():
        entries += discover(library, LIBRARY)
    return entries


def find(root: Path, designation: str, library: Path | None = None) -> Entry:
    """The part (``PB6/chassis/lid``) or assembly model (``PB6/chassis``) a
    designation names; ``library/...`` names one in the parts library."""
    wanted = designation.strip().strip("/")
    for entry in discover_all(root, library):
        if entry.address == wanted:
            return entry
    raise KeyError(f"no part or assembly model {wanted!r} under {root} or its {LIBRARY_DIR} "
                   f"(a part is a directory with a {PART_SCRIPT}; an assembly model is an "
                   f"{ASSEMBLY_SCRIPT})")


def used_in(entries: list[Entry]) -> dict[str, list[str]]:
    """Library designation -> the addresses of the scripts that place it, in
    catalogue order.  A use names the item's directory, so it counts for the
    item (a part, or an assembly with its model) whatever it holds."""
    users: dict[str, list[str]] = {}
    for entry in entries:
        for item in entry.uses():
            here = users.setdefault(item, [])
            if entry.address not in here:
                here.append(entry.address)
    return users


def _assemble(roots: dict[str, Path], built: list[tuple[Entry, object]],
              users: dict[str, list[str]] | None = None) -> list[Product]:
    """The product (and library category) trees from built parts, with titles
    and blurbs from the markdown files, and each library item's users."""
    users = users or {}
    products: dict[tuple[str, str], Product] = {}
    nodes: dict[tuple[str, ...], Assembly] = {}
    for entry, part in built:
        root = roots[entry.section]
        product = products.get((entry.section, entry.product))
        if product is None:
            title, blurb = read_heading(root / entry.product / TOP_FILE[entry.section],
                                        entry.product.replace("_", " ").capitalize()
                                        if entry.section == LIBRARY else entry.product)
            product = products[entry.section, entry.product] = Product(
                entry.product, title, blurb, section=entry.section,
                used_in=users.get(entry.product, []) if entry.section == LIBRARY else [])
        siblings, node = product.assemblies, product
        for depth in range(1, len(entry.assemblies) + 1):
            key = (entry.section, entry.product, *entry.assemblies[:depth])
            node = nodes.get(key)
            if node is None:
                slug = entry.assemblies[depth - 1]
                title, blurb = read_heading(root.joinpath(*key[1:]) / "assembly.md",
                                            slug.replace("_", " ").capitalize())
                where = "/".join(key[1:])
                node = nodes[key] = Assembly(slug, title, blurb, used_in=users.get(where, [])
                                             if entry.section == LIBRARY else [])
                siblings.append(node)
            siblings = node.assemblies
        if entry.is_assembly:
            node.model = part
        else:
            if entry.section == LIBRARY:
                part.used_in = users.get(entry.designation, [])
            node.parts.append(part)
    return list(products.values())


def build_catalog(root: Path, results: Path, site_dir: Path, log=print,
                  library: Path | None = None) -> tuple[Path, list[str]]:
    """Build every part under ``root``, and in the parts library (``library``,
    by default ``library/`` beside ``root``), and render the site.

    Returns (the index page, the parts that failed to build, as messages).
    Failed parts are left off the site; the caller decides whether that fails
    the run.
    """
    root, results = Path(root), Path(results)
    library = library_for(root) if library is None else Path(library)
    entries = discover_all(root, library)
    built, failures = [], []
    for entry in entries:
        out = entry.out_dir(results)
        result = run_script(entry.script, out)
        if not result.ok:
            failures.append(f"{entry.address}: {result.error}")
            log(f"FAILED {entry.address}: {result.error.strip().splitlines()[-1]}")
            continue
        log(f"built {entry.address}")
        name = entry.part or (entry.assemblies[-1] if entry.assemblies else entry.product)
        built.append((entry, read_part(out, name)))
    trees = _assemble({PRODUCTS: root, LIBRARY: library}, built, used_in(entries))
    index = build_site(trees, site_dir)
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
    parser.add_argument("--library", type=Path, default=None,
                        help="the parts library: <category>/<item>/... "
                             "(default: library/ beside the catalogue)")
    args = parser.parse_args(argv)
    try:
        index, failures = build_catalog(args.root, args.out, args.site, library=args.library)
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
