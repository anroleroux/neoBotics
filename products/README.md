# Products

The catalogue the GitHub Pages site is built from: a product breakdown of
products, assemblies (nested to any depth) and parts. The site has an overview
page with a card per product, and one page per product showing its assembly
tree and every part.

```
products/<PRODUCT>/product.md                               "# Title", then a blurb
products/<PRODUCT>/<assembly>/assembly.md                   "# Title", then a blurb
products/<PRODUCT>/<assembly>/<sub>/.../assembly.md          sub-assemblies, any depth
products/<PRODUCT>/<assembly>/.../<part>/description.md     the natural-language description
products/<PRODUCT>/<assembly>/.../<part>/part.py            the CadQuery script (B-rep code)
```

The rules:

- A product holds assemblies.
- An assembly holds either sub-assemblies or parts (it is a leaf), never both.
- A part is any directory with a `part.py`. It sits inside an assembly, never
  directly under a product.

A part's **designation** is its path, for example `PB4/chassis/base_plate`.
Product directories keep their code (`PB4`). Assembly and part slugs are
lowercase with underscores. Titles come from `product.md`, from `assembly.md`,
and from the first line of a part script's docstring. Without them, the slug
is shown.

## Adding or changing a part

In a Claude Code session, give the designation and the instructions, for
example: "PB4 / chassis / base_plate: a 160 × 120 × 4 mm plate with …". The
`neobotics-part` skill (`.claude/skills/neobotics-part/SKILL.md`) then:

1. writes or edits the description;
2. writes the script;
3. builds and checks the part;
4. updates the site;
5. commits.

By hand, the steps are:

```bash
$EDITOR products/PB4/chassis/base_plate/description.md   # the instructions
$EDITOR products/PB4/chassis/base_plate/part.py          # the B-rep code
neobotics build PB4/chassis/base_plate                   # -> results/PB4/chassis/base_plate/cad/
neobotics site products --out results --site site        # every part, then the pages
```

To have Claude write the script through the API instead:
`neobotics generate --description products/PB4/chassis/base_plate/description.md --out results/gen`.
Then copy `results/gen/part.py` into the part's directory. In CI, this is
Actions → **cad** → *Run workflow* with `design` set to the designation. It
needs the `ANTHROPIC_API_KEY` repository secret.

CI runs `neobotics site` on every push and publishes the result. A part whose
script fails to build fails the job.
