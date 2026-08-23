import runpy


def run_quickstart(capsys):
    runpy.run_module("examples.quickstart", run_name="__main__")
    return capsys.readouterr().out


def test_the_example_runs_and_improves_the_program(capsys):
    printed = run_quickstart(capsys)
    assert "value 0 -> 36" in printed
    assert "value 36 -> 45" in printed


def test_it_shows_the_program_it_ended_with(capsys):
    assert "def pack(items, capacity):" in run_quickstart(capsys)


def test_it_shows_a_rejected_patch_rather_than_hiding_it(capsys):
    assert "patch rejected" in run_quickstart(capsys)
