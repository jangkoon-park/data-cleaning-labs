"""
Generate a vendor registry where the same company appears under many spellings.

Every raw record carries a hidden true entity id, so an entity-resolution
strategy can be scored with precision and recall instead of being judged by
how tidy the output looks.

Seeded variance:

    legal form      (주)대한건설 / 주식회사 대한건설 / 대한건설(주) / 대한건설
    spacing         대한 건설 / 대한건설
    latin case      Daehan E&C / DAEHAN E&C / daehan e&c
    punctuation     Daehan E&C / Daehan E and C
    stray whitespace and full-width characters

Two traps are planted deliberately:

    TRAP-1  Distinct companies with confusingly similar names
            (대한건설 vs 대한건설산업 vs 대한종합건설) — a fuzzy matcher will
            want to merge these, and merging them is a data corruption.
    TRAP-2  A business registration number is present on only some records, so
            it cannot be used as the sole key, but it is authoritative where
            it exists.

Usage:
    python src/generate_data.py
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260726
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# (canonical korean name, latin alias)
COMPANIES = [
    ("대한건설", "Daehan E&C"),
    ("대한건설산업", "Daehan Industrial"),      # TRAP-1 sibling
    ("대한종합건설", "Daehan General"),          # TRAP-1 sibling
    ("한성이엔지", "Hansung ENG"),
    ("남광토건", "Namkwang Construction"),
    ("서해기술", "Seohae Technology"),
    ("서해기술산업", "Seohae Tech Industrial"),  # TRAP-1 sibling
    ("동보엔지니어링", "Dongbo Engineering"),
    ("정우철강", "Jungwoo Steel"),
    ("삼호전기", "Samho Electric"),
    ("우성설비", "Woosung Plumbing"),
    ("케이엘산업", "KL Industrial"),
]

LEGAL_FORMS = ["{n}", "(주){n}", "{n}(주)", "주식회사 {n}", "㈜{n}", "{n} 주식회사"]
BUSINESS_NO_COVERAGE = 0.40
# Three vendors were never assigned a registration number in the source system,
# so they can only be resolved by name. This is what makes the lab non-trivial.
NO_BRN_ENTITIES = {4, 7, 11}


def korean_variants(name: str, rng: np.random.Generator) -> str:
    form = LEGAL_FORMS[int(rng.integers(0, len(LEGAL_FORMS)))]
    text = form.format(n=name)
    if rng.random() < 0.25 and len(name) > 2:
        cut = int(rng.integers(1, len(name)))
        spaced = name[:cut] + " " + name[cut:]
        text = form.format(n=spaced)
    if rng.random() < 0.20:
        text = "  " + text + " "
    if rng.random() < 0.10:
        text = unicodedata.normalize("NFKD", text).replace(" ", "\u3000")
    return text


def latin_variants(alias: str, rng: np.random.Generator) -> str:
    text = alias
    roll = rng.random()
    if roll < 0.25:
        text = alias.upper()
    elif roll < 0.45:
        text = alias.lower()
    if rng.random() < 0.30:
        text = text.replace("&", " and ")
    if rng.random() < 0.20:
        text = text.replace(" ", "")
    if rng.random() < 0.15:
        text = "  " + text
    return text


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    record_id = 1
    for entity_id, (korean, alias) in enumerate(COMPANIES, start=1):
        business_no = f"{rng.integers(100, 999)}-{rng.integers(10, 99)}-{rng.integers(10000, 99999)}"
        n_records = int(rng.integers(4, 11))
        for _ in range(n_records):
            use_latin = rng.random() < 0.30
            raw = latin_variants(alias, rng) if use_latin else korean_variants(korean, rng)
            has_no = (entity_id not in NO_BRN_ENTITIES) and (rng.random() < BUSINESS_NO_COVERAGE)
            rows.append(
                {
                    "record_id": record_id,
                    "vendor_name_raw": raw,
                    "business_no": business_no if has_no else "",
                    "_entity_id": entity_id,
                }
            )
            record_id += 1

    df = pd.DataFrame(rows).sample(frac=1.0, random_state=SEED).reset_index(drop=True)

    df[["record_id", "vendor_name_raw", "business_no"]].to_csv(
        DATA_DIR / "vendor_registry.csv", index=False
    )
    df[["record_id", "_entity_id"]].rename(
        columns={"_entity_id": "entity_id_true"}
    ).to_csv(DATA_DIR / "ground_truth.csv", index=False)

    print(f"records                 {len(df):>8,}")
    print(f"  distinct raw strings  {df['vendor_name_raw'].nunique():>8,}")
    print(f"  business_no present   {(df['business_no'] != '').sum():>8,}"
          f"  ({(df['business_no'] != '').mean():.0%})")
    print()
    print("GROUND TRUTH")
    print(f"  true entities         {df['_entity_id'].nunique():>8,}")


if __name__ == "__main__":
    main()
