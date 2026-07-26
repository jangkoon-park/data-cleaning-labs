"""
Resolve vendor names to entities deterministically, and refuse to guess.

Three stages, in decreasing order of confidence:

    1. business number   authoritative where present, ignored where absent
    2. normalisation key removes only what is provably meaningless: legal-form
                         markers, whitespace, case, unicode width, punctuation
    3. review queue      near-misses that survive stage 2 are reported for a
                         human to decide, and are NOT merged automatically

Stage 3 is the point of the lab. A fuzzy matcher can raise recall a few points
and will, on this dataset, also merge three genuinely different companies. The
queue keeps the benefit and drops the risk.

Usage:
    python src/clean.py
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

LEGAL_MARKERS = [
    "주식회사", "(주)", "㈜", "유한회사", "(유)",
    "co.,ltd", "co.ltd", "coltd", "ltd", "inc", "corp", "llc",
]
PUNCT = re.compile(r"[^0-9a-z가-힣]")
REVIEW_THRESHOLD = 0.78


def normalisation_key(name: str) -> str:
    """Strip only what carries no information about identity."""
    text = unicodedata.normalize("NFKC", str(name)).strip().casefold()
    text = text.replace("&", "and")
    for marker in LEGAL_MARKERS:
        text = text.replace(marker, "")
    text = PUNCT.sub("", text)
    return text


def resolve_entities(df: pd.DataFrame) -> pd.DataFrame:
    """Assign an entity_id per record using deterministic evidence only."""
    out = df.copy()
    out["norm_key"] = out["vendor_name_raw"].map(normalisation_key)

    # Stage 1: a business number, where present, overrides the name entirely.
    has_no = out["business_no"].astype(str).str.strip() != ""
    out["cluster_key"] = out["norm_key"]
    out.loc[has_no, "cluster_key"] = "BRN:" + out.loc[has_no, "business_no"]

    # Propagate the business number to name-matched records that lack one.
    key_to_brn = (
        out.loc[has_no]
        .groupby("norm_key")["business_no"]
        .agg(lambda s: s.mode().iat[0])
    )
    inferred = out["norm_key"].map(key_to_brn)
    fill = (~has_no) & inferred.notna()
    out.loc[fill, "cluster_key"] = "BRN:" + inferred[fill]
    out["brn_inferred"] = fill

    codes, _ = pd.factorize(out["cluster_key"])
    out["entity_id"] = codes + 1
    return out


def build_review_queue(resolved: pd.DataFrame, threshold: float = REVIEW_THRESHOLD) -> pd.DataFrame:
    """Report near-misses. Deliberately does not merge them."""
    reps = (
        resolved.groupby("entity_id")
        .agg(name=("vendor_name_raw", "first"), key=("norm_key", "first"), n=("record_id", "size"))
        .reset_index()
    )

    rows = []
    keys = reps[["entity_id", "name", "key", "n"]].to_dict("records")
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            score = difflib.SequenceMatcher(None, a["key"], b["key"]).ratio()
            if score >= threshold:
                rows.append(
                    {
                        "entity_a": a["entity_id"],
                        "name_a": a["name"].strip(),
                        "entity_b": b["entity_id"],
                        "name_b": b["name"].strip(),
                        "similarity": round(score, 3),
                    }
                )
    return pd.DataFrame(rows).sort_values("similarity", ascending=False) if rows else pd.DataFrame(
        columns=["entity_a", "name_a", "entity_b", "name_b", "similarity"]
    )


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    resolved = resolve_entities(df)
    return resolved, build_review_queue(resolved)


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profile import pair_scores  # noqa: E402

    df = pd.read_csv(DATA_DIR / "vendor_registry.csv", dtype=str, keep_default_na=False)
    df["record_id"] = df["record_id"].astype(int)
    truth = pd.read_csv(DATA_DIR / "ground_truth.csv")

    resolved, queue = clean(df)
    merged = resolved.merge(truth, on="record_id", validate="one_to_one")
    precision, recall = pair_scores(merged["entity_id"], merged["entity_id_true"])

    print(f"records                 {len(resolved):>8,}")
    print(f"  distinct raw strings  {resolved['vendor_name_raw'].nunique():>8,}")
    print(f"  resolved entities     {resolved['entity_id'].nunique():>8,}")
    print(f"  true entities         {truth['entity_id_true'].nunique():>8,}")
    print(f"  business_no inferred  {resolved['brn_inferred'].sum():>8,}")
    print()
    print(f"precision               {precision:>8.1%}")
    print(f"recall                  {recall:>8.1%}")
    print()
    print(f"review queue            {len(queue):>8,} pair(s) held for a human")
    if len(queue):
        print(queue.head(6).to_string(index=False))


if __name__ == "__main__":
    main()
