"""Who the output is for, and how the commands decide.

clig.dev's rule: be human-readable by default, machine-readable when the
output is not going to a human. Nothing else in cadence gets to ask.
"""

from cadence.commands.reading import wanted_json


class TestWhoIsReading:
    def test_json_is_asked_for(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert wanted_json(True) is True

    def test_and_can_be_refused(self, monkeypatch):
        """--no-json is for someone who wants the table in a file."""
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert wanted_json(False) is False

    def test_a_terminal_gets_the_table(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert wanted_json(None) is False

    def test_a_pipe_gets_json(self, monkeypatch):
        """A pipe, a log and a CI job all want JSON and none of them can say
        so. Not being a terminal is the only signal there is."""
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert wanted_json(None) is True
