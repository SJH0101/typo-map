"""스타일 뇌를 꺼내 쓰는 도구.

목록이 아니라 그래프를 낸다. 마디에는 값과 판정이, 선에는 «함께 움직인다»
가 실린다. 그리고 cannot_say 에 이 뇌가 «말할 수 없는 것» 이 함께 실린다 —
받아 쓰는 쪽이 한계를 모르면 없는 것을 주장하게 된다.

뇌는 코퍼스마다 하나다. 캐시를 굽고 나서 build 로 한 번 만들어 두고,
그 뒤로는 읽기만 한다 — 선을 찾는 데 순열 4000번이 들어 시간이 걸린다.
"""
import json
import os

import brain as _brain
import rules
from tools.shared import CACHE_ARG, _cache, _need


def _path(cache):
    d, f = os.path.dirname(cache), os.path.basename(cache)
    return os.path.join(d, 'brain-' + f)


def _slug(name):
    """파일 이름으로 쓸 수 있게. 한글은 그대로 두고 경로에 못 쓰는 것만 뺀다."""
    bad = '/\\:*?"<>|'
    return ''.join(c for c in name.strip() if c not in bad).replace(' ', '_') or 'corpus'


def add_designer(args):
    """폴더 하나로 작가를 늘린다 — 측정 · 규칙 · 뇌까지 한 번에.

    새 작가를 붙이는 데 필요한 것은 포스터 폴더와 이름뿐이다. 나머지는
    이미 있는 조각을 순서대로 부른다.
    """
    import glob
    import rules as _rules

    name = (args.get("name") or "").strip()
    d = os.path.expanduser(args.get("directory") or "")
    if not name:
        return {"ok": False, "error": "작가 이름이 필요하다"}
    if not d or not os.path.isdir(d):
        return {"ok": False, "error": f"디렉토리를 찾을 수 없다: {d}"}

    pats = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG")
    rec = args.get("recursive", True)
    paths = sorted(p for q in pats for p in
                   (glob.glob(os.path.join(d, "**", q), recursive=True) if rec
                    else glob.glob(os.path.join(d, q))))
    if args.get("limit"):
        paths = paths[:int(args["limit"])]
    if not paths:
        return {"ok": False, "error": f"이미지가 없다: {d}"}

    slug = _slug(name)
    cache = os.path.join(os.path.dirname(_cache(args)), slug + ".json")
    errors = []
    import measure_corpus as MC                       # 옛 경로(baseline/scan)를 더 쓰지 않는다
    raw, _failed = MC.measure_items(MC.items_of(paths), log=None)
    errors += [{"path": p, "why": why} for p, why in _failed]
    if not raw:
        return {"ok": False, "error": "측정에 성공한 포스터가 없다", "failed": errors}
    # 폴더 구조를 이름에 담는다 — 나중에 계열별로 나눠 볼 수 있다
    keyed = {}
    for p in paths:
        b = os.path.basename(p)
        if b not in raw:
            continue
        rel = os.path.relpath(p, d)
        keyed["__".join(rel.split(os.sep)) if os.sep in rel else b] = raw[b]

    R = _rules.derive(keyed)
    _rules.save(cache, keyed, R, provenance=MC.provenance(source=cache, n=len(keyed)))
    b = _brain.build(keyed, name, derived=R)
    bp = _path(cache)
    json.dump(b, open(bp, "w"), ensure_ascii=False)

    out = {"ok": True, "who": name, "cache": cache, "brain": bp,
           "n_found": len(paths), "n_measured": len(keyed),
           "n_failed": len(errors), "failed": errors[:10],
           "n_nodes": len(b["nodes"]), "n_edges": len(b["edges"]),
           "edges_estimable": b["edges_estimable"],
           "rules": list(R["rules"]),
           "note": "이제 style_brain 에 cache 로 이 경로를 주면 이 작가의 뇌가 나온다."}
    if not b["edges_estimable"]:
        out["warning"] = (f'포스터 {b["n_posters"]}장으로는 선을 잴 수 없다 '
                          f'(마디 {len(b["nodes"])}개를 서로 붙들고 재려면 '
                          f'{b["edges_need"]}장 필요). 마디의 값은 쓸 수 있다.')
    return out


