"""What .env means, and what it does not mean."""

import os

from cadence.commands.environment import load_env, read_env


class TestReadingTheFile:
    def test_a_plain_assignment(self):
        assert read_env("NAME=value\n") == {"NAME": "value"}

    def test_export_is_allowed_because_people_paste_it(self):
        assert read_env("export NAME=value\n") == {"NAME": "value"}

    def test_quotes_come_off(self):
        assert read_env("A=\"one\"\nB='two'\n") == {"A": "one", "B": "two"}

    def test_a_hash_inside_quotes_is_part_of_the_value(self):
        """Which is the whole reason quotes are handled at all: a password
        with a # in it is not a comment."""
        assert read_env('PASSWORD="hunt#er2"\n') == {"PASSWORD": "hunt#er2"}

    def test_a_trailing_comment_is_not_part_of_an_unquoted_value(self):
        assert read_env("PORT=5433 # the mapped one\n") == {"PORT": "5433"}

    def test_a_url_keeps_its_fragment(self):
        # `#` only starts a comment after a space, the way compose reads it.
        assert read_env("U=postgres://a@b/c#frag\n") == {"U": "postgres://a@b/c#frag"}

    def test_comments_and_blank_lines_are_skipped(self):
        assert read_env("# a note\n\nNAME=value\n") == {"NAME": "value"}

    def test_a_line_with_no_equals_is_skipped_rather_than_guessed_at(self):
        assert read_env("this is not an assignment\n") == {}

    def test_a_name_that_is_not_a_name_is_skipped(self):
        assert read_env("not-a-name=value\n") == {}

    def test_no_interpolation(self):
        """A shell is not being emulated; a value that looks like it wants
        expanding is passed through as written."""
        assert read_env("A=$HOME\n") == {"A": "$HOME"}


class TestLoadingIt:
    def test_it_fills_in_what_is_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CADENCE_TEST_VALUE", raising=False)
        (tmp_path / ".env").write_text("CADENCE_TEST_VALUE=from-the-file\n")
        load_env(tmp_path)
        assert os.environ["CADENCE_TEST_VALUE"] == "from-the-file"

    def test_the_real_environment_wins(self, tmp_path, monkeypatch):
        """Otherwise `DATABASE_URL=... cadence run` would be overruled by a
        file, which is the opposite of what anyone means by that."""
        monkeypatch.setenv("CADENCE_TEST_VALUE", "exported")
        (tmp_path / ".env").write_text("CADENCE_TEST_VALUE=from-the-file\n")
        load_env(tmp_path)
        assert os.environ["CADENCE_TEST_VALUE"] == "exported"

    def test_no_file_is_not_an_error(self, tmp_path):
        load_env(tmp_path)

    def test_an_unreadable_env_is_not_an_error(self, tmp_path):
        (tmp_path / ".env").mkdir()
        load_env(tmp_path)
