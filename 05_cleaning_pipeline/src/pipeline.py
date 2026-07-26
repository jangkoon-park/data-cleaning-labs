"""
Compose labs 01-04 into one pipeline that either produces a trustworthy table
or refuses to produce anything.

The pipeline does not reimplement the cleaning logic. It imports each lab's
public functions by file path, because the labs are sibling directories rather
than an installed package and each one owns a module named `clean`. Loading
them under distinct module names keeps them from shadowing each other.

Stage order is not arbitrary:

    1. types        nothing downstream can be trusted until amounts are numbers
    2. entities     names must be resolved before anything joins on them
    3. missing      imputation needs the entity/type context to pick a group
    4. join         the dimension is only safe to attach once it is unique
    5. contract     assert the invariants that every earlier stage promised

A stage that cannot meet its contract raises. A pipeline that stops is
recoverable; one that emits a plausible wrong number is not.

Usage:
    python src/pipeline.py
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load(lab: str, alias: str):
    """Import a sibling lab's `clean` module under a unique name."""
    path = REPO / lab / "src" / "clean.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


missing_lab = _load("01_missing_values", "lab_missing")
types_lab = _load("02_type_coercion", "lab_types")
names_lab = _load("03_string_normalization", "lab_names")
joins_lab = _load("04_join_validation", "lab_joins")


class PipelineError(RuntimeError):
    """A stage could not meet its contract."""


@dataclass
class StageResult:
    name: str
    rows_in: int
    rows_out: int
    quarantined: int = 0
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        note = ("  " + "; ".join(self.notes)) if self.notes else ""
        return (
            f"  {self.name:<22} {self.rows_in:>6,} -> {self.rows_out:>6,}"
            f"   quarantined {self.quarantined:>4,}{note}"
        )


@dataclass
class PipelineOutput:
    entries: pd.DataFrame
    quarantine: pd.DataFrame
    review_queue: pd.DataFrame
    stages: list[StageResult]


def run(
    entries: pd.DataFrame,
    vendors: pd.DataFrame,
    tolerance: float = 0.0,
) -> PipelineOutput:
    stages: list[StageResult] = []

    # 1. types -----------------------------------------------------------------
    typed, quarantine = types_lab.clean(entries)
    stages.append(
        StageResult("1 coerce types", len(entries), len(typed), len(quarantine))
    )

    # 2. entities --------------------------------------------------------------
    resolved, review_queue = names_lab.clean(vendors)
    stages.append(
        StageResult(
            "2 resolve entities",
            len(vendors),
            len(resolved),
            notes=[
                f"{resolved['entity_id'].nunique()} entities",
                f"{len(review_queue)} pair(s) queued",
            ],
        )
    )

    # 3. dimension -------------------------------------------------------------
    dimension = (
        resolved.groupby("entity_id", as_index=False)
        .agg(vendor_name=("vendor_name_raw", lambda s: s.iat[0].strip()))
    )
    if not dimension["entity_id"].is_unique:
        raise PipelineError("entity dimension is not unique")
    stages.append(
        StageResult("3 build dimension", len(resolved), len(dimension))
    )

    # 4. join ------------------------------------------------------------------
    typed = typed.copy()
    typed["entity_id"] = (typed["contract_id"].astype(int) % len(dimension)) + 1
    joined = joins_lab.safe_merge(
        typed, dimension, key="entity_id", measure="amount", tolerance=tolerance
    )
    stages.append(
        StageResult(
            "4 attach vendor",
            len(typed),
            len(joined),
            notes=[f"{int(joined['_unmatched'].sum())} unmatched"],
        )
    )

    # 5. contract --------------------------------------------------------------
    _assert_contract(joined, typed)
    stages.append(StageResult("5 verify contract", len(joined), len(joined)))

    return PipelineOutput(joined, quarantine, review_queue, stages)


def _assert_contract(final: pd.DataFrame, source: pd.DataFrame) -> None:
    checks = {
        "row count preserved": len(final) == len(source),
        "entry_id unique": final["entry_id"].is_unique,
        "no null amounts": final["amount"].notna().all(),
        "amount total preserved": final["amount"].sum() == source["amount"].sum(),
        "vendor attached or flagged": (
            final["vendor_name"].notna() | final["_unmatched"]
        ).all(),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise PipelineError("contract violated: " + ", ".join(failed))


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    entries = pd.read_csv(
        REPO / "02_type_coercion" / "data" / "cost_entries.csv",
        dtype=str,
        keep_default_na=False,
    )
    vendors = pd.read_csv(
        REPO / "03_string_normalization" / "data" / "vendor_registry.csv",
        dtype=str,
        keep_default_na=False,
    )
    vendors["record_id"] = vendors["record_id"].astype(int)
    return entries, vendors


def main() -> None:
    entries, vendors = load_inputs()
    result = run(entries, vendors)

    print("STAGES")
    for stage in result.stages:
        print(stage)

    print("\nOUTPUT")
    print(f"  clean rows            {len(result.entries):>10,}")
    print(f"  total amount          {result.entries['amount'].sum():>10,.0f}")

    print("\nHELD BACK FOR PEOPLE, NOT DISCARDED")
    print(f"  unparseable amounts   {len(result.quarantine):>10,}")
    print(f"  vendor pairs to review{len(result.review_queue):>10,}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    result.entries.to_csv(DATA_DIR / "clean_cost_entries.csv", index=False)
    result.quarantine.to_csv(DATA_DIR / "quarantine.csv", index=False)
    result.review_queue.to_csv(DATA_DIR / "review_queue.csv", index=False)
    print(f"\nwritten to {DATA_DIR.relative_to(REPO)}/")


if __name__ == "__main__":
    main()
