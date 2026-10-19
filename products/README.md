# Products

The catalogue the GitHub Pages site is built from, as product → subcategory → part.
The site has an overview page with a card per product, and one page per
product listing its subcategories and parts.

```
products/<product>/product.md                          "# Title", then a blurb
products/<product>/<subcategory>/category.md            "# Title", then a blurb
products/<product>/<subcategory>/<part>/description.md  the natural-language description
products/<product>/<subcategory>/<part>/part.py         the CadQuery script (B-rep code)
```

Directory names are slugs: they appear in URLs and anchors, so keep them
lowercase with underscores (`motor_mounts`, `nema17_bracket`); a product's slug
can be its code (`B4`). Titles and blurbs come from `product.md` and
`category.md`; without them the slug is shown. The title of a part is the
first line of its script's docstring.

To add a part, write its `description.md`, then its `part.py` following the
contract in the main README. You can write the script by hand, have Claude
write it in a coding session, or generate it:

```bash
neobotics generate --description products/B4/grippers/jaw/description.md --out results/jaw
cp results/jaw/part.py products/B4/grippers/jaw/part.py
```

In CI, generation is Actions → **cad** → *Run workflow*, with `design` set to
`B4/grippers/jaw`. It needs the `ANTHROPIC_API_KEY` repository secret.

`neobotics site` builds every part and renders the pages. CI runs it on every
push and publishes the result. A part whose script fails to build fails the
job.
