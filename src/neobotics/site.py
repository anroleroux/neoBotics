"""A static HTML catalogue of built parts, for GitHub Pages: ``neobotics site``.

A downstream consumer like :mod:`neobotics.cadview`: it reads run directories
(``description.md``, ``part.py``, ``cad/``) and never runs a script.  Parts are
organised as a product breakdown — product -> assembly -> sub-assembly ... ->
part, with parts allowed on the product itself; :mod:`neobotics.catalog`
reads that tree from ``products/``.

The site is one page per level, and each page shows only what is in it:

    site/
      index.html                                    every product, as a card
      products/<product>/index.html                 the product: its assembled model,
                                                    then a card per assembly and part in it
      products/<product>/<assembly>/index.html      an assembly: the same, one level down
      products/<product>/.../_assembly/             an assembled model's files
      products/<product>/.../<part>/index.html      a part: 3D view, description,
                                                    measurements, downloads, script

Cards drill down a level; a breadcrumb on every page leads back up, and all
links are relative, so the site works from any base URL — a GitHub Pages
project path or a local folder.  3D views use three.js, loaded from a CDN,
with the shaded PNGs as the fallback.
"""

from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

#: three.js, pinned; the page loads it as an ES module through an import map.
THREE_VERSION = "0.160.0"
_THREE = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}"

#: CAD files copied next to the page, and how the download list labels them;
#: the script (part.py or assembly.py) is listed after them.
DOWNLOADS = [
    ("part.step", "STEP", "for other CAD tools"),
    ("part.stl", "STL", "for slicers and renderers"),
    ("part.brep", "BREP", "the exact OpenCascade shape"),
]
SCRIPT_NOTE = "the CadQuery script (B-rep code)"
#: Where an assembly's model is published, inside its directory (catalog.ASSEMBLY_DIR).
ASSEMBLY_DIR = "_assembly"
IMAGES = ["part.png", "part_rear_below.png"]


@dataclass
class Part:
    """One built part, read from a run directory."""

    name: str
    title: str
    description: str
    script: str
    summary: dict
    cad_dir: Path
    script_name: str = "part.py"


@dataclass
class Assembly:
    """An assembly: either sub-assemblies or (a leaf) parts, in order, and
    optionally its assembled model."""

    slug: str
    title: str
    blurb: str = ""
    assemblies: list["Assembly"] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    model: Part | None = None  # the assembled model, from assembly.py

    @property
    def n_parts(self) -> int:
        return len(self.parts) + sum(a.n_parts for a in self.assemblies)


@dataclass
class Product(Assembly):
    """A product: the top of the breakdown.  Like an assembly, but it may hold
    assemblies and parts of its own side by side."""

    def chains(self) -> Iterator[tuple[Assembly, ...]]:
        """Every assembly, as the chain from the top-level one down to it."""
        def visit(chain):
            yield chain
            for sub in chain[-1].assemblies:
                yield from visit(chain + (sub,))
        for top in self.assemblies:
            yield from visit((top,))

    def nodes(self) -> Iterator[tuple[Assembly, ...]]:
        """The product (as the empty chain) and every assembly below it."""
        yield ()
        yield from self.chains()

    def walk(self) -> Iterator[tuple[tuple[Assembly, ...], Part]]:
        """Every part with the chain of assemblies above it (empty for the
        product's own parts), depth first."""
        for chain in self.nodes():
            for part in self.node(chain).parts:
                yield chain, part

    def node(self, chain: tuple[Assembly, ...]) -> Assembly:
        return chain[-1] if chain else self


def read_part(run_dir: Path, name: str | None = None) -> Part:
    """A part from a run directory: ``cad/`` from ``neobotics cad`` or ``generate``.

    The description is ``description.md`` in the run directory, or next to the
    script the run was built from; it may be missing.
    """
    run_dir = Path(run_dir)
    cad = run_dir / "cad"
    summary_path = cad / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"{run_dir}: no cad/summary.json; build the part first")
    summary = json.loads(summary_path.read_text())
    script_name = summary.get("script", "part.py")
    script = (cad / script_name).read_text()
    description_path = run_dir / "description.md"
    description = description_path.read_text().strip() if description_path.exists() else ""
    name = name or run_dir.name
    return Part(name, _title(script, name), description, script, summary, cad, script_name)


def _published(part: Part) -> list[str]:
    components = [c["stl"] for c in part.summary.get("components", []) if c.get("stl")]
    return [f for f, *_ in DOWNLOADS] + [part.script_name] + IMAGES + components


