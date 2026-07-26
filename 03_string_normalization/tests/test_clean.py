"""The cleaning contract for entity resolution.

The governing rule of these tests: precision is a hard requirement, recall is a
target. A false merge invents a business relationship; a missed merge only
leaves work on the table.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import load_lab_module  # noqa: E402

_clean = load_lab_module(__file__)
_profile = load_lab_module(__file__, "profile")
clean, normalisation_key = _clean.clean, _clean.normalisation_key
resolve_entities = _clean.resolve_entities
naive_fuzzy, pair_scores = _profile.naive_fuzzy, _profile.pair_scores

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def registry() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "vendor_registry.csv", dtype=str, keep_default_na=False)
    df["record_id"] = df["record_id"].astype(int)
    return df


@pytest.fixture(scope="module")
def truth() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "ground_truth.csv")


@pytest.fixture(scope="module")
def scored(registry, truth):
    resolved, queue = clean(registry)
    merged = resolved.merge(truth, on="record_id", validate="one_to_one")
    precision, recall = pair_scores(merged["entity_id"], merged["entity_id_true"])
    return resolved, queue, precision, recall


@pytest.mark.parametrize(
    "a,b",
    [
        ("(주)대한건설", "대한건설(주)"),
        ("주식회사 대한건설", "대한건설"),
        ("  대한건설 ", "대한건설"),
        ("Daehan E&C", "DAEHAN E and C"),
        ("Seohae Technology", "seohaetechnology"),
    ],
)
def test_meaningless_variance_collapses(a, b):
    assert normalisation_key(a) == normalisation_key(b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("대한건설", "대한건설산업"),
        ("대한건설", "대한종합건설"),
        ("서해기술", "서해기술산업"),
    ],
)
def test_distinct_companies_stay_distinct(a, b):
    """The normalisation key must never conflate different legal entities."""
    assert normalisation_key(a) != normalisation_key(b)


def test_no_false_merges(scored):
    """Precision must be exact. This is the test that must never be relaxed."""
    _, _, precision, _ = scored
    assert precision == 1.0


def test_recall_beats_naive_strategies(registry, truth, scored):
    _, _, _, recall = scored
    merged = registry.merge(truth, on="record_id", validate="one_to_one")
    labels = merged["entity_id_true"]

    _, exact_recall = pair_scores(merged["vendor_name_raw"], labels)
    _, lower_recall = pair_scores(
        merged["vendor_name_raw"].str.strip().str.lower(), labels
    )
    assert recall > exact_recall
    assert recall > lower_recall


def test_fuzzy_auto_merge_would_corrupt(registry, truth):
    """Documents why the tempting approach was rejected."""
    merged = registry.merge(truth, on="record_id", validate="one_to_one")
    precision, _ = pair_scores(naive_fuzzy(merged["vendor_name_raw"]), merged["entity_id_true"])
    assert precision < 1.0


def test_row_count_is_preserved(scored, registry):
    resolved, _, _, _ = scored
    assert len(resolved) == len(registry)
    assert resolved["record_id"].is_unique


def test_every_record_gets_an_entity(scored):
    resolved, _, _, _ = scored
    assert resolved["entity_id"].notna().all()


def test_near_misses_are_queued_not_merged(scored):
    resolved, queue, _, _ = scored
    assert len(queue) > 0, "the sibling company names should surface for review"
    for _, row in queue.iterrows():
        assert row["entity_a"] != row["entity_b"], "queued pairs must remain separate"
