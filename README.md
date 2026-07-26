# Data Cleaning Labs

Production-oriented data cleaning patterns in pandas — focused on the **decisions** behind each transformation, not the syntax.

Each lab starts from a defect in a dataset, weighs the options that were actually available, and documents why one was chosen. Every figure quoted in a README is printed by the code in that folder.

---

## Why This Repository Exists

Most cleaning code answers *how*. In practice the expensive question is *which* — whether a 15% null rate should be imputed or dropped, whether two rows with different vendor spellings are the same company, whether a merge that returned more rows than it received is a bug or a feature.

Getting that wrong is silent. The pipeline runs, the dashboard renders, and the number is wrong.

These labs make that judgment explicit, measurable, and testable.

---

## Labs

| # | Lab | The defect | Cost of getting it wrong |
|---|-----|-----------|--------------------------|
| 01 | [`missing_values`](./01_missing_values) | One NaN, two causes: site closed vs. report not submitted | `fillna(mean)` overstates labour by **22.87%** |
| 02 | [`type_coercion`](./02_type_coercion) | Money arriving as display text | `to_numeric(errors="coerce")` deletes **76%** of the total |
| 03 | [`string_normalization`](./03_string_normalization) | One company, 5.6 spellings — and three lookalike companies that are not the same | Fuzzy auto-merge drops precision to **74.6%** |
| 04 | [`join_validation`](./04_join_validation) | A dimension with history, joined naively | Contract totals inflate by **22.37%** |
| 05 | [`cleaning_pipeline`](./05_cleaning_pipeline) | Four defects at once, and the seams between them | A plausible wrong number with no audit trail |

Total: **57 assertions**, all passing.

---

## Structure of Each Lab

Every lab is the same four-part record:

- **Problem** — what is defective, quantified against a known ground truth
- **Approach** — the options considered, and what each one costs
- **Decision** — what was chosen and why, including which business assumptions it depends on
- **Result** — before/after figures and honest limitations

```
0X_lab_name/
├── README.md              # the decision record
├── data/                  # written by the generator below
├── src/
│   ├── generate_data.py   # seeded dataset with known defects + ground truth
│   ├── profile.py         # measure the defect, and what naive fixes cost
│   └── clean.py           # the transformation, as reusable functions
└── tests/
    └── test_clean.py      # the cleaning contract, as assertions
```

---

## Design Principles

**Cleaning is a contract, not a script.** Each lab asserts what must be true afterwards — row counts, totals, uniqueness, null rates — so a regression breaks the build instead of quietly changing a figure on a report.

**Rejected options stay in the test suite.** Where an approach was considered and rejected as unsafe, a test asserts that it *would* have failed. The reasoning stays executable rather than becoming a comment nobody rereads.

**Quarantine, don't drop.** Rows that cannot be cleaned are returned as a deliverable with their original values, so they can be sent back to the source system. A visible bad row is a reportable problem; a deleted one is not.

**Domain assumptions are written down.** Every rule that depends on business context is stated in the lab README. A rule nobody can explain is a bug waiting to happen.

---

## Verifiability

Datasets are synthetic and generated from a fixed seed. This is deliberate rather than a convenience: because the generator knows the true values, each strategy can be **scored** — deviation from a known total, MAE on imputed rows, pairwise precision and recall on entity resolution — instead of being judged by how tidy the output looks.

No client or proprietary data appears in this repository. Schemas and defect patterns are modelled on enterprise ERP systems, where effective-dated dimensions, spreadsheet-formatted exports and partially populated reference keys are ordinary.

---

## Environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.11+ · pandas 2.x or 3.x

Run any lab:

```bash
cd 0X_lab_name
python src/generate_data.py    # seeded; prints ground truth
python src/profile.py          # quantify the defect
python src/clean.py            # apply the transformation
pytest tests/ -q               # verify the contract
```

Run everything:

```bash
for d in 0*/; do (cd "$d" && python src/generate_data.py >/dev/null 2>&1); done
pytest -q
```

---

## Related Work

| Repository | Focus |
|---|---|
| `sql-plan-tuning-labs` | Oracle execution plan analysis and query optimization |
| `data-engineering-pipeline-labs` | NiFi → Airflow → Elasticsearch ingestion pipelines |
| `data-engineering-fundamentals-project` | Architecture and design trade-off documentation |

---

## Author

**Jangkoon Park** — Backend and data engineer, 17 years in enterprise Java/Oracle systems. M.S. in Big Data, Sejong University.

---

## 한국어 요약

pandas 기반 데이터 정제 패턴을 **판단 근거 중심**으로 정리한 저장소입니다. 문법 설명이 아니라 의사결정 기록을 목표로 합니다.

각 랩이 다루는 결함과, 흔한 처리 방식이 실제로 얼마를 틀리는지는 이렇습니다.

- **01 결측치** — 같은 NaN이 휴무일과 미제출 두 가지 의미. 평균 대치 시 **22.87% 과대**
- **02 타입 변환** — 금액이 문자열로 도착. `errors="coerce"` 사용 시 총액의 **76% 소실**
- **03 문자열 정규화** — 한 업체가 평균 5.6가지 표기. 유사도 자동 병합 시 정밀도 **74.6%**로 하락
- **04 조인 검증** — 이력형 차원을 그대로 조인. 계약금액 **22.37% 과대계상**
- **05 통합 파이프라인** — 네 결함이 동시에, 그리고 단계 사이 이음매

각 랩은 문제 / 접근 / 결정 / 결과 네 부분으로 통일되어 있고, 정제 결과가 지켜야 할 조건을 테스트로 고정합니다. **총 57건의 검증이 모두 통과합니다.**

검토했다가 기각한 방식은 주석이 아니라 테스트로 남겼습니다. "이 방법을 썼다면 실패했을 것"을 실행 가능한 형태로 유지하기 위해서입니다.

데이터는 시드 고정 생성기로 만들어 정답값을 알고 있으므로, 각 전략을 눈으로 판단하는 대신 **편차·MAE·정밀도/재현율로 채점**할 수 있습니다. 고객사 데이터는 포함되어 있지 않습니다.