def _title(script: str, fallback: str) -> str:
    """The first line of the script's docstring, without its full stop."""
    for quote in ('"""', "'''"):
        start = script.find(quote)
        end = script.find(quote, start + 3) if start != -1 else -1
        if end != -1:
            first = script[start + 3:end].strip().splitlines()
            if first:
                return first[0].strip().rstrip(".")
    return fallback.replace("_", " ")


def designation(product: Product, chain: tuple[Assembly, ...], part: Part | None = None) -> str:
    """``PRODUCT/assembly/.../part``: how a part (or assembly) is named and addressed."""
    return "/".join([product.slug, *(a.slug for a in chain), *([part.name] if part else [])])


def product_dir(product: Product) -> str:
    """Where a product's page lives, relative to the site root; everything in
    it sits below, one directory per level."""
    return f"products/{product.slug}"


def node_dir(product: Product, chain: tuple[Assembly, ...]) -> Path:
    return Path(product_dir(product), *(a.slug for a in chain))


def _check_unique(products: list[Product]) -> None:
    def check(kind, slugs):
        if len(set(slugs)) != len(slugs):
            raise ValueError(f"{kind} names must be unique, got {slugs}")

    check("product", [p.slug for p in products])
    for p in products:
        for chain in p.nodes():
            node = p.node(chain)
            check(f"part or assembly in {designation(p, chain)}",
                  [a.slug for a in node.assemblies] + [x.name for x in node.parts])


def build_site(products: list[Product], site_dir: Path) -> Path:
    """Write the overview, a page per product, assembly and part, and every
    part's and assembled model's files."""
    site_dir = Path(site_dir)
    products = [p for p in products if p.n_parts or p.model]
    if not products:
        raise ValueError("no parts to publish")
    _check_unique(products)
    for product in products:
        for chain in product.nodes():
            node, here = product.node(chain), site_dir / node_dir(product, chain)
            here.mkdir(parents=True, exist_ok=True)
            if node.model:
                _copy(node.model, here / ASSEMBLY_DIR)
            (here / "index.html").write_text(render_node(product, chain))
            for part in node.parts:
                _copy(part, here / part.name)
                (here / part.name / "index.html").write_text(render_part(product, chain, part))
    index = site_dir / "index.html"
    index.write_text(render_overview(products))
    (site_dir / ".nojekyll").write_text("")
    return index


