# 인수인계 — 2026-09-11

브랜치 `remeasure-surya-20260911`. 새 세션은 이 문서만 읽고 시작할 수 있게 쓴다.

작업 규칙은 저장소 루트 `CLAUDE.md` 에 있다 (새 세션이 자동으로 읽는다). 더 자세한 기록이 필요하면 아래를 이 순서로 본다:
- `docs/VALIDATION_NEEDS.md`
- `docs/HUMAN_DATA.md`
- `docs/legacy_numbers.md`
- `docs/CORE.md`
- `docs/method.json`

---

## 1. 연구 방향 전환

**버린 방식.** 저해상도 브로크만 스캔(판 약 560×800px, 123장)으로 파이프라인을 검증하던 방식이다. 정답을 모르는 자료로 도구를 검증하려 했다. 그래서 사람 참조는 한 명이고, 출처가 불명이거나 모델이 만든 것이었다. 결과가 측정 잡음과 규칙의 성질을 가르지 못했다 (4·6절).

**새 순서.**
1. **합성 포스터 통제 실험으로 도구를 검증한다.** 정답(블록 · 베이스라인 · 캡 · 행간 · 격자)을 알고 그린 포스터에 해상도 · 압축 · 잡음 · 기울기 같은 저하를 통제해 걸고, 각 도구가 정답을 얼마나 되찾는지 잰다.
2. **검증된 도구를 브로크만에 적용한다.** `docs/CORE.md` 의 발견은 이 단계에서 다시 확인한다.
3. **MCP 활용.** `place_text` · `check_layout` · `style_card` 등.

**1단계를 시작하기 전에 정할 것.** 아래는 제안이지 결정이 아니다. 정한 것은 사전등록부터 쓴다.
- **생성기.** 이미 있는 것은 `generate.py`(v4) · `render.py` · `naive.py` · `content_1965.py`. 이것을 쓸지, 정답을 파일로 함께 내는 새 생성기를 만들지.
- **저하 조건.** 브로크만 스캔과 같은 800px 높이를 기준으로 할지, 해상도 사다리를 둘지.
- **도구별 검증 대상.**
  - 검출 — Surya 줄과 묶기
  - 재기 — `measure/ground.py` 의 베이스라인 · 캡 · 행간
  - 규칙 도출 — 알려진 분포에서 `rules.derive` 가 규칙을 되찾는가
  - `check_layout` — 알려진 위반을 가르는가
  - `place_text`

## 2. 현재 파이프라인과 주요 파일

```
포스터 이미지
  │  Surya DetectionPredictor (surya-ocr 0.22.1) — «줄» 상자
  ▼
detect_surya.py   group() / boxes_norm() — 줄을 «블록» 으로 묶는다
                  (H_RATIO 0.60~1.70 · X_OVER 0.15 · Y_GAP −0.40~1.60 · MIN_AREA 200)
                  columns() — 단 수
  ▼
measure/ground.py entry() — 받은 상자 «안» 만 잰다
                  └ measure/region.py measure() → measure/ink.py (극성 · 문턱 · 줄) · measure/grid.py
                  블록: x1 y1 x2 y2 · n · xh · lead(베이스라인 간격 중앙값) · bases · caps · xtops
                  판: size · color(color/fields.py) · region · n_columns · skew / skewed(EasyOCR 각 ≥ 14°)
  ▼
measure_corpus.py measure_items() · write() — 캐시 ~/.typo-mcp/{코퍼스}.json + provenance
  ▼
rules.py          derive() — 지표 23개. 계층 가르기(LAYER_GAP 10).
                  채택: CV ≤ 0.30 · N ≥ 20, 자리 지표는 discrim.py AUC ≥ 0.75.
                  작가 갈림 딱지: distinct.py. 관계: relate.py · features.py
  ▼
server.py (JSON-RPC) → tools/
    corpus.py     measure_corpus · show_rules · style_card
    grounding.py  measure_boxes (부르는 쪽이 짚은 상자를 잰다)
    layout.py     place_text · check_layout
    brain.py      add_designer · style_brain · compare_brains · pool_brains · list_brains
```

