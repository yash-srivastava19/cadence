import re
import textwrap
from pathlib import Path

import pytest

from cadence.control.manifest import Manifest, ManifestError, load

COMPLETE = """\
apiVersion: cadence/v1alpha1
program: pack.py
metrics: {value: maximize}
run: python pack.py
method:
  evolution:
    size: 8
objective:
  weighted_sum:
    value: 1.0
model:
  scripted: {}
budget:
  trials: 30
sandbox:
  seconds: 5
  memory_mb: 128
"""

MINIMAL = """\
apiVersion: cadence/v1alpha1
program: train.py
metrics: {val_bpb: minimize}
"""


def write(tmp_path, text, name=".cadence"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(text))
    return path


class TestReadingAManifest:
    def test_a_complete_manifest_loads(self, tmp_path):
        assert load(write(tmp_path, COMPLETE)).program == "pack.py"

    def test_a_directory_is_enough(self, tmp_path):
        write(tmp_path, COMPLETE)
        assert load(tmp_path).program == "pack.py"

    def test_a_repo_without_one_is_not_a_cadence_project(self, tmp_path):
        with pytest.raises(ManifestError, match="where a cadence project starts"):
            load(tmp_path)

    def test_broken_yaml_says_so(self, tmp_path):
        with pytest.raises(ManifestError, match="not valid YAML"):
            load(write(tmp_path, "apiVersion: [unclosed\n"))

    def test_a_list_is_not_a_manifest(self, tmp_path):
        with pytest.raises(ManifestError, match="should contain a mapping"):
            load(write(tmp_path, "- one\n- two\n"))


class TestTheVersionIsChecked:
    def test_a_missing_version_is_named(self, tmp_path):
        text = COMPLETE.replace("apiVersion: cadence/v1alpha1\n", "")
        with pytest.raises(ManifestError, match="apiVersion"):
            load(write(tmp_path, text))

    def test_an_unknown_version_lists_the_known_ones(self, tmp_path):
        text = COMPLETE.replace("cadence/v1alpha1", "cadence/v2")
        with pytest.raises(ManifestError, match="known versions: cadence/v1alpha1"):
            load(write(tmp_path, text))

    def test_the_message_names_the_version_that_was_given(self, tmp_path):
        text = COMPLETE.replace("cadence/v1alpha1", "cadence/v2")
        with pytest.raises(ManifestError, match="cadence/v2"):
            load(write(tmp_path, text))


class TestTyposAreErrorsNotDefaults:
    def test_an_unknown_top_level_key_is_refused(self, tmp_path):
        with pytest.raises(ManifestError, match="sandboxx"):
            load(write(tmp_path, COMPLETE + "sandboxx: {}\n"))

    def test_a_misspelled_budget_key_is_refused(self, tmp_path):
        text = COMPLETE.replace("  trials: 30", "  trial: 30")
        with pytest.raises(ManifestError, match="trial"):
            load(write(tmp_path, text))

    def test_every_problem_is_reported_at_once(self, tmp_path):
        text = MINIMAL + "budget: {trials: 0}\nsandbox: {memory_mb: -1}\n"
        with pytest.raises(ManifestError) as caught:
            load(write(tmp_path, text))
        assert "budget.trials" in str(caught.value)
        assert "sandbox.memory_mb" in str(caught.value)

    def test_an_empty_file_says_what_is_missing(self, tmp_path):
        with pytest.raises(ManifestError, match="apiVersion"):
            load(write(tmp_path, ""))

    def test_a_problem_says_where_it_is(self, tmp_path):
        text = COMPLETE.replace("  seconds: 5", "  seconds: -1")
        with pytest.raises(ManifestError, match=re.escape("sandbox.seconds")):
            load(write(tmp_path, text))