def _copy(part: Part, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for filename in _published(part):
        shutil.copyfile(part.cad_dir / filename, target / filename)


# --------------------------------------------------------------------------
# HTML pieces
# --------------------------------------------------------------------------
def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    return "".join(f"<p>{_e(' '.join(b.split()))}</p>" for b in blocks)


def _num(value: float) -> str:
    return f"{value:,.1f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _size(summary: dict) -> str:
    return " × ".join(_num(v) for v in summary["bounding_box"]["size"]) + " mm"


def _summary_rows(summary: dict) -> str:
    faces = ", ".join(f"{n} {k.lower()}" for k, n in summary["face_types"].items())
    regions = summary.get("regions") or {}
    rows = [
        ("Size (x × y × z)", _size(summary)),
        ("Volume", f"{_num(summary['volume_mm3'])} mm³"),
        ("Surface area", f"{_num(summary['surface_area_mm2'])} mm²"),
        ("Solids", str(summary["n_solids"])),
        ("Faces", f"{summary['n_faces']} ({faces})"),
        ("Regions", ", ".join(regions) if regions else "none"),
    ]
    return "".join(f"<tr><th scope=row>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows)


def _components_table(summary: dict) -> str:
    """An assembled model's components and whether any of them overlap."""
    rows = "".join(
        f"<tr><th scope=row>{_e(c['name'])}</th><td>{_num(c['volume_mm3'])} mm³</td></tr>"
        for c in summary.get("components", [])
    )
    clashes = summary.get("interference", [])
    if clashes:
        status = "".join(f"<li class=clash>{_e(c['a'])} and {_e(c['b'])} overlap by "
                         f"{_num(c['volume_mm3'])} mm³</li>" for c in clashes)
    else:
        status = "<li class=fit>No interference: no two components share volume.</li>"
    contacts = summary.get("contacts", [])
    status += "".join(f"<li class=touch>{_e(c['a'])} and {_e(c['b'])} touch over "
                      f"{_num(c['area_mm2'])} mm²</li>" for c in contacts)
    verdict = (_plural(len(clashes), "interference", "interferences") if clashes
               else "no interference")
    line = (f"{_plural(len(summary.get('components', [])), 'component')} · {verdict} · "
            f"{_plural(len(contacts), 'contact')}")
    return (f'<details class="fit-details{" clashing" if clashes else ""}"{" open" if clashes else ""}>'
            f"<summary><h4>Components and fit</h4><span class=fit-line>{_e(line)}</span></summary>"
            f"<table>{rows}</table><ul class=fit-list>{status}</ul></details>")


def _detail(part: Part, base: str, *, model: bool = False) -> str:
    """The 3D view, facts, downloads and script of a part or an assembled model;
    ``base`` is where its files are, relative to the page."""
    prefix = f"{base}/" if base else ""
    downloads = "".join(
        f'<li><a href="{prefix}{f}" download><span class=fmt>{_e(label)}</span>'
        f"<span class=note>{_e(note)}</span></a></li>"
        for f, label, note in [*DOWNLOADS, (part.script_name, part.script_name, SCRIPT_NOTE)]
    )
    parts = [c for c in part.summary.get("components", []) if c.get("stl")] if model else []
    stl = " ".join(f"{prefix}{c['stl']}" for c in parts) or f"{prefix}part.stl"
    # an assembled model's components, for the viewer's colours and its show/see-through controls
    names = f' data-names="{_e(" ".join(c["name"] for c in parts))}"' if parts else ""
    colors = (f' data-colors="{_e(" ".join(c["color"] for c in parts))}"'
              if parts and all(c.get("color") for c in parts) else "")
    description = (
        f"<div class=description><h4>Description</h4>{_paragraphs(part.description)}</div>"
        if part.description else ""
    )
    extra = _components_table(part.summary) if model else ""
    return f"""
<section class="part{' model' if model else ''}">
  <div class=part-grid>
    <figure class=viewer data-stl="{_e(stl)}"{names}{colors}>
      <img src="{prefix}part.png" alt="Shaded view of {_e(part.title)}" class=fallback>
      <figcaption>Drag to orbit · scroll to zoom · <button type=button class=reset>reset view</button></figcaption>
    </figure>
    <div class=facts>
      {description}
      <h4>Measured from the B-rep</h4>
      <table>{_summary_rows(part.summary)}</table>
      {extra}
      <h4>Downloads</h4>
      <ul class=downloads>{downloads}</ul>
    </div>
  </div>
  <details class=views>
    <summary>Static views</summary>
    <div class=view-pair>
      <img src="{prefix}part.png" alt="From the front, right and above" loading=lazy>
      <img src="{prefix}part_rear_below.png" alt="From the rear, left and below" loading=lazy>
    </div>
  </details>
  <details class=code>
    <summary>CadQuery script <span class=muted>{_e(part.script_name)}</span></summary>
    <pre><code>{_e(part.script)}</code></pre>
  </details>
</section>"""


def _thumb(node: Assembly) -> str:
    """A picture for a node, relative to its own directory: its assembled model,
    else its first part, else the first picture further down."""
    if node.model:
        return f"{ASSEMBLY_DIR}/part.png"
    if node.parts:
        return f"{node.parts[0].name}/part.png"
    for sub in node.assemblies:
        if sub.n_parts or sub.model:
            return f"{sub.slug}/{_thumb(sub)}"
    return ""


def _counts(node: Assembly) -> str:
    bits = []
    if node.assemblies:
        bits.append(_plural(len(node.assemblies), "assembly", "assemblies"))
    if node.parts:
        bits.append(_plural(len(node.parts), "part"))
    return " · ".join(bits) or "empty"


def _card(href: str, thumb: str, kind: str, title: str, slug: str, meta: str) -> str:
    image = f'<img src="{_e(thumb)}" alt="" loading=lazy>' if thumb else ""
    return f"""
<li class=item-card>
  <a href="{_e(href)}">
    <span class=thumb>{image}</span>
    <span class=card-body>
      <span class=kind>{_e(kind)}</span>
      <span class=item-name>{_e(title)}</span>
      <code class=slug>{_e(slug)}</code>
      <span class=count>{_e(meta)}</span>
    </span>
  </a>
</li>"""


def _contents(product: Product, chain: tuple[Assembly, ...]) -> str:
    """Cards for what one level holds: its assemblies, then its parts."""
    node = product.node(chain)
    kind = "Sub-assembly" if chain else "Assembly"
    cards = [
        _card(f"{a.slug}/index.html", f"{a.slug}/{_thumb(a)}" if _thumb(a) else "", kind,
              a.title, designation(product, chain + (a,)), _counts(a))
        for a in node.assemblies
    ] + [
        _card(f"{p.name}/index.html", f"{p.name}/part.png", "Part", p.title,
              designation(product, chain, p), _size(p.summary))
        for p in node.parts
    ]
    if not cards:
        return ""
    return (f'<section class=contents><h2>Contents <span class=count>{_counts(node)}</span></h2>'
            f'<ul class=item-grid>{"".join(cards)}</ul></section>')


def _breadcrumb(product: Product, chain: tuple[Assembly, ...], root: str,
                current: str | None) -> str:
    """neoBotics products › PB4 › Chassis › … — every level a link but the page itself."""
    levels = [("neoBotics products", f"{root}index.html"),
              (product.title, f"{root}{product_dir(product)}/index.html")]
    for depth, a in enumerate(chain, start=1):
        path = node_dir(product, chain[:depth]).as_posix()
        levels.append((a.title, f"{root}{path}/index.html"))
    if current is None:  # the last level is this page
        *links, (here, _) = levels
    else:
        links, here = levels, current
    items = "".join(f'<li><a href="{_e(href)}">{_e(title)}</a></li>' for title, href in links)
    return (f"<nav class=crumbs-bar aria-label=Breadcrumb><ol>{items}"
            f"<li aria-current=page>{_e(here)}</li></ol></nav>")


def _up(title: str, href: str) -> str:
    return f'<p class=up-link><a class=back href="{_e(href)}">← Back to {_e(title)}</a></p>'


_ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
         "%3Cpath d='M2 14V2h4v8h8v4z' fill='%232f6fb1'/%3E%3C/svg%3E")


def _page(title: str, description: str, body: str, *, viewer: bool) -> str:
    """A whole page: shared head, ``body``, footer; ``viewer`` loads three.js and the viewer script."""
    head_extra = ""
    script = ""
    if viewer:
        head_extra = (f'<script type=importmap>\n{{"imports": {{"three": "{_THREE}/build/three.module.js", '
                      f'"three/addons/": "{_THREE}/examples/jsm/"}}}}\n</script>')
        script = f"<script type=module>{_JS}</script>"
    return f"""<!doctype html>
<html lang=en>
<head>
<meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<meta name=description content="{_e(description)}">
<link rel=icon href="{_ICON}">
<style>{_CSS}</style>
{head_extra}
</head>
<body>
{body}
<footer class=wrap><p class=muted>Built by <code>neobotics site</code> from
<a href="https://github.com/anroleroux/neoBotics">anroleroux/neoBotics</a>. Units are millimetres; z is up.</p></footer>
{script}
</body>
</html>
"""


def _root(product: Product, chain: tuple[Assembly, ...], extra: int = 0) -> str:
    """The relative path from a page up to the site root."""
    return "../" * (2 + len(chain) + extra)


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
def render_node(product: Product, chain: tuple[Assembly, ...] = ()) -> str:
    """A product's or an assembly's page: its assembled model, then its contents."""
    node = product.node(chain)
    root = _root(product, chain)
    if chain:
        kind = "Assembly" if len(chain) == 1 else "Sub-assembly"
        parent_title = product.node(chain[:-1]).title
    else:
        kind, parent_title = "Product", "all products"
    model = ""
    if node.model:
        model = (f'<h2 class=section-title>Assembled model '
                 f'<span class=muted>{_e(node.model.title)}</span></h2>'
                 + _detail(node.model, ASSEMBLY_DIR, model=True))
    blurb = _paragraphs(node.blurb) if node.blurb else ""
    body = f"""<header class="site-head compact">
  <div class=wrap>
    {_breadcrumb(product, chain, root, None)}
    <p class=eyebrow>{kind} <code>{_e(designation(product, chain))}</code></p>
    <h1 class=product-title>{_e(node.title)}</h1>
    <p class=count>{_counts(node)}{' · assembled model' if node.model else ''}</p>
    {blurb}
  </div>
</header>
<main class=wrap>
  {_contents(product, chain)}
  {model}
  {_up(parent_title, '../index.html')}
</main>"""
    return _page(f"{node.title} · neoBotics", f"{node.title}: its assembled model and contents, "
                 "built as CadQuery B-rep code.", body, viewer=bool(node.model))


def render_part(product: Product, chain: tuple[Assembly, ...], part: Part) -> str:
    """A part's own page: everything about it."""
    root = _root(product, chain, extra=1)
    parent = product.node(chain)
    body = f"""<header class="site-head compact">
  <div class=wrap>
    {_breadcrumb(product, chain, root, part.title)}
    <p class=eyebrow>Part <code>{_e(designation(product, chain, part))}</code></p>
    <h1 class=product-title>{_e(part.title)}</h1>
    <p class=count>{_e(_size(part.summary))}</p>
  </div>
</header>
<main class=wrap>
  {_detail(part, "")}
  {_up(parent.title, '../index.html')}
</main>"""
    return _page(f"{part.title} · neoBotics", f"{part.title}: built as CadQuery B-rep code.",
                 body, viewer=True)


def _product_card(product: Product) -> str:
    thumb = _thumb(product)
    return _card(f"{product_dir(product)}/index.html",
                 f"{product_dir(product)}/{thumb}" if thumb else "", "Product",
                 product.title, product.slug, _counts(product))


def render_overview(products: list[Product]) -> str:
    """The landing page: what the pipeline does, then a card per product."""
    cards = "".join(_product_card(p) for p in products)
    n_parts = sum(p.n_parts for p in products)
    body = f"""<header class=site-head>
  <div class=wrap>
    <h1>neoBotics</h1>
    <p class=lede>Parts described in plain language, written as CadQuery B-rep code, built and checked as exact solids.</p>
    <ol class=flow>
      <li><span>Description</span><small>natural language</small></li>
      <li><span>part.py</span><small>CadQuery B-rep code</small></li>
      <li><span>Solid</span><small>checked: valid, closed, with volume</small></li>
      <li><span>STEP · STL · BREP</span><small>and shaded views</small></li>
    </ol>
  </div>
</header>
<main class=wrap>
  <section class=contents>
    <h2>Products <span class=count>{_plural(len(products), 'product')} · {_plural(n_parts, 'part')}</span></h2>
    <ul class=item-grid>{cards}</ul>
  </section>
</main>"""
    return _page("neoBotics products", "Products, their assemblies and parts, built from "
                 "natural-language descriptions as CadQuery B-rep code.", body, viewer=False)


_CSS = """
:root{--bg:#f6f7f9;--panel:#fff;--ink:#1b2430;--muted:#5d6876;--line:#dde2e8;--accent:#2f6fb1;
--code-bg:#f0f2f5;--viewer:#eef1f5;--part:#5b8fc7;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0f1318;--panel:#171c23;--ink:#e3e8ee;--muted:#98a3b0;
--line:#2a313b;--accent:#7fb0e6;--code-bg:#11161c;--viewer:#1b222b;--part:#6f9fd4;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
a{color:var(--accent)}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88em}
.muted{color:var(--muted)}
.site-head{border-bottom:1px solid var(--line);background:var(--panel);padding:28px 0 18px}
h1{margin:0;font-size:1.9rem;letter-spacing:-.01em}
.lede{margin:.3rem 0 1.1rem;color:var(--muted);max-width:60ch}
.flow{list-style:none;display:flex;flex-wrap:wrap;gap:8px;padding:0;margin:0 0 14px}
.flow li{display:flex;flex-direction:column;padding:8px 12px;border:1px solid var(--line);border-radius:8px;
background:var(--bg);min-width:150px;position:relative}
.flow li span{font-weight:600}.flow small{color:var(--muted)}
.parts-nav{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.95rem}
.part{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin:24px 0;padding:20px}
.part-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin-bottom:12px}
.part-head h2{margin:0;font-size:1.35rem}
.slug{color:var(--muted)}
.part-grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:20px}
@media (max-width:820px){.part-grid{grid-template-columns:1fr}}
.viewer{margin:0;align-self:start;background:var(--viewer);border-radius:10px;overflow:hidden;position:relative;
aspect-ratio:4/3;display:flex;flex-direction:column}
.viewer canvas{display:block;width:100%;flex:1;min-height:0;touch-action:none;cursor:grab}
.viewer canvas:active{cursor:grabbing}
.viewer .fallback{width:100%;flex:1;min-height:0;object-fit:contain}
.viewer.live .fallback{display:none}
.viewer figcaption{font-size:.8rem;color:var(--muted);padding:6px 10px;border-top:1px solid var(--line)}
.viewer button{font:inherit;color:var(--accent);background:none;border:0;padding:0;cursor:pointer;text-decoration:underline}
.viewer .layers{display:flex;flex-wrap:wrap;gap:4px 6px;padding:6px 10px;border-top:1px solid var(--line);
font-size:.8rem;max-height:30%;overflow:auto}
.viewer .layer{display:inline-flex;align-items:center;gap:5px;padding:2px 4px 2px 6px;border:1px solid var(--line);
border-radius:6px}
.viewer .layer label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.viewer .layer input{margin:0}
.viewer .swatch{width:10px;height:10px;border-radius:2px;flex:none}
.viewer .layer.hidden label{color:var(--muted);text-decoration:line-through}
.viewer .layer .ghost{text-decoration:none;padding:0 3px;border-radius:4px;color:var(--muted)}
.viewer .layer .ghost[aria-pressed=true]{color:var(--accent);background:var(--code-bg)}
.facts h3,.description h3{font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 6px}
.description{margin-bottom:16px}.description p{margin:0 0 .6em}
table{border-collapse:collapse;width:100%;margin-bottom:16px;font-size:.92rem}
th,td{text-align:left;padding:5px 0;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:500;color:var(--muted);width:42%;padding-right:12px}
td{font-variant-numeric:tabular-nums}
.downloads{list-style:none;padding:0;margin:0;display:grid;gap:6px}
.downloads a{display:flex;gap:10px;align-items:baseline;padding:7px 10px;border:1px solid var(--line);
border-radius:8px;text-decoration:none;color:var(--ink)}
.downloads a:hover{border-color:var(--accent)}
.fmt{font-weight:600;flex:0 0 6.6em;color:var(--accent);overflow-wrap:anywhere}.note{color:var(--muted);font-size:.88rem}
details{margin-top:14px;border-top:1px solid var(--line);padding-top:10px}
summary{cursor:pointer;font-weight:500}
.view-pair{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}
.view-pair img{width:100%;background:var(--viewer);border-radius:8px}
@media (max-width:600px){.view-pair{grid-template-columns:1fr}}
pre{background:var(--code-bg);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto;
margin:10px 0 0;line-height:1.45}
footer{padding:8px 16px 32px;font-size:.88rem}
.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:28px;align-items:start}
@media (max-width:900px){.layout{grid-template-columns:1fr;gap:0}}
.tree{position:sticky;top:16px;margin-top:24px;font-size:.92rem;max-height:calc(100vh - 32px);overflow-y:auto}
@media (max-width:900px){.tree{position:static;max-height:none;margin-top:20px}}
.tree ul{list-style:none;margin:0;padding:0}
.tree ul ul{padding-left:12px;border-left:1px solid var(--line);margin:4px 0 8px 4px}
.tree li{margin:3px 0}
.tree a{color:var(--ink);text-decoration:none}
.tree a:hover{color:var(--accent);text-decoration:underline}
.tree ul ul ul a{color:var(--muted)}
.nav-product{font-weight:600}
.eyebrow{margin:0 0 4px;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}
.product{margin:24px 0 40px}
.product-head{padding:4px 0 6px}
.product-title{margin:0;font-size:2rem;letter-spacing:-.01em}
.product-head p{max-width:65ch}
.count{color:var(--muted);font-size:.88rem}
.product-head>.count{margin:2px 0 8px}
.cards{list-style:none;padding:0;margin:14px 0 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.cards a{display:flex;flex-direction:column;gap:2px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;
background:var(--panel);text-decoration:none;color:var(--ink)}
.cards a:hover{border-color:var(--accent)}
.card-title{font-weight:600}
.site-head.compact{padding:18px 0 22px}
.site-head .product-title{font-size:2.1rem}
.site-head .count{margin:2px 0 10px}
.site-head p{max-width:65ch}
.crumbs-bar ol{list-style:none;display:flex;flex-wrap:wrap;gap:4px;padding:0;margin:0 0 14px;font-size:.9rem}
.crumbs-bar li+li::before{content:"›";margin-right:4px;color:var(--muted)}
.crumbs-bar [aria-current]{color:var(--muted)}
.back{display:inline-block;margin-bottom:14px;font-weight:500;text-decoration:none}
.back:hover{text-decoration:underline}
.pager{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;margin:36px 0 8px;border-top:1px solid var(--line);padding-top:18px}
.pager a{display:flex;flex-direction:column;gap:2px;padding:10px 14px;border:1px solid var(--line);border-radius:10px;
background:var(--panel);text-decoration:none;color:var(--ink)}
.pager a:hover{border-color:var(--accent)}
.pager small{color:var(--muted);font-size:.78rem}
.pager .up{text-align:center}.pager .next{text-align:right}
@media (max-width:600px){.pager{grid-template-columns:1fr}.pager .next,.pager .up{text-align:left}}
.overview-head{display:flex;align-items:baseline;gap:12px;margin:28px 0 14px}
.overview-head h2{margin:0;font-size:1.4rem}
.product-grid{list-style:none;padding:0;margin:0 0 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.product-card a{display:flex;flex-direction:column;height:100%;border:1px solid var(--line);border-radius:12px;
overflow:hidden;background:var(--panel);text-decoration:none;color:var(--ink)}
.product-card a:hover{border-color:var(--accent)}
.product-card a:hover .open{text-decoration:underline}
.thumb{display:block;position:relative;background:var(--viewer);aspect-ratio:16/10;overflow:hidden}
.thumb img{position:absolute;inset:6%;width:88%;height:88%;object-fit:contain}
.card-body{display:flex;flex-direction:column;gap:4px;padding:14px 16px 16px;flex:1}
.product-name{font-size:1.35rem;font-weight:700}
.card-blurb p{margin:4px 0;color:var(--muted);font-size:.93rem}
.card-cats{list-style:none;padding:0;margin:6px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.card-cats li{font-size:.85rem;padding:3px 9px;border:1px solid var(--line);border-radius:999px}
.open{margin-top:auto;padding-top:10px;color:var(--accent);font-weight:600}
.part-head h3{margin:0;font-size:1.2rem}
.facts h4,.description h4{font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 6px}
section[id]{scroll-margin-top:12px}
.section-title{font-size:1.15rem;margin:26px 0 0}
.section-title .muted{font-weight:400;font-size:.95rem;margin-left:6px}
.contents{margin:30px 0 8px}
.contents h2{font-size:1.25rem;margin:0 0 12px;display:flex;align-items:baseline;gap:10px}
.contents h2 .count{font-weight:400}
.item-grid{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.item-card a{display:flex;flex-direction:column;height:100%;border:1px solid var(--line);border-radius:12px;
overflow:hidden;background:var(--panel);text-decoration:none;color:var(--ink)}
.item-card a:hover{border-color:var(--accent)}
.item-card a:hover .item-name{color:var(--accent)}
.item-card .card-body{display:flex;flex-direction:column;gap:3px;padding:12px 14px 14px}
.kind{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}
.item-name{font-size:1.08rem;font-weight:650}
.item-card .slug{font-size:.78rem}
.up-link{margin:28px 0 8px}
.fit-details{margin:0 0 16px;border-top:0;padding-top:0}
.fit-details summary{list-style:none;display:flex;flex-direction:column;gap:2px;cursor:pointer}
.fit-details summary::-webkit-details-marker{display:none}
.fit-details summary h4{margin:0}
.fit-line{font-size:.92rem;color:var(--ink)}
.fit-line::after{content:" ▸";color:var(--muted)}
.fit-details[open] .fit-line::after{content:" ▾"}
.fit-details table{margin-top:8px}
.clashing .fit-line{color:#c0392b;font-weight:600}
.assembly{margin-top:28px}
.assembly .assembly{margin:22px 0 0 0;padding-left:16px;border-left:3px solid var(--line)}
.assembly-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;border-bottom:2px solid var(--line);padding-bottom:8px}
.assembly-head .eyebrow{flex-basis:100%;margin:0}
.assembly-head h2{margin:0;font-size:1.3rem}
.depth-2 .assembly-head h2,.depth-3 .assembly-head h2{font-size:1.12rem}
.assembly-head p:not(.eyebrow){flex-basis:100%;margin:2px 0 0;color:var(--muted)}
.eyebrow code{text-transform:none;letter-spacing:0;font-weight:500}
.part-head .eyebrow{flex-basis:100%;margin:0}
.tree li.leaf::before{content:"◦ ";color:var(--muted)}
.tree li.model::before{content:"▣ "}
.part.model{border-color:var(--accent)}
.fit-list{list-style:none;padding:0;margin:0 0 16px;font-size:.92rem}
.fit-list li{padding:6px 10px;border-radius:8px;border:1px solid var(--line)}
.fit-list .fit::before{content:"✓ ";color:#2e8b57;font-weight:700}
.fit-list .clash::before{content:"✕ ";color:#c0392b;font-weight:700}
.fit-list .touch::before{content:"⇵ ";color:var(--muted)}
.fit-list li+li{margin-top:6px}
"""

_JS = """
import * as THREE from "three";
import {STLLoader} from "three/addons/loaders/STLLoader.js";
import {OrbitControls} from "three/addons/controls/OrbitControls.js";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// an assembly's components take the colours its PNG views use (data-colors, from
// the build summary), falling back to this palette (cadview.COMPONENT_RGB);
// a single part uses the page's --part colour
const COMPONENT_COLORS = [0x5b8fc7, 0xe08f3d, 0x66ad73, 0x9e7ac7, 0xcc6673, 0x73b3b8];
const SEE_THROUGH = 0.22;  // a see-through component's opacity
const HALF_DISC = '<svg width=12 height=12 viewBox="0 0 12 12" aria-hidden=true style="vertical-align:-1px">' +
  '<circle cx=6 cy=6 r=5 fill=none stroke=currentColor stroke-width=1.4 />' +
  '<path d="M6 1a5 5 0 0 1 0 10z" fill=currentColor /></svg>';

// one chip per component under the view: a checkbox shows or hides it, the
// half-disc button makes it see-through; a single part gets the button alone
function layers(figure, parts, colors, names) {
  const bar = document.createElement("div");
  bar.className = "layers";
  parts.forEach(({mesh, edges, material}, i) => {
    const chip = document.createElement("span");
    chip.className = "layer";
    if (names) {
      const label = document.createElement("label");
      label.title = names[i];
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = true;
      box.addEventListener("change", () => {
        mesh.visible = edges.visible = box.checked;
        chip.classList.toggle("hidden", !box.checked);
      });
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = "#" + material.color.getHexString();
      label.append(box, swatch, names[i].split("/").pop());
      chip.append(label);
    }
    const ghost = document.createElement("button");
    ghost.type = "button";
    ghost.className = "ghost";
    ghost.innerHTML = HALF_DISC + (names ? "" : " see-through");
    ghost.title = "see-through";
    ghost.setAttribute("aria-pressed", "false");
    ghost.addEventListener("click", () => {
      const on = ghost.getAttribute("aria-pressed") !== "true";
      ghost.setAttribute("aria-pressed", String(on));
      material.transparent = on;
      material.opacity = on ? SEE_THROUGH : 1;
      material.depthWrite = !on;  // so parts behind it still draw
      material.needsUpdate = true;
      edges.material.opacity = on ? 0.25 : 0.55;
    });
    chip.append(ghost);
    bar.append(chip);
  });
  figure.insertBefore(bar, figure.querySelector("figcaption"));
}

function mount(figure) {
  const loader = new STLLoader();
  const urls = figure.dataset.stl.split(" ").filter(Boolean);
  Promise.all(urls.map((url) => loader.loadAsync(url))).then((geometries) => {
    const box = new THREE.Box3();
    geometries.forEach((g) => { g.computeBoundingBox(); box.union(g.boundingBox); });
    const centre = box.getCenter(new THREE.Vector3());
    const radius = box.getSize(new THREE.Vector3()).length() / 2;

    const scene = new THREE.Scene();
    const colors = figure.dataset.colors ? figure.dataset.colors.split(" ") : null;
    const names = figure.dataset.names ? figure.dataset.names.split(" ") : null;
    const parts = geometries.map((geometry, i) => {
      geometry.translate(-centre.x, -centre.y, -centre.z);
      geometry.computeVertexNormals();
      const color = geometries.length === 1 ? css("--part")
        : colors ? colors[i] : COMPONENT_COLORS[i % COMPONENT_COLORS.length];
      const material = new THREE.MeshStandardMaterial({color, metalness: 0.15, roughness: 0.55});
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30),
        new THREE.LineBasicMaterial({color: 0x1a2330, transparent: true, opacity: 0.55}));
      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh, edges);
      return {mesh, edges, material};
    });
    const materials = parts.map((p) => p.material);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(1, -1.4, 2);
    scene.add(sun);

    const camera = new THREE.PerspectiveCamera(35, 1, radius / 100, radius * 100);
    camera.up.set(0, 0, 1);  // parts are modelled z up
    const direction = new THREE.Vector3(0.62, -0.95, 0.55).normalize();

    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    figure.insertBefore(renderer.domElement, figure.firstChild);
    figure.classList.add("live");
    layers(figure, parts, colors, names && names.length === parts.length ? names : null);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    // back off until the bounding sphere fits the narrower of the two fields of view
    const fit = () => {
      const vfov = THREE.MathUtils.degToRad(camera.fov);
      const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
      return radius * 1.08 / Math.sin(Math.min(vfov, hfov) / 2);
    };
    const reset = () => {
      camera.position.copy(direction).multiplyScalar(fit());
      controls.target.set(0, 0, 0);
      controls.update();
    };
    figure.querySelector(".reset").addEventListener("click", reset);

    const resize = () => {
      const canvas = renderer.domElement;
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) ||
          canvas.height !== Math.floor(h * renderer.getPixelRatio())) {
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        return true;
      }
      return false;
    };
    resize();
    reset();
    if (geometries.length === 1) {
      matchMedia("(prefers-color-scheme: dark)").addEventListener("change",
        () => materials[0].color.set(css("--part")));
    }
    renderer.setAnimationLoop(() => { resize(); controls.update(); renderer.render(scene, camera); });
  }).catch(() => { /* keep the static image */ });
}

document.querySelectorAll(".viewer[data-stl]").forEach(mount);
"""


def main(argv: list[str] | None = None) -> int:
    from .catalog import main as catalog_main

    return catalog_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
