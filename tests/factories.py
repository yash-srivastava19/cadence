"""One place to build a valid anything.

Plain functions with obvious defaults, not generated data: a test that fails
should print the number you wrote, not one a library invented. Every default
here is a value you could read in a failure message and recognise.

Override only what the test is about:

    a_verdict()                 a scored verdict, value 45
    a_verdict(value=9)          the same thing, when 9 is the point
    a_verdict(outcome=CRASHED)  a failure, when the failure is the point
"""

from cadence.control.entities import Candidate, Run, Trial
from cadence.control.methods.evolution import Evolution, Measured, Unmeasured
from cadence.control.model import Model
from cadence.control.objectives.ranking import WeightedSum
from cadence.core.dto import (
    Completion,
    Directive,
    Proposal,
    Recalled,
    RecordedManifest,
    RunHistory,
    TrialBudget,
    TrialResult,
)
from cadence.core.verdict import Failed, Outcome, Scored

__all__ = [
    "BASELINE",
    "IMPROVED",
    "a_candidate",
    "a_completion",
    "a_directive",
    "a_failure",
    "a_history",
    "a_manifest",
    "a_measured",
    "a_model",
    "a_proposal",
    "a_recalled",
    "a_result",
    "a_run",
    "a_trial",
    "a_verdict",
    "an_evolution",
    "an_unmeasured",
    "some_budget",
]

#: The program every test starts from, and one that scores better. Real
#: enough to run in a sandbox, small enough to read in a diff.
BASELINE = "print('value: 0')"
IMPROVED = "print('value: 45')"

FINGERPRINT = "fp0123456789abcd"


def a_verdict(value: float = 45.0, **metrics: float) -> Scored:
    return Scored(fingerprint=FINGERPRINT, metrics={"value": value, **metrics})


def a_failure(outcome: Outcome = Outcome.CRASHED, reason: str = "it broke") -> Failed:
    return Failed(fingerprint=FINGERPRINT, outcome=outcome, reason=reason)


def a_candidate(code: str = BASELINE, **fields) -> Candidate:
    return Candidate(code=code, **fields)


def a_trial(seq: int = 0, run: str = "h1", **fields) -> Trial:
    return Trial(id=Trial.id_for(run, seq), seq=seq, parent=a_candidate(), **fields)


def a_run(id: str = "h1", **fields) -> Run:
    return Run(id=id, **fields)


def a_result(code: str = IMPROVED, value: float = 45.0) -> TrialResult:
    return TrialResult(code=code, verdict=a_verdict(value))


def a_history(*results: TrialResult, run_id: str = "h1", seeds=(BASELINE,)):
    return RunHistory(run_id=run_id, seeds=seeds, results=results)


def some_budget(spent: int = 0, budget: int = 10) -> TrialBudget:
    return TrialBudget(spent=spent, budget=budget)


def a_directive(index: int = 0, code: str = BASELINE) -> Directive:
    return Directive(parent=FINGERPRINT, code=code, index=index)


def a_completion(text: str = "hello", **fields) -> Completion:
    return Completion(
        **{
            "text": text,
            "model": "scripted-1",
            "tokens_in": 7,
            "tokens_out": 3,
            "latency_ms": 12.0,
            **fields,
        }
    )


def a_recalled(text: str = "hello", digest: str = "d0") -> Recalled:
    return Recalled(prompt_digest=digest, completion=a_completion(text))


def a_proposal(**fields) -> Proposal:
    return Proposal(
        **{
            "patch": ("--- a/program", "+++ b/program"),
            "prompt": "improve this",
            "recipe": {"template": "region"},
            "raw_response": "```python\npass\n```",
            **fields,
        }
    )


def a_measured(value: float = 45.0, code: str = IMPROVED) -> Measured:
    return Measured(candidate=a_candidate(code), verdict=a_verdict(value))


def an_unmeasured(code: str = BASELINE) -> Unmeasured:
    return Unmeasured(candidate=a_candidate(code))


def an_evolution(**options) -> Evolution:
    return Evolution(objective=WeightedSum(value=1.0), **options)


def a_model(*responses: str, **options) -> Model:
    from cadence.control.backends import Scripted

    return Model(backend=Scripted(*responses), **options)


def a_manifest(**fields) -> RecordedManifest:
    return RecordedManifest(
        **{
            "hash": "manifest0123abcd",
            "source": "api_version: cadence/v1alpha2\nprogram: prog.py\n",
            "api_version": "cadence/v1alpha2",
            **fields,
        }
    )