def pool_brains(args):
    """코퍼스 여럿을 합쳐 하나의 뇌로. 어느 조합이든 된다.

    한 작가로는 표본이 모자라 안 보이던 관계가 합치면 보일 수 있다. 다만
    그냥 합치면 작가별 수준 차이가 가짜 선을 만들므로, 코퍼스마다 제 안에서
    순위를 매긴 뒤 합쳐서 잰다 (brain.build_pooled 참조).
    """
    raws, missing = {}, []
    for name, p in (args.get("corpora") or {}).items():
        p = os.path.expanduser(p)
        if not os.path.exists(p):
            missing.append({"name": name, "path": p}); continue
        d = json.load(open(p))
        if "raw" not in d:
            missing.append({"name": name, "why": "원자료가 없는 파일이다 (캐시를 줘라)"}); continue
        raws[name] = d["raw"]
    if len(raws) < 2:
        return {"ok": False, "error": "합칠 코퍼스가 둘 이상 필요하다", "skipped": missing}
    who = args.get("name") or ("합침: " + " + ".join(raws))
    b = _brain.build_pooled(raws, who)
    dst = args.get("save")
    if dst:
        dst = os.path.expanduser(dst)
    else:
        dst = os.path.join(os.path.dirname(_cache(args)), "brain-pool-" + _slug(who) + ".json")
    json.dump(b, open(dst, "w"), ensure_ascii=False)
    out = {"ok": True, "who": who, "brain": dst, "n_posters": b["n_posters"],
           "n_edges": len(b["edges"]), "edges_estimable": b["edges_estimable"],
           "pooled_from": b["pooled_from"]}
    if missing:
        out["skipped"] = missing
    return out


def list_brains(args):
    """만들어 둔 뇌 목록."""
    d = os.path.dirname(_cache(args))
    out = []
    for f in sorted(os.listdir(d)):
        if not (f.startswith("brain-") or f.endswith(".json")):
            continue
        p = os.path.join(d, f)
        try:
            b = json.load(open(p))
        except Exception:
            continue
        if not isinstance(b, dict) or "nodes" not in b or "edges" not in b or not b.get("who"):
            continue
        out.append(dict(who=b.get("who"), file=p, n_posters=b.get("n_posters"),
                        n_edges=len(b.get("edges") or []),
                        estimable=b.get("edges_estimable"),
                        pooled=bool(b.get("pooled_from"))))
    return {"ok": True, "dir": d, "brains": out}


def compare_brains(args):
    """뇌 둘 이상을 겹쳐 본다. 비교는 여기서만 한다 — 뇌 자체는 혼자 선다."""
    got, missing = {}, []
    for name, p in (args.get("brains") or {}).items():
        p = os.path.expanduser(p)
        bp = p if os.path.basename(p).startswith('brain-') else _path(p)
        if not os.path.exists(bp):
            missing.append({"name": name, "path": bp}); continue
        b = json.load(open(bp))
        if not b.get("edges_estimable", True):
            missing.append({"name": name, "why": f'선을 잴 수 없는 뇌다 '
                            f'({b.get("edges_have")}장, {b.get("edges_need")}장 필요)'})
            continue
        got[name] = b
    if len(got) < 2:
        return {"ok": False, "error": "겹칠 뇌가 둘 이상 필요하다", "skipped": missing}
    r = _brain.compare(got)
    if missing:
        r["skipped"] = missing
    return {"ok": True, **r}


def style_brain(args):
    """뇌를 낸다. 없으면 만든다 (build=true 면 있어도 다시 만든다)."""
    cache = _cache(args)
    if not os.path.exists(cache):
        return _need(args)
    bp = _path(cache)
    if os.path.exists(bp) and not args.get("build"):
        b = json.load(open(bp))
    else:
        d = json.load(open(cache))
        b = _brain.build(d["raw"], args.get("who") or os.path.basename(cache)[:-5],
                         derived=d.get("rules"))
        json.dump(b, open(bp, "w"), ensure_ascii=False)
    if args.get("view") == "edges":
        b = {k: v for k, v in b.items() if k != "nodes"}
    elif args.get("view") == "nodes":
        b = {k: v for k, v in b.items() if k != "edges"}
    return {"ok": True, "cache": cache, "brain": bp, **b}


