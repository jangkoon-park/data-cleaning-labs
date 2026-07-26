"""
Measure what a plain to_numeric() costs, and what rounding order costs.

Usage:
    python src/profile.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    df = pd.read_csv(DATA_DIR / "cost_entries.csv", dtype=str, keep_default_na=False)
    truth = pd.read_csv(DATA_DIR / "ground_truth.csv")
    truth["recoverable"] = truth["recoverable"].astype(str).str.lower() == "true"

    recoverable_total = truth.loc[truth["recoverable"], "amount_true"].sum()

    print("1. WHAT to_numeric(errors='coerce') DOES")
    naive = pd.to_numeric(df["amount_raw"], errors="coerce")
    lost = naive.isna().sum()
    truly_broken = (~truth["recoverable"]).sum()
    print(f"  rows                     {len(df):>12,}")
    print(f"  became NaN               {lost:>12,}")
    print(f"  actually unparseable     {truly_broken:>12,}")
    print(f"  silently destroyed       {lost - truly_broken:>12,}  <- recoverable money")
    print(f"  surviving total          {naive.sum():>12,.0f}")
    print(f"  ground truth             {recoverable_total:>12,}")
    print(f"  shortfall                {naive.sum() - recoverable_total:>12,.0f}")

    print("\n2. FORMAT VARIANTS PRESENT")
    sample = (
        df["amount_raw"]
        .str.replace(r"[\d,\.]", "", regex=True)
        .str.strip()
        .value_counts()
        .head(6)
    )
    for pattern, count in sample.items():
        label = repr(pattern) if pattern else "'' (digits only)"
        print(f"  {label:<22} {count:>6,}")

    print("\n3. ROUNDING ORDER  (unit_price stored at 4dp, displayed at 3dp)")
    price = truth["unit_price_true"]
    qty = truth["qty_true"]
    db_total = (price * qty).round(0).sum()
    screen_total = (price.round(3) * qty).round(0).sum()
    print(f"  database  (4dp x qty)    {db_total:>14,.0f}")
    print(f"  screen    (3dp x qty)    {screen_total:>14,.0f}")
    print(f"  gap                      {screen_total - db_total:>14,.0f}")
    print("  -> the two figures are both 'correct'. The defect is that nobody")
    print("     wrote down which one is authoritative.")


if __name__ == "__main__":
    main()
