# Designs

One directory per part, holding its natural-language description:

```
designs/<name>/description.md
```

Generate it locally with

```bash
neobotics generate --description designs/<name>/description.md --out results/<name>
```

or in CI: Actions → **cad** → *Run workflow*, with `design` set to `<name>`
(needs the `ANTHROPIC_API_KEY` repository secret). Once a generated
`part.py` is good, commit it next to the description, so the part can be
rebuilt with `neobotics cad designs/<name>/part.py` without the model.
