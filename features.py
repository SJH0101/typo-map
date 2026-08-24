"""포스터 한 장 → 이름 붙은 숫자 벡터.

rules.py 의 지표들은 「값의 분포」를 본다. 그런데 하루 종일 재보니 값은
네 작가가 거의 같고, 갈리는 것은 «어느 값이 어느 값과 함께 움직이는가» 였다.
관계를 재려면 포스터마다 벡터가 있어야 한다 — 지표 함수는 코퍼스 전체에서
값 목록을 뽑아 주므로 어느 값이 어느 포스터에서 왔는지가 사라진다.

못 잰 칸은 None 으로 둔다. 중앙값으로 메우면 결측률이 코퍼스마다 달라
가짜 상관이 생긴다 — 실제로 마진 결측률이 로제 0%, 브로크만 25% 였을 때
그것만으로 선 네 개가 잘못 살아났다.
"""
import numpy as np

NAMES = ['색수', '밝기', '최빈색', '채도', '무채색',
         '마진좌', '마진우', '마진상', '마진하',
         '덮음', '블록수', '단수', '활자폭', '행간비', '어센더비']

MARGIN = ['마진좌', '마진우', '마진상', '마진하']
CONTENT = ['덮음', '블록수', '단수', '활자폭', '행간비', '어센더비']
COLOR = ['색수', '밝기', '최빈색', '채도', '무채색']

_IX = {n: i for i, n in enumerate(NAMES)}


def ix(name):
    return _IX[name]


def _cap_h(b):
    return [base - c for c, base in zip(b['caps'], b['bases']) if c is not None]


def vector(r):
    """원자료 한 장 → NAMES 순서의 값 목록. 못 잰 칸은 nan."""
    nan = float('nan')
    c = r.get('color') or {}
    bs = r.get('blocks') or []
    sz, rg = r.get('size'), r.get('region')

    m = [nan] * 4
    if sz and rg and abs(r.get('angle', 0)) < 1 and sz[0] > 0 and sz[1] > 0:
        w, h = sz
        x1, y1, x2, y2 = rg
        m = [x1 / w, (w - x2) / w, y1 / h, (h - y2) / h]

    area = nan
    if sz and sz[0] > 0 and sz[1] > 0 and abs(r.get('angle', 0)) < 1:
        area = sum(max(0, b['x2'] - b['x1']) * max(0, b['y2'] - b['y1'])
                   for b in bs) / float(sz[0] * sz[1])

    xh = [b['xh'] for b in bs if b.get('xh')]
    lead = []
    for b in bs:
        L = b.get('lead_measured') or b.get('lead')
        cs = _cap_h(b)
        if L and b['n'] >= 3 and cs:
            lead.append(L / float(np.median(cs)))
    asc = [(base - cp) / (base - t) for b in bs
           for cp, t, base in zip(b['caps'], b['xtops'], b['bases'])
           if cp is not None and base - t > 0 and (base - cp) >= (base - t)]

    return [float(c.get('n_colors', nan)), float(c.get('value', nan)),
            float(c.get('ground_share', nan)), float(c.get('saturation', nan)),
            float(c.get('gray_share', nan)),
            *m, area, float(len(bs)), float(r.get('n_columns') or nan),
            (max(xh) / min(xh) if len(xh) >= 2 and min(xh) > 0 else nan),
            (float(np.median(lead)) if lead else nan),
            (float(np.median(asc)) if asc else nan)]


def matrix(raw):
    """원자료 → (포스터 x 속성) 행렬과 이름 목록."""
    keys = list(raw)
    X = np.array([vector(raw[k]) for k in keys], dtype=float)
    return X, keys, NAMES
