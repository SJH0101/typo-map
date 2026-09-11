"""배치를 다루는 도구 — 규칙대로 놓고, 놓은 것을 규칙과 대조한다."""
import os
from statistics import median

from tools.shared import (CACHE_ARG, _rules, _need, _lines, _lead,
                          _layers, _layer_list, _pick)

GAP_MIN_FALLBACK = 1.0     # 여백은 실측에서 「자유」로 나왔다. 겹침만 막는다.


def _candidate(args):
    """검사할 배치안에서 지표 값을 뽑는다.

    코퍼스를 잰 것과 같은 함수로 재야 비교가 성립한다. 이미지를 주면
    color_features 를 그대로 태우고, 블록만 주면 기하 지표만 낸다.
    """
    out, notes = {}, []
    canvas = args.get("canvas") or {}
    W, H = canvas.get("w"), canvas.get("h")
    blocks = args.get("blocks", [])

    caps = [b["cap_height"] for b in blocks if b.get("cap_height")]
    if len(caps) >= 2:
        out["cap_range"] = max(caps) / min(caps)
    out["n_blocks"] = len(blocks)

    xs = [b["x"] for b in blocks if b.get("x") is not None]
    x2 = [b["x"] + b["x_width"] for b in blocks
          if b.get("x") is not None and b.get("x_width") is not None]
    if W and xs:
        out["margin_left"] = min(xs) / float(W)
        if x2:
            out["margin_right"] = (W - max(x2)) / float(W)
        else:
            notes.append("x_width 가 없어 우 마진을 계산하지 못했다")
    tops = [min(l["baseline"] for l in b["lines"]) - (b.get("cap_height") or 0)
            for b in blocks if b.get("lines")]
    bots = [max(l["baseline"] for l in b["lines"]) for b in blocks if b.get("lines")]
    if H and tops:
        out["margin_top"] = min(tops) / float(H)
        out["margin_bottom"] = (H - max(bots)) / float(H)
    if W and H and blocks:
        area = sum((b.get("x_width") or 0) *
                   (max(l["baseline"] for l in b["lines"]) -
                    min(l["baseline"] for l in b["lines"]) + (b.get("cap_height") or 0))
                   for b in blocks if b.get("lines"))
        if area:
            out["text_area"] = area / float(W * H)

    img = args.get("image")
    if img:
        p = os.path.expanduser(img)
        if os.path.exists(p):
            from color import fields          # 코퍼스를 잰 것과 같은 함수 (measure/ground.py 와 같다)
            out.update(fields.features(p))
        else:
            notes.append(f"이미지를 찾을 수 없다: {img}")
    return out, notes


def _position(value, entry):
    """후보 값이 코퍼스 분포의 어디에 있는가. 판정이 아니라 위치다."""
    lo, hi = entry.get("lo"), entry.get("hi")
    mn, mx = entry.get("min", lo), entry.get("max", hi)
    where = ("10~90% 안" if lo is not None and lo <= value <= hi else
             "실측 범위 안, 10~90% 밖" if mn is not None and mn <= value <= mx else
             "코퍼스 실측 범위 밖")
    return {"value": round(float(value), 4), "corpus_median": entry.get("median"),
            "corpus_10_90": [lo, hi], "corpus_observed": [mn, mx], "where": where}


