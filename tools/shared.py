"""도구들이 함께 쓰는 것 — 캐시 경로와 규칙 읽기.

규칙 수치를 코드에 박지 않는다. 코퍼스를 측정해 분포를 내고, 몰려 있고
무작위와 구별되는 것만 규칙으로 채택한다 (rules.py).

───
실측 근거

  표본: 프로젝트 포스터 44점 무작위 추출, 자동 측정 (2026-08)
  검증: 1958 Musica Viva 25줄 · 1958 Végh-Quartett 17줄을 사람이 직접 찍어
        자동값과 대조. 베이스라인 22/25 가 0px 일치, 회전 포스터 각도 0.1° 차.

  쓸 수 있는 값
    행간/활자높이   n=38  중앙 1.50  10~90% 1.30~1.83  변동계수 0.12
    여백(행간−활자)  n=38  중앙 4.2px 10~90% 3.0~6.5   음수 0개
    좌측 정렬선     n=36  블록 중앙 8개에 정렬선 중앙 3개
    어센더/x높이    n=316 중앙 1.40  (폰트 성질. 측정 검산용)

  쓰지 않는 값 — 측정이 아직 불안정하다
    판면 마진      회전 좌표 미반영으로 음수가 나옴
    열 개수·열 폭   과분할 때문에 값이 뭉개짐
    활자 크기 비    인접 비가 1.0~1.2 에 몰림 = 측정 오차가 지배
    디센더         검출 실패율이 높음
───
"""
import os
from statistics import median

import rules

# 캐시는 코드 폴더 밖에 둔다. git pull 로 덮이거나 저장소에 올라가면 안 된다.
CACHE = os.environ.get(
    'TYPO_MCP_CACHE',
    os.path.join(os.path.expanduser('~'), '.typo-mcp', 'corpus.json'))
os.makedirs(os.path.dirname(CACHE), exist_ok=True)

# 짚어준 상자로 쌓는 코퍼스는 기본 캐시와 따로 둔다. 자동 검출한 분포와
# 섞으면 규칙이 어느 방법에서 나왔는지 말할 수 없다.
GROUNDED = os.path.join(os.path.dirname(CACHE), 'grounded.json')

CACHE_ARG = {"type": "string", "description":
             "볼 코퍼스 파일. 생략하면 기본 캐시. 짚어서 쌓은 코퍼스는 따로 있다"}


def _cache(a=None):
    """도구마다 cache 인자로 다른 코퍼스를 볼 수 있다. 없으면 기본 캐시."""
    p = (a or {}).get('cache')
    return os.path.expanduser(p) if p else CACHE


def _rules(a=None):
    return rules.load(_cache(a))


def _need(a=None):
    return {"ok": False,
            "error": "규칙이 없다. measure_corpus 로 포스터 디렉토리를 먼저 측정하라",
            "cache": _cache(a)}


def _lines(b):
    return sorted(b.get("lines", []), key=lambda l: l["baseline"])


def _lead(b):
    ls = _lines(b)
    if len(ls) < 2:
        return None
    return median([ls[i + 1]["baseline"] - ls[i]["baseline"] for i in range(len(ls) - 1)])


def _entry(R, key="lead_over_cap"):
    """채택 여부와 무관하게 그 지표의 항목을 찾는다."""
    R = R or {}
    return R.get("rules", {}).get(key) or R.get("not_rules", {}).get(key)


def _layers(R, key="lead_over_cap"):
    """계층 목록. 계층이 없는 지표는 항목 자신을 유일한 계층으로 본다."""
    e = _entry(R, key)
    if not e:
        return []
    return e.get("layers") or [e]


def _layer_list(R, key="lead_over_cap"):
    """호출하는 쪽에 보여줄 계층 요약. 번호는 1부터."""
    return [{"layer": i, "label": x["label"], "median": x["median"],
             "band": [x["lo"], x["hi"]],
             "observed": [x.get("min", x["lo"]), x.get("max", x["hi"])],
             "n": x["n"], "verdict": x["verdict"]}
            for i, x in enumerate(_layers(R, key), 1)]


def _pick(R, sel, key="lead_over_cap"):
    """쓸 계층을 고른다. sel 이 없으면 대표 계층 — 예전과 같은 동작.

    본문인지 실무 정보인지는 코퍼스가 모르는 정보다. 호출하는 쪽이 정한다.
    """
    ls = _layers(R, key)
    if sel is None:
        return _entry(R, key) if not ls else (R.get("rules", {}).get(key) or ls[0]), None
    try:
        i = int(sel)
    except (TypeError, ValueError):
        return None, f"layer 는 1~{len(ls)} 의 정수다: {sel!r}"
    if not 1 <= i <= len(ls):
        return None, f"layer 는 1~{len(ls)} 여야 한다. 받은 값 {i}"
    return ls[i - 1], None
