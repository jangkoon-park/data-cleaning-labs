"""
A merge that refuses to corrupt the fact table.

Three mechanisms, in order of importance:

    resolve_dimension()  collapse the effective-dated vendor dimension to one
                         row per key, so the join cannot fan out
    safe_merge()         assert row count and measure totals across the merge,
                         and fail loudly instead of returning wrong numbers
    unmatched flag       keep orphaned rows and mark them, rather than letting
                         an inner join delete them silently

Usage:
    python src/clean.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class JoinIntegrityError(AssertionError):
    """Raised when a merge changed something it was not supposed to change."""


def resolve_dimension(
    dim: pd.DataFrame,
    key: str,
    order_by: str,
) -> pd.DataFrame:
    """Keep the latest revision per key.

    The vendor dimension stores history, so vendor_id repeats. Any fact-to-dim
    merge on a non-unique key multiplies fact rows. Collapsing the dimension
    first is preferred over de-duplicating after the merge, because after the
    merge the damage is already mixed into the measures.
    """
    dim = dim.copy()
    dim[order_by] = pd.to_datetime(dim[order_by])
    resolved = (
        dim.sort_values([key, order_by])
        .groupby(key, as_index=False)
        .last()
    )
    assert resolved[key].is_unique, f"{key} still not unique after resolution"
    return resolved


def safe_merge(
    fact: pd.DataFrame,
    dim: pd.DataFrame,
    key: str,
    measure: str,
    tolerance: float = 0.0,
) -> pd.DataFrame:
    """Left-merge a dimension onto a fact table and prove nothing moved.

    Guarantees on return:
        - row count is identical to the input fact table
        - the sum of `measure` is identical within `tolerance`
        - unmatched rows survive, flagged in `_unmatched`
    """
    if not dim[key].is_unique:
        raise JoinIntegrityError(
            f"dimension key '{key}' is not unique; resolve it before merging"
        )

    rows_before = len(fact)
    sum_before = fact[measure].sum()

    merged = fact.merge(dim, on=key, how="left", indicator="_merge_source")
    merged["_unmatched"] = merged["_merge_source"] == "left_only"
    merged = merged.drop(columns="_merge_source")

    rows_after = len(merged)
    sum_after = merged[measure].sum()

    if rows_after != rows_before:
        raise JoinIntegrityError(
            f"row count changed: {rows_before:,} -> {rows_after:,}"
        )
    if abs(sum_after - sum_before) > tolerance:
        raise JoinIntegrityError(
            f"measure '{measure}' changed: {sum_before:,} -> {sum_after:,}"
        )
    return merged


def build_contract_view() -> pd.DataFrame:
    contracts = pd.read_csv(DATA_DIR / "contracts.csv")
    vendors = pd.read_csv(DATA_DIR / "vendors.csv")

    vendors_current = resolve_dimension(vendors, key="vendor_id", order_by="effective_from")
    return safe_merge(
        contracts, vendors_current, key="vendor_id", measure="contract_amount"
    )


def main() -> None:
    view = build_contract_view()

    unmatched = view["_unmatched"].sum()
    print(f"rows                  {len(view):,}")
    print(f"total contract amount {view['contract_amount'].sum():,}")
    print(f"unmatched vendors     {unmatched:,} rows "
          f"({view.loc[view['_unmatched'], 'contract_amount'].sum():,} retained)")

    if unmatched:
        print("\nunmatched vendor_id values:")
        print(sorted(int(v) for v in view.loc[view["_unmatched"], "vendor_id"].unique()))


if __name__ == "__main__":
    main()
