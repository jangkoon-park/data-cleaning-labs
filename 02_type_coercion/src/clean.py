"""
Parse monetary text without losing money, and fix the rounding boundary.

Design choices worth stating up front:

    * Repair before coercion. Stripping separators, currency marks and
      accounting parentheses recovers rows that to_numeric() would discard.
    * Quarantine, do not drop. Rows that remain unparseable are returned in a
      separate frame with the original text, so they can be sent back to the
      source system instead of vanishing.
    * Round once, at the end. Intermediate rounding is what makes the screen
      and the database disagree.

Usage:
    python src/clean.py
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

CURRENCY = re.compile(r"[\u20a9$€£]|KRW|USD", flags=re.IGNORECASE)
NOISE = re.compile(r"[,\s]")
PARENS = re.compile(r"^\((.*)\)$")


def repair_amount_text(text: str) -> str | None:
    """Normalise one display string into something to_numeric can accept."""
    if text is None:
        return None
    cleaned = CURRENCY.sub("", str(text))
    cleaned = NOISE.sub("", cleaned).strip()
    if not cleaned:
        return None

    negative = False
    match = PARENS.match(cleaned)
    if match:
        negative = True
        cleaned = match.group(1)

    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    return f"-{cleaned}" if negative else cleaned


def parse_money(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return (values, unparseable_mask). Nothing is dropped here."""
    repaired = series.map(repair_amount_text)
    values = pd.to_numeric(repaired, errors="coerce")
    return values, values.isna()


def coerce_entries(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the input into a typed frame and a quarantine frame."""
    out = df.copy()
    out["amount"], bad = parse_money(out["amount_raw"])
    out["qty"] = pd.to_numeric(out["qty"].astype(str).str.replace(",", ""), errors="coerce")
    out["unit_price"] = pd.to_numeric(out["unit_price_raw"], errors="coerce")

    quarantine = out.loc[bad, ["entry_id", "amount_raw"]].copy()
    quarantine["reason"] = "amount not parseable"

    return out.loc[~bad].copy(), quarantine


def line_total(unit_price: pd.Series, qty: pd.Series, decimals: int = 0) -> pd.Series:
    """Multiply at full precision, round exactly once.

    Rounding the unit price first is what produces the screen/database gap.
    The rounding position is a business decision and belongs in one place.
    """
    return (unit_price * qty).round(decimals)


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    typed, quarantine = coerce_entries(df)
    typed["line_total"] = line_total(typed["unit_price"], typed["qty"])
    return typed, quarantine


def main() -> None:
    df = pd.read_csv(DATA_DIR / "cost_entries.csv", dtype=str, keep_default_na=False)
    truth = pd.read_csv(DATA_DIR / "ground_truth.csv")
    truth["recoverable"] = truth["recoverable"].astype(str).str.lower() == "true"

    typed, quarantine = clean(df)

    expected = truth.loc[truth["recoverable"], "amount_true"].sum()
    naive = pd.to_numeric(df["amount_raw"], errors="coerce")

    print(f"rows in                  {len(df):>12,}")
    print(f"  parsed                 {len(typed):>12,}")
    print(f"  quarantined            {len(quarantine):>12,}")
    print()
    print(f"total amount             {typed['amount'].sum():>12,.0f}")
    print(f"ground truth             {expected:>12,}")
    print(f"deviation                {typed['amount'].sum() - expected:>12,.0f}")
    print()
    print(f"naive to_numeric total   {naive.sum():>12,.0f}")
    print(f"  money recovered        {typed['amount'].sum() - naive.sum():>12,.0f}")

    if len(quarantine):
        print("\nquarantined rows (returned, not dropped):")
        print(quarantine.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
