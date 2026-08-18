"""브로크만 조판 MCP 서버 — 검사기 + 텍스트 배치기.

규칙 수치를 코드에 박지 않는다. measure_corpus 로 포스터 디렉토리를 측정해
분포를 내고, 몰려 있는 것만 규칙으로 채택한다 (rules.py).
캐시가 없으면 place_text·check_layout 은 규칙이 없다고 답한다.

실행:  python server.py
등록:  claude mcp add brockmann -- python /경로/server.py
"""
import json
import os
import sys
from statistics import median

import rules

# ─────────────────────────────────────────────────────────────────────────
# 실측 근거
#
#   표본: 프로젝트 포스터 44점 무작위 추출, 자동 측정 (2026-08)
#   검증: 1958 Musica Viva 25줄 · 1958 Végh-Quartett 17줄을 사람이 직접 찍어
#         자동값과 대조. 베이스라인 22/25 가 0px 일치, 회전 포스터 각도 0.1° 차.
#
#   쓸 수 있는 값
#     행간/활자높이   n=38  중앙 1.50  10~90% 1.30~1.83  변동계수 0.12
#     여백(행간−활자)  n=38  중앙 4.2px 10~90% 3.0~6.5   음수 0개
#     좌측 정렬선     n=36  블록 중앙 8개에 정렬선 중앙 3개
#     어센더/x높이    n=316 중앙 1.40  (폰트 성질. 측정 검산용)
#
#   쓰지 않는 값 — 측정이 아직 불안정하다
#     판면 마진      회전 좌표 미반영으로 음수가 나옴
#     열 개수·열 폭   과분할 때문에 값이 뭉개짐
#     활자 크기 비    인접 비가 1.0~1.2 에 몰림 = 측정 오차가 지배
#     디센더         검출 실패율이 높음
# ─────────────────────────────────────────────────────────────────────────

# 캐시는 코드 폴더 밖에 둔다. git pull 로 덮이거나 저장소에 올라가면 안 된다.
CACHE = os.environ.get(
    'TYPO_MCP_CACHE',
    os.path.join(os.path.expanduser('~'), '.typo-mcp', 'corpus.json'))
os.makedirs(os.path.dirname(CACHE), exist_ok=True)

GAP_MIN_FALLBACK = 1.0     # 여백은 실측에서 「자유」로 나왔다. 겹침만 막는다.


def _rules():
    return rules.load(CACHE)


def _need():
    return {"ok": False,
            "error": "규칙이 없다. measure_corpus 로 포스터 디렉토리를 먼저 측정하라",
            "cache": CACHE}


def _lines(b):
    return sorted(b.get("lines", []), key=lambda l: l["baseline"])


def _lead(b):
    ls = _lines(b)
    if len(ls) < 2:
        return None
    return median([ls[i + 1]["baseline"] - ls[i]["baseline"] for i in range(len(ls) - 1)])


def _band(R):
    r = (R or {}).get("rules", {}).get("lead_over_cap")
    return r


# ── 도구 ─────────────────────────────────────────────────────────────────

def measure_corpus(args):
    """디렉토리의 포스터를 측정해 규칙을 뽑고 캐시에 저장한다."""
    import glob
    d = args.get("directory")
    if not d or not os.path.isdir(d):
        return {"ok": False, "error": f"디렉토리를 찾을 수 없다: {d}"}
    pats = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG")
    paths = sorted(p for q in pats for p in glob.glob(os.path.join(d, q)))
    limit = args.get("limit")
    if limit:
        paths = paths[:int(limit)]
    if not paths:
        return {"ok": False, "error": "이미지가 없다"}
    raw = rules.collect(paths)
    if not raw:
        return {"ok": False, "error": "측정에 성공한 포스터가 없다"}
    r = rules.derive(raw)
    rules.save(CACHE, raw, r)
    return {"ok": True, "cache": CACHE, "n_found": len(paths), **r,
            "note": ("측정 실패한 포스터는 조용히 제외된다. n_posters 와 n_found 가 크게 다르면 "
                     "회전·색반전 등으로 측정이 깨진 것이다.")}


def show_rules(args):
    R = _rules()
    if not R:
        return _need()
    return {"ok": True, "cache": CACHE, **R}


def check_layout(args):
    R = _rules()
    if not R:
        return _need()
    band = _band(R)
    blocks = args.get("blocks", [])
    if not blocks:
        return {"ok": False, "error": "blocks 가 비어 있다"}
    v = []
    for b in blocks:
        lead, h = _lead(b), b.get("cap_height")
        if not lead or not h:
            continue
        if band:
            r = lead / h
            if r < band["lo"] or r > band["hi"]:
                v.append({"rule": band["label"], "block": b.get("id"), "value": round(r, 2),
                          "expected": f'{band["lo"]}~{band["hi"]}',
                          "fix": round(h * band["median"], 1),
                          "message": (f'행간이 활자 높이의 {r:.2f}배. 코퍼스 10~90% 는 '
                                      f'{band["lo"]}~{band["hi"]}배 (n={band["n"]}, CV {band["cv"]})')})
        if lead - h < GAP_MIN_FALLBACK:
            v.append({"rule": "줄 겹침", "block": b.get("id"), "value": round(lead - h, 1),
                      "expected": f"{GAP_MIN_FALLBACK}px 이상",
                      "message": "윗줄과 아랫줄이 붙는다"})
        ls = _lines(b)
        if len(ls) >= 3:
            g = [ls[i + 1]["baseline"] - ls[i]["baseline"] for i in range(len(ls) - 1)]
            if max(g) - min(g) > 1:
                v.append({"rule": "블록 내 행간 일정", "block": b.get("id"),
                          "value": f"{min(g)}~{max(g)}", "expected": "편차 1px 이내",
                          "message": "한 블록 안에서 행간이 흔들린다"})
    return {"ok": not v, "n_blocks": len(blocks), "n_violations": len(v), "violations": v,
            "checked_against": {k: {"n": x["n"], "cv": x["cv"]} for k, x in R["rules"].items()},
            "not_checked": [x["label"] for x in R["not_rules"].values()],
            "note": "코퍼스에서 「자유」로 판정된 항목은 검사하지 않는다."}


