"""Natural language -> CadQuery part script, with Claude.

The model writes the part script (:mod:`neobotics.part` describes the
contract); this module only talks to it and keeps the conversation.  The loop
is one append-only conversation:

1. the description goes in, a complete script in one ```python block comes out;
2. the script is built in a child process (:func:`neobotics.part.build_part`);
   if it fails, the error goes back and the model sends a corrected script —
   up to ``max_attempts`` scripts in all;
3. once it builds, the two shaded views and the measured summary (bounding
   box, volume, faces) go back for review against the description; the model
   answers ``APPROVED`` or sends a revised script, which is built as in 2 —
   up to ``review_rounds`` reviews.

The model is reached through a :class:`Coder`, so tests (and other backends)
can stand in for Claude without a network.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

#: The model that writes the scripts.
MODEL = "claude-opus-5-5"
#: Reasoning depth: code generation is intelligence-sensitive.
EFFORT = "high"
#: Output budget per reply; streaming, so a long script never hits a timeout.
MAX_TOKENS = 64000
#: The reviewer's word for "the part matches the description".
APPROVED = "APPROVED"

SYSTEM_PROMPT = """\
You are a mechanical design engineer who writes CadQuery (Python) scripts. \
Each script builds one part as an exact B-rep solid from a natural-language \
description.

The script contract:
- Import only `cadquery as cq` and, if needed, `math`. No file I/O, no network, \
no other imports, no `show_object` outside the guard below.
- Start with a docstring: what the part is, then every assumption you made where \
the description is silent or ambiguous (dimensions, tolerances, which way a \
feature faces) — a person reads this to check your interpretation.
- Next, every dimension as a named constant in millimetres, with a short comment. \
Derive the geometry from these constants only; no magic numbers further down.
- Model with z up and the part standing on the z = 0 plane, centred on the z axis \
unless the description puts it elsewhere.
- Assign the finished part to `result` (a cq.Workplane or cq.Shape holding one \
valid solid, unless the description asks for separate bodies).
- Assign `regions`, a dict naming the places another stage will refer to — \
mounting faces, bolt holes, bores, shaft axes, contact surfaces — each a \
selection of faces, edges or vertices of `result` (e.g. \
`result.faces("<Z")`, `result.faces("%CYLINDER")`). Use an empty dict if none \
make sense.
- End with:
  if "show_object" in globals():  # CQ-editor
      show_object(result, name="part")

Prefer robust CadQuery idioms: build from sketches and workplanes, union and cut \
whole solids, and add fillets and chamfers last, on explicit selections, sized \
well below the wall thickness they sit on. Clearance holes for metric screws use \
the ISO medium series (M3 -> 3.4 mm, M4 -> 4.5 mm, M5 -> 5.5 mm) unless told \
otherwise.

Reply with the complete script in exactly one ```python fenced block. Before it, \
at most a few sentences on your approach; nothing after it."""

REPAIR_PROMPT = """\
The script failed to build:

{error}

Fix the cause and reply with the complete corrected script in one ```python block."""

REVIEW_PROMPT = """\
The script built. Above are two shaded views of the part (z up): from the front \
(-y), right (+x) and above, and from the opposite corner below. Measured from the B-rep:

{summary}

