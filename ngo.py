"""Ngo·Teo·Byrne(2003)의 레이아웃 미학 지표 13개를 우리 기준에 넣어 본다.

    D.C.L. Ngo, L.S. Teo, J.G. Byrne, "Modelling interface aesthetics",
    Information Sciences 152 (2003) 25–46.

식은 원문 PDF 에서 그대로 옮겼다. 식 번호를 주석에 남긴다.

그들은 지표 13개를 게슈탈트 이론에서 끌어와 공식으로 내고, 그것을 묶어
(OM, 식 57) 그 화면의 «미적 값» 으로 쓴다. 정당화는 사람 평점과의 상관
하나다.

빠진 것이 있다. **어느 지표가 제 밥값을 하는지 묻지 않는다.** 지표 하나가
무작위 배치보다 나은지, 두 디자이너를 가르는지, 코퍼스 안에서 몰리는지 —
셋 다 시험하지 않는다. 묶어 버리므로 어느 개념이 일했는지도 사라진다.

여기서는 그 13개를 우리 세 기준에 넣는다.

    ① 몰림   CV     이 코퍼스 안에서 값이 몰리는가
    ② 판별   AUC    상자를 흩뿌린 귀무 배치와 다른가
    ③ 갈림   eta2   네 작가를 가르는가 (다중비교 보정)

식은 원문대로지만 원문이 정하지 않은 것이 둘 있다. 우리가 넣은 수이므로
JUDGED 에 적어 둔다 — 결과를 읽을 때 이것부터 의심해야 한다.
"""
import math

import numpy as np

# ── 원문이 정하지 않아 우리가 넣은 것 ────────────────────────────
JUDGED = {
 '정규화': ('SYM(식 9~11)·RHM(식 51~53)의 X′,Y′,H′,B′,Θ′,R′,A′ 를 원문은 '
            '「정규화한 값」이라고만 하고 방식을 적지 않는다. 네 사분면의 '
            '최대값으로 나눈다 — 후속 문헌의 통상 해석이고, 값이 [0,1] 에 '
            '드는 유일한 단순 방식이다.'),
 '크기허용치': (f'n_size(식 30·45)를 원문은 정확히 같은 크기로 센다. 검출된 '
                '상자는 정확히 같을 수가 없으므로 넓이가 10% 안이면 같은 '
                '크기로 본다.'),
 '정렬허용치': ('n_vap·n_hap(식 40·43)은 Tullis/Bonsiepe 를 따라 «시작 위치» '
                '(왼쪽 모서리 x, 위 모서리 y)를 센다. 판 너비/높이의 1% 안이면 '
                '같은 점으로 본다.'),
}

SIZE_TOL = 0.10
ALIGN_TOL = 0.01
PROPS = [1 / 1.0, 1 / 1.414, 1 / 1.618, 1 / 1.732, 1 / 2.0]   # 식 39

# 값이 «자리» 가 아니라 «크기» 에만 달린 지표. 상자를 흩뿌리는 귀무모형은
# 크기를 그대로 두므로 이 셋은 정의상 귀무와 같은 값이 나온다. ② 판별을
# 적용할 수 없다 — 「정보 없음」이 아니라 「이 귀무로는 못 잼」이다.
POS_FREE = ['밀도', '절약', '비례']

NAMES = ['균형', '평형', '대칭', '순서', '응집', '통일', '비례',
         '단순', '밀도', '규칙성', '절약', '동질', '리듬', '질서']


def _q(bs, W, H):
    xc, yc = W / 2.0, H / 2.0
    q = {'UL': [], 'UR': [], 'LL': [], 'LR': []}
    for b in bs:
        x, y = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
        q[('U' if y < yc else 'L') + ('L' if x < xc else 'R')].append(b)
    return q


def _norm(d):
    """네 사분면 값을 최대값으로 나눈다 (JUDGED['정규화'])."""
    m = max(d.values())
    return {k: (v / m if m > 0 else 0.0) for k, v in d.items()}


def _pairs(d):
    """여섯 쌍의 절대차 평균 — RHM (식 51~53)."""
    k = ['UL', 'UR', 'LL', 'LR']
    p = [(0, 1), (0, 3), (0, 2), (1, 3), (1, 2), (3, 2)]
    return sum(abs(d[k[a]] - d[k[b]]) for a, b in p) / 6.0


def _sym_sum(ms, a, b):
    """열두 항 — SYM 한 방향 (식 9~11). ms 는 정규화된 모멘트 여섯 벌."""
    return sum(abs(m[a[0]] - m[b[0]]) + abs(m[a[1]] - m[b[1]]) for m in ms) / 12.0


