# 브로크만 가이드 긋기 라벨링 — 자료와 스크립트

요청서는 `docs/LABELING_REQUEST.md`. 이 폴더에는 포스터를 고른 근거와 가이드 긋기 도구가 있다.

**여기 있는 판정은 모두 사람 판정이 아니다.** 대문자 유무 · 회전 블록은 Claude(claude-opus-5)가 이미지를 눈으로 보고 붙였고, 단 수 · 줄 수 · 기울기는 파이프라인 값이다. 포스터 선정에만 썼다. 탐색용 · 논문 수치 아님.

| 파일 | 무엇 | 만든 쪽 |
|---|---|---|
| `caps_claude_eye.json` | 123장 대문자 유무 (U 73 · L 50) · 대문자만 있는 줄 유무 | **Claude 눈 판정** (2026-09-14) |
| `ocr_run.py` → `ocr_easyocr.json` | 123장 EasyOCR 글자 인식 (대문자 판정 교차 확인용) | 코드 |
| `caps_compare.py` → `caps_compare.json` | 눈 판정과 OCR 의 일치 0.878 (κ 0.75), 불일치 15장과 재확인 기록 | 코드 + Claude 재확인 |
| `rotation.json` | 기울어진 판 10장 (코드) · 회전 블록이 있는 판 4장 (Claude 눈 판정) · 판정 기준 | 코드 · Claude |
| `select.py` → `selection.json` | 50장 선정 — 칸(대문자 · 단 수) · 예상 줄 수 · 뺀 판과 까닭. **라벨러에게 주지 않는다** | 코드 |
| `select.py` → `posters_for_labelers.json` | 도구가 읽는 목록 — 순서 · 폴더 · 파일 · sha256 만 | 코드 |
| `SELECTION.md` | 선정 기록 — 뺀 것 · 층 · **같은 틀 판(독립 표본 아님)** · 대체 제안(적용 안 함) · 한계. **라벨러에게 주지 않는다** | Claude |
| `figure.py` → `lines.png` | 가이드 네 종류 참조 그림 (요청서 · 도구 공용) | 코드 (Helvetica 글리프 실측 위치) |
| `mixed_size_check.py` → `mixed_size_check.json` | 한 줄에 크기가 섞일 때 `measure/region.py` 가 내는 값 (렌더 5경우 · 실물 4판) — 요청서 5절 7 규칙의 근거 | 코드 (실물 «뺀 상자» 끝은 Claude 가 정함) |
| `compare_guides.py` | 두 라벨러 파일 견주기 — 텍스트 블록 IoU 짝 · 글줄 짝 · 선 종류마다 행 차 · 상태(글자 없음 · 판독 불가) 일치. 도구 1.0 · 2.0 파일 모두 읽는다. 연습 포스터 «같은 행» 확인에 먼저 쓴다 | 코드 |
| `request_pdf.py` | 요청서 md → 그림이 박힌 PDF 한 파일 (`~/Documents/poster/labeler/가이드긋기_요청서.pdf`, 공동 연구자에게 도구와 함께 보냄). 헤드리스 Chrome 을 CDP 로 부른다 | 코드 |
| `tool/template.html` · `tool/build.py` | 가이드 긋기 도구 원본 · 만들기 | — |
| `tool/verify_synth.json` | 도구 1.0 · 2.0 검증 기록 — 합성 포스터(정답 있음)로 좌표 약속 · 연속 확대 · 미입력/잘못된 상태 · 계속하기 · 불러오기 | Claude (브라우저 조작) |
| `tool/verify_cdp.mjs` | 도구 2.0 검증 스크립트 — 헤드리스 Chrome 을 CDP 로 조작하고 스크린샷을 남긴다 | Claude |

## 다시 만들기

```
.venv/bin/python docs/labeling/caps_compare.py docs/labeling/caps_claude_eye.json docs/labeling/ocr_easyocr.json docs/labeling/caps_compare.json
.venv/bin/python docs/labeling/select.py ~/.typo-mcp/brockmann.json docs/labeling/caps_claude_eye.json docs/labeling/rotation.json "~/Documents/연구2/브로크만 정리/corpus/코어" docs/labeling --boxed_csv ~/Downloads/boxes_송준혁-2.csv
.venv/bin/python docs/labeling/figure.py docs/labeling/lines.png
.venv/bin/python docs/labeling/mixed_size_check.py "~/Documents/연구2/브로크만 정리/corpus/코어" docs/labeling/mixed_size_check.json
.venv/bin/python docs/labeling/request_pdf.py docs/LABELING_REQUEST.md ~/Documents/poster/labeler/가이드긋기_요청서.pdf
.venv/bin/python docs/labeling/tool/build.py docs/labeling/posters_for_labelers.json "~/Documents/연구2/브로크만 정리/corpus/코어" docs/labeling/lines.png ~/Documents/poster/labeler/선긋기.html
```

OCR 은 다시 돌리면 9분쯤 걸린다 (`ocr_run.py ~/.typo-mcp/brockmann.json "~/Documents/연구2/브로크만 정리/corpus" docs/labeling/ocr_easyocr.json`).

도구 HTML 에는 포스터 이미지가 들어 있으므로 저장소에 두지 않는다. `eval/refs.json` · `eval/run_all.py` 에는 아직 올리지 않았다 (이 작업 동안 `eval/` 은 다른 세션이 쓴다).
