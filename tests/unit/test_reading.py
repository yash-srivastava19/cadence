import re

import pytest

from cadence.reading import MetricNotReported, direction, read

TRAINING_LOG = """\
step 100  loss 4.21
step 200  loss 3.02
done in 41s
val_bpb: 1.2734
"""


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
