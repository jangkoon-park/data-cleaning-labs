"""
Diagnose join hazards before any merge is written.

The checks answer three questions that a merge cannot answer for you:

    1. Is the join key unique on each side?      -> fan-out risk
    2. Do both sides cover the same key space?   -> silent row loss
    3. Does the naive merge preserve totals?     -> the actual damage

Usage:
    python src/profile.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    contracts = pd.read_csv(DATA_DIR / "contracts.csv")
    vendors = pd.read_csv(DATA_DIR / "vendors.csv")
    payments = pd.read_csv(DATA_DIR / "progress_payments.csv")
    return contracts, vendors, payments


def key_cardinality(df: pd.DataFrame, key: str, label: str) -> None:
    total = len(df)
    distinct = df[key].nunique()
    dup_keys = total - distinct
    verdict = "unique" if dup_keys == 0 else f"NOT unique ({dup_keys:,} extra rows)"
    print(f"  {label:<20} {total:>7,} rows / {distinct:>7,} distinct {key}   -> {verdict}")


def key_coverage(left: pd.DataFrame, right: pd.DataFrame, key: str) -> None:
    left_keys = set(left[key])
    right_keys = set(right[key])
    missing = left_keys - right_keys
    print(f"  keys present on left but absent on right : {len(missing):,}")
    if missing:
        sample = sorted(missing)[:5]
        rows = left[left[key].isin(missing)]
        print(f"    sample ids            : {sample}")
        print(f"    rows at risk of loss  : {len(rows):,}")
        print(f"    amount at risk        : {rows['contract_amount'].sum():,}")


def naive_merge_damage(contracts: pd.DataFrame, vendors: pd.DataFrame) -> None:
    before_rows = len(contracts)
    before_sum = contracts["contract_amount"].sum()

    naive = contracts.merge(vendors, on="vendor_id", how="left")
    after_rows = len(naive)
    after_sum = naive["contract_amount"].sum()

    print(f"  rows   {before_rows:>10,}  ->  {after_rows:>10,}"
          f"   ({after_rows - before_rows:+,})")
    print(f"  amount {before_sum:>10,}  ->  {after_sum:>10,}"
          f"   ({(after_sum / before_sum - 1) * 100:+.2f}%)")


def main() -> None:
    contracts, vendors, payments = load()

    print("1. KEY CARDINALITY")
    key_cardinality(contracts, "contract_id", "contracts")
    key_cardinality(vendors, "vendor_id", "vendors")
    key_cardinality(payments, "contract_id", "progress_payments")
    print("     note: progress_payments is a legitimate one-to-many child of")
    print("           contracts. Non-uniqueness there is expected. It is only a")
    print("           defect when the non-unique side is a dimension.")

    print("\n2. KEY COVERAGE  contracts.vendor_id -> vendors.vendor_id")
    key_coverage(contracts, vendors, "vendor_id")

    print("\n3. DAMAGE FROM A NAIVE LEFT MERGE  contracts x vendors")
    naive_merge_damage(contracts, vendors)


if __name__ == "__main__":
    main()
