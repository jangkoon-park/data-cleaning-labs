"""
Quantify what each naive missing-value strategy does to the total.

The comparison is only meaningful because a ground-truth total exists. Without
it, every strategy below looks equally reasonable.

Usage:
    python src/profile.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    obs = pd.read_csv(DATA_DIR / "daily_progress.csv", parse_dates=["work_date"])
    truth = pd.read_csv(DATA_DIR / "ground_truth.csv")
    return obs, truth


def deviation(value: float, truth: float) -> str:
    return f"{(value / truth - 1) * 100:+.2f}%"


def main() -> None:
    obs, truth = load()
    true_total = truth["manhours_true"].sum()

    n_missing = obs["manhours"].isna().sum()
    print("1. MISSINGNESS")
    print(f"  rows                {len(obs):>8,}")
    print(f"  missing manhours    {n_missing:>8,}  ({n_missing / len(obs):.1%})")

    print("\n2. IS IT RANDOM?")
    by_dow = obs.assign(dow=obs["work_date"].dt.day_name())
    rate = by_dow.groupby("dow")["manhours"].apply(lambda s: s.isna().mean())
    for day in ["Monday", "Saturday", "Sunday"]:
        print(f"  {day:<10} missing rate  {rate.get(day, 0):>6.1%}")
    print("  -> concentrated on non-working days. Missingness is not random,")
    print("     so any single imputation rule is applying one meaning to two causes.")

    print("\n3. WHAT EACH STRATEGY DOES TO THE TOTAL")
    print(f"  ground truth              {true_total:>14,.1f}")

    dropped = obs["manhours"].dropna().sum()
    print(f"  A. dropna()               {dropped:>14,.1f}   {deviation(dropped, true_total)}")

    filled_mean = obs["manhours"].fillna(obs["manhours"].mean()).sum()
    print(f"  B. fillna(mean)           {filled_mean:>14,.1f}   {deviation(filled_mean, true_total)}")

    filled_zero = obs["manhours"].fillna(0).sum()
    print(f"  C. fillna(0)              {filled_zero:>14,.1f}   {deviation(filled_zero, true_total)}")


if __name__ == "__main__":
    main()
