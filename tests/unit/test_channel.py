import logging

import pytest
from pydantic import ValidationError

from cadence.observe.channel import Channel, Fact

lab = Channel("lab")


class Measured(Fact, channel=lab):
    reading: float


class Calibrated(Fact, channel=lab):
    offset: float


class TestPublishing:
    def test_a_subscriber_receives_what_was_published(self):
        seen = []
        stop = lab.subscribe(seen.append)
        Measured(reading=1.0).emit()
        stop()
        assert [fact.reading for fact in seen] == [1.0]

    def test_a_subscriber_can_ask_for_one_kind(self):
        seen = []
        stop = lab.subscribe(seen.append, to=Measured)
        Measured(reading=1.0).emit()
        Calibrated(offset=0.5).emit()
        stop()
        assert len(seen) == 1

    def test_unsubscribing_stops_delivery(self):
        seen = []
        stop = lab.subscribe(seen.append)
        stop()
        Measured(reading=1.0).emit()
        assert seen == []

    def test_publishing_with_nobody_listening_is_fine(self):
        Measured(reading=1.0).emit()

    def test_two_channels_do_not_hear_each_other(self):
        other = Channel("other")

        class Elsewhere(Fact, channel=other):
            pass

        seen = []
        stop = lab.subscribe(seen.append)
        Elsewhere().emit()
        stop()
        assert seen == []


class TestOneSubscriberCannotBreakAnother:
    def test_a_failing_subscriber_does_not_reach_the_publisher(self):
        stop = lab.subscribe(_explode)
        Measured(reading=1.0).emit()
        stop()

    def test_a_failing_subscriber_does_not_stop_the_others(self):
        seen = []
        stops = [lab.subscribe(_explode), lab.subscribe(seen.append)]
        Measured(reading=1.0).emit()
        for stop in stops:
            stop()
        assert len(seen) == 1

    def test_a_failing_subscriber_is_logged(self, caplog):
        stop = lab.subscribe(_explode)
        with caplog.at_level(logging.ERROR, logger="cadence.observe.channel"):
            Measured(reading=1.0).emit()
        stop()
        assert "boom" in caplog.text


class TestRecording:
    def test_a_recording_collects_in_order(self):
        with lab.recording() as tape:
            Measured(reading=1.0).emit()
            Calibrated(offset=0.5).emit()
        assert [type(fact).__name__ for fact in tape] == ["Measured", "Calibrated"]

    def test_a_recording_stops_at_the_end_of_the_block(self):
        with lab.recording() as tape:
            Measured(reading=1.0).emit()
        Measured(reading=2.0).emit()
        assert len(tape) == 1

    def test_a_recording_can_watch_one_kind(self):
        with lab.recording(to=Calibrated) as tape:
            Measured(reading=1.0).emit()
            Calibrated(offset=0.5).emit()
        assert len(tape) == 1

    def test_what_was_recorded_can_be_filtered_afterwards(self):
        with lab.recording() as tape:
            Measured(reading=1.0).emit()
            Calibrated(offset=0.5).emit()
        assert len(tape.of(Measured)) == 1

    def test_two_recordings_both_see_the_same_fact(self):
        with lab.recording() as one, lab.recording() as two:
            Measured(reading=1.0).emit()
        assert len(one) == len(two) == 1


class TestFactsAreFacts:
    def test_a_fact_cannot_be_edited(self):
        fact = Measured(reading=1.0)
        with pytest.raises(ValidationError):
            fact.reading = 2.0

    def test_a_fact_stamps_itself(self):
        assert Measured(reading=1.0).at.tzinfo is not None

    def test_a_fact_refuses_a_field_nobody_declared(self):
        with pytest.raises(ValidationError):
            Measured(reading=1.0, oops=True)

    def test_a_fact_survives_json(self):
        fact = Measured(reading=1.0)
        assert Measured.model_validate_json(fact.model_dump_json()) == fact

    def test_a_fact_with_no_channel_says_so(self):
        class Homeless(Fact):
            pass

        with pytest.raises(AttributeError):
            Homeless().emit()


def _explode(fact):
    raise RuntimeError("boom")


class TestTheOneListenerThatMustSucceed:
    """A progress bar failing must not end a run. The event log failing must:
    a run that carries on past a lost write produces an audit trail with holes
    that nobody knows are there."""

    def test_a_recorder_sees_every_fact(self):
        channel = Channel("probe")
        kept = []
        channel.record(kept.append)
        channel.publish(Measured(reading=1.0))
        assert len(kept) == 1

    def test_a_failing_recorder_stops_the_publisher(self):
        channel = Channel("probe")

        def cannot_write(fact):
            raise RuntimeError("the database is down")

        channel.record(cannot_write)
        with pytest.raises(RuntimeError, match="database is down"):
            channel.publish(Measured(reading=1.0))

    def test_a_failing_recorder_means_no_subscriber_is_told(self):
        """What has not been written down has not happened."""
        channel = Channel("probe")
        seen = []
        channel.subscribe(seen.append)
        channel.record(_explode)
        with pytest.raises(RuntimeError):
            channel.publish(Measured(reading=1.0))
        assert seen == []

    def test_a_failing_subscriber_still_does_not_stop_a_run(self):
        channel = Channel("probe")
        kept = []
        channel.record(kept.append)
        channel.subscribe(_explode)
        channel.publish(Measured(reading=1.0))
        assert len(kept) == 1

    def test_a_second_recorder_is_refused(self):
        channel = Channel("probe")
        channel.record(lambda fact: None)
        with pytest.raises(RuntimeError, match="already has a recorder"):
            channel.record(lambda fact: None)

    def test_a_recorder_can_step_down(self):
        channel = Channel("probe")
        stop = channel.record(_explode)
        stop()
        channel.publish(Measured(reading=1.0))
        channel.record(lambda fact: None)
