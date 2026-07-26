# 01 · Missing Values

Choosing a treatment by the *cause* of missingness, not by the column it appears in.

---

## Problem

Daily progress reports from three construction sites, 543 rows over six months. Manhours are missing in 23.6% of rows.

The missingness is not random:

| Day | Missing rate |
|---|---|
| Monday | 6.4% |
| Saturday | 7.7% |
| **Sunday** | **100.0%** |

There are two causes hiding behind one NaN.

- **Site closed** (102 rows) — Sundays and public holidays. Nobody worked, so the true value is **zero**. This is a known value, not an unknown one.
- **Report not submitted** (26 rows) — a working day whose entry was never filed. The true value is unknown and positive.

Any single fill rule applies one meaning to both. The cost is measurable:

```
ground truth                    98,014.5
A. dropna()                     92,038.0    -6.10%
B. fillna(mean)                120,425.6   +22.87%
C. fillna(0)                    92,038.0    -6.10%
```

`fillna(mean)` is the worst outcome and the most commonly reached for. It pours a working-day average into 102 closed days and overstates labour by 22.87%.

---

## Approach

**A. Drop the missing rows.** Rejected. It understates the total by 6.10%, and worse, it biases the sample: every dropped row is a Sunday or a failed report, so any per-day analysis afterwards silently excludes weekends.

**B. Impute everything with the mean.** Rejected for the reason above — it treats a known zero as an unknown quantity.

**C. Fill everything with zero.** Rejected. Correct for closed days, wrong for the 26 unsubmitted reports, which really did consume labour.

**D. Split by cause, then treat each separately.** Chosen.

---

## Decision

Cause is inferred from the site calendar, which is external information the data itself does not carry. That is the whole trick: **the classification comes from domain knowledge, not from the distribution.**

```python
missing_reason = select(
    [~missing,   missing & ~working_day,  missing & working_day],
    ["present",  "site_closed",           "report_not_submitted"],
)
```

Then:

- `site_closed` → set to **0**, and *not* flagged as estimated. It is a fact, not a guess.
- `report_not_submitted` → filled with the **median of that site's own working days**, and flagged `is_estimated=True`.

Median rather than mean, because a handful of overtime days would drag a mean upward. Per-site rather than global, because crew sizes differ by site and a pooled statistic would import one site's staffing into another.

The `is_estimated` flag matters more than the fill value. Downstream consumers that must not mix measured and estimated labour can filter on it. A fill without a flag destroys that option permanently.

---

## Result

```
rows                  543
  known zeros         102
  estimated            26

total manhours              98,133.1
ground truth                98,014.5
deviation                      0.12%
MAE on estimated rows           28.5
```

| Strategy | Deviation from truth |
|---|---|
| `dropna()` | −6.10% |
| `fillna(mean)` | +22.87% |
| `fillna(0)` | −6.10% |
| **cause-aware** | **+0.12%** |

Eight assertions in `tests/test_clean.py`, including one that fails if the cause-aware result is ever worse than either naive strategy.

**Known limitations.** The holiday calendar is hard-coded and would need to come from a reference table in production. Site-level median assumes staffing is stable over the six-month window; a rolling median would be better for sites that ramp up or wind down. Rows missing for a third reason — say, a site that closed permanently mid-period — would currently be classified as unsubmitted reports.

---

## Reproduce

```bash
python src/generate_data.py    # writes data + ground truth
python src/profile.py          # quantify each naive strategy
python src/clean.py            # cause-aware imputation
pytest tests/ -q               # 8 passed
```

---

## 한국어 요약

**문제.** 일일 공정 보고 543건 중 23.6%에서 공수가 비어 있습니다. 그런데 같은 NaN이 두 가지 의미입니다 — **현장 휴무일**(102건, 실제 값 0)과 **보고 미제출**(26건, 실제 값 미상)입니다.

한 가지 규칙으로 채우면 반드시 틀립니다. 삭제하면 6.10% 과소, 평균 대치하면 **22.87% 과대**가 됩니다. 평균 대치가 가장 흔히 쓰이면서 가장 나쁩니다.

**판단.** 결측 원인을 현장 달력으로 분류한 뒤 따로 처리했습니다. 휴무일은 0으로 확정하되 추정 플래그를 붙이지 않았고, 미제출 건만 **현장별 근무일 중앙값**으로 채우고 `is_estimated`로 표시했습니다.

평균이 아니라 중앙값을 쓴 이유는 특근일 몇 건이 평균을 끌어올리기 때문이고, 전체가 아니라 현장별로 계산한 이유는 현장마다 인원 규모가 다르기 때문입니다.

**결과.** 실제값 대비 편차 0.12%. 추정 행에 대한 MAE는 28.5입니다.
