import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from iteration_journal import IterationJournal, ScoredConstraint


@pytest.mark.parametrize("i", range(80), ids=[f"constraint-{i}" for i in range(80)])
def test_update_constraints_creates_scored_entries(i):
    journal = IterationJournal("task", "stack")
    decision = f"decision {i}"
    journal._update_constraints([decision], i + 1)

    key = decision.lower()[:60]
    assert key in journal._constraints
    assert journal._constraints[key].confirmed == 1


@pytest.mark.parametrize("i", range(20), ids=[f"confirm-{i}" for i in range(20)])
def test_update_constraints_confirms_repeated_decisions(i):
    journal = IterationJournal("task", "stack")
    decision = f"repeat decision {i}"

    journal._update_constraints([decision], 1)
    journal._update_constraints([decision], 2)

    key = decision.lower()[:60]
    assert journal._constraints[key].confirmed == 2
    assert journal._constraints[key].score > 1.0


@pytest.mark.parametrize("i", range(20), ids=[f"prune-{i}" for i in range(20)])
def test_prune_removes_low_score_constraints(i):
    journal = IterationJournal("task", "stack")
    key = f"bad-{i}"
    journal._constraints[key] = ScoredConstraint(text=f"bad {i}", score=-4.0, key=key)

    journal._prune()

    assert key not in journal._constraints
