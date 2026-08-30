"""Who ran a run, and what it is called.

Both matter only once more than one person shares a database, which is also
when getting them wrong is expensive: a colliding id means two people writing
one run, and a missing owner means nobody can tell whose it was.
"""

import re
from datetime import UTC, datetime

from cadence.commands.identity import fresh_id, owner


class TestAGeneratedRunId:
    def test_two_in_a_row_differ(self):
        """The whole point. Ids used to default to "local" for everybody."""
        assert fresh_id() != fresh_id()

    def test_it_sorts_by_when_it_was_made(self, monkeypatch):
        """A listing ordered by id reads in the order things happened, which
        is what someone scanning one expects. Two ids from the same second
        cannot show this -- only the random tail differs -- so the clock is
        moved between them."""
        made = []
        january = datetime(2026, 1, 1, tzinfo=UTC)
        june = datetime(2026, 6, 1, tzinfo=UTC)
        for moment in (january, june):
            monkeypatch.setattr(
                "cadence.commands.identity.datetime",
                type("clock", (), {"now": staticmethod(lambda tz, m=moment: m)}),
            )
            made.append(fresh_id())
        assert made == sorted(made)

    def test_it_is_readable(self):
        assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{6}", fresh_id())

    def test_it_carries_no_identity(self):
        """Owner and experiment are columns. Encoding them here would mean
        filtering a primary key with LIKE."""
        assert "@" not in fresh_id()


class TestWhoToCreditARunTo:
    def test_the_git_address_by_default(self, monkeypatch):
        """The same identity as the pull request the run is evidence for."""
        monkeypatch.delenv("CADENCE_OWNER", raising=False)
        monkeypatch.setattr(
            "cadence.commands.identity._git_email", lambda: "her@lab.edu"
        )
        assert owner() == "her@lab.edu"

    def test_cadence_owner_wins(self, monkeypatch):
        """CI, a cluster node and a shared box all have a git identity that
        is not the person who asked for the run."""
        monkeypatch.setenv("CADENCE_OWNER", "nightly-ci")
        monkeypatch.setattr(
            "cadence.commands.identity._git_email", lambda: "her@lab.edu"
        )
        assert owner() == "nightly-ci"

    def test_it_falls_back_to_the_login(self, monkeypatch):
        monkeypatch.delenv("CADENCE_OWNER", raising=False)
        monkeypatch.setattr("cadence.commands.identity._git_email", lambda: None)
        monkeypatch.setenv("USER", "ada")
        assert owner() == "ada"

    def test_nobody_is_an_answer(self, monkeypatch):
        """A run with no owner is still a run. Inventing one would put a name
        in the database that nobody chose."""
        monkeypatch.delenv("CADENCE_OWNER", raising=False)
        monkeypatch.delenv("USER", raising=False)
        monkeypatch.setattr("cadence.commands.identity._git_email", lambda: None)
        assert owner() is None

    def test_no_git_on_the_machine_is_not_a_crash(self, monkeypatch):
        def missing(*args, **kwargs):
            raise FileNotFoundError("git")

        monkeypatch.setattr("subprocess.run", missing)
        monkeypatch.delenv("CADENCE_OWNER", raising=False)
        monkeypatch.setenv("USER", "ada")
        assert owner() == "ada"
