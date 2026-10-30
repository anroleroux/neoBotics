"""Command line: ``neobotics generate | cad | build | view | site``.

    # NL -> CadQuery script -> BREP / STEP / STL / PNG, with Claude
    neobotics generate --description products/RA6/grippers/jaw/description.md --out results/jaw
    neobotics generate "a 40 x 40 x 5 mm plate with four M3 holes" --out results/plate

    # only the CAD stage, for a script written or edited by hand
    neobotics cad tests/fixtures/nema17_bracket/part.py --out results/nema17_bracket

    # a shaded PNG of any BREP or STL
    neobotics view results/nema17_bracket/cad/part.stl

    # build one catalogue part by its designation: product/assembly/.../part
    neobotics build PB6/chassis/lid
    # or a reusable one in the parts library: library/category/item/...
    neobotics build library/battery_holders/single_18650_holder

    # build every part under products/ and render the catalogue site
    # (what GitHub Pages serves)
    neobotics site products --out results --site site
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _print_build(out: Path, summary: dict, files: dict) -> None:
    size = " x ".join(f"{v:g}" for v in summary["bounding_box"]["size"])
    print(f"part: {size} mm, {summary['volume_mm3']:g} mm^3, "
          f"{summary['n_solids']} solid(s), {summary['n_faces']} faces")
    for kind, path in files.items():
        print(f"{kind}: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="neobotics",
        description="Natural language -> CadQuery (B-rep) script -> CAD files.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="write a part script from a description with "
                                            "Claude, then build it")
    p_gen.add_argument("text", nargs="?", help="the description (or use --description)")
    p_gen.add_argument("--description", type=Path, help="a file holding the description")
    p_gen.add_argument("--out", type=Path, required=True, help="run directory")
    p_gen.add_argument("--max-attempts", type=int, default=4,
                       help="scripts the model may send in all, repairs included (default 4)")
    p_gen.add_argument("--review", type=int, default=1, dest="review_rounds",
                       help="rounds of visual review against the description (default 1; 0 skips)")
    p_gen.add_argument("--model", default=None, help="Claude model (default: claude-opus-5-5)")
    p_gen.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"])

    p_cad = sub.add_parser("cad", help="build a part script: BREP, STEP, STL and PNG views")
    p_cad.add_argument("script", type=Path)
    p_cad.add_argument("--out", type=Path, required=True, help="run directory")

    p_view = sub.add_parser("view", help="render a BREP or STL to a shaded PNG")
    p_view.add_argument("source", type=Path)
    p_view.add_argument("--out", type=Path)
    p_view.add_argument("--view", default="iso")

    p_build = sub.add_parser("build", help="build one catalogue part by its designation, "
                                           "e.g. PB6/chassis/lid")
    p_build.add_argument("designation", help="<product>/<assembly>/.../<part>, or "
                                             "library/<category>/<item>/...")
    p_build.add_argument("--root", type=Path, default=Path("products"),
                         help="the catalogue (default: products)")
    p_build.add_argument("--library", type=Path, default=None,
                         help="the parts library (default: library/ beside the catalogue)")
    p_build.add_argument("--out", type=Path, default=Path("results"),
                         help="where parts are built; this one goes to <out>/<designation> "
                              "(default: results)")

    p_site = sub.add_parser("site", help="build every part in the products/ tree and render "
                                         "the catalogue site")
    p_site.add_argument("root", type=Path, nargs="?", default=Path("products"),
                        help="<product>/<assembly>/.../<part>/part.py tree (default: products)")
    p_site.add_argument("--out", type=Path, default=Path("results"),
                        help="where the parts are built (default: results)")
    p_site.add_argument("--site", type=Path, default=Path("site"))
    p_site.add_argument("--library", type=Path, default=None,
                        help="the parts library (default: library/ beside the catalogue)")

    args = parser.parse_args(argv)

    if args.command == "build":
        from .catalog import find
        from .pipeline import run_script

        try:
            entry = find(args.root, args.designation, args.library)
        except (OSError, KeyError, ValueError) as exc:
            parser.error(f"build: {exc}")
        out = entry.out_dir(args.out)
        result = run_script(entry.script, out)
        if not result.ok:
            print(f"error: {entry.address}: {result.error}", file=sys.stderr)
            return 1
        print(f"built {entry.address}")
        _print_build(out, result.summary, result.files)
        return 0

    if args.command == "site":
        from .catalog import main as catalog_main

        rest = [str(args.root), "--out", str(args.out), "--site", str(args.site)]
        if args.library:
            rest += ["--library", str(args.library)]
        return catalog_main(rest)

    if args.command == "generate":
        from . import nl2cad
        from .pipeline import run_description

        if (args.text is None) == (args.description is None):
            parser.error("generate: give the description as text or as --description, not both")
        description = args.text if args.text is not None else args.description.read_text()
        if not description.strip():
            parser.error("generate: the description is empty")
        import anthropic

        model = args.model or nl2cad.MODEL
        coder = nl2cad.ClaudeCoder(model=model, effort=args.effort or nl2cad.EFFORT)
        try:
            generation = run_description(description, args.out, coder,
                                         max_attempts=args.max_attempts,
                                         review_rounds=args.review_rounds, model=model)
        except nl2cad.GenerationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        except anthropic.APIError as exc:
            print(f"error: the Claude API call failed: {exc}", file=sys.stderr)
            return 1
        except TypeError as exc:  # the SDK found no credentials
            if "authentication" not in str(exc):
                raise
            print("error: no Anthropic credentials; set ANTHROPIC_API_KEY or run "
                  "`ant auth login`", file=sys.stderr)
            return 1
        print(f"script: {args.out / 'part.py'}"
              + (" (approved on review)" if generation.approved else ""))
        _print_build(args.out, generation.build.summary,
                     {k: args.out / "cad" / p.name for k, p in generation.build.files.items()})
        return 0

    if args.command == "cad":
        from .pipeline import run_script

        result = run_script(args.script, args.out)
        if not result.ok:
            print(f"error: {args.script}: {result.error}", file=sys.stderr)
            return 1
        _print_build(args.out, result.summary, result.files)
        return 0

    if args.command == "view":
        from .cadview import main as view_main

        rest = [str(args.source), "--view", args.view]
        if args.out:
            rest += ["--out", str(args.out)]
        return view_main(rest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
