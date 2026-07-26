"""
Generate a synthetic subcontractor billing dataset with seeded join defects.

The data models a construction ERP schema:

    vendors            dimension, effective-dated (multiple rows per vendor_id)
    contracts          fact, one row per contract
    progress_payments  fact, many rows per contract

Two defects are seeded deliberately:

    D1  The vendor dimension keeps historical revisions, so vendor_id is NOT
        unique. A naive merge fans contracts out and inflates any sum.

    D2  A small number of contracts reference a vendor_id that was purged from
        the dimension, so an inner join silently drops them.

Ground truth totals are printed on generation so that any cleaning step can be
verified against a known answer rather than against eyeballing.

Usage:
    python src/generate_data.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260726
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

N_VENDORS = 120
N_CONTRACTS = 400
ORPHAN_CONTRACTS = 7
REVISED_VENDOR_RATIO = 0.25


def build_vendors(rng: np.random.Generator) -> pd.DataFrame:
    """Vendor dimension with effective-dated revisions (defect D1)."""
    base = pd.DataFrame(
        {
            "vendor_id": np.arange(1, N_VENDORS + 1),
            "vendor_name": [f"Subcontractor {i:03d}" for i in range(1, N_VENDORS + 1)],
            "grade": rng.choice(list("SABC"), size=N_VENDORS, p=[0.1, 0.3, 0.4, 0.2]),
            "effective_from": pd.Timestamp("2022-01-01"),
        }
    )

    # A quarter of vendors were re-registered later (name change, grade change).
    revised_ids = rng.choice(
        base["vendor_id"], size=int(N_VENDORS * REVISED_VENDOR_RATIO), replace=False
    )
    revisions = base[base["vendor_id"].isin(revised_ids)].copy()
    revisions["vendor_name"] = revisions["vendor_name"] + " Co., Ltd."
    revisions["grade"] = rng.choice(list("SABC"), size=len(revisions))
    revisions["effective_from"] = pd.Timestamp("2024-07-01")

    vendors = pd.concat([base, revisions], ignore_index=True)
    return vendors.sort_values(["vendor_id", "effective_from"]).reset_index(drop=True)


def build_contracts(rng: np.random.Generator) -> pd.DataFrame:
    """Contract fact table, one row per contract (defect D2 seeded here)."""
    valid_ids = rng.integers(1, N_VENDORS + 1, size=N_CONTRACTS - ORPHAN_CONTRACTS)
    orphan_ids = rng.integers(N_VENDORS + 50, N_VENDORS + 90, size=ORPHAN_CONTRACTS)

    contracts = pd.DataFrame(
        {
            "contract_id": np.arange(10001, 10001 + N_CONTRACTS),
            "vendor_id": np.concatenate([valid_ids, orphan_ids]),
            "contract_amount": rng.integers(20_000, 4_000_000, size=N_CONTRACTS) * 1000,
            "signed_date": pd.to_datetime("2023-01-01")
            + pd.to_timedelta(rng.integers(0, 900, size=N_CONTRACTS), unit="D"),
        }
    )
    return contracts.sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def build_payments(rng: np.random.Generator, contracts: pd.DataFrame) -> pd.DataFrame:
    """Progress payments, a legitimate one-to-many child of contracts."""
    rows = []
    payment_id = 500001
    for contract_id, amount in zip(contracts["contract_id"], contracts["contract_amount"]):
        n = int(rng.integers(1, 7))
        splits = rng.dirichlet(np.ones(n)) * float(amount)
        for period, value in enumerate(splits, start=1):
            rows.append(
                {
                    "payment_id": payment_id,
                    "contract_id": contract_id,
                    "period": period,
                    "paid_amount": round(float(value), 2),
                }
            )
            payment_id += 1
    return pd.DataFrame(rows)


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    vendors = build_vendors(rng)
    contracts = build_contracts(rng)
    payments = build_payments(rng, contracts)

    vendors.to_csv(DATA_DIR / "vendors.csv", index=False)
    contracts.to_csv(DATA_DIR / "contracts.csv", index=False)
    payments.to_csv(DATA_DIR / "progress_payments.csv", index=False)

    print(f"vendors            {len(vendors):>6,} rows "
          f"({vendors['vendor_id'].nunique():,} distinct vendor_id)")
    print(f"contracts          {len(contracts):>6,} rows")
    print(f"progress_payments  {len(payments):>6,} rows")
    print()
    print("GROUND TRUTH")
    print(f"  total contract amount   {contracts['contract_amount'].sum():>18,}")
    print(f"  total paid amount       {payments['paid_amount'].sum():>18,.2f}")


if __name__ == "__main__":
    main()
