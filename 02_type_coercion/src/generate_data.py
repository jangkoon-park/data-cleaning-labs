"""
Generate cost entries whose monetary columns arrive as free-form text.

Two independent defects are seeded:

    T1  FORMAT VARIANCE  Amounts are exported as display strings: thousands
        separators, a currency prefix, accounting-style negatives in
        parentheses, stray whitespace, and a residue of genuinely unusable
        placeholders. A plain to_numeric(errors="coerce") turns recoverable
        money into NaN without saying so.

    T2  PRECISION MISMATCH  Unit prices are stored at 4 decimal places but
        rendered at 3 on screen. The screen therefore multiplies a rounded
        price by quantity while the database multiplies the unrounded one,
        and the two totals disagree.

Ground truth values are written alongside so both defects can be scored.

Usage:
    python src/generate_data.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260726
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

N_ROWS = 600
UNRECOVERABLE = ["N/A", "-", "", "  ", "TBD"]


def format_amount(value: int, style: int) -> str:
    """Render an integer amount the way a spreadsheet export would."""
    negative = value < 0
    magnitude = abs(value)

    if style == 0:
        text = f"{magnitude:,}"
    elif style == 1:
        text = f"\u20a9{magnitude:,}"
    elif style == 2:
        text = f"{magnitude}"
    elif style == 3:
        text = f"  {magnitude:,}  "
    elif style == 4:
        text = f"{magnitude:,}.00"
    else:
        text = f"KRW {magnitude:,}"

    if negative:
        # accounting convention: negatives in parentheses, no minus sign
        return f"({text.strip()})"
    return text


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    qty = rng.integers(1, 60_000, size=N_ROWS)
    unit_price = np.round(rng.uniform(120, 9_000, size=N_ROWS), 4)

    amount = (unit_price * qty).round(0).astype(np.int64)
    credit = rng.random(N_ROWS) < 0.08
    amount = np.where(credit, -amount, amount)

    styles = rng.integers(0, 6, size=N_ROWS)
    amount_raw = [format_amount(int(a), int(s)) for a, s in zip(amount, styles)]

    broken_idx = rng.choice(N_ROWS, size=int(N_ROWS * 0.04), replace=False)
    for i, choice in zip(broken_idx, rng.integers(0, len(UNRECOVERABLE), size=len(broken_idx))):
        amount_raw[i] = UNRECOVERABLE[choice]

    df = pd.DataFrame(
        {
            "entry_id": np.arange(70001, 70001 + N_ROWS),
            "contract_id": rng.integers(10001, 10401, size=N_ROWS),
            "qty": [f"{q:,}" for q in qty],
            "unit_price_raw": [f"{p:.4f}" for p in unit_price],
            "amount_raw": amount_raw,
        }
    )

    truth = pd.DataFrame(
        {
            "entry_id": df["entry_id"],
            "amount_true": amount,
            "unit_price_true": unit_price,
            "qty_true": qty,
            "recoverable": ~pd.Index(np.arange(N_ROWS)).isin(broken_idx),
        }
    )

    df.to_csv(DATA_DIR / "cost_entries.csv", index=False)
    truth.to_csv(DATA_DIR / "ground_truth.csv", index=False)

    recoverable_total = amount[truth["recoverable"].to_numpy()].sum()

    print(f"rows                  {N_ROWS:>12,}")
    print(f"  unrecoverable text  {len(broken_idx):>12,}")
    print(f"  credit entries      {int(credit.sum()):>12,}  (rendered in parentheses)")
    print()
    print("GROUND TRUTH")
    print(f"  recoverable total   {recoverable_total:>12,}")


if __name__ == "__main__":
    main()
