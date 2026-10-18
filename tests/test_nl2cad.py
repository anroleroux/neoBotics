"""The NL -> script loop, with a scripted stand-in for the model."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from neobotics import nl2cad
from neobotics.nl2cad import APPROVED, GenerationError, extract_script, generate, is_approved
from neobotics.pipeline import run_description

GOOD = """\
\"\"\"A 40 x 40 x 5 mm plate with four M3 holes.\"\"\"
import cadquery as cq

size = 40.0
thickness = 5.0
pitch = 30.0
m3_clearance = 3.4

result = (
    cq.Workplane("XY").box(size, size, thickness, centered=(True, True, False))
    .faces(">Z").workplane().rect(pitch, pitch, forConstruction=True).vertices()
    .hole(m3_clearance)
)
regions = {"top": result.faces(">Z"), "holes": result.faces("%CYLINDER")}
"""
BROKEN = "import cadquery as cq\nresult = cq.Workplane().box(40, 40, 5).fillet(30)\n"


def reply(script=None, prose="Here is the part."):
    return prose if script is None else f"{prose}\n\n```python\n{script}```\n"


class ScriptedCoder:
    """Returns canned replies in order and records every conversation it saw."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []
        self.usage = {"input_tokens": 10, "output_tokens": 5}

    def __call__(self, system, messages):
        self.seen.append([dict(m) for m in messages])
        text = self.replies.pop(0)
        return text, [{"type": "text", "text": text}]