**옛 경로(비교용으로 남김).** `baseline/scan.py` + `baseline/detect.py` (EasyOCR). MCP 에서는 부르지 않는다.

**평가 · 탐색 스크립트.** 참조 경로는 모두 인자로 받는다. 한 번에 재현하는 명령은 `python eval/run_all.py eval/refs.json`.

| 스크립트 | 무엇 | 결과 |
|---|---|---|
| `detector_compare.py` | 참조 · 검출기 상자 파일 만들기 | `boxes/*.json` |
| `detector_score.py` | 검출기 셋과 사람 상자의 일치도 | `docs/detector_compare.json` |
| `oracle_group.py` | Surya 줄 + 오라클 묶기 상한 | `docs/oracle_upper.json` |
| `idml_explore.py` | IDML 가이드로 베이스라인 · 어센더선 재현율 | `docs/idml_explore.json` |
| `eval/loo_place_text.py` | place_text leave-one-out | `docs/loo_place_text.json` |
| `eval/series_check.py` · `series_check_diag.py` | 시리즈 판별 시험과 진단 | `docs/series_check*.json` |
| `eval/refs.json` · `eval/idml_map.json` | 참조 데이터 경로 · IDML 짝 | — |

**283장 재측정 · 9월 분석 재실행.**
- `remeasure.py` 가 283장(4 코퍼스)을 새 경로로 다시 쟀다. 실패 0 · 뒤집힌 아래끝 0. 캐시 provenance 의 commit 은 9b252ed.
- `rerun_sept.py` 와 `score_rerun.py` 가 9월 분석을 옛 경로와 새 경로 양쪽에 다시 걸었다 (`docs/rerun_result.json`).
- 옛 캐시 백업: `~/.typo-mcp/old-20260824/`

## 3. 확정된 사실

- **검출기는 Surya 로 간다** (사용자 결정, 2026-09-11). 참고로 검출기 비교(4절)에서는 사전등록 규칙상 VLM 이 뽑혔다. 다만 경계였다: 차이 구간이 0 을 포함했고, VLM 둘째 패스로는 Surya 가 뽑혔다.
- **사람 측정 자료는 전부 탐색용 임시 자료다.** 라벨러가 모두 한 명이거나, 만든 이 기록이 없거나, 모델이 만든 것이다. 결과는 «정확도» 가 아니라 «참조와의 일치도» 로 적는다. 현황은 `docs/HUMAN_DATA.md`, 필요한 자료의 조건은 `docs/VALIDATION_NEEDS.md`.
  - 사람 상자 v2: 송준혁 1인, 26장 · 130개
  - IDML 가로 가이드: 공동 연구자, 18(+1)점 · 361개. 선 종류 구분 없음
  - 8/18 손 찍기: 만든 이 기록 없음, 3장
  - `labels.json`: 송준혁 1인, 199개
  - `recall52`: 송준혁 1인
  - `triage122`: **Claude** — `SKEW = 14°` 가 여기서 나왔다
- **옛 수치는 인용하기 전에 `docs/legacy_numbers.md` 를 본다.**
  - README 의 행간비 1.50 과 «1958 Musica Viva 1px 재현» 은 지금 코드로 재현되지 않는다 — 대표값 1.40, 까닭은 그 문서에.
  - 독스트링의 IDML «재현율 45% · 정밀도 52% · 0.51px» 는 스크립트와 분모가 없다.

## 4. 탐색 결과 요약 — 방향 확인용이며 논문 수치가 아니다

