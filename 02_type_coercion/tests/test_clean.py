"""The cleaning contract for monetary text coercion."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import load_lab_module  # noqa: E402

_clean = load_lab_module(__file__)
clean, line_total = _clean.clean, _clean.line_total
parse_money, repair_amount_text = _clean.parse_money, _clean.repair_amount_text

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "cost_entries.csv", dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def truth() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "ground_truth.csv")
    df["recoverable"] = df["recoverable"].astype(str).str.lower() == "true"
    return df


@pytest.fixture(scope="module")
def cleaned(raw):
    return clean(raw)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1,234,567", 1234567.0),
        ("\u20a91,234,567", 1234567.0),
        ("  1,234,567  ", 1234567.0),
        ("1,234,567.00", 1234567.0),
        ("KRW 1,234,567", 1234567.0),
        ("(12,345)", -12345.0),
        ("1234567", 1234567.0),
    ],
)
def test_display_formats_are_recovered(text, expected):
    assert float(repair_amount_text(text)) == expected


@pytest.mark.parametrize("text", ["N/A", "-", "", "  ", "TBD"])
def test_genuine_junk_is_still_rejected(text):
    assert repair_amount_text(text) is None


def test_accounting_negatives_survive(raw):
    values, _ = parse_money(raw["amount_raw"])
    assert (values < 0).any(), "parenthesised credits should parse as negative"


def test_nothing_recoverable_is_lost(raw, truth):
    typed, quarantine = clean(raw)
    assert len(quarantine) == (~truth["recoverable"]).sum()
    assert len(typed) + len(quarantine) == len(raw)


def test_total_matches_ground_truth(cleaned, truth):
    typed, _ = cleaned
    expected = truth.loc[truth["recoverable"], "amount_true"].sum()
    assert typed["amount"].sum() == expected


def test_beats_naive_coercion(cleaned, raw, truth):
    typed, _ = cleaned
    expected = truth.loc[truth["recoverable"], "amount_true"].sum()
    naive = pd.to_numeric(raw["amount_raw"], errors="coerce").sum()
    assert abs(typed["amount"].sum() - expected) < abs(naive - expected)


def test_quarantine_keeps_the_original_text(cleaned):
    _, quarantine = cleaned
    assert "amount_raw" in quarantine.columns
    assert quarantine["amount_raw"].notna().all()


def test_rounding_happens_once(truth):
    """Rounding the price first changes the total; rounding once does not."""
    price, qty = truth["unit_price_true"], truth["qty_true"]
    once = line_total(price, qty).sum()
    twice = line_total(price.round(3), qty).sum()
    assert once != twice