def check_layout(args):
    R = _rules(args)
    if not R:
        return _need(args)
    sel = args.get("layer")
    forced, err = (_pick(R, sel) if sel is not None else (None, None))
    if err:
        return {"ok": False, "error": err, "layers": _layer_list(R)}
    lyr = _layers(R)          # 아래 루프의 ls 는 「줄」이다. 이름을 겹치지 않게 둔다
    blocks = args.get("blocks", [])
    if not blocks:
        return {"ok": False, "error": "blocks 가 비어 있다"}
    v, held = [], []
    for b in blocks:
        lead, h = _lead(b), b.get("cap_height")
        if not lead or not h:
            continue
        if lyr:
            r = lead / h
            # layer 를 지정하면 그 계층으로만 검사한다. 지정하지 않으면 계층 전체를
            # 놓고 본다 — 채택된 계층에 들면 통과, 판정 보류인 계층에 들면 보류,
            # 어느 계층에도 없으면 위반이다. 코퍼스가 아직 판정하지 못한 값을
            # 위반이라고 단정하지 않는다.
            cands = [forced] if forced else lyr
            # 통과는 채택된 계층의 권장 범위(10~90%)로 본다 — 기존 판정 그대로.
            # 보류는 판정 못 한 계층의 실측 전폭으로 본다. 「코퍼스에 그런 값이
            # 있었는가」와 「권장 범위에 드는가」는 다른 질문이다.
            ok_fit = [x for x in cands
                      if x["verdict"] == "제약" and x["lo"] <= r <= x["hi"]]
            held_fit = [x for x in cands
                        if x["verdict"] != "제약"
                        and x.get("min", x["lo"]) <= r <= x.get("max", x["hi"])]
            band = forced or (R.get("rules", {}).get("lead_over_cap") or lyr[0])
            if ok_fit:
                pass
            elif held_fit:
                x = held_fit[0]
                held.append({"block": b.get("id"), "value": round(r, 2),
                             "layer": lyr.index(x) + 1,
                             "layer_observed": [x.get("min", x["lo"]), x.get("max", x["hi"])],
                             "layer_band": [x["lo"], x["hi"]],
                             "message": (f'행간이 활자 높이의 {r:.2f}배. 코퍼스에 '
                                         f'{x.get("min", x["lo"])}~{x.get("max", x["hi"])}배 계층이 '
                                         f'있으나 표본 {x["n"]} 개로 판정 보류다 ({x["verdict"]}). '
                                         f'위반으로 보지 않는다')})
            else:
                v.append({"rule": band["label"], "block": b.get("id"), "value": round(r, 2),
                          "expected": f'{band["lo"]}~{band["hi"]}',
                          "fix": round(h * band["median"], 1),
                          "message": (f'행간이 활자 높이의 {r:.2f}배. 코퍼스의 어느 계층에도 '
                                      f'없다. 채택된 계층은 {band["lo"]}~{band["hi"]}배 '
                                      f'(n={band["n"]}, CV {band["cv"]})')})
        else:
            continue
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
    # ── 나머지 지표 ────────────────────────────────────────────────
    # 「제약」인 지표만 위반으로 센다. 「자유」와 「표본 부족」은 판정하지 않고
    # 후보가 코퍼스 분포의 어디에 있는지만 알려준다. 코퍼스가 규칙이라 말하지
    # 않은 것을 도구가 위반이라 부르면 안 된다.
    cand, cnotes = _candidate(args)
    reference, more_v = {}, []
    for key, val in cand.items():
        if key == "lead_over_cap":
            continue
        e = R["rules"].get(key) or R["not_rules"].get(key)
        if not e:
            continue
        pos = _position(val, e)
        pos["label"] = e["label"]
        pos["corpus_verdict"] = e["verdict"]
        if e["verdict"] == "제약":
            pos["ok"] = pos["where"] == "10~90% 안"
            if not pos["ok"]:
                more_v.append({"rule": e["label"], "block": None,
                               "value": pos["value"],
                               "expected": f'{e["lo"]}~{e["hi"]}',
                               "message": (f'{e["label"]} 가 {pos["value"]}. 코퍼스 10~90% 는 '
                                           f'{e["lo"]}~{e["hi"]} (n={e["n"]}, CV {e["cv"]})')})
        reference[key] = pos
    v = v + more_v

    return {"ok": not v, "n_blocks": len(blocks), "n_violations": len(v), "violations": v,
            "n_held": len(held), "held": held,
            "measured": reference,
            "not_measured": cnotes,
            "layer": (int(sel) if sel is not None else None),
            "layers": _layer_list(R),
            "checked_against": {k: {"n": x["n"], "cv": x["cv"]} for k, x in R["rules"].items()},
            "not_checked": [x["label"] for x in R["not_rules"].values()],
            "note": ("violations 는 「제약」으로 채택된 지표에서만 나온다. 「자유」·「표본 부족」 "
                     "지표는 measured 에 후보의 분포상 위치만 싣는다 — 코퍼스가 규칙이라 하지 "
                     "않은 것을 위반이라 부르지 않는다. canvas 와 블록 x·x_width 를 주면 마진을, "
                     "image 를 주면 색까지 코퍼스와 같은 방식으로 잰다.")}