def place_text(args):
    R = _rules()
    if not R:
        return _need()
    band = _band(R)
    if not band:
        return {"ok": False, "error": "행간 규칙이 코퍼스에서 채택되지 않았다. 표본을 늘려라"}
    blocks = args.get("blocks", [])
    if not blocks:
        return {"ok": False, "error": "blocks 가 비어 있다"}
    grid = args.get("grid_lead")
    if grid is None:
        hs = [b["cap_height"] for b in blocks if b.get("cap_height")]
        if not hs:
            return {"ok": False, "error": "cap_height 가 있는 블록이 없다"}
        grid = max(1, round(min(hs) * band["median"]))
    out, notes = [], []
    for b in blocks:
        h, n = b.get("cap_height"), int(b.get("n_lines", 1))
        if not h:
            notes.append(f'{b.get("id")}: cap_height 없음, 건너뜀')
            continue
        k = max(1, round(h * band["median"] / grid))
        lead = k * grid
        while lead - h < GAP_MIN_FALLBACK:
            k += 1
            lead = k * grid
        first = float(b.get("y", 0)) + h
        r = lead / h
        out.append({"id": b.get("id"), "x": b.get("x"), "cap_height": h,
                    "lead": lead, "lead_ratio": round(r, 2), "grid_multiple": k,
                    "baselines": [round(first + i * lead, 1) for i in range(n)],
                    "in_range": band["lo"] <= r <= band["hi"]})
        if not (band["lo"] <= r <= band["hi"]):
            notes.append(f'{b.get("id")}: 격자 정수배로 맞추니 비가 {r:.2f} 로 코퍼스 범위 밖')
    return {"ok": True, "grid_lead": grid, "blocks": out, "notes": notes,
            "based_on": {"n": band["n"], "median": band["median"], "cv": band["cv"]},
            "not_computed": ["x 좌표", "판면 마진", "이미지 영역과의 관계"],
            "note": "모든 블록의 행간을 하나의 격자의 정수배로 맞춘다."}


TOOLS = [
    {"name": "measure_corpus",
     "description": ("포스터 디렉토리를 측정해 조판 규칙을 뽑아 캐시에 저장한다. "
                     "값이 몰린 지표만 「제약」으로 채택하고, 흩어진 것은 「자유」로 기록한다. "
                     "다른 디자이너의 포스터를 넣으면 그 디자이너의 규칙이 나온다."),
     "inputSchema": {"type": "object", "properties": {
         "directory": {"type": "string", "description": "포스터 이미지가 있는 폴더"},
         "limit": {"type": "integer", "description": "앞에서 이 개수만 측정 (시험용)"}},
         "required": ["directory"]}},
    {"name": "show_rules",
     "description": "캐시에 저장된 규칙과 각 지표의 분포·표본 수·채택 여부를 보여준다.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "place_text",
     "description": ("활자 크기와 줄 수를 주면 행간과 베이스라인을 계산한다. "
                     "모든 블록이 하나의 격자를 정수배로 공유하게 만든다. "
                     "가로 위치와 판면 구성은 계산하지 않는다."),
     "inputSchema": {"type": "object", "properties": {
         "grid_lead": {"type": "number", "description": "격자 간격(px). 생략하면 가장 작은 활자에서 정한다"},
         "blocks": {"type": "array", "items": {"type": "object", "properties": {
             "id": {"type": "string"}, "x": {"type": "number"},
             "y": {"type": "number", "description": "블록 상단"},
             "cap_height": {"type": "number"}, "n_lines": {"type": "integer"}},
             "required": ["cap_height", "n_lines"]}}},
         "required": ["blocks"]}},
    {"name": "check_layout",
     "description": "배치안을 캐시의 규칙과 대조해 위반 목록을 돌려준다.",
     "inputSchema": {"type": "object", "properties": {
         "blocks": {"type": "array", "items": {"type": "object", "properties": {
             "id": {"type": "string"}, "x": {"type": "number"},
             "cap_height": {"type": "number"},
             "lines": {"type": "array", "items": {"type": "object", "properties": {
                 "baseline": {"type": "number"}}}}},
             "required": ["lines"]}}},
         "required": ["blocks"]}},
]

FUNCS = {"measure_corpus": measure_corpus, "show_rules": show_rules,
         "place_text": place_text, "check_layout": check_layout}


def rpc(req):
    m, i = req.get("method"), req.get("id")
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": i, "result": {
            "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "brockmann", "version": "0.3.0"}}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": i, "result": {"tools": TOOLS}}
    if m == "tools/call":
        p = req.get("params", {})
        fn = FUNCS.get(p.get("name"))
        r = fn(p.get("arguments", {})) if fn else {"error": f'unknown tool {p.get("name")}'}
        return {"jsonrpc": "2.0", "id": i, "result": {
            "content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}}
    if i is None:
        return None
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"unknown method {m}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            res = rpc(json.loads(line))
        except Exception as e:
            res = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
        if res is not None:
            print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
