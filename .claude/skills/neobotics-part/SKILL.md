---
name: neobotics-part
description: Add or change a 3D part, or an assembly's assembled model, in the neoBotics product catalogue from natural-language instructions, then build its CAD (B-rep, STEP, STL, views) and update the HTML site. Use whenever the user names a product, assembly and part designation (e.g. "PB4 / chassis / lid", "PB4-chassis-lid", "in PB4, assembly drive, sub-assembly left_wheel, part hub") or an assembly designation ("PB4 / chassis: assemble the lid on the box") together with modelling instructions, or asks to add, modify, remove, rename or rebuild a product, assembly, sub-assembly or part.
---

# Add or change a neoBotics part

The catalogue is a product breakdown under `products/`, and each part is a
CadQuery script written from a plain-language description. This skill takes
the user's instructions for one part from words to a published 3D model:
**description → part.py (B-rep code) → CAD files → HTML**.

## The breakdown

```
products/<PRODUCT>/product.md                       "# Title" + blurb
products/<PRODUCT>/assembly.py                      optional: the whole product, assembled
products/<PRODUCT>/<part>/...                       a part of the product itself (e.g. PB4/lid)
products/<PRODUCT>/<assembly>/assembly.md           "# Title" + blurb
products/<PRODUCT>/<assembly>/<sub>/.../assembly.md  sub-assemblies, any depth
products/<PRODUCT>/<assembly>/.../<part>/description.md   the instructions (source of truth)
products/<PRODUCT>/<assembly>/.../<part>/part.py          the CadQuery script
products/<PRODUCT>/<assembly>/assembly.py                 optional: the assembled model
```

- A product holds assemblies **and** parts of its own (`PB4/lid`), and may have
  an `assembly.py` for the whole product. An assembly holds **either**
  sub-assemblies **or** parts (it is a leaf), never both.
- A part's **designation** is its path: `PB4/chassis/lid`. An assembly's is
  its path too: `PB4/chassis`.
- Product directories keep the user's code as given (`PB4`). Assembly and part
  slugs are lowercase with underscores (`motor_mounts`, `left_wheel`). Titles
  for display go in the markdown files.
- `neobotics site` refuses a breakdown that breaks these rules, and names the
  offending directory.

## Steps

0. **Set up, once per session**: `pip install -e ".[dev]"` (CadQuery is heavy,
   so give it a few minutes). Check it with `neobotics --help`.

1. **Resolve the designation.** Split what the user gave into product, the
   assembly chain and the part, and normalise the slugs. List what exists with
   `find products -name part.py` (and `ls` the product). Decide which levels
   are new and which already exist.
   - If the user's designation conflicts with the rules (for example, a part
     placed in an assembly that already has sub-assemblies), say so and propose
     where it should go. Don't restructure silently.
   - If the user gives no assembly, ask for one. Don't invent the hierarchy.

2. **Create the missing levels.**
   - For a new product, write `product.md`: `# <Title>`, then one or two
     sentences.
   - For each new assembly or sub-assembly, write `assembly.md` the same way.
   - Use the user's wording where they gave it. Otherwise keep it short and
     factual.

3. **Write or update `description.md`.** This file is the natural-language
   source of truth that the page shows.
   - **New part:** record the user's instructions as clear prose. Keep every
     dimension, count, position and standard they gave. Fix only grammar.
   - **Changed part:** edit the sentences the change touches and keep the rest
     verbatim. Don't rewrite the whole description.

4. **Write or update `part.py`.** Follow the part-script contract, which is the
   same one `neobotics.nl2cad.SYSTEM_PROMPT` gives the model:
   - Import only `cadquery as cq` (and `math` if needed).
   - Open with a docstring:
     - **First line:** the part's title (it becomes the heading on the page).
     - **Then:** every assumption made where the description is silent.
   - Name every dimension as a constant in mm with a short comment. No magic
     numbers further down.
   - Model z up, with the part standing on z = 0.
   - Assign `result`: a valid solid.
   - Assign `regions`: a dict naming mounting faces, holes, bores and similar.
     Use `{}` if there are none.
   - End with the `show_object` guard.
   - Prefer sketches and workplanes. Add fillets last, on explicit selections.
   - ISO clearance holes: M3 → 3.4, M4 → 4.5, M5 → 5.5 mm.
   - When changing a part, edit the existing script: change the constants and
     features the instruction touches, and keep the assumptions list current.

   - **A part that must fit another one** (a lid on a box, a shaft in a
     bore) reads the other part's variables instead of copying the numbers:
     `box = load_part("../base")`, then `box.l`, `box.wall`. The path is
     relative to the script's directory, and `load_part` is available in every
     script. That way the fit survives a change to the other part. Put the
     fit itself (clearance, overlap) in named constants.

   Worked examples:
   - `products/B4/motor_mounts/nema17_bracket/part.py`: a standalone part;
   - `products/PB4/chassis/lid/part.py`: a part sized from another with
     `load_part`.

