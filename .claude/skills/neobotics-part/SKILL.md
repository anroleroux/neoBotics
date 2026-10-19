---
name: neobotics-part
description: Add or change a 3D part in the neoBotics product catalogue from natural-language instructions, then build its CAD (B-rep, STEP, STL, views) and update the HTML site. Use whenever the user names a product, assembly and part designation (e.g. "PB4 / chassis / base_plate", "PB4-chassis-base_plate", "in PB4, assembly drive, sub-assembly left_wheel, part hub") together with modelling instructions, or asks to add, modify, rename or rebuild a product, assembly, sub-assembly or part.
---

# Add or change a neoBotics part

The catalogue is a product breakdown under `products/`, and each part is a
CadQuery script written from a plain-language description. This skill takes
the user's instructions for one part from words to a published 3D model:
**description → part.py (B-rep code) → CAD files → HTML**.

## The breakdown

```
products/<PRODUCT>/product.md                       "# Title" + blurb
products/<PRODUCT>/<assembly>/assembly.md           "# Title" + blurb
products/<PRODUCT>/<assembly>/<sub>/.../assembly.md  sub-assemblies, any depth
products/<PRODUCT>/<assembly>/.../<part>/description.md   the instructions (source of truth)
products/<PRODUCT>/<assembly>/.../<part>/part.py          the CadQuery script
```

- A product holds assemblies. An assembly holds **either** sub-assemblies **or**
  parts (it is a leaf), never both. A part never sits directly under a product.
- A part's **designation** is its path: `PB4/chassis/base_plate`.
- Product directories keep the user's code as given (`PB4`). Assembly and part
  slugs are lowercase with underscores (`motor_mounts`, `base_plate`). Titles
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

   `products/B4/motor_mounts/nema17_bracket/part.py` is a worked example.

5. **Build and check it.** Run `neobotics build <designation>`. It writes
   `results/<designation>/cad/`:
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
   It rebuilds every part, then writes:
   - `site/index.html`, the overview;
   - `site/products/<PRODUCT>/index.html`, the product page.

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
   - Message: `Add PB4/chassis/base_plate: <one line>` or `Update …: <what changed>`.
   - Push to the working branch. CI rebuilds every part and redeploys GitHub
     Pages on push.

9. **Report back**, in a few lines:
   - the designation;
   - what was built: size and key features;
   - any assumptions you had to make;
   - the page link: `https://anroleroux.github.io/neoBotics/products/<PRODUCT>/index.html#<assembly>--...--<part>`.

## Other changes

- **Rename or move a part or assembly**: use `git mv` on the directory, then
  run steps 6–9. The designation changes with the path, so tell the user the
  new one.
- **Remove**: `git rm -r` the directory. If an assembly is left empty, remove
  it too. Then run steps 6–9.
- **Change only a title or blurb**: edit `product.md` or `assembly.md`, or
  the first docstring line for a part, then run steps 6–9.
- **Several parts in one request**: do steps 1–5 for each part, then steps
  6–9 once.
