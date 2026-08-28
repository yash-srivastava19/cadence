import json
import re

import pytest

from cadence.errors import MetricNotReported
from cadence.parsing.metrics import JsonReport, KeyValueLines, direction, read

TRAINING_LOG = """\
step 100  loss 4.21
step 200  loss 3.02
done in 41s
val_bpb: 1.2734
"""


@pytest.fixture(params=["json", "lines"])
def reader(request):
    """Both ways a program is allowed to report its numbers."""
    return JsonReport() if request.param == "json" else KeyValueLines()


def as_reported(reader, metrics):
    """The same metrics, written the way that reader expects to find them."""
    if isinstance(reader, JsonReport):
        return json.dumps(metrics)
    return "\n".join(f"{name}: {value}" for name, value in metrics.items())


class TestAnyReader:
    """What every reader must do. A third way of reporting numbers is added
    to the fixture above and inherits all of it."""

    def test_it_finds_what_was_reported(self, reader):
        assert reader.read(as_reported(reader, {"value": 1.5})) == {"value": 1.5}

    def test_it_finds_several_at_once(self, reader):
        written = as_reported(reader, {"value": 1.5, "weight": 2.0})
        assert reader.read(written) == {"value": 1.5, "weight": 2.0}

    def test_empty_output_reports_nothing(self, reader):
        assert reader.read("") == {}

    def test_output_with_no_numbers_in_it_reports_nothing(self, reader):
        assert reader.read("training finished\nall done\n") == {}

    def test_it_survives_being_surrounded_by_noise(self, reader):
        written = f"starting up\n{as_reported(reader, {'value': 1.5})}\ndone\n"
        assert reader.read(written) == {"value": 1.5}

    def test_it_says_how_to_report_a_metric_that_is_missing(self, reader):
        assert "value" in reader.shape("value")


class TestReadingWhatAProgramPrinted:
    def test_a_named_number_is_found(self):
        assert read(TRAINING_LOG, ["val_bpb"]) == {"val_bpb": 1.2734}

    def test_equals_works_as_well_as_colon(self):
        assert read("accuracy = 0.91\n", ["accuracy"]) == {"accuracy": 0.91}

    def test_the_last_report_wins(self):
        assert read("loss: 9\nloss: 2\n", ["loss"]) == {"loss": 2.0}

    def test_several_metrics_come_back_together(self):
        printed = "loss: 0.5\nacc: 0.9\n"
        assert read(printed, ["loss", "acc"]) == {"loss": 0.5, "acc": 0.9}

    def test_only_what_was_asked_for_comes_back(self):
        assert read("loss: 0.5\nnoise: 99\n", ["loss"]) == {"loss": 0.5}

    def test_scientific_notation_is_a_number(self):
        assert read("lr: 3e-4\n", ["lr"]) == {"lr": 0.0003}

    def test_a_negative_number_is_a_number(self):
        assert read("delta: -1.5\n", ["delta"]) == {"delta": -1.5}

    def test_prose_around_it_is_ignored(self):
        assert read("Training finished.\nval_bpb: 1.0\nBye.\n", ["val_bpb"])


class TestJsonIsPreferredWhenPresent:
    def test_a_json_line_is_read(self):
        assert read('{"val_bpb": 1.5}\n', ["val_bpb"]) == {"val_bpb": 1.5}

    def test_json_wins_over_a_stray_log_line(self):
        printed = 'val_bpb: 9.9\n{"val_bpb": 1.5}\n'
        assert read(printed, ["val_bpb"]) == {"val_bpb": 1.5}

    def test_broken_json_falls_back_to_lines(self):
        printed = "{not json\nval_bpb: 1.5\n"
        assert read(printed, ["val_bpb"]) == {"val_bpb": 1.5}


class TestWhenTheNumberIsMissing:
    def test_it_says_which_metric(self):
        with pytest.raises(MetricNotReported, match="val_bpb"):
            read("nothing useful here\n", ["val_bpb"])

    def test_it_says_how_to_report_one(self):
        with pytest.raises(MetricNotReported, match=re.escape("val_bpb: 1.23")):
            read("", ["val_bpb"])

    def test_one_missing_metric_fails_the_whole_reading(self):
        with pytest.raises(MetricNotReported, match="acc"):
            read("loss: 1.0\n", ["loss", "acc"])

    def test_a_word_is_not_a_number(self):
        with pytest.raises(MetricNotReported):
            read("val_bpb: unknown\n", ["val_bpb"])


class TestGoals:
    def test_minimize_points_down(self):
        assert direction("minimize") == -1.0

    def test_maximize_points_up(self):
        assert direction("maximize") == 1.0

    def test_anything_else_is_refused(self):
        with pytest.raises(ValueError, match="minimize or maximize"):
            direction("lower")


class TestJsonIsTheContract:
    def test_a_json_object_wins_over_lines_that_disagree(self):
        """The line reader matches a stray `progress: 0.5`. Merging the two
        would let a log line overwrite what the program deliberately printed,
        and the search would optimize toward the noise."""
        stdout = 'value: 0.5\n{"value": 9.0}'
        assert read(stdout, ["value"]) == {"value": 9.0}

    def test_lines_are_not_consulted_to_fill_a_gap_in_the_json(self):
        stdout = 'value: 0.5\nother: 2.0\n{"value": 9.0}'
        with pytest.raises(MetricNotReported, match="other"):
            read(stdout, ["value", "other"])

    def test_lines_are_read_when_there_is_no_json_at_all(self):
        assert read("value: 0.5\n", ["value"]) == {"value": 0.5}
