"""Writing down what happened, as it happens.

The Journal is the channel's recorder: the one listener whose failure stops
the run, because a run that carries on past a lost write leaves an audit trail
with holes that nobody knows are there.

It is the only thing in cadence that writes rows. Experiment holds no session
and knows nothing about it -- recording is a consequence of a fact being
published, not a step the loop has to remember.

    journal = Journal(session)
    stop = cadence.record(journal.record)

What it writes today: the tape, the run that produced it, the trials and
candidates the run made, and what each of them scored.
"""

from collections.abc import Mapping
from typing import Any, ClassVar

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.orm import Session

from cadence.control.locking import LocalLocks
from cadence.control.storage import (
    blobs,
    candidates,
    events,
    manifests,
    model_calls,
    runs,
    trials,
    verdicts,
)
from cadence.core.dto import RecordedManifest
from cadence.core.identity import fingerprint as digest_of
from cadence.core.ports import Locks
from cadence.core.verdict import Scored
from cadence.lifecycle.states import CandidateState, RunState, TrialState
from cadence.observe.channel import Fact
from cadence.observe.signals import (
    CandidateBuilt,
    ModelCalled,
    ModelRequested,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunStarted,
    TrialAbandoned,
    TrialMeasured,
    TrialRetried,
    TrialStarted,
)

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
            self._about_the_trial(fact, run_id)
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
            for seed in fact.seeds:
                # The programs the run started from are candidates too, and
                # they are what every later candidate's lineage points back to.
                self._blob(seed)
                self._candidate(run_id, digest_of(seed), seed, parent=None)
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

    REACHED: ClassVar[Mapping[type[Fact], TrialState]] = {
        TrialStarted: TrialState.STARTED,
        ModelCalled: TrialState.PROMPTED,
        ProposalReceived: TrialState.GENERATED,
        CandidateBuilt: TrialState.MATERIALIZED,
        TrialMeasured: TrialState.MEASURED,
        PatchRejected: TrialState.UNUSABLE,
        TrialAbandoned: TrialState.ABANDONED,
    }
    """Which state a trial is in, once a given fact has been seen.

    The facts and the machine's states line up one to one, so the tape alone
    says where a trial got to and no fact has to carry a status.
    """

    def _about_the_trial(self, fact: Fact, run_id: str) -> None:
        if isinstance(fact, TrialStarted):
            self.session.execute(
                sa.insert(trials).values(
                    id=fact.trial_id,
                    run_id=run_id,
                    seq=fact.seq,
                    status=TrialState.STARTED,
                    attempts=0,
                    parent_fingerprint=fact.parent,
                    started_at=fact.at,
                )
            )
        elif isinstance(fact, TrialRetried):
            self.session.execute(
                sa.update(trials)
                .where(trials.c.id == fact.trial_id)
                .values(attempts=trials.c.attempts + 1)
            )
        elif isinstance(fact, CandidateBuilt):
            self._built(fact, run_id)
        elif isinstance(fact, TrialMeasured):
            self._measured(fact)
        elif isinstance(fact, ModelRequested):
            self._asking(fact, run_id)
        elif isinstance(fact, ModelCalled):
            self._answered(fact)
        reached = self.REACHED.get(type(fact))
        trial_id = getattr(fact, "trial_id", None)
        if (
            reached is not None
            and trial_id is not None
            and reached is not TrialState.STARTED
        ):
            self.session.execute(
                sa.update(trials)
                .where(trials.c.id == trial_id)
                .values(status=reached, reason=getattr(fact, "reason", None))
            )

    IN_FLIGHT = "in_flight"
    DONE = "done"

    def _asking(self, fact: ModelRequested, run_id: str) -> None:
        """Written before the call, so a restart can tell what is in doubt.

        Everything else a trial does happens inside our own process: if we
        die, it either committed or it did not. A model call is the one step
        where dying leaves the question open, and a row with no response is
        the answer to "did we already pay for this?".
        """
        self.session.execute(
            upsert(model_calls)
            .values(
                id=fact.key,
                run_id=run_id,
                trial_id=fact.trial_id,
                request_hash=fact.prompt_digest,
                recipe=dict(fact.recipe),
                status=self.IN_FLIGHT,
                occurred_at=fact.at,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

    def _answered(self, fact: ModelCalled) -> None:
        """The reply came back. Only ever an update: the row was written
        before the call, and a call nobody asked for should not appear."""
        self.session.execute(
            sa.update(model_calls)
            .where(model_calls.c.id == fact.key)
            .values(
                status=self.DONE,
                tokens_in=fact.tokens_in,
                tokens_out=fact.tokens_out,
            )
        )

    def _measured(self, fact: TrialMeasured) -> None:
        """What this candidate scored, against this task, on these seeds.

        The three together are the primary key, so the row is the record of a
        measurement and, once a manifest declares the verifier deterministic,
        the cache that says it need not be taken again. Written either way --
        what a candidate scored is worth keeping whether or not it may be
        reused, and re-measuring is the same measurement, so on conflict the
        row stands.
        """
        verdict = fact.verdict
        self.session.execute(
            upsert(verdicts)
            .values(
                candidate_hash=verdict.fingerprint,
                task_hash=fact.task_hash,
                seeds_hash=fact.seeds_hash,
                outcome=verdict.outcome,
                metrics=dict(verdict.metrics) if isinstance(verdict, Scored) else None,
                reason=None if isinstance(verdict, Scored) else verdict.reason,
                occurred_at=fact.at,
            )
            .on_conflict_do_nothing(
                index_elements=["candidate_hash", "task_hash", "seeds_hash"]
            )
        )

    def _built(self, fact: CandidateBuilt, run_id: str) -> None:
        self._blob(fact.code)
        self._candidate(run_id, fact.fingerprint, fact.code, parent=fact.parent)

    def _blob(self, code: str) -> None:
        """Content-addressed. The model re-proposes the same program
        constantly, and a 500-trial run would otherwise store it 500 times."""
        self.session.execute(
            upsert(blobs)
            .values(hash=digest_of(code), body=code)
            .on_conflict_do_nothing(index_elements=["hash"])
        )

    def _candidate(
        self, run_id: str, fingerprint: str, code: str, parent: str | None
    ) -> None:
        # Derived, never generated: the same program in the same run is the
        # same candidate however many trials propose it, which is what
        # UNIQUE (run_id, fingerprint) says and what a uuid would break.
        self.session.execute(
            upsert(candidates)
            .values(
                id=f"{run_id}/{fingerprint}",
                run_id=run_id,
                fingerprint=fingerprint,
                code_hash=digest_of(code),
                parent_id=f"{run_id}/{parent}" if parent else None,
                status=CandidateState.ALIVE,
            )
            .on_conflict_do_nothing(index_elements=["id"])
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
        # The source lives in blobs, keyed by content. Keeping it on the tape
        # as well would store every program twice and grow the one table that
        # is never allowed to be pruned.
        written.pop("code", None)
        written.pop("seeds", None)
        # The recipe is what rebuilds a prompt byte for byte, and it holds the
        # whole parent program. It lives in model_calls, where replay reads it.
        written.pop("recipe", None)
        return written
