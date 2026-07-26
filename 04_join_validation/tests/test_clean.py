"""The cleaning contract, expressed as assertions.

These tests are the point of the lab. They state what must remain true after
the merge, so that a future change to the dimension data breaks the build
instead of quietly changing a total on a dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import load_lab_module  # noqa: E402

_clean = load_lab_module(__file__)
JoinIntegrityError = _clean.JoinIntegrityError
build_contract_view = _clean.build_contract_view
resolve_dimension, safe_merge = _clean.resolve_dimension, _clean.safe_merge

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def contracts() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "contracts.csv")


@pytest.fixture(scope="module")
def vendors() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "vendors.csv")


@pytest.fixture(scope="module")
def view() -> pd.DataFrame:
    return build_contract_view()


def test_source_dimension_is_not_unique(vendors):
    """Guard the premise: if this ever passes, the lab has lost its subject."""
    assert not vendors["vendor_id"].is_unique


def test_resolution_yields_one_row_per_key(vendors):
    resolved = resolve_dimension(vendors, key="vendor_id", order_by="effective_from")
    assert resolved["vendor_id"].is_unique
    assert len(resolved) == vendors["vendor_id"].nunique()


def test_resolution_keeps_the_latest_revision(vendors):
    resolved = resolve_dimension(vendors, key="vendor_id", order_by="effective_from")
    revised = vendors.groupby("vendor_id")["effective_from"].max()
    merged = resolved.set_index("vendor_id")["effective_from"]
    assert (merged == pd.to_datetime(revised)).all()


def test_row_count_is_preserved(view, contracts):
    assert len(view) == len(contracts)


def test_measure_total_is_preserved(view, contracts):
    assert view["contract_amount"].sum() == contracts["contract_amount"].sum()


def test_contract_id_remains_unique(view):
    assert view["contract_id"].is_unique


def test_orphans_are_retained_and_flagged(view):
    orphans = view[view["_unmatched"]]
    assert len(orphans) > 0, "seeded orphan contracts should survive the merge"
    assert orphans["vendor_name"].isna().all()


def test_unresolved_dimension_is_rejected(contracts, vendors):
    """The unsafe merge must fail fast rather than return inflated numbers."""
    with pytest.raises(JoinIntegrityError):
        safe_merge(contracts, vendors, key="vendor_id", measure="contract_amount")