def place_text(args):
    R = _rules(args)
    if not R:
        return _need(args)
    sel = args.get("layer")
    band, err = _pick(R, sel)
    if err:
        return {"ok": False, "error": err, "layers": _layer_list(R)}
    if not band:
        return {"ok": False, "error": "행간 규칙이 코퍼스에서 채택되지 않았다. 표본을 늘려라",
                "layers": _layer_list(R)}
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
    if band["verdict"] != "제약":
        notes.append(f'고른 계층은 표본 {band["n"]} 개로 판정 보류다 ({band["verdict"]}). '
                     f'배치는 했으나 규칙이라 부를 근거는 아직 없다')
    return {"ok": True, "grid_lead": grid, "blocks": out, "notes": notes,
            "based_on": {"n": band["n"], "median": band["median"], "cv": band["cv"],
                         "verdict": band["verdict"],
                         "layer": (int(sel) if sel is not None else None)},
            "layers": _layer_list(R),
            "not_computed": ["x 좌표", "판면 마진", "이미지 영역과의 관계"],
            "note": ("모든 블록의 행간을 하나의 격자의 정수배로 맞춘다. "
                     "본문인지 실무 정보인지는 코퍼스가 모르므로 layer 로 골라라. "
                     "고르지 않으면 대표 계층을 쓴다.")}


TOOLS = [
    {"name": "place_text",
     "description": ("활자 크기와 줄 수를 주면 행간과 베이스라인을 계산한다. "
                     "모든 블록이 하나의 격자를 정수배로 공유하게 만든다. "
                     "가로 위치와 판면 구성은 계산하지 않는다."),
     "inputSchema": {"type": "object", "properties": {
         "cache": CACHE_ARG,
         "layer": {"type": "integer", "description": ("쓸 행간 계층 번호(1부터). show_rules 의 layers 참조. "
                                                      "생략하면 대표 계층. 코퍼스는 본문인지 실무 정보인지 모른다")},
         "grid_lead": {"type": "number", "description": "격자 간격(px). 생략하면 가장 작은 활자에서 정한다"},
         "blocks": {"type": "array", "items": {"type": "object", "properties": {
             "id": {"type": "string"}, "x": {"type": "number"},
             "y": {"type": "number", "description": "블록 상단"},
             "cap_height": {"type": "number"}, "n_lines": {"type": "integer"}},
             "required": ["cap_height", "n_lines"]}}},
         "required": ["blocks"]}},
    {"name": "check_layout",
     "description": ("배치안을 캐시의 규칙과 대조해 위반 목록을 돌려준다. "
                     "행간 규칙이 여러 계층이면 계층 전체를 놓고 보고, 판정 보류인 계층에 드는 값은 "
                     "위반이 아니라 「보류」로 따로 보고한다."),
     "inputSchema": {"type": "object", "properties": {
         "cache": CACHE_ARG,
         "layer": {"type": "integer", "description": ("이 계층으로만 검사한다(1부터). "
                                                      "생략하면 계층 전체를 놓고 본다")},
         "canvas": {"type": "object", "description": "판면 크기. 주면 마진과 글자 면적을 잰다",
                    "properties": {"w": {"type": "number"}, "h": {"type": "number"}}},
         "image": {"type": "string",
                   "description": ("렌더된 포스터 이미지 경로. 주면 색을 코퍼스와 같은 "
                                   "방식으로 잰다. 다르게 재면 비교가 성립하지 않는다")},
         "blocks": {"type": "array", "items": {"type": "object", "properties": {
             "id": {"type": "string"}, "x": {"type": "number"},
             "x_width": {"type": "number", "description": "블록 가로 폭. 우 마진 계산에 필요"},
             "cap_height": {"type": "number"},
             "lines": {"type": "array", "items": {"type": "object", "properties": {
                 "baseline": {"type": "number"}}}}},
             "required": ["lines"]}}},
         "required": ["blocks"]}},
]

FUNCS = dict(place_text=place_text, check_layout=check_layout)
