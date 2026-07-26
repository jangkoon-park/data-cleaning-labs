# 05 · Cleaning Pipeline

Composing labs 01–04 into a pipeline that either produces a trustworthy table or produces nothing.

---

## Problem

The first four labs each solve one defect in isolation. Real data arrives with all of them at once, and the interactions are where things break:

- Entity resolution cannot run before amounts are typed, because the quarantine decision changes which rows exist.
- Imputation cannot run before entities are resolved, because the group it imputes from is defined by entity.
- The join cannot run before the dimension is unique, and the dimension only becomes unique as a *result* of entity resolution.

So the second problem is ordering, and the third is what happens when one stage silently under-delivers. A pipeline of five correct stages can still emit a wrong number if nobody checks the seams.

---

## Approach

**A. One function that does everything.** Rejected. Untestable, and every defect fix risks the others.

**B. Five independent scripts run by hand in order.** Rejected. The ordering constraint lives in someone's head, and the intermediate files invite someone to pick up stage 3's output and use it as if it were final.

**C. Stages with an explicit contract at the seam, composed in one runner.** Chosen.

A separate question was whether the pipeline should reimplement the cleaning logic or import it. Reimplementing would have been simpler to package, but it means the pipeline and the labs can drift — and the labs are where the reasoning is documented. So the pipeline imports each lab's public functions directly.

The labs are sibling directories rather than an installed package, and each owns a module named `clean`. Loading them by file path under distinct module names avoids the shadowing that a plain `sys.path` insert would cause:

```python
def _load(lab, alias):
    spec = importlib.util.spec_from_file_location(alias, REPO / lab / "src" / "clean.py")
    ...
```

---

## Decision

**Stage order is a dependency, not a preference.**

```
1 coerce types      nothing downstream is trustworthy until amounts are numbers
2 resolve entities  names must be resolved before anything joins on them
3 build dimension   one row per entity, or the join is unsafe
4 attach vendor     validated merge, invariants asserted across the seam
5 verify contract   assert what every earlier stage promised
```

**Every stage reports what it did to the row count.** The stage log is not decoration — it is the audit trail that makes an unexpected total explainable:

```
1 coerce types            600 ->    576   quarantined   24
2 resolve entities         85 ->     85   17 entities; 3 pair(s) queued
3 build dimension          85 ->     17
4 attach vendor           576 ->    576   0 unmatched
5 verify contract         576 ->    576
```

**The pipeline raises rather than returns on a broken contract.**

```python
checks = {
    "row count preserved":       len(final) == len(source),
    "entry_id unique":           final["entry_id"].is_unique,
    "no null amounts":           final["amount"].notna().all(),
    "amount total preserved":    final["amount"].sum() == source["amount"].sum(),
    "vendor attached or flagged": (final["vendor_name"].notna() | final["_unmatched"]).all(),
}
```

**Nothing is deleted.** The two human-facing outputs — quarantined amounts and queued vendor pairs — are written as files alongside the clean table, not logged and forgotten. They are deliverables. A cleaning run that produces 576 good rows and says nothing about the other 24 has not finished its job.

---

## Result

```
OUTPUT
  clean rows                   576
  total amount          67,210,551,275

HELD BACK FOR PEOPLE, NOT DISCARDED
  unparseable amounts           24
  vendor pairs to review         3
```

Three files are written: `clean_cost_entries.csv`, `quarantine.csv`, `review_queue.csv`.

9 assertions in `tests/test_pipeline.py`. Two are worth calling out:

- **every input row is accounted for** — clean rows plus quarantined rows must equal the input count, so rows cannot go missing between stages
- **the pipeline fails when it should** — a deliberately corrupted dimension must raise `PipelineError`. A pipeline that cannot fail is one that hides its failures.

**Known limitations.** The entity link between cost entries and vendors is synthetic; a real system would carry a foreign key. Stages run in memory and in one process, which is fine at this scale and not at production volume — the natural next step is one task per stage in Airflow, with the contract assertions as the task's success condition rather than a Python `assert`. There is no incremental mode; every run reprocesses everything.

---

## Reproduce

Labs 02 and 03 must have generated their data first.

```bash
cd ../02_type_coercion       && python src/generate_data.py
cd ../03_string_normalization && python src/generate_data.py
cd ../05_cleaning_pipeline

python src/pipeline.py       # run all five stages
pytest tests/ -q             # 9 passed
```

---

## 한국어 요약

**문제.** 01~04 랩은 결함을 하나씩 따로 다뤘지만, 실제 데이터는 네 가지가 동시에 들어옵니다. 여기서는 **순서 자체가 제약**입니다. 금액이 숫자가 되기 전에는 아무것도 신뢰할 수 없고, 업체가 정리되기 전에는 조인할 수 없으며, 차원이 유일해지기 전에는 붙일 수 없습니다.

그리고 더 중요한 문제가 있습니다. 각 단계가 개별적으로 맞아도, **단계 사이 이음매를 아무도 검사하지 않으면** 파이프라인은 그럴듯한 틀린 숫자를 내놓습니다.

**판단.** 단계를 독립 스크립트로 두면 순서 제약이 사람 머릿속에만 남습니다. 그래서 **이음매마다 계약을 명시하고 하나의 러너로 합치는** 방식을 택했습니다. 정제 로직은 재구현하지 않고 각 랩의 함수를 직접 import 합니다 — 판단 근거가 기록된 곳이 랩이기 때문에, 재구현하면 둘이 어긋납니다.

각 단계는 행 수 변화를 보고하고, 계약 위반 시 **반환이 아니라 예외를 던집니다.** 멈춘 파이프라인은 복구할 수 있지만, 그럴듯한 틀린 숫자는 복구할 수 없습니다.

격리된 금액 24건과 검토 대기 업체 3쌍은 로그에 남기고 끝내는 것이 아니라 **파일로 출력**합니다. 576건을 정제하고 나머지 24건에 대해 아무 말도 하지 않는 작업은 끝난 것이 아닙니다.

**결과.** 정제 576건, 총액 672억, 계약 검증 9건 통과. 그중 하나는 파이프라인이 **실패해야 할 때 실패하는지**를 검증합니다.
