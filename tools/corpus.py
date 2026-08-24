"""코퍼스를 보는 도구 — 측정하고, 분포를 보이고, 카드로 낸다."""
import json
import os

import rules
from tools.shared import CACHE_ARG, _cache, _rules, _need, _entry, _layers, _layer_list


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
    raw = scan.collect(paths, errors=errors)
    if not raw:
        return {"ok": False, "error": "측정에 성공한 포스터가 없다", "failed": errors}
    refs, missing = _refs(args)
    r = rules.derive(raw, references=refs or None)
    rules.save(_cache(args), raw, r)
    out = {"ok": True, "cache": _cache(args), "n_found": len(paths), **r,
           "n_failed": len(errors), "failed": errors,
           "note": ("실패한 포스터는 failed 에 이유와 함께 나온다. 조용히 빠지지 않는다.")}
    if missing:
        out["reference_missing"] = missing
    if not refs:
        out["note_scope"] = (
            "reference 를 주지 않아 지표마다 «갈림/공통» 를 가리지 않았다. "
            "다른 작가의 캐시를 주면 이 값이 이 사람의 선택인지 다들 그런 것인지 "
            "함께 낸다 — 폰트 상수는 가장 안 흔들려서 규칙으로 먼저 채택된다.")
    return out


def _refs(args):
    """{이름: 캐시경로} → {이름: 원자료}. 없는 것은 따로 알린다."""
    refs, missing = {}, []
    for name, path in (args.get("reference") or {}).items():
        p = os.path.expanduser(path)
        if not os.path.exists(p):
            missing.append({"name": name, "path": p}); continue
        try:
            refs[name] = json.load(open(p))["raw"]
        except Exception as e:
            missing.append({"name": name, "path": p, "why": f"{type(e).__name__}: {e}"})
    return refs, missing


def show_rules(args):
    R = _rules(args)
    if not R:
        return _need(args)
    return {"ok": True, "cache": _cache(args), **R}


def style_card(args):
    """AI 가 추론에 쓸 정량 데이터. 결론은 담지 않는다.

    show_rules 는 사람이 읽는 리포트다. 이쪽은 소비자가 스스로 판단할 수 있게
    재료를 준다 — 대표값 하나가 아니라 흔들림·표본 수·계층 수·무엇이 빠졌는지·
    참조와 어떻게 다른지를 함께 넘긴다. 「유파 공통 문법」 같은 해석은 쓰지
    않는다. 그건 이 숫자를 읽는 쪽의 몫이다.
    """
    R = _rules(args)
    if not R:
        return _need(args)
    d = json.load(open(_cache(args)))
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

    return {"ok": True, "cache": _cache(args),
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


TOOLS = [
    {"name": "measure_corpus",
     "description": ("포스터 디렉토리를 측정해 조판 규칙을 뽑아 캐시에 저장한다. "
                     "값이 몰린 지표만 「제약」으로 채택하고, 흩어진 것은 「자유」로 기록한다. "
                     "reference 로 다른 작가의 캐시를 주면 «이 사람 것» 인지 «다들 그런 것» 인지 "
                     "함께 가린다. "
                     "다른 디자이너의 포스터를 넣으면 그 디자이너의 규칙이 나온다."),
     "inputSchema": {"type": "object", "properties": {
         "cache": CACHE_ARG,
         "reference": {"type": "object",
                       "description": ("다른 작가의 캐시. {이름: 캐시경로}. 주면 지표마다 "
                                       "«갈림/공통» 를 가린다 — 값이 몰려도 다른 작가와 "
                                       "같으면 작가의 선택이 아니라 폰트·판형에서 오는 것이다"),
                       "additionalProperties": {"type": "string"}},
         "directory": {"type": "string", "description": "포스터 이미지가 있는 폴더"},
         "limit": {"type": "integer", "description": "앞에서 이 개수만 측정 (시험용)"}},
         "required": ["directory"]}},
    {"name": "show_rules",
     "description": "캐시에 저장된 규칙과 각 지표의 분포·표본 수·채택 여부를 보여준다.",
     "inputSchema": {"type": "object", "properties": {
         "cache": CACHE_ARG,}}},
    {"name": "style_card",
     "description": ("AI 가 추론에 쓸 정량 데이터를 낸다. 대표값 하나가 아니라 흔들림·표본 수·"
                     "계층 수·제외된 것·참조와의 차이를 함께 준다. 해석과 결론은 담지 않는다. "
                     "사람이 읽을 리포트가 필요하면 show_rules 를 써라."),
     "inputSchema": {"type": "object", "properties": {
         "cache": CACHE_ARG,
         "reference": {"type": "object",
                       "description": ("참조 코퍼스. {이름: 캐시경로}. 주면 지표마다 "
                                       "중앙값 차이와 신뢰구간이 갈리는 쌍 수를 함께 낸다"),
                       "additionalProperties": {"type": "string"}}}}},
]

FUNCS = dict(measure_corpus=measure_corpus, show_rules=show_rules, style_card=style_card)