def fake_build(ok_scripts):
    """A build that passes the scripts in ``ok_scripts`` and writes stub views."""

    def build(path, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        if path.read_text() not in ok_scripts:
            return SimpleNamespace(ok=False, error="boom: bad fillet", summary={}, files={})
        files = {}
        for kind in ("png", "png_rear", "script"):
            files[kind] = out_dir / f"{kind}.png"
            files[kind].write_bytes(b"\x89PNG stub")
        summary = {"bounding_box": {"min": [0, 0, 0], "max": [1, 1, 1], "size": [1, 1, 1]},
                   "volume_mm3": 1.0, "surface_area_mm2": 6.0, "n_solids": 1, "n_faces": 6,
                   "face_types": {"PLANE": 6}, "regions": {}}
        return SimpleNamespace(ok=True, error=None, summary=summary, files=files)

    return build


def test_extract_script_takes_the_last_python_block():
    text = "first\n```python\na = 1\n```\nthen\n```py\nb = 2\n```"
    assert extract_script(text) == "b = 2\n"
    assert extract_script("no code here") is None


@pytest.mark.parametrize("text, ok", [
    (APPROVED, True), (" approved.\n", True), ("APPROVED, but the holes are off", False),
])
def test_is_approved(text, ok):
    assert is_approved(text) is ok


def test_repairs_until_it_builds_then_review_approves(tmp_path):
    coder = ScriptedCoder(reply(BROKEN), reply(GOOD), APPROVED)
    gen = generate("a plate", tmp_path, coder, fake_build({GOOD}), log=lambda _: None)
    assert gen.approved and gen.script == GOOD
    assert [(a.kind, a.ok) for a in gen.attempts] == [("initial", False), ("repair", True)]
    # the failing build's error went back to the model, verbatim
    assert "boom: bad fillet" in coder.seen[1][-1]["content"]
    # the review carries both views and the measured summary
    review = coder.seen[2][-1]["content"]
    assert [b["type"] for b in review] == ["image", "image", "text"]
    assert "bounding box" in review[2]["text"]
    # every script is kept
    assert (tmp_path / "attempts" / "01.py").read_text() == BROKEN
    assert (tmp_path / "attempts" / "02.py").read_text() == GOOD


def test_conversation_is_append_only(tmp_path):
    coder = ScriptedCoder(reply(BROKEN), reply(GOOD), APPROVED)
    generate("a plate", tmp_path, coder, fake_build({GOOD}), log=lambda _: None)
    for earlier, later in zip(coder.seen, coder.seen[1:]):
        assert later[:len(earlier)] == earlier
    assert [m["role"] for m in coder.seen[-1]] == ["user", "assistant", "user", "assistant", "user"]


def test_review_revision_replaces_the_script(tmp_path):
    revised = GOOD.replace("pitch = 30.0", "pitch = 32.0")
    coder = ScriptedCoder(reply(GOOD), reply(revised, "The holes were too close."), APPROVED)
    gen = generate("a plate", tmp_path, coder, fake_build({GOOD, revised}),
                   review_rounds=2, log=lambda _: None)
    assert gen.approved and gen.script == revised
    assert [a.kind for a in gen.attempts] == ["initial", "review"]


def test_review_rounds_cap_the_loop(tmp_path):
    coder = ScriptedCoder(reply(GOOD), reply(GOOD))
    gen = generate("a plate", tmp_path, coder, fake_build({GOOD}), review_rounds=1,
                   log=lambda _: None)
    assert not gen.approved and len(gen.attempts) == 2 and not coder.replies


def test_no_review_returns_after_the_first_build(tmp_path):
    coder = ScriptedCoder(reply(GOOD))
    gen = generate("a plate", tmp_path, coder, fake_build({GOOD}), review_rounds=0,
                   log=lambda _: None)
    assert gen.script == GOOD and not gen.approved


def test_a_reply_without_code_counts_as_a_failed_attempt(tmp_path):
    coder = ScriptedCoder("I think a plate would be nice.", reply(GOOD))
    gen = generate("a plate", tmp_path, coder, fake_build({GOOD}), review_rounds=0,
                   log=lambda _: None)
    assert gen.attempts[0].error.startswith("the reply has no ```python block")
    assert gen.script == GOOD


def test_gives_up_after_max_attempts(tmp_path):
    coder = ScriptedCoder(reply(BROKEN), reply(BROKEN))
    with pytest.raises(GenerationError, match="no script built in 2 attempts"):
        generate("a plate", tmp_path, coder, fake_build(set()), max_attempts=2,
                 log=lambda _: None)


def test_a_broken_revision_keeps_the_last_good_part(tmp_path):
    coder = ScriptedCoder(reply(GOOD), reply(BROKEN, "Let me fix the holes."))
    gen = generate("a plate", tmp_path, coder, fake_build({GOOD}), max_attempts=2,
                   log=lambda _: None)
    assert gen.script == GOOD and not gen.approved


def test_claude_coder_request_shape():
    """The request ClaudeCoder sends, against a stand-in client."""
    captured = {}
    response = SimpleNamespace(
        stop_reason="end_turn", stop_details=None,
        content=[SimpleNamespace(type="thinking", thinking=""),
                 SimpleNamespace(type="text", text=reply(GOOD))],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50,
                              cache_read_input_tokens=0, cache_creation_input_tokens=0),
    )

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return response

    def stream(**kwargs):
        captured.update(kwargs)
        return Stream()

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    coder = nl2cad.ClaudeCoder(client=client)
    text, content = coder("sys", [{"role": "user", "content": "a plate"}])
    assert extract_script(text) == GOOD
    assert content is response.content  # thinking blocks go back unchanged
    assert captured["model"] == "claude-opus-5-5"
    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["fallbacks"] == "default"
    assert coder.usage["output_tokens"] == 50

    response.stop_reason = "refusal"
    response.stop_details = SimpleNamespace(category="cyber")
    with pytest.raises(GenerationError, match="declined"):
        coder("sys", [{"role": "user", "content": "a plate"}])


def test_run_description_end_to_end(tmp_path):
    """Description in, real CadQuery build, every artifact on disk."""
    coder = ScriptedCoder(reply(BROKEN), reply(GOOD), APPROVED)
    gen = run_description("A 40 x 40 x 5 mm plate with four M3 holes.", tmp_path, coder,
                          model="stand-in", log=lambda _: None)
    assert gen.approved
    assert (tmp_path / "part.py").read_text() == GOOD
    assert (tmp_path / "description.md").read_text().startswith("A 40 x 40")
    for name in ("part.brep", "part.step", "part.stl", "part.png", "part_rear_below.png",
                 "summary.json"):
        assert (tmp_path / "cad" / name).exists(), name
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["approved"] and manifest["model"] == "stand-in"
    assert [a["ok"] for a in manifest["attempts"]] == [False, True]
    assert manifest["summary"]["bounding_box"]["size"] == pytest.approx([40, 40, 5])
    assert manifest["summary"]["face_types"]["CYLINDER"] == 4
    assert "Attempt 1 (initial): failed" in (tmp_path / "transcript.md").read_text()
