from pathlib import Path

from cadence.control.manifest import load
from cadence.control.registry import build

LAB = Path(__file__).parents[2] / "examples" / "lab"


def test_a_run_records_the_manifest_it_was_given(tmp_path: Path) -> None:
    """Under --config the recorded text is the arm's, not <root>/.cadence."""
    for name in (".cadence", "pack.py", "items.py", "IMPROVE.md"):
        (tmp_path / name).write_text((LAB / name).read_text())
    arm = tmp_path / "arm.cadence"
    arm.write_text((LAB / ".cadence").read_text() + "\n# the arm\n")

    experiment = build(load(arm), tmp_path, "r2", source=arm)

    assert experiment.manifest.source.endswith("# the arm")
