from pathlib import Path

from typer.testing import CliRunner

from cadence.commands import app

LAB = Path(__file__).resolve().parents[2] / "examples" / "lab"
runner = CliRunner()

# check requires a marked region: without one, the model's reply would
# replace the whole file.
MARKED = "# CADENCE:BEGIN\n%s\n# CADENCE:END\n"


class TestCheck:
    def test_a_real_repo_passes(self):
        result = runner.invoke(app, ["check", str(LAB)])
        assert result.exit_code == 0, result.output

    def test_it_runs_the_baseline_and_reports_the_metric(self):
        assert "value = 0" in runner.invoke(app, ["check", str(LAB)]).output

    def test_it_says_it_is_ready(self):
        assert "ready" in runner.invoke(app, ["check", str(LAB)]).output

    def test_a_directory_with_no_manifest_fails(self, tmp_path):
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1

    def test_a_missing_program_fails_before_anything_runs(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: gone.py\nmetrics: {v: maximize}\n"
        )
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1
        assert "gone.py" in result.output

    def test_a_program_that_never_reports_the_metric_fails(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {absent: maximize}\n"
        )
        (tmp_path / "p.py").write_text(MARKED % "print('done')")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1
        assert "absent" in result.output

    def test_an_unknown_method_names_the_known_ones(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {v: maximize}\nmethod: {evolutin: {}}\n"
        )
        (tmp_path / "p.py").write_text(MARKED % "print('v: 1')")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1


class TestCheckAsksAboutTheProjectNotTheMachine:
    def test_it_passes_without_any_credentials(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {v: maximize}\nmodel: {gemini: {}}\n"
        )
        (tmp_path / "p.py").write_text(MARKED % "print('v: 1')")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_it_never_mentions_a_key(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {v: maximize}\nmodel: {gemini: {}}\n"
        )
        (tmp_path / "p.py").write_text(MARKED % "print('v: 1')")
        assert "key" not in runner.invoke(app, ["check", str(tmp_path)]).output


class TestSchema:
    def test_it_prints_json_schema(self):
        import json

        result = runner.invoke(app, ["schema"])
        assert json.loads(result.output)["required"] == [
            "api_version",
            "program",
            "metrics",
        ]


class TestRun:
    def test_it_needs_a_manifest(self, tmp_path):
        assert runner.invoke(app, ["run", str(tmp_path)]).exit_code == 1


class TestRunFailsWithAMessageNotATraceback:
    """`experiment.run()` used to sit outside the try, so anything it raised
    reached the user as a traceback."""

    def _run(self, tmp_path, program):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\n"
            "program: p.py\n"
            "metrics: {value: maximize}\n"
            "budget: {trials: 1}\n"
        )
        (tmp_path / "p.py").write_text(program)
        return runner.invoke(app, ["run", str(tmp_path)])

    WORKS = "# CADENCE:BEGIN\nx = 1\n# CADENCE:END\nprint('value: 1')\n"

    def test_a_failed_run_exits_one(self, tmp_path):
        assert self._run(tmp_path, self.WORKS).exit_code == 1

    def test_it_explains_itself(self, tmp_path):
        assert "ran out of responses" in self._run(tmp_path, self.WORKS).output

    def test_it_leaves_no_traceback(self, tmp_path):
        result = self._run(tmp_path, self.WORKS)
        assert isinstance(result.exception, SystemExit)
        assert "Traceback" not in result.output


class TestCheckSaysWhatItVerified:
    def _project(self, tmp_path, extra="", program="print('value: 1')"):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {value: maximize}\n" + extra
        )
        (tmp_path / "p.py").write_text(MARKED % program)
        return runner.invoke(app, ["check", str(tmp_path)])

    def test_it_names_the_lines_the_model_may_rewrite(self, tmp_path):
        assert "lines 2-2" in self._project(tmp_path).output

    def test_it_shows_the_options_the_method_was_built_with(self, tmp_path):
        assert "size=8, tournament=3" in self._project(tmp_path).output

    def test_it_names_the_objective_it_derived(self, tmp_path):
        assert "weighted_sum" in self._project(tmp_path).output

    def test_it_says_the_metric_and_which_way_is_better(self, tmp_path):
        output = self._project(tmp_path).output
        assert "value = 1" in output
        assert "maximize is better" in output

    def test_it_says_when_guidance_is_missing(self, tmp_path):
        assert "no IMPROVE.md" in self._project(tmp_path).output

    def test_findings_go_to_stdout_and_the_verdict_to_stderr(self, tmp_path):
        # CliRunner merges the streams, so assert both halves are present.
        output = self._project(tmp_path).output
        assert "manifest" in output
        assert "ready." in output


class TestCheckCatchesWhatItUsedToWaveThrough:
    def test_an_unmarked_program_fails(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\nmetrics: {v: maximize}\n"
        )
        (tmp_path / "p.py").write_text("print('v: 1')")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1
        assert "CADENCE:BEGIN" in result.output

    def test_two_begin_markers_fail(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\nmetrics: {v: maximize}\n"
        )
        (tmp_path / "p.py").write_text(
            "# CADENCE:BEGIN\nx = 1\n# CADENCE:BEGIN\ny = 2\n# CADENCE:END\n"
        )
        assert runner.invoke(app, ["check", str(tmp_path)]).exit_code == 1

    def test_a_mistyped_method_option_fails_here_not_at_run_time(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {value: maximize}\nmethod: {evolution: {sizee: 12}}\n"
        )
        (tmp_path / "p.py").write_text(MARKED % "print('value: 1')")
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1
        assert "sizee" in result.output

    def test_it_suggests_the_option_that_was_meant(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: p.py\n"
            "metrics: {value: maximize}\nmethod: {evolution: {sizee: 12}}\n"
        )
        (tmp_path / "p.py").write_text(MARKED % "print('value: 1')")
        output = runner.invoke(app, ["check", str(tmp_path)]).output
        # Cadence writes this, not CPython: the interpreter only started
        # suggesting keyword arguments in 3.12, and never lists the rest.
        assert "has no option 'sizee'" in output
        assert "Did you mean 'size'?" in output
        assert "Options: size, tournament" in output
