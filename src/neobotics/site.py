"""A static HTML catalogue of built parts, for GitHub Pages: ``neobotics site``.

A downstream consumer like :mod:`neobotics.cadview`: it reads run directories
(``description.md``, ``part.py``, ``cad/``) and never runs a script.  Parts are
grouped as product -> subcategory -> part (:mod:`neobotics.catalog` reads that
tree from ``products/``), and the site is one page per level that matters:

    site/
      index.html                                 overview: a card per product
      products/<product>/index.html              the product: its subcategories and parts
      products/<product>/<subcategory>/<part>/   part.stl, part.step, part.brep, part.py, views

Every product page links back to the overview (breadcrumb, "All products",
and a previous / up / next pager), and all links are relative, so the site
works from any base URL — a GitHub Pages project path or a local folder.  On a
product page every part gets its description, an interactive 3D view of its
STL (three.js, loaded from a CDN, with the shaded PNGs as the fallback), the
measured summary, the CadQuery script and downloads of every CAD file.
"""

from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

#: three.js, pinned; the page loads it as an ES module through an import map.
THREE_VERSION = "0.160.0"
_THREE = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}"

#: Files copied next to the page, and how the download list labels them.
DOWNLOADS = [
    ("part.step", "STEP", "for other CAD tools"),
    ("part.stl", "STL", "for slicers and renderers"),
    ("part.brep", "BREP", "the exact OpenCascade shape"),
    ("part.py", "part.py", "the CadQuery script (B-rep code)"),
]
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


@dataclass
class Category:
    """A subcategory of a product: a named group of parts."""

    slug: str
    title: str
    blurb: str = ""
    parts: list[Part] = field(default_factory=list)


@dataclass
class Product:
    """A product: its subcategories, in order."""

    slug: str
    title: str
    blurb: str = ""
    categories: list[Category] = field(default_factory=list)

    @property
    def n_parts(self) -> int:
        return sum(len(c.parts) for c in self.categories)


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
    script = (cad / "part.py").read_text()
    description_path = run_dir / "description.md"
    description = description_path.read_text().strip() if description_path.exists() else ""
    name = name or run_dir.name
    return Part(name, _title(script, name), description, script,
                json.loads(summary_path.read_text()), cad)


def _title(script: str, fallback: str) -> str:
    """The first line of the script's docstring, without its full stop."""
    for quote in ('"""', "'''"):
        start = script.find(quote)
        if start != -1:
            first = script[start + 3:].strip().splitlines()
            if first:
                return first[0].rstrip(".")
    return fallback.replace("_", " ")


def _anchor(*slugs: str) -> str:
    return "--".join(slugs)


def _plural_categories(n: int) -> str:
    return f"{n} {'subcategory' if n == 1 else 'subcategories'}"


#: Where a product's page lives, relative to the site root; its parts' files
#: sit below it, at <subcategory>/<part>/.
def product_dir(product: Product) -> str:
    return f"products/{product.slug}"


def _check_unique(products: list[Product]) -> None:
    for kind, slugs in (("product", [p.slug for p in products]),
                        *((f"subcategory of {p.slug}", [c.slug for c in p.categories])
                          for p in products),
                        *((f"part in {p.slug}/{c.slug}", [x.name for x in c.parts])
                          for p in products for c in p.categories)):
        if len(set(slugs)) != len(slugs):
            raise ValueError(f"{kind} names must be unique, got {slugs}")


def build_site(products: list[Product], site_dir: Path) -> Path:
    """Write the overview, one page per product, and every part's files.

        site/index.html                                  every product, as a card
        site/products/<product>/index.html               the product's subcategories and parts
        site/products/<product>/<subcategory>/<part>/    the part's STEP, STL, BREP, script, views
    """
    site_dir = Path(site_dir)
    products = [p for p in products if p.n_parts]
    if not products:
        raise ValueError("no parts to publish")
    _check_unique(products)
    for i, product in enumerate(products):
        page_dir = site_dir / product_dir(product)
        for category in product.categories:
            for part in category.parts:
                target = page_dir / category.slug / part.name
                target.mkdir(parents=True, exist_ok=True)
                for filename in [f for f, *_ in DOWNLOADS] + IMAGES:
                    shutil.copyfile(part.cad_dir / filename, target / filename)
        siblings = (products[i - 1] if i > 0 else None,
                    products[i + 1] if i + 1 < len(products) else None)
        (page_dir / "index.html").write_text(render_product(product, siblings))
    index = site_dir / "index.html"
    index.write_text(render_overview(products))
    (site_dir / ".nojekyll").write_text("")
    return index


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    return "".join(f"<p>{_e(' '.join(b.split()))}</p>" for b in blocks)


