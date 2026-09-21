import json
from pathlib import Path

from cadence.control.backends import Scripted
from cadence.control.manifest import load
from cadence.control.registry import build
from cadence.delivery.runlog import KINDS, RunLog
from cadence.observe.signals import Event, cadence

LAB = Path(__file__).parents[2] / "examples" / "lab"
GOOD = "```python\ndef pack(items, capacity):\n    return [0]\n```"


def _events() -> set[type[Event]]:
    found, todo = set(), [Event]
    while todo:
        for sub in todo.pop().__subclasses__():
            found.add(sub)
            todo.append(sub)
    return found


def test_every_field_of_every_event_has_a_kind() -> None:
    """A field nobody classified is a field that could leak."""
    for event in _events():
        assert event in KINDS, f"{event.__name__} has no entry in KINDS"
        missing = set(event.model_fields) - set(KINDS[event])
        assert not missing, f"{event.__name__} fields without a kind: {missing}"


def test_a_run_writes_one_line_per_step_and_no_code(tmp_path: Path) -> None:
    for name in (".cadence", "pack.py", "items.py", "IMPROVE.md"):
        (tmp_path / name).write_text((LAB / name).read_text())
    log = RunLog(tmp_path, env="test")
    stop = cadence.subscribe(log)
    try:
        build(load(tmp_path), tmp_path, "r1", backend=Scripted(GOOD, GOOD)).run()
    finally:
        stop()
        log.close()

    assert log.path == tmp_path / "cadence-runs" / "test" / "r1.jsonl"
    text = log.path.read_text()
    lines = [json.loads(line) for line in text.splitlines()]
    assert all(line["run"] == "r1" and line["message"] for line in lines)
    assert "def pack" not in text
    spans = [(line["span"], line["phase"]) for line in lines if line.get("trial")]
    assert spans[:2] == [("trial", "start"), ("model_call", "start")]
    assert ("trial", "end") in spans
    assert (tmp_path / "cadence-runs" / ".gitignore").read_text().endswith("*\n")


def test_every_line_carries_otel_ids_that_form_one_tree(tmp_path: Path) -> None:
    for name in (".cadence", "pack.py", "items.py", "IMPROVE.md"):
        (tmp_path / name).write_text((LAB / name).read_text())
    log = RunLog(tmp_path, env="test")
    stop = cadence.subscribe(log)
    try:
        build(load(tmp_path), tmp_path, "r3", backend=Scripted(GOOD, GOOD)).run()
    finally:
        stop()
        log.close()
    assert log.path is not None
    lines = [json.loads(line) for line in log.path.read_text().splitlines()]

    assert all(
        len(line["trace_id"]) == 32 and len(line["span_id"]) == 16 for line in lines
    )
    spans = {line["span_id"]: line for line in lines}
    for line in lines:
        if "parent_span_id" in line:
            parent = spans[line["parent_span_id"]]
            assert parent["trace_id"] == line["trace_id"]
    trial = [line for line in lines if line.get("trial") == "r3/0"]
    assert len({line["trace_id"] for line in trial}) == 1