4b. **Assembled model (`assembly.py`)**, when the user asks for parts to be
   put together ("assemble the lid on top of the box"). Write
   `products/<PRODUCT>/<assembly>/assembly.py`:
   - **Docstring:** first line is the model's title.
   - **Load the parts:** `base = load_part("base")`, `lid = load_part("lid")`.
     The paths are relative to the assembly directory. A sub-assembly loads
     the same way (`chassis = load_part("chassis")` gives its `cq.Assembly`
     as `.result`), so a product-level `assembly.py` can place whole
     assemblies.
   - **Several copies of one part** (four cells): add `part.result` once per
     copy, each with its own `name` (`battery_1` …) and `loc`. To lay a part
     down, rotate it: `cq.Location(cq.Vector(x, y, z), cq.Vector(0, 1, 0), 90)`
     turns its +z axis to +x.
   - **Place them:** `result = cq.Assembly(name=...)`, with `.add(part.result,
     name=..., loc=cq.Location((x, y, z)))` for each part. Derive every offset
     from the parts' own variables (`base.h - lid.lip_depth`), never from
     copied numbers. Give each part a `color`: the PNGs and the 3D viewer
     use it (a component without one gets a palette colour). Set `regions = {}`.
   - **Build:** `neobotics build <PRODUCT>/<assembly>`. The summary lists:
     - **components**: what the assembly holds directly (a part, or a whole
       sub-assembly as one), by name, with volume, bounding box and the
       meshes (STL and colour) of every shape inside;
     - **interference**: pairs of components that share volume. It must be
       empty unless an overlap is intended;
     - **contacts**: pairs touching over an area, in mm². A seated lid shows
       its rim area.
   - **Check:** fix any interference or missing contact, then look at both
     PNGs, where each component has its own colour.

5. **Build and check it.** Run `neobotics build <designation>`. For a part it
   writes `results/<designation>/cad/` (for an assembly model,
   `results/<designation>/_assembly/cad/`):
   - `part.brep`, `part.step`, `part.stl`;
   - `part.png` and `part_rear_below.png`;
   - `summary.json`.

   If the build fails, the error names the script line. Fix the script and
   build again. Then verify against the description; don't skip this:
   - Compare `summary.json` with the description: bounding box, volume, the
     number of cylinder faces (holes and bores), and the regions.
   - **Look at both PNGs** with the Read tool. Check every feature is there, in
     the right count, place and orientation, and that nothing extra appeared.
   - Iterate until it matches. If a dimension cannot work as described (for
     example, holes that overlap an edge), choose the nearest sound value,
     record it under the docstring's assumptions, and tell the user.

6. **Update the site.** Run `neobotics site products --out results --site site`.
   It rebuilds every part, then writes one page per level:
   - `site/index.html`: the overview, a card per product;
   - `site/products/<PRODUCT>/index.html` and `.../<assembly>/index.html`:
     each level's contents as cards, then its assembled model;
   - `site/products/<PRODUCT>/.../<part>/index.html`: one page per part.

   It exits non-zero if any part fails to build. To look at the page, serve
   `site/` with `python -m http.server` and screenshot it with headless
   Chromium (Playwright with `executablePath: /opt/pw-browsers/chromium-*/chrome-linux/chrome`).
   Three.js loads from jsDelivr. If the sandbox blocks the CDN, the page falls
   back to the PNG views.

7. **Test**: `python -m pytest -q`. This is needed only when code changed, but
   it is cheap enough to run every time.

8. **Commit and push.**
   - Commit only `products/` changes (and code, if any). Never commit
     `results/` or `site/`; they are build output and are git-ignored.
   - Message: `Add PB4/chassis/lid: <one line>` or `Update …: <what changed>`.
   - Push to the working branch. CI rebuilds every part and redeploys GitHub
     Pages on push.

9. **Report back**, in a few lines:
   - the designation;
   - what was built: size and key features;
   - any assumptions you had to make;
   - the page link: `https://anroleroux.github.io/neoBotics/products/<designation>/index.html`
     (e.g. `.../products/PB4/chassis/battery_18650/index.html`).

## Other changes

- **Rename or move a part or assembly**: use `git mv` on the directory, then
  run steps 6–9. The designation changes with the path, so tell the user the
  new one.
- **Remove**: `git rm -r` the directory, and search for `load_part` calls
  that name it (`grep -rn load_part products`). If an assembly is left empty,
  remove it too. Then run steps 6–9.
- **Change only a title or blurb**: edit `product.md` or `assembly.md`, or
  the first docstring line for a part, then run steps 6–9.
- **Several parts in one request**: do steps 1–5 for each part, then steps
  6–9 once.