class TestDefaults:
    def test_three_lines_are_a_whole_manifest(self, tmp_path):
        manifest = load(write(tmp_path, MINIMAL))
        assert manifest.program == "train.py"
        assert manifest.metrics == {"val_bpb": "minimize"}

    def test_guidance_defaults_to_a_conventional_file(self, tmp_path):
        assert load(write(tmp_path, MINIMAL)).guidance == "IMPROVE.md"

    def test_no_task_module_is_needed(self, tmp_path):
        assert load(write(tmp_path, MINIMAL)).task is None

    def test_the_method_defaults(self, tmp_path):
        assert load(write(tmp_path, MINIMAL)).method.name == "evolution"

    def test_the_model_defaults(self, tmp_path):
        assert load(write(tmp_path, MINIMAL)).model.name == "scripted"

    def test_the_objective_is_left_to_be_inferred(self, tmp_path):
        assert load(write(tmp_path, MINIMAL)).objective is None

    def test_the_run_command_defaults_to_the_program(self, tmp_path):
        assert load(write(tmp_path, MINIMAL)).command == "python train.py"

    def test_a_run_command_may_be_given(self, tmp_path):
        text = MINIMAL + "run: uv run {program} --fast\n"
        assert load(write(tmp_path, text)).command == "uv run train.py --fast"

    def test_a_goal_must_be_minimize_or_maximize(self, tmp_path):
        text = MINIMAL.replace("minimize", "lower")
        with pytest.raises(ManifestError, match="metrics"):
            load(write(tmp_path, text))

    def test_at_least_one_metric_is_required(self, tmp_path):
        text = MINIMAL.replace("metrics: {val_bpb: minimize}", "metrics: {}")
        with pytest.raises(ManifestError, match="metrics"):
            load(write(tmp_path, text))

    def test_a_python_task_stays_available_for_the_hard_cases(self, tmp_path):
        text = MINIMAL + "task: verify:Knapsack\n"
        assert load(write(tmp_path, text)).task == "verify:Knapsack"

    def test_naming_an_objective_still_works(self, tmp_path):
        text = MINIMAL + "objective: {pareto: {value: 1, weight: -1}}\n"
        assert load(write(tmp_path, text)).objective.name == "pareto"

    def test_budget_and_sandbox_may_be_omitted(self, tmp_path):
        manifest = load(write(tmp_path, MINIMAL))
        assert manifest.budget.trials == 20
        assert manifest.sandbox.memory_mb == 256

    def test_what_is_given_wins(self, tmp_path):
        manifest = load(write(tmp_path, COMPLETE))
        assert manifest.budget.trials == 30
        assert manifest.sandbox.seconds == 5.0


class TestPlugins:
    def test_a_plugin_is_named_by_its_key(self, tmp_path):
        assert load(write(tmp_path, COMPLETE)).method.name == "evolution"

    def test_its_options_come_with_it(self, tmp_path):
        assert load(write(tmp_path, COMPLETE)).method.options == {"size": 8}

    def test_options_may_be_empty(self, tmp_path):
        text = MINIMAL + "method: {evolution: {}}\n"
        assert load(write(tmp_path, text)).method.options == {}

    def test_two_plugins_in_one_slot_is_an_error(self, tmp_path):
        text = MINIMAL + "method: {evolution: {}, hill: {}}\n"
        with pytest.raises(ManifestError, match="name exactly one"):
            load(write(tmp_path, text))

    def test_the_manifest_does_not_know_what_a_method_is(self):
        source = Path(Manifest.__module__.replace(".", "/") + ".py").read_text()
        assert "Evolution" not in source


class TestThePlan:
    def test_it_shows_what_was_resolved(self, tmp_path):
        plan = load(write(tmp_path, MINIMAL)).plan
        assert "evolution" in plan
        assert "20 trials" in plan
        assert "python train.py" in plan

    def test_it_says_which_way_the_metric_should_go(self, tmp_path):
        assert "minimize val_bpb" in load(write(tmp_path, MINIMAL)).plan

    def test_it_shows_defaults_that_were_filled_in(self, tmp_path):
        assert "256MB" in load(write(tmp_path, MINIMAL)).plan


class TestMarkers:
    def test_they_default_to_the_cadence_pair(self, tmp_path):
        markers = load(write(tmp_path, MINIMAL)).markers
        assert (markers.begin, markers.end) == ("CADENCE:BEGIN", "CADENCE:END")

    def test_they_can_be_changed(self, tmp_path):
        text = MINIMAL + "markers: {begin: EVOLVE-START, end: EVOLVE-END}\n"
        markers = load(write(tmp_path, text)).markers
        assert (markers.begin, markers.end) == ("EVOLVE-START", "EVOLVE-END")

    def test_only_one_of_them_may_be_changed(self, tmp_path):
        text = MINIMAL + "markers: {begin: START_BLOCK}\n"
        assert load(write(tmp_path, text)).markers.end == "CADENCE:END"

    def test_they_must_differ(self, tmp_path):
        text = MINIMAL + "markers: {begin: SAME, end: SAME}\n"
        with pytest.raises(ManifestError, match="must differ"):
            load(write(tmp_path, text))

    def test_a_blank_marker_is_refused(self, tmp_path):
        text = MINIMAL + "markers: {begin: '  '}\n"
        with pytest.raises(ManifestError, match=re.escape("markers.begin")):
            load(write(tmp_path, text))

    def test_the_plan_shows_them(self, tmp_path):
        assert "CADENCE:BEGIN .. CADENCE:END" in load(write(tmp_path, MINIMAL)).plan
