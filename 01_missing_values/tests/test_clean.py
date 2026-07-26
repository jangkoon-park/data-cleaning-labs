"""The cleaning contract for cause-aware imputation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import load_lab_module  # noqa: E402

_clean = load_lab_module(__file__)
classify_missing, clean = _clean.classify_missing, _clean.clean

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TOLERANCE = 0.02  # 2% of the true total


@pytest.fixture(scope="module")
def observed() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "daily_progress.csv", parse_dates=["work_date"])


@pytest.fixture(scope="module")
def truth() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "ground_truth.csv")


@pytest.fixture(scope="module")
def result(observed) -> pd.DataFrame:
    return clean(observed)


def test_missingness_is_not_random(observed):
    """Guard the premise of the lab."""
    sunday = observed["work_date"].dt.dayofweek == 6
    assert observed.loc[sunday, "manhours"].isna().mean() == 1.0
    assert observed.loc[~sunday, "manhours"].isna().mean() < 0.2


def test_both_causes_are_detected(observed):
    labelled = classify_missing(observed)
    reasons = set(labelled["missing_reason"].unique())
    assert {"present", "site_closed", "report_not_submitted"} <= reasons


def test_no_missing_values_remain(result):
    assert result["manhours"].notna().all()
    assert result["crew_size"].notna().all()


def test_row_count_is_preserved(result, observed):
    assert len(result) == len(observed)


def test_closed_days_are_zero_not_estimated(result):
    closed = result[result["missing_reason"] == "site_closed"]
    assert (closed["manhours"] == 0).all()
    assert not closed["is_estimated"].any()


def test_estimates_are_flagged(result):
    unsubmitted = result[result["missing_reason"] == "report_not_submitted"]
    assert unsubmitted["is_estimated"].all()


def test_total_is_within_tolerance_of_truth(result, truth):
    merged = result.merge(truth, on="report_id", validate="one_to_one")
    got = merged["manhours"].sum()
    expected = merged["manhours_true"].sum()
    assert abs(got / expected - 1) < TOLERANCE


def test_beats_both_naive_strategies(result, observed, truth):
    expected = truth["manhours_true"].sum()
    ours = abs(result["manhours"].sum() - expected)
    dropped = abs(observed["manhours"].dropna().sum() - expected)
    mean_filled = abs(
        observed["manhours"].fillna(observed["manhours"].mean()).sum() - expected
    )
    assert ours < dropped
    assert ours < mean_filled
