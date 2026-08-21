# 조판 규칙 MCP 서버

포스터 디렉토리를 측정해 **규칙을 스스로 찾아내고**, 그 규칙으로 텍스트 배치를
계산·검사한다. 수치는 코드에 없다. 코퍼스에서 나온다.

브로크만 전용이 아니다. 호프만 포스터를 넣으면 호프만 규칙이 나온다.

**[문서 (PDF, 11쪽)](docs/typo-map.pdf)** — 무엇을 재는지, 어떻게 쓰는지,
InDesign 가이드 361개로 어떻게 검증했는지, 판본이 어떻게 올라왔는지.

## 설치

```bash
git clone https://github.com/SJH0101/typo-map.git
cd typo-map
pip install -r requirements.txt
claude mcp add typo -- python "$(pwd)/server.py"
```

Claude Desktop 이면 설정 파일에 아래를 넣는다.

```json
{"mcpServers": {"typo": {"command": "python", "args": ["/절대경로/typo-map/server.py"]}}}
```

## 업데이트

```bash
cd typo-map && git pull
```

경로가 그대로이므로 재등록할 필요가 없다.
측정 캐시는 `~/.typo-mcp/corpus.json` 에 저장되어 저장소 밖에 있으므로
`git pull` 로 덮이지 않는다. 위치는 `TYPO_MCP_CACHE` 환경변수로 바꿀 수 있다.

## 회귀 검사

측정을 고칠 때 「표본이 늘었다」만 보면 안 된다. 늘면서 이미 맞던 것이 깨질 수 있다.
`snapshot.py` 는 지금까지 고친 문제마다 대표 포스터를 하나씩 두고 측정값을 굳혀 둔다.

```bash
TYPO_MCP_CORPUS=/포스터/폴더 python snapshot.py           # 검사
TYPO_MCP_CORPUS=/포스터/폴더 python snapshot.py --bless   # 현재값으로 갱신
```

측정은 결정적이라 같은 입력에 같은 값이 나온다. 그래서 정확히 비교한다.
값이 달라졌다고 곧 틀린 것은 아니다. 무엇이 어떻게 달라졌는지, 그 포스터가
무엇을 지키려고 들어 있는지 함께 보여주므로, 눈으로 확인한 뒤 `--bless` 로 다시 굳힌다.

`GPU` 로 재려면 `TYPO_MCP_GPU=1` 을 준다. M 계열에서는 빠르지 않다 (mps 1.9 vs cpu 1.7s/장).

## 도구

### `measure_corpus`

```json
{"directory": "/포스터/폴더"}
```

폴더의 이미지를 전부 측정해 지표별 분포를 내고, **몰린 것만 규칙으로 채택**한다.

```
변동계수 <= 0.30  이고  표본 >= 20   →  제약
그 외                              →  자유 / 표본 부족
```

「자유」로 판정된 항목은 검사도 배치도 하지 않는다.
표본이 늘면 다시 돌려서 재판정할 수 있다.

### `show_rules`

채택된 규칙과 탈락한 항목을 표본 수·변동계수와 함께 보여준다.

### `place_text`

활자 크기와 줄 수를 주면 행간과 베이스라인을 낸다.
모든 블록이 하나의 격자를 정수배로 공유하게 만든다.

### `check_layout`

배치안을 규칙과 대조해 위반을 돌려준다.

## 실제 결과 (프로젝트 포스터 44점)

```
채택   행간 / 활자높이    중앙 1.50   10~90% 1.30~1.83   CV 0.123  n=38
채택   어센더 / x높이     중앙 1.40   10~90% 1.15~1.50   CV 0.265  n=316
자유   여백 px                                          CV 0.34   n=38
자유   정렬선 수 / 블록 수                                CV 0.486  n=36
```

`asc_over_xh` 는 폰트의 성질이므로 규칙이라기보다 **측정 검산용**이다.
이 값이 1.4 에서 크게 벗어나는 블록은 측정이 깨진 것이다.

**검증** — 1958 Musica Viva 의 활자 크기와 줄 수만 넣었을 때
`place_text` 가 격자 14px, 본문 654/668/682…, 제목 661, 하단 738/752/766/780 을 냈다.
실제 포스터를 사람이 직접 찍은 값과 1px 차이다.

## 하지 않는 것

```
x 좌표 · 판면 마진 · 도형과의 관계   실측이 없다
활자 크기 비                       측정 오차가 지배한다
디센더                            검출 실패율이 높다
```

**이 서버가 정하는 것은 세로 방향 조판뿐이다.** 배치 판단은 하지 않는다.

## 구성

```
server.py       MCP 서버
rules.py        코퍼스 → 분포 → 규칙 채택 판정
pipeline.py     회전 보정 + 영역 검출
blocks.py       단·줄·기준선·블록 (스스로 훑어 찾는 쪽)
boxmeasure.py   주어진 상자 안만 잰다 (받아서 재는 쪽)
rotate.py       회전각 검출
```

## typographic metrology — 짚는 일과 재는 일을 나눈다

`blocks.py` 는 판면을 스스로 훑어 덩어리를 찾고 그 안을 잰다. 두 일을 한
함수가 하므로 찾기가 틀리면 재기가 아무리 정확해도 소용이 없다.

오페라하우스 두 점을 IDML 가이드로 대조해 그 경계를 실측했다.

    덩어리 찾기   VLM 6/6 맞음      ·  blocks.run() 은 17개·12개로 쪼갬
    상자 위치     VLM ±1px (8변 중 7)
    행간 재기     VLM +24% 편향     ·  boxmeasure 21.0px (정답 21px)
    정렬 판정     —                 ·  왼쪽 흩어짐 0.0px 대 오른쪽 39.6px

짚는 일은 추정이 허용되고 재는 일은 허용되지 않는다. 재는 값이 행간/활자높이
같은 비율이므로, 24% 편향은 규칙 채택을 통째로 바꾼다.

그래서 `boxmeasure.py` 를 따로 둔다. 상자를 받아 그 안만 재므로 도형을 글자로
오인하거나 검은 바탕의 흰 글자를 놓치는 실패가 구조적으로 생기지 않는다.

```python
from boxmeasure import measure
measure(path, (x1, y1, x2, y2))
# → baselines · x_heights · lead · lead_over_xh · align · align_spread
```

의존: `requirements.txt` 참고

## 코퍼스를 바꿀 때

`measure_corpus` 를 다른 폴더로 다시 돌리면 캐시가 통째로 갈린다.
여러 코퍼스를 오가려면 `TYPO_MCP_CACHE` 를 따로 지정한다.

```bash
TYPO_MCP_CACHE=~/.typo-mcp/hofmann.json claude mcp add hofmann -- python /경로/server.py
```
