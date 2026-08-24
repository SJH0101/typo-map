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
         '덮음', '블록수', '단수', '활자폭', '행간비', '어센더비',
         '무게x', '무게y', '퍼짐x', '퍼짐y', '축공유', '빈띠']

MARGIN = ['마진좌', '마진우', '마진상', '마진하']
CONTENT = ['덮음', '블록수', '단수', '활자폭', '행간비', '어센더비']
COLOR = ['색수', '밝기', '최빈색', '채도', '무채색']
# 「어디에」 — 마진은 글자 영역의 «바깥 경계» 일 뿐이라, 그 안에서 덩어리가
# 어디에 앉고 무슨 축에 서는지는 아무것도 말하지 않았다. 그래서 뇌에서 값을
# 뽑아 그림을 그리면 놓을 자리를 렌더러가 임의로 정할 수밖에 없었고, 뽑을
# 때 0.08 이던 관계가 그리고 나면 부호까지 뒤집혔다.
PLACE = ['무게x', '무게y', '퍼짐x', '퍼짐y', '축공유', '빈띠']

AXIS_EPS = 2.0    # 이 픽셀 안이면 같은 정렬축으로 본다 (안티에일리어싱 폭)

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

    # ── 어디에 ────────────────────────────────────────────────────
    gx = gy = sx = sy = ax = gap = nan
    if bs and sz and sz[0] > 0 and sz[1] > 0 and abs(r.get('angle', 0)) < 1:
        W, H = float(sz[0]), float(sz[1])
        box = [(b['x1'], b['y1'], b['x2'], b['y2']) for b in bs]
        a = np.array([max(0, x2 - x1) * max(0, y2 - y1) for x1, y1, x2, y2 in box], float)
        cx = np.array([(x1 + x2) / 2 for x1, _y1, x2, _y2 in box], float)
        cy = np.array([(y1 + y2) / 2 for _x1, y1, _x2, y2 in box], float)
        if a.sum() > 0:
            gx = float((cx * a).sum() / a.sum() / W)      # 잉크 무게중심
            gy = float((cy * a).sum() / a.sum() / H)
        if len(bs) >= 2:
            sx = float(np.std(cx) / W)                    # 덩어리가 얼마나 흩어졌나
            sy = float(np.std(cy) / H)
            # 왼쪽 축을 몇 개가 공유하나 — 가장 큰 무리 / 전체
            xs = sorted(b['x1'] for b in bs)
            g, best = [xs[0]], 1
            for x in xs[1:]:
                if x - g[-1] <= AXIS_EPS:
                    g.append(x)
                else:
                    best = max(best, len(g)); g = [x]
            ax = float(max(best, len(g)) / len(bs))
            # 글자 영역 안의 가장 넓은 «빈 가로 띠» — 판을 가르는 그 틈
            iv = sorted((b['y1'], b['y2']) for b in bs)
            top, bot, cur, mx = iv[0][0], max(v[1] for v in iv), iv[0][1], 0.0
            for y1, y2 in iv[1:]:
                mx = max(mx, y1 - cur)
                cur = max(cur, y2)
            gap = float(mx / H) if bot > top else nan

    return [float(c.get('n_colors', nan)), float(c.get('value', nan)),
            float(c.get('ground_share', nan)), float(c.get('saturation', nan)),
            float(c.get('gray_share', nan)),
            *m, area, float(len(bs)), float(r.get('n_columns') or nan),
            (max(xh) / min(xh) if len(xh) >= 2 and min(xh) > 0 else nan),
            (float(np.median(lead)) if lead else nan),
            (float(np.median(asc)) if asc else nan),
            gx, gy, sx, sy, ax, gap]


def matrix(raw):
    """원자료 → (포스터 x 속성) 행렬과 이름 목록."""
    keys = list(raw)
    X = np.array([vector(raw[k]) for k in keys], dtype=float)
    return X, keys, NAMES
