"""One clean database per session.

A belt, not the fix. What makes these tests deterministic is that each one
asserts about the run it started -- scoped by run id, or by the fingerprints
that run produced -- so a row somebody else left cannot change an answer.
There is a test for exactly that: the suite passes against a database
deliberately seeded with a foreign run, stray events and an extra verdict.

This is here because most of these tests roll back but a few really commit,
and a run interrupted halfway leaves those behind. Finding out an hour later
that a count was counting last Tuesday is worth ten lines to avoid.

Only ever TEST_DATABASE_URL. DATABASE_URL is somebody's real work.
"""

import os

import pytest

#: Emptied in this order: children before parents, so foreign keys hold.
#: verdicts first because it is keyed on what was measured rather than on a
#: run, so nothing else deleting by run_id reaches it.
LEFTOVERS = (
    "verdicts",
    "model_calls",
    "events",
    "trials",
    "candidates",
    "runs",
    "blobs",
    "templates",
    "manifests",
)


@pytest.fixture(scope="session", autouse=True)
def a_clean_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:  # the integration tests skip themselves; nothing to clean
        return
    import sqlalchemy as sa

    from cadence.control.storage import engine

    bound = engine(url)
    with bound.begin() as connection:
        for table in LEFTOVERS:
            connection.execute(sa.text(f"delete from {table}"))
    bound.dispose()
