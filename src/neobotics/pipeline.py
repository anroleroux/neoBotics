"""The NL -> B-rep code -> CAD pipeline, end to end, into one run directory.

    <run>/
      description.md      the natural-language input, as given
      part.py             the CadQuery script that built the part (the B-rep code)
      cad/                part.brep, part.step, part.stl, part.png,
                          part_rear_below.png, summary.json
      attempts/NN.py      every script the model sent, and NN/ its build
      transcript.md       the model's replies, in order
      manifest.json       model, attempts, review verdict, token usage, summary

:func:`run_description` runs all of it; :func:`run_script` only the last
stage, for a part script written (or edited) by hand.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .nl2cad import Coder, Generation, generate
from .part import BuildResult, build_part


def run_script(script: Path, out_dir: Path) -> BuildResult:
    """Build a part script into ``out_dir/cad``.

    The script is copied into ``out_dir`` under its own name (``part.py`` or
    ``assembly.py``), and a ``description.md`` next to it (a design
    directory) to ``out_dir/description.md``.
    """
    script, out_dir = Path(script), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = build_part(script, out_dir / "cad")
    if result.ok:
        for source, target in ((script, out_dir / script.name),
                               (script.parent / "description.md", out_dir / "description.md")):
            if source.exists() and source.resolve() != target.resolve():
                shutil.copyfile(source, target)
    return result


def run_description(
    description: str,
    out_dir: Path,
    coder: Coder,
    *,
    max_attempts: int = 4,
    review_rounds: int = 1,
    model: str | None = None,
    log: Callable[[str], None] = print,
) -> Generation:
    """Generate a part script from ``description`` and build it into ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "description.md").write_text(description.strip() + "\n")

    generation = generate(description, out_dir, coder, build_part,
                          max_attempts=max_attempts, review_rounds=review_rounds, log=log)
    generation.usage = dict(getattr(coder, "usage", {}) or {})

    (out_dir / "part.py").write_text(generation.script)
    cad = out_dir / "cad"
    if cad.exists():
        shutil.rmtree(cad)
    shutil.copytree(generation.build.files["script"].parent, cad)

    _write_transcript(out_dir / "transcript.md", generation)
    manifest = {
        "model": model,
        "approved": generation.approved,
        "attempts": [
            {k: v for k, v in asdict(a).items() if k not in ("script", "reply")}
            for a in generation.attempts
        ],
        "usage": generation.usage,
        "summary": generation.build.summary,
        "files": {k: str(Path("cad") / p.name) for k, p in generation.build.files.items()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return generation


def _write_transcript(path: Path, generation: Generation) -> None:
    parts = ["# Transcript\n"]
    for a in generation.attempts:
        status = "built" if a.ok else f"failed — {a.error}"
        parts.append(f"## Attempt {a.number} ({a.kind}): {status}\n\n{a.reply.strip()}\n")
    if generation.approved:
        parts.append("## Review\n\nAPPROVED\n")
    path.write_text("\n".join(parts))
