# Designs

One directory per part, holding its natural-language description:

```
designs/<name>/description.md
```

Write the part script by hand (or have Claude write it in a coding session)
as `designs/<name>/part.py`, following the contract in the main README. CI
builds every committed `part.py` and publishes it on the GitHub Pages site.

Or generate it locally with

```bash
neobotics generate --description designs/<name>/description.md --out results/<name>
```

or in CI: Actions → **cad** → *Run workflow*, with `design` set to `<name>`
(needs the `ANTHROPIC_API_KEY` repository secret). Once a generated
`part.py` is good, commit it next to the description, so the part can be
rebuilt with `neobotics cad designs/<name>/part.py` without the model.
