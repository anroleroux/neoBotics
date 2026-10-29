# Parts library

Parts and assemblies kept for reuse in any product, filed by category. A
battery holder, for example, is the assembly `battery_holders/holder_18650`:
a holder body and a terminal, with the terminal placed at both ends.

```
library/<category>/category.md                     "# Title", then a blurb
library/<category>/<part>/part.py                  a reusable part
library/<category>/<assembly>/assembly.md          a reusable assembly
library/<category>/<assembly>/assembly.py          optional: its parts placed together
library/<category>/<assembly>/<part>/part.py       its parts (or sub-assemblies, any depth)
```

A category follows a product's rules: it holds parts and assemblies side by
side, and an assembly holds either parts or sub-assemblies, never both. Each
part has its `description.md` and `part.py`, written to the same contract as
a product's parts.

## Using a library item in a product

Every part and assembly script has `load_library`. It takes the item's
designation in the library, from any depth:

```python
holder = load_library("battery_holders/holder_18650")   # the assembly: holder.result is a cq.Assembly
body = load_library("battery_holders/holder_18650/holder")  # one part: body.length, body.axis_height, ...

result = (
    cq.Assembly(name="power")
    .add(base.result, name="base")
    .add(holder.result, name="holder", loc=cq.Location((0, 0, base.wall)))
)
```

It returns the item's variables, like `load_part`. So a product can size a
mounting boss or pocket from the holder's `length`, `width` or
`hole_spacing`, and the product follows when the library item changes.

`load_library` looks for the `library/` directory nearest above the calling
script. Set `NEOBOTICS_LIBRARY` to use a library kept somewhere else.

## Building

```bash
neobotics build library/battery_holders/holder_18650          # the assembled model
neobotics build library/battery_holders/holder_18650/terminal # one part
neobotics site products --out results --site site             # products and library
```

The site lists the library on the overview and at `library/index.html`.
Each library item's page shows the `load_library` call that places it, and
links every product script that uses it.
