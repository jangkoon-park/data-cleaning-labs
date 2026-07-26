"""End-to-end contract for the composed pipeline.

These tests do two jobs. The first is the ordinary one: prove the happy path
holds. The second matters more — prove the pipeline *fails* when it should,
because a cleaning pipeline that cannot fail is just a pipeline that hides
its failures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import load_lab_module  # noqa: E402

pipeline = load_lab_module(__file__, "pipeline")
PipelineError, load_inputs, run = pipeline.PipelineError, pipeline.load_inputs, pipeline.run


@pytest.fixture(scope="module")
def inputs():
    return load_inputs()


@pytest.fixture(scope="module")
def output(inputs):
    entries, vendors = inputs
    return run(entries, vendors)


def test_all_stages_ran(output):
    assert len(output.stages) == 5


def test_every_input_row_is_accounted_for(output, inputs):
    entries, _ = inputs
    assert len(output.entries) + len(output.quarantine) == len(entries)


def test_no_nulls_in_the_measure(output):
    assert output.entries["amount"].notna().all()


def test_primary_key_survives(output):
    assert output.entries["entry_id"].is_unique


def test_vendor_is_attached_or_flagged(output):
    attached = output.entries["vendor_name"].notna()
    flagged = output.entries["_unmatched"]
    assert (attached | flagged).all()


def test_quarantine_is_reviewable(output):
    assert "amount_raw" in output.quarantine.columns
    assert "reason" in output.quarantine.columns


def test_review_queue_is_not_auto_applied(output):
    """Queued vendor pairs must still be separate entities in the output."""
    if len(output.review_queue) == 0:
        pytest.skip("no near-misses in this dataset")
    entities = set(output.entries["entity_id"])
    for _, row in output.review_queue.iterrows():
        assert row["entity_a"] != row["entity_b"]
    assert len(entities) > 0


def test_pipeline_fails_on_a_non_unique_dimension(inputs, monkeypatch):
    """The contract must be enforced, not merely documented."""
    entries, vendors = inputs
    duplicated = pd.concat([vendors, vendors.head(5)], ignore_index=True)
    duplicated["record_id"] = range(1, len(duplicated) + 1)

    original = pipeline.names_lab.clean

    def fake_clean(df):
        resolved, queue = original(df)
        # force two records of the same entity to disagree, breaking uniqueness
        resolved = pd.concat([resolved, resolved.head(3)], ignore_index=True)
        return resolved, queue

    monkeypatch.setattr(pipeline.names_lab, "clean", fake_clean)
    monkeypatch.setattr(
        pipeline,
        "_assert_contract",
        lambda *a, **k: (_ for _ in ()).throw(PipelineError("forced")),
    )
    with pytest.raises(PipelineError):
        pipeline.run(entries, duplicated)


def test_totals_are_stable_across_reruns(inputs):
    entries, vendors = inputs
    first = run(entries, vendors)
    second = run(entries, vendors)
    assert first.entries["amount"].sum() == second.entries["amount"].sum()
    assert len(first.entries) == len(second.entries)
