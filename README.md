# neoBotics

Natural language in, a 3D CAD model out. A description of a part goes to
Claude. Claude writes a [CadQuery](https://github.com/CadQuery/cadquery)
script: the B-rep code, Python that builds the part's exact boundary
representation. The script is run, checked and exported as BREP, STEP, STL and
shaded PNG views.

The CAD stage follows [topocombo](https://github.com/anroleroux/topocombo): a
part is a CadQuery script that assigns the part to `result` and names places on
it in `regions`. A script opens as-is in CQ-editor. The pipeline reads every
fact it needs from the built shape, never from parameters. neoBotics adds the
stage in front, which writes that script from a description.

## Pipeline

```
description.md ──► Claude ──► part.py ──► CadQuery (child process) ──► part.brep / .step / .stl
   (NL)                (B-rep code)           │                        part.png, part_rear_below.png
                          ▲                   │                        summary.json
                          └── build error ────┤
                          └── views + summary ┘  (review: APPROVED, or a revised script)
```

1. **NL → script.** The description goes to Claude (`claude-opus-5-5`, adaptive
   thinking, streamed) with a system prompt that fixes the script contract:
   - millimetres, z up, the part standing on z = 0;
   - every dimension as a named constant;
   - a docstring that lists each assumption the description left open;
   - `result` and `regions`;
   - only `cadquery` and `math` imported.
2. **Script → B-rep.** The script runs in a child process with a timeout,
   because it is model-written code. The child checks that `result` holds
   valid solids with volume and that every region selects faces, edges or
   vertices. It then exports the part. A failure goes back to Claude verbatim
   (the traceback with the script's line numbers, or the check that failed),
   and Claude sends a corrected script. By default four scripts are allowed in
   all.
3. **Review.** Claude gets two shaded views of the built part plus its measured
   bounding box, volume, face types and regions. It compares them with the
   description and answers `APPROVED` or sends a revised script, which goes
   back through step 2. One round by default (`--review 0` skips it).

The whole exchange is a single append-only conversation, and every script
Claude sends is kept under `attempts/`.

## Usage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...        # or `ant auth login`

# NL -> B-rep code -> CAD
neobotics generate --description products/B4/grippers/jaw/description.md --out results/jaw
neobotics generate "a 40 x 40 x 5 mm plate with four M3 holes on a 30 mm square" --out results/plate

# only the CAD stage, for a script written or edited by hand (no model, no key)
neobotics cad products/B4/motor_mounts/nema17_bracket/part.py --out results/nema17_bracket

# a shaded PNG of any BREP or STL (--view iso | rear_below)
neobotics view results/nema17_bracket/cad/part.stl

# build one catalogue part by its designation
neobotics build PB4/chassis/lid

# build every part in the catalogue and render the site: an overview page,
# then one page per product with its assembly tree and each part's 3D viewer
neobotics site products --out results --site site
```

### Without an API key

The NL → script step does not have to be a `generate` run. A person (or
Claude in a coding session) can read a part's `description.md`, write its
`part.py` to the same contract, and commit both. CI builds every committed
`part.py` and publishes it, so no key is involved. This is how parts are added
for now. `generate` automates the same step once a key is
set.

### The catalogue

Parts live in a product breakdown, `products/<PRODUCT>/<assembly>/.../<part>/`.
Assemblies nest to any depth, and the leaf assemblies hold the parts. Each
part has its `description.md` and `part.py`. `product.md` and `assembly.md`
name and describe the levels above.

- **B4** has the assembly **Motor mounts** with the NEMA 17 bracket.
- **PB4** has:
  - the assembly **Chassis**: a base driven by `l`, `b`, `h` and `wall`, and an
    18650 cell. The chassis `assembly.py` lays four cells along x against the
    back wall.
  - its own part, the **lid**, sized from the base.

  `PB4/assembly.py` seats the lid on the chassis, and the build checks the fit.

A part's designation is its path (`PB4/chassis/lid`).
`neobotics build <designation>` builds just that part, or an assembly's
assembled model (`PB4/chassis`). A script can read another part's variables
with `load_part("../base")`. See `products/README.md`.

In a Claude Code session, the `neobotics-part` skill
(`.claude/skills/neobotics-part/SKILL.md`) takes a designation plus modelling
instructions. It writes or edits the description and the script, builds and
checks the part, updates the site, and commits.

`generate` options: `--max-attempts N` (scripts in all, repairs included),
`--review N` (review rounds), `--model`, `--effort low|medium|high|xhigh|max`
(default `high`).

### A run directory

```
results/jaw/
  description.md     the input, as given
  part.py            the script that built the part
  cad/               part.brep, part.step, part.stl, part.png, part_rear_below.png, summary.json
  attempts/NN.py     every script Claude sent, NN/ its build
  transcript.md      Claude's replies, in order
  manifest.json      model, attempts and their errors, review verdict, token usage, summary
```

### The part script

`products/B4/motor_mounts/nema17_bracket/` is a hand-written reference: a
NEMA 17 motor bracket with its description next to it. It follows the same contract a generated
script does:

```python
"""An L-bracket that holds a NEMA 17 stepper motor.

Assumptions where the description is silent:
- ...
"""
import cadquery as cq

width = 50.0  # along x, both plates
thickness = 3.0
...
result = vertical.union(base) ...      # the part: valid solid(s), z up, on z = 0
regions = {                            # named places for later stages
    "motor_face": result.faces("<Y"),
    "base_bottom": result.faces("<Z"),
}
```

`regions` is how a later stage refers to the part without knowing its
geometry. In topocombo, a study fixes and loads parts by region name; here the
same names can carry an assembly's mates or a study's loads.

## Modules

| Module | Role |
| --- | --- |
| `neobotics.nl2cad` | the prompt, the Claude client (`ClaudeCoder`), the generate → build → repair → review loop |
| `neobotics.part` | runs a part script in a child process, checks it, exports BREP / STEP / STL / PNG and `summary.json` |
| `neobotics.cadview` | headless shaded rendering (numpy z-buffer, no OpenGL), adapted from topocombo's `cadview` |
| `neobotics.pipeline` | lays out a run directory around the two stages |
| `neobotics.site` | the static page: an interactive three.js view of each part's STL, its description, measurements, script and downloads |
| `neobotics.catalog` | reads the `products/` breakdown (assemblies to any depth), builds every part, renders the site |
| `neobotics.cli` | `neobotics generate / cad / build / view / site` |

The model sits behind a small `Coder` interface (`(system, messages) ->
(text, content)`), so the tests drive the whole loop with scripted replies and
real CadQuery builds, with no network.

## CI and GitHub Pages

`.github/workflows/cad.yml` runs on every push and pull request:

1. it runs the tests;
2. `neobotics site` builds every part under `products/` and renders the
   pages; a part that fails to build fails the job;
3. it uploads the CAD files as the `parts` artifact.

On a push, it also deploys the site to GitHub Pages:

- `index.html`, the overview: one card per product;
- `products/<product>/index.html`, and one page per assembly below it: that
  level's contents as cards you can click into, then its assembled model with
  its fit; under the model's 3D view, each component can be hidden or made
  see-through;
- one page per part: its designation, a 3D view you can orbit (and make
  see-through), the
  description, measurements, and STEP / STL / BREP / script downloads.

Every page leads back up through a breadcrumb and a "Back to …" link. Links are
relative, so the site also works opened from a local folder. Pages
must be set to deploy from GitHub Actions (Settings → Pages → Source).

To generate a design with Claude in CI, add an `ANTHROPIC_API_KEY` repository
secret and start the workflow by hand with `design` set to a part path such
as `B4/grippers/jaw` (see `products/README.md`).

## Safety

Generated scripts are arbitrary Python. They run in a separate process with a
timeout, but not in a sandbox. Run `generate` somewhere you would run code
you have not read, such as a container or CI, and read `part.py` before you
reuse it elsewhere.
