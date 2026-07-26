# 02 · Type Coercion

Parsing monetary text without silently deleting money, and deciding where rounding is allowed to happen.

---

## Problem

600 cost entries exported from an upstream system. The amount column arrived as display text, not as numbers.

```
1,234,567          thousands separators
₩1,234,567         currency prefix
KRW 1,234,567      currency word
  1,234,567        stray whitespace
1,234,567.00       trailing decimals
(12,345)           accounting negative — a credit note
N/A  -  TBD  ""    genuinely unusable
```

The reflex is `pd.to_numeric(errors="coerce")`. Here is what that costs:

```
rows                              600
became NaN                        499
actually unparseable               24
silently destroyed                475   <- recoverable money
surviving total          15,881,373,292
ground truth             67,210,551,275
shortfall               -51,329,177,983
```

**476 of the 499 discarded rows were perfectly readable.** The function did exactly what it was told and threw away 76% of the money without raising anything.

There is a second, quieter defect. Unit prices are stored at 4 decimal places and displayed at 3. So the screen multiplies a rounded price by quantity while the database multiplies the unrounded one:

```
database  (4dp x qty)    83,929,012,110
screen    (3dp x qty)    83,929,011,709
gap                                -401
```

Small in relative terms, and that is precisely why it survives for years — it is never large enough to trigger an investigation, but it is large enough that two reports never reconcile.

---

## Approach

**A. `errors="coerce"`.** Rejected. Fast, silent, and wrong by 76%.

**B. `errors="raise"`.** Rejected for the opposite reason. One `N/A` in row 54 stops a batch that had 576 perfectly good rows behind it. Correct, but operationally useless.

**C. Repair the text, then coerce, then quarantine whatever is left.** Chosen.

For the rounding gap, three positions were possible: round the unit price to 3dp and make the database match the screen, round nothing and make the screen match the database, or round only the final line total. The third was chosen.

---

## Decision

**Repair before coercion.** Currency marks, separators and whitespace are display artefacts and carry no information. Accounting parentheses do carry information — they mean negative — so they are translated rather than stripped. Only after that does `to_numeric` run, and by then it has nothing left to reject except real junk.

**Quarantine instead of drop.** Unparseable rows are returned in a second frame with their original text and a reason:

```python
def clean(df) -> tuple[pd.DataFrame, pd.DataFrame]:
    ...
    return typed, quarantine
```

Returning two frames instead of one is deliberate. A single-frame API forces the caller to choose between dropping bad rows and carrying nulls; two frames make the bad rows a deliverable — something to send back to the source system. `entry_id` and the original string are preserved so the person fixing it can find the record.

**Round once, at the end.** `line_total` multiplies at full precision and rounds a single time:

```python
def line_total(unit_price, qty, decimals=0):
    return (unit_price * qty).round(decimals)
```

Rounding the *input* is what creates the gap, because the error is then multiplied by quantity. Rounding the *output* bounds the error at half a unit per row regardless of quantity. The rounding position is a business decision, so it lives in exactly one function rather than being scattered across queries and view layers — which is how the original discrepancy arose.

---

## Result

```
rows in                           600
  parsed                          576
  quarantined                      24

total amount             67,210,551,275
ground truth             67,210,551,275
deviation                             0

naive to_numeric total   15,881,373,292
  money recovered        51,329,177,983
```

| | Naive coercion | Repair + quarantine |
|---|---|---|
| Rows retained | 101 | 576 + 24 quarantined |
| Total | 15,881,373,292 | 67,210,551,275 |
| Deviation from truth | −76.4% | **0** |
| Bad rows visible | no | yes, with original text |

18 assertions in `tests/test_clean.py`, including parametrised cases for each display format and a test that fails if rounding ever stops being idempotent.

**Known limitations.** The parser assumes a period decimal separator; European-style `1.234.567,89` would need a locale hint, which cannot be inferred safely from the data alone. Currency detection is limited to a fixed set of marks and does not attempt conversion — a mixed-currency file would be parsed into a meaningless total. Quarantined rows are reported but not routed anywhere.

---

## Reproduce

```bash
python src/generate_data.py    # writes data + ground truth
python src/profile.py          # measure the loss and the rounding gap
python src/clean.py            # repair, coerce, quarantine
pytest tests/ -q               # 18 passed
```

---

## 한국어 요약

**문제.** 금액 컬럼이 숫자가 아니라 화면 표시용 문자열로 넘어옵니다. 천 단위 콤마, 통화 기호, 회계식 음수 괄호가 섞여 있습니다. `pd.to_numeric(errors="coerce")` 를 그대로 쓰면 499행이 NaN이 되는데, 그중 **475행은 충분히 복구 가능한 값**이었습니다. 금액의 76%가 오류 없이 사라집니다.

두 번째 결함은 더 조용합니다. 단가가 DB에는 소수점 4자리, 화면에는 3자리로 표시되어 **화면 합계와 DB 합계가 401원 어긋납니다.** 조사에 착수할 만큼 크지 않으면서 두 보고서가 절대 일치하지 않을 만큼은 큰 금액입니다.

**판단.** `errors="raise"` 는 한 행 때문에 배치 전체가 멈춰 실무에서 못 씁니다. 그래서 **문자열 보정 → 변환 → 실패분 격리** 순서를 택했습니다. 괄호는 제거가 아니라 음수로 번역했습니다. 정보를 담고 있기 때문입니다.

실패한 행은 버리지 않고 원본 문자열과 사유를 붙여 **별도 프레임으로 반환**합니다. 원천 시스템에 되돌려 보낼 수 있어야 하기 때문입니다.

반올림은 입력이 아니라 **출력에서 한 번만** 수행합니다. 단가를 먼저 반올림하면 오차가 수량만큼 증폭되지만, 마지막에 반올림하면 행당 오차가 0.5 이내로 묶입니다.

**결과.** 실제값과 정확히 일치(편차 0), 복구 금액 513억.