TOOLS = [
    {"name": "style_brain",
     "description": ("한 작가의 스타일을 «그래프» 로 낸다. 마디는 측정된 속성과 그 값·판정, "
                     "선은 그 작가 «안에서» 함께 움직이는 속성 쌍이다. "
                     "값 목록(show_rules·style_card)으로는 작가가 잘 안 갈린다 — 몰린 값은 "
                     "여러 작가가 공유하고(폰트 상수) 갈리는 값은 흩어져 있기 때문이다. "
                     "갈리는 것은 «묶임» 이라 그래프로 낸다. 생성할 때는 선으로 묶인 마디를 "
                     "따로 뽑으면 안 된다. cannot_say 를 반드시 함께 읽어라."),
     "inputSchema": {"type": "object", "properties": {
         "cache": CACHE_ARG,
         "who": {"type": "string", "description": "작가 이름. 뇌에 이름표로 실린다"},
         "view": {"type": "string", "enum": ["all", "nodes", "edges"],
                  "description": "all(기본) · nodes 만 · edges 만"},
         "build": {"type": "boolean",
                   "description": "이미 만들어 둔 뇌가 있어도 다시 만든다. 순열 2000번이라 느리다"}}}},
    {"name": "add_designer",
     "description": ("포스터 폴더 하나로 새 작가를 늘린다. 측정·규칙 채택·뇌 만들기를 "
                     "한 번에 한다. 이름과 폴더만 주면 된다. "
                     "포스터가 적으면 선을 못 재는데(마디 수의 3배는 필요) 그때는 "
                     "warning 으로 알린다 — 선이 0개인 것과 못 잰 것은 다르다."),
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "작가 이름. 뇌의 이름표가 된다"},
         "directory": {"type": "string", "description": "포스터 이미지가 있는 폴더"},
         "recursive": {"type": "boolean", "description": "하위 폴더까지 훑는다 (기본 true)"},
         "limit": {"type": "integer", "description": "앞에서 이 개수만 (시험용)"},
         "cache": CACHE_ARG},
         "required": ["name", "directory"]}},
    {"name": "list_brains",
     "description": "만들어 둔 뇌 목록. 어느 작가가 있고 몇 장이며 선을 잴 수 있는지 낸다.",
     "inputSchema": {"type": "object", "properties": {"cache": CACHE_ARG}}},
    {"name": "pool_brains",
     "description": ("코퍼스 여럿을 합쳐 하나의 뇌로 만든다. 한 작가로는 표본이 모자라 안 보이던 "
                     "관계가 보일 수 있다. 그냥 합치면 작가별 값 수준 차이가 가짜 선을 만들므로 "
                     "코퍼스마다 제 안에서 순위를 매긴 뒤 합쳐서 잰다. 그래서 여기 선은 "
                     "«누구의 작업이든 한 사람 안에서 함께 움직이는» 관계지 어느 한 사람의 것이 아니다."),
     "inputSchema": {"type": "object", "properties": {
         "corpora": {"type": "object", "description": "{이름: 캐시경로}. 둘 이상",
                     "additionalProperties": {"type": "string"}},
         "name": {"type": "string", "description": "합친 뇌의 이름표"},
         "save": {"type": "string", "description": "저장할 경로. 생략하면 캐시 옆에"},
         "cache": CACHE_ARG},
         "required": ["corpora"]}},
    {"name": "compare_brains",
     "description": ("뇌 둘 이상을 겹쳐 본다. 마디마다 값이 갈리는지, 선마다 누구에게 있는지를 낸다. "
                     "뇌 하나는 혼자 서므로 비교는 필요할 때만 부른다. "
                     "여럿에게 다 나온 선은 셈법에서 오는 것일 가능성이 높고, 한 명에게만 나온 선은 "
                     "그의 것일 수도 표본이 작아 남들에게서 안 잡힌 것일 수도 있다."),
     "inputSchema": {"type": "object", "properties": {
         "brains": {"type": "object",
                    "description": "{이름: 캐시경로 또는 뇌파일경로}. 둘 이상 필요하다",
                    "additionalProperties": {"type": "string"}}},
         "required": ["brains"]}},
]

FUNCS = dict(style_brain=style_brain, compare_brains=compare_brains,
             add_designer=add_designer, list_brains=list_brains,
             pool_brains=pool_brains)
