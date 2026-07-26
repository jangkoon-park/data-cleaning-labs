"""
Resolve missing manhours by cause rather than by column.

Two rules, applied in order:

    structural   -> 0, because the site was closed. This is a known value, not
                    an estimate, and is not flagged as imputed.
    entry failure -> median of the same site's working days, flagged so that any
                    downstream consumer can exclude estimates if it needs to.

The public functions take and return DataFrames so that the pipeline lab can
reuse them without going through the CLI.

Usage:
    python src/clean.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

HOLIDAYS = pd.to_datetime(
    [
        "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30",
        "2025-03-01", "2025-05-05", "2025-05-06", "2025-06-06",
    ]
)


def classify_missing(df: pd.DataFrame, date_col: str = "work_date") -> pd.DataFrame:
    """Label every row with the reason its measure is (or is not) missing."""
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    working = (out[date_col].dt.dayofweek != 6) & (~out[date_col].isin(HOLIDAYS))
    out["working_day"] = working

    missing = out["manhours"].isna()
    out["missing_reason"] = np.select(
        [~missing, missing & ~working, missing & working],
        ["present", "site_closed", "report_not_submitted"],
        default="unknown",
    )
    return out


def impute_manhours(df: pd.DataFrame) -> pd.DataFrame:
    """Fill by cause. Estimates are flagged; known zeros are not."""
    out = df.copy()

    site_median = (
        out.loc[out["missing_reason"] == "present"]
        .groupby("site_id")[["manhours", "crew_size"]]
        .median()
    )

    closed = out["missing_reason"] == "site_closed"
    out.loc[closed, ["manhours", "crew_size"]] = 0.0

    unsubmitted = out["missing_reason"] == "report_not_submitted"
    for col in ("manhours", "crew_size"):
        fill = out.loc[unsubmitted, "site_id"].map(site_median[col])
        out.loc[unsubmitted, col] = fill.to_numpy()

    out["is_estimated"] = unsubmitted
    return out


def clean(df: pd.DataFrame) -> pd.DataFrame:
    result = impute_manhours(classify_missing(df))
    assert result["manhours"].notna().all(), "manhours still missing after cleaning"
    return result


def main() -> None:
    obs = pd.read_csv(DATA_DIR / "daily_progress.csv", parse_dates=["work_date"])
    truth = pd.read_csv(DATA_DIR / "ground_truth.csv")

    result = clean(obs)
    merged = result.merge(truth, on="report_id", validate="one_to_one")

    true_total = merged["manhours_true"].sum()
    got_total = merged["manhours"].sum()

    est = merged[merged["is_estimated"]]
    mae = (est["manhours"] - est["manhours_true"]).abs().mean()

    print(f"rows                  {len(merged):,}")
    print(f"  known zeros         {(merged['missing_reason'] == 'site_closed').sum():,}")
    print(f"  estimated           {merged['is_estimated'].sum():,}")
    print()
    print(f"total manhours        {got_total:>14,.1f}")
    print(f"ground truth          {true_total:>14,.1f}")
    print(f"deviation             {(got_total / true_total - 1) * 100:>13.2f}%")
    print(f"MAE on estimated rows {mae:>14,.1f}")


if __name__ == "__main__":
    main()
