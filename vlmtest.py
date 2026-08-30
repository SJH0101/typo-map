"""VLM 이 자연어로 쓴 «디자인 원리» 를 코퍼스로 검사한다.

booktest.py 는 브로크만이 «책에» 쓴 규칙을 그의 포스터로 검사한다. 이
모듈은 같은 자리에 다른 입력을 넣는다 — 작가가 쓴 규칙 대신 VLM 이 포스터를
보고 쓴 규칙을.

PRISM(arXiv 2601.11747) 이 하는 일이 그것이다. VLM 에게 예시를 보이고
자연어 가이드라인을 쓰게 한 뒤 그것을 지식으로 삼는다. 그 가이드라인이
맞는지는 검사하지 않는다 — 검사하는 것은 «그것으로 만든 결과물» 이다
(디자이너 30명 평가, 실루엣 점수). 원리 자체는 한 번도 반증 가능한 자리에
놓이지 않는다.

여기서는 원리를 두 가지로 나누어 묻는다.

    참인가      코퍼스가 실제로 그렇게 하는가
    갈림인가    그것이 이 사람 것인가, 다들 그러는가

둘은 다르다. 「왼쪽 정렬을 쓴다」 는 참이면서 동시에 브로크만 얘기가 아닐
수 있다. 그러면 그 문장은 옳지만 아무것도 고르지 못한다. PRISM 은 이 둘을
가르지 않는다.

세 번째 칸이 가장 많이 나온다 — **못 옮김**. 「기하 도형을 쓴다」 를 잴 수
있는 양으로 옮길 수 없으면 그 문장은 참도 거짓도 아니다. 그 칸을 비워
두지 않고 이유와 함께 적는 것이 이 모듈이 하는 일의 절반이다.
"""
import json
import os

import numpy as np

import distinct
import features

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, 'docs', 'vlm_rules.json')

# 「필수」라고 쓴 원리는 대부분의 판이 지켜야 하고, 「선택」은 더러 있으면 된다.
# 문턱을 눈에 보이게 둔다 — VLM 의 문장에는 수가 없으므로 읽는 쪽이 넣는
# 수밖에 없고, 넣은 수를 숨기면 판정이 취향이 된다.
NEED = {'필수': 0.80, '선택': 0.20, '금지': 0.80, '관찰': 0.50}
HALF = 0.50       # 필수인데 이 아래로 떨어지면 「거짓」, 사이면 「반쯤」



# ── 지표를 새로 재야 하는 원리 ──────────────────────────────────────
# 「블록들이 같은 왼쪽 축에 선다」 를 features 의 축공유 로 옮겼더니 브로크만
# 판의 33% 만 지킨다고 나왔다. 지표가 틀렸다. 축공유 는 «가장 큰 무리 / 전체»
# 라서 두 단으로 «잘» 정렬된 판을 벌준다 — 9개 블록이 두 축에 4:5 로 나뉘면
# 0.44 다. 그리고 허용치 2px 를 32px 로 늘리면 0.33 이 0.61 이 된다. 값이
# 허용치에 끌려다니는 지표로 문장의 참/거짓을 물으면 안 된다.
#
# 물어야 할 것은 «축이 몇 개인가» 이고, 허용치는 귀무모형이 흡수한다 —
# 같은 판 안에서 x1 을 흩뿌려 다시 세면 허용치가 양쪽에 똑같이 먹는다.
AXIS_EPS_FRAC = 0.01   # 판 너비의 1% (566px 판에서 5.7px)
AXIS_MIN_BLOCKS = 5    # 이보다 적으면 축을 셀 수 없다
AXIS_NULL = 400


def _n_axes(xs, eps):
    xs = sorted(xs)
    k = 1
    for i in range(1, len(xs)):
        if xs[i] - xs[i - 1] > eps:
            k += 1
    return k


def 축여유(raw, seed=distinct.SEED):
    """(귀무의 축 수 − 실제 축 수) / 귀무. 양수면 우연보다 많이 정렬돼 있다."""
    rnd = np.random.RandomState(seed)
    out = []
    for r in raw.values():
        bs = [b for b in (r.get('blocks') or []) if b['x2'] > b['x1']]
        if len(bs) < AXIS_MIN_BLOCKS or not r.get('size'):
            continue
        W = r['size'][0]
        eps = max(2.0, W * AXIS_EPS_FRAC)
        x1 = np.array([b['x1'] for b in bs], float)
        lo, hi = x1.min(), x1.max()
        if hi <= lo:
            continue
        got = _n_axes(x1, eps) / len(bs)
        null = np.mean([_n_axes(rnd.uniform(lo, hi, len(bs)), eps) / len(bs)
                        for _ in range(AXIS_NULL)])
        if null > 0:
            out.append((null - got) / null)
    return np.array(out, float)