def _n_classes(vals, tol, rel=True):
    v = sorted(vals)
    if not v:
        return 0
    k, ref = 1, v[0]
    for x in v[1:]:
        gap = (x - ref) / max(ref, 1.0) if rel else (x - ref)
        if gap > tol:
            k += 1
            ref = x
    return k


def measures(bs, W, H):
    """상자 목록 → Ngo 지표 13개 + 묶음(OM). 못 잴 판은 {} 를 낸다."""
    bs = [b for b in bs if b[2] > b[0] and b[3] > b[1]]
    n = len(bs)
    if n < 2 or W <= 0 or H <= 0:
        return {}
    xc, yc = W / 2.0, H / 2.0
    A = [(b[2] - b[0]) * (b[3] - b[1]) for b in bs]
    BW = [b[2] - b[0] for b in bs]
    HH = [b[3] - b[1] for b in bs]
    X = [(b[0] + b[2]) / 2.0 for b in bs]
    Y = [(b[1] + b[3]) / 2.0 for b in bs]
    sa = float(sum(A))
    f = {}

    # ── 균형 (식 1~4) ──────────────────────────────────────────
    def w(sel, pos, c):
        return sum(a * abs(p - c) for a, p, s in zip(A, pos, sel) if s)
    wl, wr = w([x < xc for x in X], X, xc), w([x >= xc for x in X], X, xc)
    wt, wb = w([y < yc for y in Y], Y, yc), w([y >= yc for y in Y], Y, yc)
    bv = (wl - wr) / max(abs(wl), abs(wr)) if max(abs(wl), abs(wr)) > 0 else 0.0
    bh = (wt - wb) / max(abs(wt), abs(wb)) if max(abs(wt), abs(wb)) > 0 else 0.0
    f['균형'] = 1.0 - (abs(bv) + abs(bh)) / 2.0

    # ── 평형 (식 5~7) ── 분모에 n 이 있다. 물체가 많으면 저절로 1 에 붙는다
    ex = 2 * sum(a * (x - xc) for a, x in zip(A, X)) / (n * W * sa)
    ey = 2 * sum(a * (y - yc) for a, y in zip(A, Y)) / (n * H * sa)
    f['평형'] = 1.0 - (abs(ex) + abs(ey)) / 2.0

    # ── 대칭 (식 8~17) ── 사분면마다 모멘트 여섯 개
    Q = _q(bs, W, H)
    def mom(fn):
        return _norm({k: sum(fn(b) for b in v) for k, v in Q.items()})
    def th(b):
        dx = (b[0] + b[2]) / 2.0 - xc
        dy = (b[1] + b[3]) / 2.0 - yc
        return abs(dy / dx) if dx else 0.0
    ms = [mom(lambda b: abs((b[0] + b[2]) / 2.0 - xc)),          # X  (12)
          mom(lambda b: abs((b[1] + b[3]) / 2.0 - yc)),          # Y  (13)
          mom(lambda b: b[3] - b[1]),                            # H  (14)
          mom(lambda b: b[2] - b[0]),                            # B  (15)
          mom(th),                                               # Θ  (16)
          mom(lambda b: math.hypot((b[0] + b[2]) / 2.0 - xc,
                                   (b[1] + b[3]) / 2.0 - yc))]   # R  (17)
    sv = _sym_sum(ms, ('UL', 'LL'), ('UR', 'LR'))
    sh = _sym_sum(ms, ('UL', 'UR'), ('LL', 'LR'))
    sr = _sym_sum(ms, ('UL', 'UR'), ('LR', 'LL'))
    f['대칭'] = 1.0 - (abs(sv) + abs(sh) + abs(sr)) / 3.0

    # ── 순서 (식 18~22) ──────────────────────────────────────
    qw = {'UL': 4, 'UR': 3, 'LL': 2, 'LR': 1}
    wj = {k: qw[k] * sum((b[2] - b[0]) * (b[3] - b[1]) for b in v)
          for k, v in Q.items()}
    rank = sorted(wj, key=lambda k: -wj[k])
    vj = {k: 4 - i for i, k in enumerate(rank)}
    f['순서'] = 1.0 - sum(abs(qw[k] - vj[k]) for k in qw) / 8.0

    # ── 응집 (식 23~28) ── 판·틀·물체의 가로세로비가 맞나
    lx1, ly1 = min(b[0] for b in bs), min(b[1] for b in bs)
    lx2, ly2 = max(b[2] for b in bs), max(b[3] for b in bs)
    lb, lh = float(lx2 - lx1), float(ly2 - ly1)
    def flip(c):
        return c if c <= 1 else 1.0 / c
    cfl = flip((lh / lb) / (H / W)) if lb > 0 and H > 0 else 0.0
    clo = float(np.mean([flip((h / b) / (lh / lb)) if b > 0 and lb > 0 and lh > 0
                         else 0.0 for b, h in zip(BW, HH)]))
    f['응집'] = (abs(cfl) + abs(clo)) / 2.0

    # ── 통일 (식 29~31) ── 원문 분모는 n 이다 (n−1 아님)
    ns = _n_classes(A, SIZE_TOL)
    uf = 1.0 - (ns - 1) / float(n)
    la = lb * lh
    us = 1.0 - (la - sa) / (W * H - sa) if (W * H - sa) > 0 else 1.0
    f['통일'] = (abs(uf) + abs(us)) / 2.0

    # ── 비례 (식 32~39) ── 물체·판의 비가 «좋은 비» 에 얼마나 가깝나
    def pnear(r):
        p = r if r <= 1 else 1.0 / r
        return 1.0 - min(abs(q - p) for q in PROPS) / 0.5
    f['비례'] = (abs(float(np.mean([pnear(h / b) for b, h in zip(BW, HH) if b > 0])))
                 + abs(pnear(lh / lb) if lb > 0 else 0.0)) / 2.0

    # ── 단순 (식 40) ── 정렬점은 «시작 위치» 만 센다
    vap = _n_classes([b[0] for b in bs], W * ALIGN_TOL, rel=False)
    hap = _n_classes([b[1] for b in bs], H * ALIGN_TOL, rel=False)
    f['단순'] = 3.0 / (vap + hap + n)

    # ── 밀도 (식 41) ── 절반 덮을 때 가장 높다
    f['밀도'] = 1.0 - 2.0 * abs(0.5 - sa / (W * H))

    # ── 규칙성 (식 42~44) ────────────────────────────────────
    ra = 1.0 if n == 1 else 1.0 - (vap + hap) / (2.0 * n)
    xs, ys = sorted(b[0] for b in bs), sorted(b[1] for b in bs)
    gaps = ([xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
            + [ys[i + 1] - ys[i] for i in range(len(ys) - 1)])
    nsp = _n_classes(gaps, max(W, H) * ALIGN_TOL, rel=False) if gaps else 1
    rs = 1.0 if n == 1 else 1.0 - (nsp - 1) / (2.0 * (n - 1))
    f['규칙성'] = (abs(ra) + abs(rs)) / 2.0

    # ── 절약 (식 45) ─────────────────────────────────────────
    f['절약'] = 1.0 / ns if ns else 0.0

    # ── 동질 (식 46~49) ── 네 사분면에 고르게 퍼졌나
    cnt = [len(Q[k]) for k in ('UL', 'UR', 'LL', 'LR')]
    def mn(c):
        r = math.factorial(sum(c))
        for x in c:
            r //= math.factorial(x)
        return r
    even = [n // 4 + (1 if i < n % 4 else 0) for i in range(4)]
    f['동질'] = mn(cnt) / mn(even)

    # ── 리듬 (식 50~56) ──────────────────────────────────────
    rx = _pairs(_norm({k: sum(abs((b[0] + b[2]) / 2.0 - xc) for b in v)
                       for k, v in Q.items()}))
    ry = _pairs(_norm({k: sum(abs((b[1] + b[3]) / 2.0 - yc) for b in v)
                       for k, v in Q.items()}))
    rr = _pairs(_norm({k: sum((b[2] - b[0]) * (b[3] - b[1]) for b in v)
                       for k, v in Q.items()}))
    f['리듬'] = 1.0 - (abs(rx) + abs(ry) + abs(rr)) / 3.0

    # ── 질서 (식 57~58) ── 원문은 «묶음» 이라고만 한다. 실무 관행대로 평균
    f['질서'] = float(np.mean([f[k] for k in NAMES[:-1]]))
    return f


def boxes(raw):
    """우리 원자료 → (상자, W, H) 목록."""
    out = []
    for r in raw.values():
        bs = [(b['x1'], b['y1'], b['x2'], b['y2'])
              for b in (r.get('blocks') or [])]
        sz = r.get('size')
        if len(bs) >= 2 and sz and sz[0] > 0 and sz[1] > 0:
            out.append((bs, float(sz[0]), float(sz[1])))
    return out


def column(raw, name):
    v = [measures(bs, W, H).get(name) for bs, W, H in boxes(raw)]
    return np.array([x for x in v if x is not None], float)