| 무엇 | 결과 | 기록 |
|---|---|---|
| 검출기 비교 (사람 상자 26장 · 130개, IoU ≥ 0.5 1:1) | F1: EasyOCR 0.292 · Surya 0.576 · VLM 1차 0.677 (2차 0.618). Surya−VLM 차이 구간 [−0.231, 0.026]. 실행 간 일치: EasyOCR · Surya 1.0, VLM 0.735. Surya 의 주된 실패는 과병합(43/130) | `docs/detector_compare.json` |
| 오라클 묶기 상한 (Surya 줄 284개를 사람 상자에 배정) | F1 **0.820** (재현율 0.754 에서 막힘). 못 맞힌 32개: 줄을 못 찾음 18 · 줄 경계 틀림 12 · 기타 2. 묶기만 고쳐서는 넘을 수 없는 몫이 있다 | `docs/oracle_upper.json` |
| IDML 가이드 (오페라하우스 18점, 짝 가이드 192개) | 베이스라인 ±3px 재현율: 옛 경로 0.979 · Surya 0.938. 맞은 선의 오차 중앙 **0.4~0.5px** (두 경로 비슷). 어센더선 0.74~0.75. pt→px 환산은 옛 방식과 0.000px 차. 짝을 못 지은 가이드 169개는 뺐다 | `docs/idml_explore.json` |
| place_text leave-one-out (손 찍기 2장) | 한 장을 빼도 규칙이 거의 안 움직인다 (대표 1.40, n 257→254). 1958 Musica viva 는 실제 행간비 1.56 이라 격자 13px 가 끝줄에서 10~11px 벌어진다 (대표 1.50 이면 1~2px). Végh-Quartett 은 45° 기울어진 판이다 | `docs/loo_place_text.json` |
| 시리즈 판별 시험 (Musica_Viva 를 빼고 뽑은 규칙) | 통과율 56%. 비통과는 대부분 «블록 내 행간 일정» 이다 — 브로크만 나머지 시리즈의 블록 안 간격 편차가 중앙 6px. 비율 규칙은 ±10% 변형을 9~14% 만 잡는다 (부동소수 오차 제외). 줄 ±2px 이동은 99~100% 잡는다. 블록 간 격자 공유 AUC 0.64~0.69 (0.75 넘는 조건 없음) | `docs/series_check.json` · `_diag.json` |
| 283장 두 경로 재확인 | 조판 지표는 네 작가가 공유하고 갈리는 것은 색수, 격자는 가로 자리를 좁히되 칸은 정하지 않음, 행간 ≈ x높이 × 약 1.9 (블록 단위). **저해상도 브로크만 위의 결과라 도구 검증 뒤 다시 확인한다** | `docs/CORE.md` · `docs/rerun_result.json` |

## 5. 작업 규칙 (요약 — 전문은 `CLAUDE.md`)

1. 사전등록 파일은 실행 전에 **단독 커밋**한다. 탐색은 사전등록 없이 해도 되지만, 결과 파일에 «탐색용 · 논문 수치 아님» 을 적는다.
2. 참조 데이터 경로는 스크립트 **인자**로 받는다. 경로는 `eval/refs.json` 한 곳에만 둔다. `eval/run_all.py` 로 재현하고, 스크립트를 고치면 커밋본과 바이트 단위로 같은지 확인한다.
3. 검증 자료가 필요해지면 `docs/VALIDATION_NEEDS.md` 에 항목을 더한다 (무엇 · 어떤 분석 · 몇 개 · 누가 · 지금 임시 자료).

## 6. 보류한 작업

