# 조판 규칙 MCP 서버

포스터 디렉토리를 측정해 **규칙을 스스로 찾아내고**, 그 규칙으로 텍스트 배치를
계산·검사한다. 수치는 코드에 없다. 코퍼스에서 나온다.

브로크만 전용이 아니다. 호프만 포스터를 넣으면 호프만 규칙이 나온다.

## 설치

```bash
git clone https://github.com/사용자명/typo-mcp.git
cd typo-mcp
pip install -r requirements.txt
claude mcp add typo -- python "$(pwd)/server.py"
```

Claude Desktop 이면 설정 파일에 아래를 넣는다.

```json
{"mcpServers": {"typo": {"command": "python", "args": ["/절대경로/typo-mcp/server.py"]}}}
```

## 업데이트

```bash
cd typo-mcp && git pull
```

경로가 그대로이므로 재등록할 필요가 없다.
측정 캐시는 `~/.typo-mcp/corpus.json` 에 저장되어 저장소 밖에 있으므로
`git pull` 로 덮이지 않는다. 위치는 `TYPO_MCP_CACHE` 환경변수로 바꿀 수 있다.

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
server.py     MCP 서버
rules.py      코퍼스 → 분포 → 규칙 채택 판정
pipeline.py   회전 보정 + 영역 검출
blocks.py     단·줄·기준선·블록
rotate.py     회전각 검출
```

의존: `requirements.txt` 참고

## 코퍼스를 바꿀 때

`measure_corpus` 를 다른 폴더로 다시 돌리면 캐시가 통째로 갈린다.
여러 코퍼스를 오가려면 `TYPO_MCP_CACHE` 를 따로 지정한다.

```bash
TYPO_MCP_CACHE=~/.typo-mcp/hofmann.json claude mcp add hofmann -- python /경로/server.py
```
