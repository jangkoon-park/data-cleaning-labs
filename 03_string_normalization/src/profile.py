"""
Score each grouping strategy against the true entity labels.

Entity resolution is scored on *pairs*, not on rows: for every pair of records,
did the strategy correctly decide whether they are the same company? This is
what makes precision and recall meaningful here.

    precision  of the pairs we merged, how many really were the same company
    recall     of the pairs that really were the same, how many did we find

Precision matters more. A missed match leaves two rows to reconcile later; a
false match invents a payment history that never existed.

Usage:
    python src/profile.py
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def pair_scores(assigned: pd.Series, truth: pd.Series) -> tuple[float, float]:
    """Precision and recall over same/different-cluster pairs."""
    df = pd.DataFrame({"pred": assigned.to_numpy(), "true": truth.to_numpy()})

    def pair_count(counts: pd.Series) -> int:
        return int((counts * (counts - 1) // 2).sum())

    predicted_pairs = pair_count(df["pred"].value_counts())
    true_pairs = pair_count(df["true"].value_counts())
    agreed_pairs = pair_count(df.groupby(["pred", "true"]).size())

    precision = agreed_pairs / predicted_pairs if predicted_pairs else 1.0
    recall = agreed_pairs / true_pairs if true_pairs else 1.0
    return precision, recall


def report(label: str, assigned: pd.Series, truth: pd.Series) -> None:
    precision, recall = pair_scores(assigned, truth)
    clusters = assigned.nunique()
    print(f"  {label:<28} clusters {clusters:>4}   "
          f"precision {precision:>6.1%}   recall {recall:>6.1%}")


def naive_fuzzy(names: pd.Series, threshold: float = 0.80) -> pd.Series:
    """Single-link agglomeration on string similarity. The tempting approach."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    unique = names.unique().tolist()
    for name in unique:
        parent.setdefault(name, name)
    for i, a in enumerate(unique):
        for b in unique[i + 1:]:
            if difflib.SequenceMatcher(None, a, b).ratio() >= threshold:
                union(a, b)
    return names.map(find)


def main() -> None:
    df = pd.read_csv(DATA_DIR / "vendor_registry.csv", dtype=str, keep_default_na=False)
    truth = pd.read_csv(DATA_DIR / "ground_truth.csv")
    df["record_id"] = df["record_id"].astype(int)
    df = df.merge(truth, on="record_id", validate="one_to_one")
    labels = df["entity_id_true"]

    print("1. RAW STATE")
    print(f"  records                 {len(df):>8,}")
    print(f"  distinct raw strings    {df['vendor_name_raw'].nunique():>8,}")
    print(f"  true entities           {labels.nunique():>8,}")
    print(f"  -> the same company is spread over "
          f"{df['vendor_name_raw'].nunique() / labels.nunique():.1f} spellings on average")

    print("\n2. STRATEGY SCORES  (pairwise)")
    report("A. exact string match", df["vendor_name_raw"], labels)
    report("B. lowercase + strip", df["vendor_name_raw"].str.strip().str.lower(), labels)
    report("C. fuzzy 0.80 auto-merge", naive_fuzzy(df["vendor_name_raw"]), labels)

    print("\n3. WHY FUZZY IS DANGEROUS HERE")
    fuzzy = naive_fuzzy(df["vendor_name_raw"])
    merged = pd.DataFrame({"cluster": fuzzy, "true": labels})
    contaminated = merged.groupby("cluster")["true"].nunique()
    bad = contaminated[contaminated > 1]
    print(f"  clusters containing more than one real company: {len(bad)}")
    if len(bad):
        example = bad.index[0]
        names = df.loc[fuzzy == example, "vendor_name_raw"].unique()[:5]
        print("  example cluster contents:")
        for n in names:
            print(f"    {n!r}")
        print("  -> these are different legal entities with different contracts.")


if __name__ == "__main__":
    main()
