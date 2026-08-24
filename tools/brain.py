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
        refs = {}
        for name, p in (args.get("reference") or {}).items():
            p = os.path.expanduser(p)
            if os.path.exists(p):
                refs[name] = json.load(open(p))["raw"]
        b = _brain.build(d["raw"], args.get("who") or os.path.basename(cache)[:-5],
                         references=refs or None, derived=d.get("rules"))
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
                   "description": "이미 만들어 둔 뇌가 있어도 다시 만든다. 순열 4000번이라 느리다"},
         "reference": {"type": "object",
                       "description": ("다른 작가의 캐시 {이름: 경로}. 주면 선마다 «그에게만인가» 를 "
                                       "가린다. 없으면 기계적인 선과 양식적인 선이 섞인다"),
                       "additionalProperties": {"type": "string"}}}}},
]

FUNCS = dict(style_brain=style_brain)
