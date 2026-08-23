import runpy
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2] / "examples" / "lab"


def run_demo(capsys):
    sys.path.insert(0, str(LAB))
    try:
        runpy.run_path(str(LAB / "demo.py"), run_name="__main__")
    finally:
        sys.path.remove(str(LAB))
    return capsys.readouterr().out


def test_the_demo_improves_the_program(capsys):
    printed = run_demo(capsys)
    assert "scored   value 45" in printed


def test_it_shows_the_program_it_ended_with(capsys):
    assert "def pack(items, capacity):" in run_demo(capsys)


def test_it_shows_a_rejected_patch_rather_than_hiding_it(capsys):
    assert "rejected" in run_demo(capsys)
