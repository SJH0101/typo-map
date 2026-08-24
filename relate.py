"""관계 지표 — 어느 값이 어느 값과 «함께 움직이는가».

rules.py 는 값의 분포를 보고 「행간 1.42」 같은 것을 낸다. 그런데 코퍼스
4종 274장을 재보니 그런 값은 네 작가가 거의 같았다. 갈리는 것은 관계였다.

    마진 — 글자면적 결합도

        브로크만 0.21   로제 0.34   루더 0.45   호프만 0.54

    낮으면 마진이 내용과 무관하다 — 마진이 먼저 정해지고 내용이 그 안에
    담긴다. 격자 체계다. 높으면 마진이 구성의 결과다.

브로크만만 낮고 나머지 셋은 엮인다. 값으로는 안 보이던 것이 관계로는
보인다 — 그리고 이것은 그가 『Grid Systems』 에서 주장한 그것이다.

셈법은 순위 상관의 절댓값 평균이다. 이상치에 덜 흔들리고 방향이 섞여도
크기가 살아남는다. 판정은 작가 딱지를 섞은 귀무모형과 견준다 — 결합도는
표본이 작을수록 커지므로 절대값으로 자르면 안 된다.
"""
import numpy as np

import features

MIN_PAIR = 20     # 쌍마다 둘 다 실제로 잰 포스터가 이만큼은 있어야 센다
N_NULL = 2000
SEED = 20260824
BAND = 95         # 귀무 분포의 이 구간 밖이면 «높음/낮음» 으로 본다

# 재는 관계들. (이름, 왼쪽 마디 묶음, 오른쪽 마디 묶음)
RELATIONS = [
    ('마진–내용', features.MARGIN, features.CONTENT),
    ('마진–글자면적', features.MARGIN, ['덮음']),
    ('마진끼리', features.MARGIN, features.MARGIN),
    ('내용끼리', features.CONTENT, features.CONTENT),
]


def _rank(a):
    return a.argsort().argsort() + 1.0


def coupling(X, left, right, min_pair=MIN_PAIR):
    """두 마디 묶음 사이 순위상관 절댓값의 평균. 같은 마디 쌍은 뺀다."""
    vals = []
    for a in left:
        for b in right:
            if a == b:
                continue
            i, j = features.ix(a), features.ix(b)
            ok = ~np.isnan(X[:, i]) & ~np.isnan(X[:, j])
            if ok.sum() < min_pair:
                continue
            x, y = X[ok, i], X[ok, j]
            if x.std() == 0 or y.std() == 0:
                continue
            vals.append(abs(np.corrcoef(_rank(x), _rank(y))[0, 1]))
    if not vals:
        return None, 0
    return float(np.mean(vals)), len(vals)


def measure(raw, references, n_null=N_NULL, seed=SEED):
    """이 코퍼스의 관계 지표를, 작가 딱지를 섞은 귀무모형과 견준다.

    references = {이름: 원자료}. 귀무모형이 딱지를 섞으려면 남들이 필요하다.
    """
    X0, _, _ = features.matrix(raw)
    if not references:
        return None
    others = [features.matrix(r)[0] for r in references.values()]
    pool = np.vstack([X0] + others)
    sizes = [len(X0)] + [len(o) for o in others]
    rnd = np.random.RandomState(seed)

    out = {}
    for name, L, R in RELATIONS:
        real, npair = coupling(X0, L, R)
        if real is None:
            continue
        null = []
        for _ in range(n_null):
            p = rnd.permutation(len(pool))[:len(X0)]
            v, _n = coupling(pool[p], L, R)
            if v is not None:
                null.append(v)
        if len(null) < n_null // 2:
            continue
        lo = float(np.percentile(null, (100 - BAND) / 2))
        hi = float(np.percentile(null, 100 - (100 - BAND) / 2))
        out[name] = dict(value=round(real, 4), n_pairs=npair,
                         null_lo=round(lo, 4), null_hi=round(hi, 4),
                         verdict=('높음' if real > hi else
                                  '낮음' if real < lo else '구분 안 됨'),
                         n_posters=len(X0), n_reference=len(references))
    return out
