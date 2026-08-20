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
    errors = []
    raw = rules.collect(paths, errors=errors)
    if not raw:
        return {"ok": False, "error": "측정에 성공한 포스터가 없다", "failed": errors}
    r = rules.derive(raw)
    rules.save(CACHE, raw, r)
    return {"ok": True, "cache": CACHE, "n_found": len(paths), **r,
            "n_failed": len(errors), "failed": errors,
            "note": ("실패한 포스터는 failed 에 이유와 함께 나온다. 조용히 빠지지 않는다.")}


def show_rules(args):
    R = _rules()
    if not R:
        return _need()
    return {"ok": True, "cache": CACHE, **R}


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
            out.update(rules.color_features(p))
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
    R = _rules()
    if not R:
        return _need()
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


def style_card(args):
    """AI 가 추론에 쓸 정량 데이터. 결론은 담지 않는다.

    show_rules 는 사람이 읽는 리포트다. 이쪽은 소비자가 스스로 판단할 수 있게
    재료를 준다 — 대표값 하나가 아니라 흔들림·표본 수·계층 수·무엇이 빠졌는지·
    참조와 어떻게 다른지를 함께 넘긴다. 「유파 공통 문법」 같은 해석은 쓰지
    않는다. 그건 이 숫자를 읽는 쪽의 몫이다.
    """
    R = _rules()
    if not R:
        return _need()
    d = json.load(open(CACHE))
    raw = d.get("raw", {})

    refs = {}
    for name, path in (args.get("reference") or {}).items():
        p = os.path.expanduser(path)
        if os.path.exists(p):
            refs[name] = json.load(open(p)).get("raw", {})
    if refs:
        refs = dict({"이 코퍼스": raw}, **refs)

    n_rot = sum(1 for v in raw.values() if abs(v.get("angle", 0)) >= 1)

    # 사진 판정은 선택 기능이다. 켜져 있을 때만 원자료에 들어 있다.
    # 지표를 못 낸 포스터가 무작위가 아니라는 것을 말하는 데 쓴다.
    seen = [v for v in raw.values() if v.get("photo")]
    pic = None
    if seen:
        by = {"있음": 0, "없음": 0, "모름": 0}
        labs = {}
        for v in seen:
            by[v["photo"].get("verdict", "모름")] = by.get(v["photo"].get("verdict", "모름"), 0) + 1
            for o in v["photo"]["objects"]:
                labs[o["label"]] = labs.get(o["label"], 0) + 1
        pic = {"judged": len(seen), **by,
               "objects": dict(sorted(labs.items(), key=lambda t: -t[1])[:6]),
               "how": ("깊이 기울기와 COCO 물체 검출을 함께 본다. 두 근거가 같은 쪽을 "
                       "가리킬 때만 확정하고 엇갈리면 「모름」 으로 둔다. 네 코퍼스 71장을 "
                       "손으로 라벨해 재니 「있음」 10장은 10장 다 맞았고(100%), "
                       "「없음」 41장은 38장 맞았다(93%). 30% 는 모름으로 남는다."),
               "read_as": "「모름」 은 사진이 없다는 뜻이 아니라 가리지 못했다는 뜻이다",
               "not_used_for": "측정을 바꾸지 않는다. 사진 위에 얹힌 진짜 글자까지 지우게 된다"}
    out = {}
    for key, (fn, label, unit) in rules.METRICS.items():
        e = R["rules"].get(key) or R["not_rules"].get(key)
        if not e:
            out[key] = {"label": label, "verdict": "값 없음",
                        "note": "이 코퍼스에서 이 지표를 하나도 뽑지 못했다"}
            continue
        layers = e.get("layers") or [e]
        card = {
            "label": label, "unit": rules.UNITS.get(key, unit),
            "verdict": e["verdict"],
            "median": e["median"], "cv": e["cv"], "n": e["n"],
            "range_10_90": [e["lo"], e["hi"]],
            "observed": [e.get("min"), e.get("max")],
            "n_layers": len(layers),
            # n 은 측정값 수, from_posters 는 그 값을 낸 포스터 수다. 행간처럼
            # 한 장에서 여러 값이 나오는 지표는 둘이 크게 다르고, 값을 못 낸
            # 포스터는 무작위가 아니라 사진·해상도 한계에 몰려 있다.
            "sample": {"n": e.get("n_all", e["n"]),
                       "from_posters": e.get("n_posters"),
                       "of_posters": e.get("n_posters_all", len(raw))},
        }
        if len(layers) > 1:
            card["layers"] = [{"median": x["median"], "cv": x["cv"], "n": x["n"],
                               "range_10_90": [x["lo"], x["hi"]],
                               "observed": [x.get("min"), x.get("max")],
                               "verdict": x["verdict"]} for x in layers]
        if e.get("coverage"):
            card["sample"]["note"] = e["coverage"]
        if pic is not None:
            card["sample"]["pictures"] = pic
        if key in rules.EXCLUDES:
            card["sample"]["excluded"] = n_rot
            card["sample"]["exclusion_reason"] = rules.EXCLUDES[key]
        if refs:
            c = rules.compare(key, refs)
            if c:
                card["reference"] = c
        out[key] = card

    return {"ok": True, "cache": CACHE,
            "n_posters": len(raw),
            "criteria": R.get("criteria"),
            "metrics": out,
            "blocked": rules.BLOCKED,
            "reading": {
                "verdict": {"제약": "이 값을 지켜라",
                            "자유": "재봤으나 규칙이 아니다. range_10_90 에서 뽑아 쓸 수는 있다",
                            "표본 부족": "판정하지 못했다. n 과 criteria.n_min 을 비교하라",
                            "혼합": "여러 작은 계층을 모은 잔여물이다. 하나의 무리가 아니므로 규칙으로 쓰지 마라"},
                "n_layers": "1 보다 크면 단봉이 아니다. median 하나로 읽지 마라",
                "reference": ("separating_pairs 가 0 이면 지금 참조로는 이 지표가 아무도 "
                              "구분하지 못한다는 뜻이다. 그것이 지표의 성질인지 참조가 "
                              "치우쳐서인지는 이 도구가 알 수 없다"),
                "blocked": "재려 했으나 못 잰 항목. reason 과 blocked_by 를 보고 필요하면 더 나은 입력을 요구하라"},
            "note": "결론은 담지 않는다. 이 숫자로 판단하는 것은 읽는 쪽이다."}


def place_text(args):
    R = _rules()
    if not R:
        return _need()
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
    {"name": "style_card",
     "description": ("AI 가 추론에 쓸 정량 데이터를 낸다. 대표값 하나가 아니라 흔들림·표본 수·"
                     "계층 수·제외된 것·참조와의 차이를 함께 준다. 해석과 결론은 담지 않는다. "
                     "사람이 읽을 리포트가 필요하면 show_rules 를 써라."),
     "inputSchema": {"type": "object", "properties": {
         "reference": {"type": "object",
                       "description": ("참조 코퍼스. {이름: 캐시경로}. 주면 지표마다 "
                                       "중앙값 차이와 신뢰구간이 갈리는 쌍 수를 함께 낸다"),
                       "additionalProperties": {"type": "string"}}}}},
    {"name": "place_text",
     "description": ("활자 크기와 줄 수를 주면 행간과 베이스라인을 계산한다. "
                     "모든 블록이 하나의 격자를 정수배로 공유하게 만든다. "
                     "가로 위치와 판면 구성은 계산하지 않는다."),
     "inputSchema": {"type": "object", "properties": {
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

FUNCS = {"measure_corpus": measure_corpus, "show_rules": show_rules, "style_card": style_card,
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
