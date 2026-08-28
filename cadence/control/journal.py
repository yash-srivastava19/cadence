"""Writing down what happened, as it happens.

The Journal is the channel's recorder: the one listener whose failure stops
the run, because a run that carries on past a lost write leaves an audit trail
with holes that nobody knows are there.

It is the only thing in cadence that writes rows. Experiment holds no session
and knows nothing about it -- recording is a consequence of a fact being
published, not a step the loop has to remember.

    journal = Journal(session)
    stop = cadence.record(journal.record)

What it writes today: the tape, and the run that produced it. Candidates,
trials and verdicts need facts that carry more than these do.
"""

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.orm import Session

from cadence.control.locking import LocalLocks
from cadence.control.storage import events, manifests, runs
from cadence.core.dto import RecordedManifest
from cadence.core.ports import Locks
from cadence.lifecycle.states import RunState
from cadence.observe.channel import Fact
from cadence.observe.signals import RunFinished, RunStarted

__all__ = ["Journal"]


class Journal:
    def __init__(self, session: Session, locks: Locks | None = None) -> None:
        self.session = session
        # A lock per run, so two workers writing the same tape do not collide
        # on (run_id, seq). The primary key is what makes a duplicate
        # impossible; this is what makes it rare.
        self.locks = locks or LocalLocks()

    def record(self, fact: Fact) -> None:
        run_id = getattr(fact, "run_id", None)
        if run_id is None:  # not a fact about a run; nothing to write it against
            return
        with self.locks.with_lock(f"runs/{run_id}"):
            self._about_the_run(fact, run_id)
            self._append(fact, run_id)
            self.session.commit()

    def _about_the_run(self, fact: Fact, run_id: str) -> None:
        if isinstance(fact, RunStarted):
            self._remember(fact.manifest)
            self.session.execute(
                sa.insert(runs).values(
                    id=run_id,
                    status=RunState.RUNNING,
                    trials=0,
                    manifest_hash=fact.manifest.hash,
                    started_at=fact.at,
                )
            )
        elif isinstance(fact, RunFinished):
            self.session.execute(
                sa.update(runs)
                .where(runs.c.id == run_id)
                .values(
                    status=fact.status,
                    trials=fact.trials,
                    best=fact.best,
                    reason=fact.reason,
                )
            )

    def _remember(self, manifest: RecordedManifest) -> None:
        """Content-addressed, so the hundredth run of one config writes no row.

        runs.manifest_hash points here, so this has to land first.
        """
        self.session.execute(
            upsert(manifests)
            .values(
                hash=manifest.hash,
                source=manifest.source,
                api_version=manifest.api_version,
            )
            .on_conflict_do_nothing(index_elements=["hash"])
        )

    def _append(self, fact: Fact, run_id: str) -> None:
        self.session.execute(
            sa.insert(events).values(
                run_id=run_id,
                seq=self._next_seq(run_id),
                type=type(fact).__name__,
                payload=self._payload(fact),
                # Two clocks. occurred_at is when the thing happened, and comes
                # from the fact; recorded_at is when we wrote it down, and comes
                # from the database. A trial that starts first can finish
                # second, so ordering by write time would rewrite history.
                occurred_at=fact.at,
            )
        )

    def _next_seq(self, run_id: str) -> int:
        """Read rather than counted in memory, so a resumed run continues the
        tape instead of starting a second one at zero."""
        highest = self.session.execute(
            sa.select(sa.func.max(events.c.seq)).where(events.c.run_id == run_id)
        ).scalar()
        return 0 if highest is None else highest + 1

    def _payload(self, fact: Fact) -> Mapping[str, Any]:
        # run_id and the timestamp are columns; keeping them in the payload as
        # well would give a reader two places to look and one to be wrong.
        written = fact.model_dump(mode="json")
        written.pop("run_id", None)
        written.pop("at", None)
        return written
