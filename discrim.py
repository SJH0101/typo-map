"""판별력 — 이 지표가 «브로크만다움» 을 재는가.

지금 채택 기준은 「값이 모이는가(CV ≤ 0.30)」다. 그런데 모인다고 그 값이
작가의 선택인 것은 아니다. 판면에 상자를 아무렇게나 흩어도 똑같이 모이는
지표가 있다.

진짜 배치와 «같은 상자를 자리만 섞은» 배치를 견주면 갈린다. 사람이 그린
상자 26장 · 무작위 780장으로 재 보니 이렇다.

    AUC   지표              진짜    무작위
    0.79  왼쪽 축 공유       0.50    0.25   ← 정보 있음
    0.78  겹침(낮을수록)     0.000   0.008
    0.70  아래 마진(낮게)    0.019   0.116
    0.54  덮음 면적          0.103   0.103  ← 정보 없음
    0.53  가로 무게중심      0.482   0.493  ← 정보 없음

덮음 면적은 CV 0.85 로 «흩어지는데» 무작위와 구분도 안 된다. 왼쪽 축 공유는
CV 0.45 로 «흩어지는데» 무작위와는 확실히 다르다. CV 로는 이 둘이 똑같이
「자유」로 떨어진다.

여기서 재는 것은 «자리» 에서 나오는 지표뿐이다. 행간비나 어센더비처럼 상자
안에서 나오는 값은 자리를 섞어도 안 변하므로 이 방법이 안 통한다 — 그런
지표는 CV 판정을 그대로 쓴다.
"""
import itertools, random
import numpy as np

N_NULL = 30          # 포스터당 무작위 배치 몇 벌
AUC_MIN = 0.75       # 이보다 크면 «무작위와 다르다» 로 본다
SEED = 20260823


def _share(vals, tol):
    v = sorted(vals)
    g = [[v[0]]]
    for x in v[1:]:
        if x - g[-1][-1] <= tol:
            g[-1].append(x)
        else:
            g.append([x])
    return max(len(x) for x in g) / len(vals), len(g)


def layout_features(bs, W, H):
    """상자 «자리» 에서만 나오는 지표. 상자 안은 보지 않는다."""
    if not bs:
        return {}
    x1 = [b[0] for b in bs]; x2 = [b[2] for b in bs]
    y1 = [b[1] for b in bs]; y2 = [b[3] for b in bs]
    ar = [(b[2] - b[0]) * (b[3] - b[1]) for b in bs]
    f = {}
    f['축_왼쪽공유'], f['축_왼쪽수'] = _share(x1, 4)
    f['축_오른쪽공유'], _ = _share(x2, 6)
    f['축_위공유'], _ = _share(y1, 4)
    f['축_아래공유'], _ = _share(y2, 4)
    f['마진왼쪽'] = min(x1) / W; f['마진오른쪽'] = (W - max(x2)) / W
    f['마진위'] = min(y1) / H;   f['마진아래'] = (H - max(y2)) / H
    f['덮음'] = sum(ar) / (W * H)
    f['외곽폭'] = (max(x2) - min(x1)) / W
    f['세로무게'] = float(np.mean([(a + b) / 2 for a, b in zip(y1, y2)])) / H
    f['가로무게'] = float(np.mean([(a + b) / 2 for a, b in zip(x1, x2)])) / W
    ov = 0
    for a, b in itertools.combinations(bs, 2):
        ox = min(a[2], b[2]) - max(a[0], b[0]); oy = min(a[3], b[3]) - max(a[1], b[1])
        if ox > 0 and oy > 0:
            ov += ox * oy
    f['겹침'] = ov / max(sum(ar), 1)
    return f


def shuffle_layout(bs, W, H, rnd):
    """상자 크기는 그대로 두고 자리만 흩는다. 크기 분포를 통제한 귀무모형."""
    out = []
    for b in bs:
        w, h = b[2] - b[0], b[3] - b[1]
        x = rnd.randint(0, max(0, int(W - w))); y = rnd.randint(0, max(0, int(H - h)))
        out.append((x, y, x + w, y + h))
    return out


def _auc(a, b, cap=600):
    """진짜 a 가 무작위 b 보다 큰 쪽으로 얼마나 갈리나. 0.5 = 구분 못함."""
    b = list(b)[:cap]
    if not len(a) or not len(b):
        return 0.5
    s = sum(1 for x, y in itertools.product(a, b) if x > y) \
        + 0.5 * sum(1 for x, y in itertools.product(a, b) if x == y)
    return s / (len(a) * len(b))


def separability(posters, n_null=N_NULL, seed=SEED):
    """posters = [(boxes, W, H), ...]  →  지표별 판별력.

    boxes 는 (x1, y1, x2, y2) 목록. 사람이 그린 것이든 VLM 이 짚은 것이든
    상관없다 — 자리가 실제 배치이기만 하면 된다.
    """
    rnd = random.Random(seed)
    real, null = [], []
    for bs, W, H in posters:
        if not bs:
            continue
        real.append(layout_features(bs, W, H))
        for _ in range(n_null):
            null.append(layout_features(shuffle_layout(bs, W, H, rnd), W, H))
    if not real:
        return {}
    out = {}
    for k in real[0]:
        a = np.array([x[k] for x in real]); b = np.array([x[k] for x in null])
        v = _auc(a, b)
        out[k] = dict(auc=round(max(v, 1 - v), 3),
                      direction='높을수록' if v > 0.5 else '낮을수록',
                      real=round(float(np.median(a)), 3),
                      null=round(float(np.median(b)), 3),
                      cv=round(float(np.std(a) / np.mean(a)) if np.mean(a) else 9.9, 3),
                      n=len(a))
        out[k]['verdict'] = '제약' if out[k]['auc'] >= AUC_MIN else '정보 없음'
    return dict(sorted(out.items(), key=lambda kv: -kv[1]['auc']))
