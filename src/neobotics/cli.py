"""Command line: ``neobotics generate | cad | view | site``.

    # NL -> CadQuery script -> BREP / STEP / STL / PNG, with Claude
    neobotics generate --description designs/gripper/description.md --out results/gripper
    neobotics generate "a 40 x 40 x 5 mm plate with four M3 holes" --out results/plate

    # only the CAD stage, for a script written or edited by hand
    neobotics cad examples/motor_mount/part.py --out results/motor_mount

    # a shaded PNG of any BREP or STL
    neobotics view results/motor_mount/cad/part.stl

    # a static HTML site of built parts (what GitHub Pages serves)
    neobotics site results/motor_mount results/gripper --site site
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

    p_site = sub.add_parser("site", help="render built parts as a static HTML site")
    p_site.add_argument("runs", type=Path, nargs="+", help="run directories holding cad/")
    p_site.add_argument("--site", type=Path, default=Path("site"))

    args = parser.parse_args(argv)

    if args.command == "site":
        from .site import build_site, read_part

        try:
            index = build_site([read_part(r) for r in args.runs], args.site)
        except (OSError, ValueError) as exc:
            parser.error(f"site: {exc}")
        print(f"site: {index}")
        return 0

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