| 작업 | 상태 · 다음에 할 일 |
|---|---|
| 시리즈 판별 시험 | 한 번 돌렸다 (`a338546`). 변형 (a) 의 부동소수 오차를 어떻게 처리할지 **결정이 남았다** — (i) 변형 베이스라인을 정수 px 로 반올림 (f 가 조금 어긋남), (ii) 진단을 나란히 두고 끝냄. 다른 시리즈 빼기는 안 했다. 새 방향에서는 합성 실험으로 `check_layout` 판별력을 먼저 보는 편이 맞다 |
| 하이브리드 (Surya 줄 + VLM 묶기) | 오라클 상한(F1 0.820)만 확인했다. 개발하지 않았다. VLM 을 쓰면 상자를 파일로 고정해야 한다 (모델명 · 날짜 · 지시문) |
| check_layout image 버그 | **고쳤다** (`2df4965`, `color.fields.features` 로). 남은 일 없음 |
| 저장소 정리 («핵심만 남기기») | `git stash list` 의 `stash@{0}` 에 보관, **적용 안 함**. 그 안에서 `baseline/` 을 attic 으로 옮긴 부분은 «EasyOCR 경로 보존» 방침과 충돌하므로 적용할 때 되돌린다. `store.py` 추출은 그 뒤 커밋들(detector_* 등)과 충돌할 수 있다 |
| place_text 설계 물음 | 대표값 하나(1.40)로 배치하면 행간비가 다른 판(1.56)은 줄마다 밀린다. 계층 · 판별 대표값을 쓸지는 정하지 않았다 |
| IDML 가이드 | `Oberon_Carmen.idml` 미사용 (포스터와 크기 일치), `Arabella.idml` 은 포스터를 못 찾음. 짝 없는 가이드 169개. 어센더선이 캡선인지 공동 연구자에게 확인 필요 (`VALIDATION_NEEDS` 4번) |
| HUMAN_DATA.md 보강 | 8/18 손 찍기 파일 위치(`~/Downloads/lines_20260818-2048.csv`), Oberon IDML, 사진 71장 · 베이스라인 42줄을 만든 이 |
| 옛 서술 정리 | `tools/shared.py` 독스트링 «1.50 n=38», `baseline/detect.py` · `scan.py` 독스트링 «베이스라인 361개 45% · 52%», `rules.py` 의 easyocr 주석, `measure/ground.py` 독스트링의 옛 이름 `rules.collect` |
| SKEW 판정 | 14° 문턱이 Claude 라벨에서 나왔다. 사람 2인 라벨이 필요하다 (`VALIDATION_NEEDS` 5번) |
| 푸시 | `origin/remeasure-surya-20260911` 은 06d9d3a 까지 올라가 있고 그 뒤 커밋은 **푸시하지 않았다**. `origin/main` 은 8/24 b301765 (tools/ 분리 이전 구조), 로컬 `main` 은 9b252ed |

## 7. 환경 · 외부 자료

- **Python.** `.venv/bin/python`. 셸은 zsh 라 따옴표 없는 변수가 단어로 쪼개지지 않는다 (`for s in "a 1"` 이 인자 하나로 들어간다).
- **MCP 등록.** `~/.claude.json` 의 `typo` 가 이 폴더의 `server.py` 를 가리킨다. 작업 트리 그대로 돌기 때문에 파일을 옮기면 MCP 가 깨진다.
- **캐시.** `~/.typo-mcp/{brockmann, corpus(호프만), rose, ruder}.json` (surya+ground, provenance 있음). `brockmann-ground.json` (Claude 가 짚은 4장, provenance 없음). 옛 캐시 `old-20260824/`.
- **외부 자료** (경로는 `eval/refs.json`):
  - 포스터: `~/Documents/연구2/{브로크만 정리, 호프만정리, 로제정리, 루더정리}` (브로크만 `corpus/index.csv` · `분류기준.md`)
  - 사람 상자: `~/Downloads/boxes_송준혁-2.csv`, 라벨 도구: `~/Documents/poster/labeler/`
  - IDML: `~/Downloads/아카이브/*.idml`, 옛 채점 스크립트: `~/Documents/poster/out/`
  - 손 찍기: `~/Downloads/lines_20260818-2048.csv` · `blocks_20260818-2048.csv`
- **발행한 도식** (세션 앞부분, 지금 코드와 다를 수 있다):
  - 파이프라인 순서도: https://claude.ai/code/artifact/9364c101-cf72-4359-817d-341089ee1f28
  - 방법론: https://claude.ai/code/artifact/b13f50fd-636e-4dc7-938b-c99e483f47be
  - 결정도: https://claude.ai/code/artifact/db140238-e765-43f6-8b75-1ae16f2baba5