EXTRA = {'축여유': 축여유}


def _col(raw, name):
    """코퍼스에서 그 지표의 장별 값. 못 잰 장은 뺀다."""
    if name in EXTRA:
        return EXTRA[name](raw)
    j = features.ix(name)
    v = np.array([features.vector(raw[k])[j] for k in raw], float)
    return v[~np.isnan(v)]


def _holds(v, way, thr):
    return float((v <= thr).mean()) if way == '≤' else float((v >= thr).mean())


def _cv(v):
    m = float(np.mean(v))
    return float(np.std(v) / m) if m else float('nan')


def _true(kind, share):
    need = NEED.get(kind, 0.5)
    if share >= need:
        return '참'
    if kind in ('필수', '금지') and share >= HALF:
        return '반쯤'
    return '거짓'


def _scopes(corpora, names, n_tests):
    """지표마다 «갈림/공통» — 네 코퍼스 딱지를 섞은 귀무와 견준다."""
    out = {}
    for nm in names:
        per = {c: _col(r, nm) for c, r in corpora.items()}
        per = {c: v for c, v in per.items() if len(v)}
        r = distinct.explained(list(per.values()), n_tests=n_tests)
        if r:
            r['코퍼스'] = [c for c, v in per.items() if len(v) >= distinct.MIN_PER]
        out[nm] = r
    return out


def one(p, raw, scopes, book=None):
    """원리 하나 → 판정 한 줄."""
    row = {'id': p['id'], '말': p['말'], '종류': p.get('종류'),
           '전과': p.get('전과')}
    t = p.get('옮김')
    if not t:
        row.update(판정='못옮김', 왜=p.get('왜못옮김'))
        return row

    row['옮김'] = t.get('뜻')
    kind = t['검사']

    if kind == '이미잼':
        row['어디'] = t.get('어디')
        if book is None:
            row.update(판정='안돌림', 왜='booktest 결과를 주지 않았다')
        else:
            row.update(판정=book.get('verdict', '?'), 근거=book)
        return row

    nm = t['지표']
    v = _col(raw, nm)
    row.update(지표=nm, n=len(v))
    if len(v) < distinct.MIN_PER:
        row.update(판정='못잼', 왜=f'{nm} 를 잰 판이 {len(v)}장뿐이다')
        return row

    if kind == '장마다':
        share = _holds(v, t['향'], t['값'])
        row.update(술어=f"{nm} {t['향']} {t['값']}",
                   지킴=round(share, 3), 문턱=NEED.get(p.get('종류'), 0.5),
                   중앙값=round(float(np.median(v)), 3),
                   판정=_true(p.get('종류'), share))
    elif kind == '몰림':
        cv = _cv(v)
        ok = (cv >= t['값']) if t['향'] == '≥' else (cv <= t['값'])
        row.update(술어=f"CV({nm}) {t['향']} {t['값']}", CV=round(cv, 3),
                   중앙값=round(float(np.median(v)), 3),
                   판정='참' if ok else '거짓')

    s = scopes.get(nm)
    if s:
        row['갈림'] = s['scope']
        row['설명력'] = f"{s['eta2']:.3f} (귀무 {s['eta2_null']:.3f}, {s['ratio']}배)"
    else:
        row['갈림'] = '못셈'
    return row


def run(raw, corpora=None, path=RULES, book=None):
    """before / after 두 묶음을 같은 잣대로 재고 나란히 낸다."""
    d = json.load(open(path, encoding='utf-8'))
    sets = {k: d[k]['원리'] for k in ('before', 'after')}

    used = sorted({p['옮김']['지표'] for ps in sets.values() for p in ps
                   if p.get('옮김') and p['옮김'].get('지표')})
    scopes = _scopes(corpora, used, n_tests=len(used)) if corpora else {}

    out = {}
    for k, ps in sets.items():
        out[k] = [one(p, raw, scopes, book=book) for p in ps]

    # 두 묶음을 견준다 — 데이터가 한 일이 있는가
    def tally(rows):
        c = {}
        for r in rows:
            c[r['판정']] = c.get(r['판정'], 0) + 1
        return c

    out['셈'] = {k: tally(v) for k, v in out.items() if k in sets}
    out['옮긴지표'] = used
    out['문턱'] = dict(NEED=NEED, HALF=HALF)
    return out