def _num(value: float) -> str:
    return f"{value:,.1f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _summary_rows(summary: dict) -> str:
    bb = summary["bounding_box"]
    size = " × ".join(_num(v) for v in bb["size"])
    faces = ", ".join(f"{n} {k.lower()}" for k, n in summary["face_types"].items())
    regions = summary.get("regions") or {}
    rows = [
        ("Size (x × y × z)", f"{size} mm"),
        ("Volume", f"{_num(summary['volume_mm3'])} mm³"),
        ("Surface area", f"{_num(summary['surface_area_mm2'])} mm²"),
        ("Solids", str(summary["n_solids"])),
        ("Faces", f"{summary['n_faces']} ({faces})"),
        ("Regions", ", ".join(regions) if regions else "none"),
    ]
    return "".join(f"<tr><th scope=row>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows)


def _part_section(category: Category, part: Part) -> str:
    base = f"{category.slug}/{part.name}"  # relative to the product page
    downloads = "".join(
        f'<li><a href="{base}/{f}" download><span class=fmt>{_e(label)}</span>'
        f"<span class=note>{_e(note)}</span></a></li>"
        for f, label, note in DOWNLOADS
    )
    description = (
        f"<div class=description><h4>Description</h4>{_paragraphs(part.description)}</div>"
        if part.description else ""
    )
    return f"""
<section class=part id="{_e(_anchor(category.slug, part.name))}">
  <header class=part-head>
    <h3>{_e(part.title)}</h3>
    <code class=slug>{_e(part.name)}</code>
  </header>
  <div class=part-grid>
    <figure class=viewer data-stl="{base}/part.stl">
      <img src="{base}/part.png" alt="Shaded view of {_e(part.title)}" class=fallback>
      <figcaption>Drag to orbit · scroll to zoom · <button type=button class=reset>reset view</button></figcaption>
    </figure>
    <div class=facts>
      {description}
      <h4>Measured from the B-rep</h4>
      <table>{_summary_rows(part.summary)}</table>
      <h4>Downloads</h4>
      <ul class=downloads>{downloads}</ul>
    </div>
  </div>
  <details class=views>
    <summary>Static views</summary>
    <div class=view-pair>
      <img src="{base}/part.png" alt="From the front, right and above" loading=lazy>
      <img src="{base}/part_rear_below.png" alt="From the rear, left and below" loading=lazy>
    </div>
  </details>
  <details class=code>
    <summary>CadQuery script <span class=muted>part.py</span></summary>
    <pre><code>{_e(part.script)}</code></pre>
  </details>
</section>"""


def _category_section(category: Category) -> str:
    parts = "".join(_part_section(category, p) for p in category.parts)
    blurb = _paragraphs(category.blurb) if category.blurb else ""
    return f"""
<section class=category id="{_e(category.slug)}">
  <header class=category-head>
    <h2>{_e(category.title)}</h2>
    <span class=count>{_plural(len(category.parts), 'part')}</span>
    {blurb}
  </header>{parts}
</section>"""


def _product_tree(product: Product) -> str:
    cats = "".join(
        f'<li><a href="#{_e(c.slug)}">{_e(c.title)}</a><ul>'
        + "".join(f'<li><a href="#{_e(_anchor(c.slug, x.name))}">{_e(x.title)}</a></li>'
                  for x in c.parts)
        + "</ul></li>"
        for c in product.categories
    )
    return (f'<nav class=tree aria-label="{_e(product.title)} contents">'
            f'<a class=back href="../../index.html">← All products</a>'
            f'<p class=eyebrow>{_e(product.title)}</p><ul>{cats}</ul></nav>')


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


def render_product(product: Product, siblings: tuple[Product | None, Product | None] = (None, None)) -> str:
    """One product's page: breadcrumb back to the overview, its subcategories and parts."""
    cards = "".join(
        f'<li><a href="#{_e(c.slug)}"><span class=card-title>{_e(c.title)}</span>'
        f"<span class=count>{_plural(len(c.parts), 'part')}</span></a></li>"
        for c in product.categories
    )
    categories = "".join(_category_section(c) for c in product.categories)
    blurb = _paragraphs(product.blurb) if product.blurb else ""
    prev, nxt = siblings
    pager = "".join([
        f'<a class=prev href="../{_e(prev.slug)}/index.html"><small>Previous product</small>'
        f"<span>← {_e(prev.title)}</span></a>" if prev else "<span></span>",
        '<a class=up href="../../index.html"><small>Back to</small><span>All products</span></a>',
        f'<a class=next href="../{_e(nxt.slug)}/index.html"><small>Next product</small>'
        f"<span>{_e(nxt.title)} →</span></a>" if nxt else "<span></span>",
    ])
    body = f"""<header class="site-head compact">
  <div class=wrap>
    <nav class=crumbs-bar aria-label=Breadcrumb>
      <ol><li><a href="../../index.html">neoBotics products</a></li>
      <li aria-current=page>{_e(product.title)}</li></ol>
    </nav>
    <p class=eyebrow>Product</p>
    <h1 class=product-title>{_e(product.title)}</h1>
    <p class=count>{_plural_categories(len(product.categories))} · {_plural(product.n_parts, 'part')}</p>
    {blurb}
    <ul class=cards>{cards}</ul>
  </div>
</header>
<div class="wrap layout">
  {_product_tree(product)}
  <main>{categories}
    <nav class=pager aria-label="Other products">{pager}</nav>
  </main>
</div>"""
    return _page(f"{product.title} · neoBotics", f"{product.title}: its parts, built as CadQuery B-rep code.",
                 body, viewer=True)


def _product_card(product: Product) -> str:
    href = f"{product_dir(product)}/index.html"
    first = product.categories[0]
    thumb = f"{product_dir(product)}/{first.slug}/{first.parts[0].name}/part.png"
    cats = "".join(f"<li>{_e(c.title)} <span class=count>{len(c.parts)}</span></li>"
                   for c in product.categories)
    blurb = _paragraphs(product.blurb) if product.blurb else ""
    return f"""
<li class=product-card>
  <a href="{_e(href)}">
    <span class=thumb><img src="{_e(thumb)}" alt="" loading=lazy></span>
    <span class=card-body>
      <span class=product-name>{_e(product.title)}</span>
      <span class=count>{_plural_categories(len(product.categories))} · {_plural(product.n_parts, 'part')}</span>
      <span class=card-blurb>{blurb}</span>
      <ul class=card-cats>{cats}</ul>
      <span class=open>Open {_e(product.title)} →</span>
    </span>
  </a>
</li>"""


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
  <div class=overview-head>
    <h2>Products</h2>
    <span class=count>{_plural(len(products), 'product')} · {_plural(n_parts, 'part')}</span>
  </div>
  <ul class=product-grid>{cards}</ul>
</main>"""
    return _page("neoBotics products", "Products and their parts, built from natural-language "
                 "descriptions as CadQuery B-rep code.", body, viewer=False)


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
.fmt{font-weight:600;min-width:62px;color:var(--accent)}.note{color:var(--muted);font-size:.88rem}
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
.category{margin-top:28px;padding-top:4px}
.category-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;border-bottom:2px solid var(--line);padding-bottom:8px}
.category-head h2{margin:0;font-size:1.3rem}
.category-head p{flex-basis:100%;margin:2px 0 0;color:var(--muted)}
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
"""

_JS = """
import * as THREE from "three";
import {STLLoader} from "three/addons/loaders/STLLoader.js";
import {OrbitControls} from "three/addons/controls/OrbitControls.js";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function mount(figure) {
  const loader = new STLLoader();
  loader.load(figure.dataset.stl, (geometry) => {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    const centre = box.getCenter(new THREE.Vector3());
    const radius = box.getSize(new THREE.Vector3()).length() / 2;
    geometry.translate(-centre.x, -centre.y, -centre.z);
    geometry.computeVertexNormals();

    const scene = new THREE.Scene();
    const material = new THREE.MeshStandardMaterial({color: css("--part"), metalness: 0.15, roughness: 0.55});
    const mesh = new THREE.Mesh(geometry, material);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30),
      new THREE.LineBasicMaterial({color: 0x1a2330, transparent: true, opacity: 0.55}));
    scene.add(mesh, edges);
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
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change",
      () => material.color.set(css("--part")));
    renderer.setAnimationLoop(() => { resize(); controls.update(); renderer.render(scene, camera); });
  }, undefined, () => { /* keep the static image */ });
}

document.querySelectorAll(".viewer[data-stl]").forEach(mount);
"""


def main(argv: list[str] | None = None) -> int:
    from .catalog import main as catalog_main

    return catalog_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
