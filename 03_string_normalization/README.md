# 03 · String Normalization

Resolving vendor records to companies — and knowing when to stop and ask a human.

---

## Problem

A vendor registry of 85 records covering 12 real companies. The same company appears under **5.6 different spellings on average**.

```
(주)대한건설      대한건설(주)      주식회사 대한건설      ㈜대한건설
대한 건설         "  대한건설 "     Daehan E&C          DAEHAN E and C
```

Three things vary, and only two of them are meaningless.

| Variance | Carries information? |
|---|---|
| Legal-form marker, whitespace, case, unicode width | no — safe to strip |
| Punctuation, `&` vs `and` | no — safe to normalise |
| **The name itself** | **yes — must never be touched** |

That last row is the whole problem, because the registry contains companies whose names are genuinely similar but legally distinct:

```
대한건설    대한건설산업    대한종합건설
서해기술    서해기술산업
```

These are different entities with different contracts and different payment histories. Merging them is not untidiness — it is fabricating a business relationship that does not exist.

A second complication: business registration numbers are present on only 27% of records, and three companies have none at all. So the number is authoritative where it exists but cannot be the key.

---

## Approach

Scored pairwise against the true entity labels — for every pair of records, did the strategy correctly decide *same company or not*.

| Strategy | Clusters | Precision | Recall |
|---|---|---|---|
| A. Exact string match | 67 | 100.0% | 7.4% |
| B. Lowercase + strip | 55 | 100.0% | 14.8% |
| C. **Fuzzy 0.80 auto-merge** | 46 | **74.6%** | 15.5% |

**A and B** are safe and nearly useless. They leave the registry in 55–67 pieces.

**C** is the approach most people reach for, and it is the one to be afraid of. It raises recall by less than a point over B while dropping precision to 74.6% — it merged **three clusters that each contain more than one real company**:

```
'대한 종합건설(주)'
'대한건설(주)'
'  대한건설산업(주) '
'대한건설산업(주)'
```

Three separate legal entities, silently collapsed into one vendor. Every payment, every contract, every performance record for those three companies is now pooled.

---

## Decision

**Precision is a hard constraint; recall is a target.** A missed match leaves two rows for someone to reconcile later. A false match invents history that nobody will ever notice is wrong. The two failure modes are not symmetric, so they should not be traded off symmetrically.

Three stages, in decreasing order of confidence:

1. **Business number where present.** Authoritative. It overrides the name entirely.
2. **Normalisation key.** Removes only provably meaningless variance — NFKC width, case, whitespace, punctuation, and a fixed list of legal-form markers. The company name itself is never altered, so `대한건설` and `대한건설산업` cannot collide. Where a normalised name matches a record that *does* carry a business number, the number is propagated to the ones that lack it.
3. **Review queue.** Pairs that are similar but not provably identical are *reported*, not merged.

Stage 3 is the point. The fuzzy signal is genuinely useful — it is just not evidence. Turning it into a queue keeps the benefit and removes the risk:

```
 entity_a  name_a        entity_b  name_b            similarity
        3  (주)대한건설         10  대한 종합건설(주)          0.8
        3  (주)대한건설         12  대한건설산업(주)           0.8
        4  ㈜서해기술산업        14  ㈜서해기 술               0.8
```

Row 3 is a real match that normalisation missed. Rows 1 and 2 are the trap. A human resolves all three in under a minute; an algorithm resolves all three wrongly in milliseconds.

---

## Result

```
records                       85
  distinct raw strings        67
  resolved entities           17
  true entities               12

precision                 100.0%
recall                     80.9%
review queue                   3 pair(s) held for a human
```

| Strategy | Precision | Recall |
|---|---|---|
| Exact match | 100.0% | 7.4% |
| Lowercase + strip | 100.0% | 14.8% |
| Fuzzy auto-merge | 74.6% | 15.5% |
| **Deterministic + queue** | **100.0%** | **80.9%** |

Five times the recall of the fuzzy matcher, with zero false merges.

14 assertions in `tests/test_clean.py`. Two matter more than the rest: one asserts precision is exactly 1.0 and is never to be relaxed, and one asserts that the fuzzy approach *would* have corrupted the data — so the rejected option stays documented in executable form.

**Known limitations.** The remaining 19% of recall is almost entirely Korean names versus Latin aliases for the three companies with no registration number. No string method can bridge `한성이엔지` and `Hansung ENG`; that needs an alias table, which is reference data rather than cleaning. The legal-marker list is fixed and Korean/English only. The review queue is produced but not persisted or assigned to anyone.

---

## Reproduce

```bash
python src/generate_data.py    # writes registry + true entity labels
python src/profile.py          # score each strategy pairwise
python src/clean.py            # resolve + build review queue
pytest tests/ -q               # 14 passed
```

---

## 한국어 요약

**문제.** 협력사 85건이 실제로는 12개 업체인데, 한 업체가 평균 **5.6가지 표기**로 흩어져 있습니다. 법인격 표기(`(주)`, `㈜`, `주식회사`), 띄어쓰기, 대소문자, 전각/반각이 섞여 있습니다.

여기까지는 단순한 정규화 문제지만, 진짜 함정은 따로 있습니다. **대한건설 / 대한건설산업 / 대한종합건설**은 이름만 비슷할 뿐 서로 다른 법인입니다. 유사도 기반 자동 병합을 돌리면 이 셋이 하나로 합쳐집니다. 실제로 정밀도가 **74.6%**까지 떨어졌고, 서로 다른 세 업체의 계약·지급 이력이 한 덩어리가 됩니다.

**판단.** 정밀도는 **타협 불가 조건**, 재현율은 목표치로 두었습니다. 놓친 병합은 나중에 사람이 처리하면 되지만, 잘못된 병합은 존재하지 않는 거래 관계를 만들어내고 아무도 알아채지 못합니다. 두 오류의 무게가 다르므로 대칭적으로 저울질하지 않았습니다.

따라서 확신도 순으로 3단계를 적용했습니다.

1. 사업자번호가 있으면 그것이 최우선 (전체의 27%)
2. 의미 없는 변형만 제거한 정규화 키 — **상호명 자체는 절대 건드리지 않음**
3. 유사하지만 확정 못 하는 쌍은 **병합하지 않고 검토 큐로 보고**

유사도는 유용한 신호지만 증거는 아닙니다. 큐로 돌리면 이득은 유지하고 위험만 제거됩니다.

**결과.** 정밀도 100%, 재현율 80.9%. 자동 병합 대비 재현율 5배, 오병합 0건.
