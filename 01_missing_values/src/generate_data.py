"""
Generate daily site progress reports with two distinct causes of missingness.

The point of this dataset is that a single NaN carries two different meanings:

    M1  STRUCTURAL   No crew worked that day (Sunday or public holiday), so no
                     manhours were logged. The true value is zero, not unknown.

    M2  ENTRY FAILURE A working day whose report was never submitted. The true
                     value is unknown and positive.

Treating both the same way is the defect this lab is about. A ground-truth file
is written alongside the observed data so that any imputation strategy can be
scored rather than argued about.

Usage:
    python src/generate_data.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260726
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

SITES = ["SITE-A", "SITE-B", "SITE-C"]
START, END = "2025-01-01", "2025-06-30"
ENTRY_FAILURE_RATE = 0.06

HOLIDAYS = pd.to_datetime(
    [
        "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30",
        "2025-03-01", "2025-05-05", "2025-05-06", "2025-06-06",
    ]
)


def is_working_day(dates: pd.Series) -> pd.Series:
    return (dates.dt.dayofweek != 6) & (~dates.isin(HOLIDAYS))


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    calendar = pd.date_range(START, END, freq="D")
    rows = []
    for site in SITES:
        base_crew = int(rng.integers(18, 45))
        for day in calendar:
            rows.append({"site_id": site, "work_date": day, "base_crew": base_crew})

    df = pd.DataFrame(rows)
    df["report_id"] = np.arange(1, len(df) + 1)
    df["working_day"] = is_working_day(df["work_date"])

    # True values -------------------------------------------------------------
    crew = df["base_crew"] + rng.integers(-4, 5, size=len(df))
    crew = crew.clip(lower=5)
    hours = rng.normal(8.2, 0.9, size=len(df)).clip(4.0, 12.0)

    df["crew_size_true"] = np.where(df["working_day"], crew, 0)
    df["manhours_true"] = np.where(
        df["working_day"], (crew * hours).round(1), 0.0
    )

    # Observed values ---------------------------------------------------------
    df["crew_size"] = df["crew_size_true"].astype(float)
    df["manhours"] = df["manhours_true"].astype(float)

    structural = ~df["working_day"]
    df.loc[structural, ["crew_size", "manhours"]] = np.nan

    working_idx = df.index[df["working_day"]]
    failed = rng.choice(
        working_idx,
        size=int(len(working_idx) * ENTRY_FAILURE_RATE),
        replace=False,
    )
    df.loc[failed, ["crew_size", "manhours"]] = np.nan

    observed = df[["report_id", "site_id", "work_date", "crew_size", "manhours"]]
    truth = df[["report_id", "working_day", "crew_size_true", "manhours_true"]]

    observed.to_csv(DATA_DIR / "daily_progress.csv", index=False)
    truth.to_csv(DATA_DIR / "ground_truth.csv", index=False)

    print(f"rows                     {len(df):>10,}")
    print(f"  structural missing     {structural.sum():>10,}  (true value = 0)")
    print(f"  entry-failure missing  {len(failed):>10,}  (true value unknown)")
    print(f"  observed               {df['manhours'].notna().sum():>10,}")
    print()
    print("GROUND TRUTH")
    print(f"  total manhours         {df['manhours_true'].sum():>14,.1f}")


if __name__ == "__main__":
    main()