Check the part against the original description: overall size, every feature, \
its position, count and orientation, and that nothing is missing or extra. If it \
matches, reply with exactly {approved} and nothing else. Otherwise list what is \
wrong in a sentence or two and reply with the complete corrected script in one \
```python block."""

_CODE_BLOCK = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)


class GenerationError(RuntimeError):
    """The model could not produce a part that builds."""


class Coder(Protocol):
    """Sends a conversation, returns (the reply's text, the content to append)."""

    def __call__(self, system: str, messages: list[dict[str, Any]]) -> tuple[str, Any]: ...


def extract_script(text: str) -> str | None:
    """The last fenced Python block of a reply, or None if there is none."""
    blocks = _CODE_BLOCK.findall(text)
    return blocks[-1].strip() + "\n" if blocks else None


def is_approved(text: str) -> bool:
    return text.strip().rstrip(".").upper() == APPROVED


@dataclass
class Attempt:
    """One script the model sent, and what came of building it."""

    number: int
    kind: str  # "initial", "repair" or "review"
    script: str | None
    ok: bool
    error: str | None = None
    reply: str = ""


@dataclass
class Generation:
    """The outcome of :func:`generate`."""

    script: str
    build: Any  # neobotics.part.BuildResult of the final script
    attempts: list[Attempt] = field(default_factory=list)
    approved: bool = False
    usage: dict[str, int] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Claude
# --------------------------------------------------------------------------
class ClaudeCoder:
    """A :class:`Coder` on the Claude API: streaming, adaptive thinking, and the
    server-side refusal fallback."""

    def __init__(self, model: str = MODEL, effort: str = EFFORT, client=None):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.usage: dict[str, int] = {}

    def __call__(self, system: str, messages: list[dict[str, Any]]) -> tuple[str, Any]:
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            response = stream.get_final_message()
        self._count(response.usage)
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise GenerationError(f"the model declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            raise GenerationError("the reply was cut off at max_tokens before the script ended")
        text = "".join(b.text for b in response.content if b.type == "text")
        # the whole content goes back, thinking blocks included, unchanged
        return text, response.content

    def _count(self, usage) -> None:
        for key in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                    "cache_creation_input_tokens"):
            value = getattr(usage, key, None)
            if isinstance(value, int):
                self.usage[key] = self.usage.get(key, 0) + value


# --------------------------------------------------------------------------
# the loop
# --------------------------------------------------------------------------
def _image_block(path: Path) -> dict[str, Any]:
    data = base64.standard_b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


def _format_summary(summary: dict[str, Any]) -> str:
    bb = summary["bounding_box"]
    lines = [
        f"- bounding box: x {bb['min'][0]:g} .. {bb['max'][0]:g}, "
        f"y {bb['min'][1]:g} .. {bb['max'][1]:g}, z {bb['min'][2]:g} .. {bb['max'][2]:g} "
        f"(size {bb['size'][0]:g} x {bb['size'][1]:g} x {bb['size'][2]:g} mm)",
        f"- volume: {summary['volume_mm3']:g} mm^3, surface area: {summary['surface_area_mm2']:g} mm^2",
        f"- solids: {summary['n_solids']}, faces: {summary['n_faces']} "
        f"({', '.join(f'{n} {k}' for k, n in summary['face_types'].items())})",
    ]
    regions = summary.get("regions") or {}
    if regions:
        lines.append("- regions: " + ", ".join(
            f"{name} ({r['count']} x {r['type']})" for name, r in regions.items()))
    else:
        lines.append("- regions: none")
    return "\n".join(lines)


def generate(
    description: str,
    work_dir: Path,
    coder: Coder,
    build: Callable[[Path, Path], Any],
    max_attempts: int = 4,
    review_rounds: int = 1,
    log: Callable[[str], None] = print,
) -> Generation:
    """Turn a description into a part script that builds, and build it.

    ``build(script_path, out_dir)`` is :func:`neobotics.part.build_part` (or a
    stand-in); every script the model sends is written to
    ``work_dir/attempts/NN.py`` and built into ``work_dir/attempts/NN/``.
    Raises :class:`GenerationError` when no script builds within
    ``max_attempts``.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    attempts_dir = Path(work_dir) / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    messages: list[dict[str, Any]] = [{"role": "user", "content": description.strip()}]
    attempts: list[Attempt] = []
    good: tuple[str, Any] | None = None  # the latest script that built, and its build
    reviews = 0
    kind = "initial"

    while True:
        log(f"[{len(attempts) + 1}] asking the model ({kind})")
        text, content = coder(SYSTEM_PROMPT, messages)
        messages.append({"role": "assistant", "content": content})

        if kind == "review" and is_approved(text):
            log("    reviewer approved the part")
            return Generation(good[0], good[1], attempts, approved=True)

        script = extract_script(text)
        number = len(attempts) + 1
        if script is None:
            error = "the reply has no ```python block with the script"
            attempts.append(Attempt(number, kind, None, False, error, text))
        else:
            path = attempts_dir / f"{number:02d}.py"
            path.write_text(script)
            result = build(path, attempts_dir / f"{number:02d}")
            attempts.append(Attempt(number, kind, script, result.ok, result.error, text))
            error = result.error
            if result.ok:
                good = (script, result)
        log(f"    {'built' if attempts[-1].ok else 'failed: ' + _last_line(error)}")

        if len(attempts) >= max_attempts and not attempts[-1].ok:
            if good is not None:  # a review revision broke; keep the last good part
                log("    out of attempts; keeping the last script that built")
                return Generation(good[0], good[1], attempts, approved=False)
            raise GenerationError(
                f"no script built in {max_attempts} attempts; last error:\n{error}")

        if not attempts[-1].ok:
            kind = "repair"
            messages.append({"role": "user", "content": REPAIR_PROMPT.format(error=error)})
            continue

        if reviews >= review_rounds:
            return Generation(good[0], good[1], attempts, approved=False)
        reviews += 1
        kind = "review"
        files = good[1].files
        messages.append({"role": "user", "content": [
            _image_block(files["png"]),
            _image_block(files["png_rear"]),
            {"type": "text", "text": REVIEW_PROMPT.format(
                summary=_format_summary(good[1].summary), approved=APPROVED)},
        ]})


def _last_line(text: str | None) -> str:
    return (text or "").strip().splitlines()[-1] if text and text.strip() else ""
