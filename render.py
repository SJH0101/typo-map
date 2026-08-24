"""값 묶음 하나를 실제 판면으로 옮긴다.

sample.py 가 «어떤 값들이어야 하는가» 를 내면, 여기서 «그 값이 되도록» 놓는다.
잰 지표를 거꾸로 미는 것이라, 그린 판을 다시 재면 시킨 값이 나와야 한다 —
그 왕복이 이 파일의 유일한 시험이다.

책에서 확인된 규칙 하나를 여기서 지킨다. R2 — 한 판의 행간들은 하나의 단위의
정수배다. 브로크만 코퍼스 50장에서 벗어남 2.4%, 귀무 7.3% 로 확인했고,
1959 Juni-Festwochen 의 행간이 [22, 11, 11] 이었다. 그래서 여기서도 행간을
자유롭게 두지 않고 격자에 물린다.

내용은 코퍼스에 실제로 되풀이되는 독일어를 쓴다. 로렘입숨을 쓰면 낱말 길이가
달라져 단 폭이 딴 값이 된다.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 566, 800                  # F4 비율. 코퍼스 스캔과 같은 크기로 둔다
FACE = ['/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/Supplemental/Arial.ttf']
GUTTER = 0.035                   # 단 사이 틈 (판면 폭 대비)

TITLE = ['musica viva', 'konzert', 'ausstellung', 'juni-festwochen', 'opernhaus']
NAMES = ['anton webern', 'alban berg', 'arnold schönberg', 'igor strawinsky',
         'béla bartók', 'paul hindemith', 'olivier messiaen', 'frank martin']
LINES = ['tonhalle grosser saal', 'dienstag 20.15 uhr', 'kunstgewerbemuseum zürich',
         'musikalische leitung', 'inszenierung', 'bühnenbild und kostüme',
         'vorverkauf tonhalle', 'karten fr. 3.- bis 12.-', 'eintritt frei',
         'geöffnet täglich 10-12 und 14-18 uhr', 'schweizerische erstaufführung']


_CACHE = {}


def _font(px):
    # 헬베티카는 8px 아래에서 죽는다 (division by zero). 하한을 둔다.
    k = max(8, int(round(px)))
    if k in _CACHE:
        return _CACHE[k]
    for p in FACE:
        if not os.path.exists(p):
            continue
        try:
            f = ImageFont.truetype(p, k)
            f.getbbox('H')
            _CACHE[k] = f
            return f
        except Exception:
            continue
    f = ImageFont.load_default()
    _CACHE[k] = f
    return f


def _capof(f):
    """이 크기의 폰트가 내는 캡 높이 (px). 지표는 캡 기준이므로 되돌려 맞춘다."""
    b = f.getbbox('H')
    return b[3] - b[1]


def _size_for_cap(cap):
    """캡 높이가 cap 이 되는 폰트 크기를 찾는다."""
    if not np.isfinite(cap) or cap <= 0:
        cap = 10.0
    lo, hi = 8, 320
    for _ in range(24):
        mid = (lo + hi) / 2
        c = _capof(_font(mid))
        if c < cap:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _fitcap(text, w, cap0):
    """이 폭 안에 들어가도록 캡 높이를 줄인다. 표제가 판 밖으로 나가지 않게."""
    cap = cap0
    for _ in range(14):
        f = _font(_size_for_cap(cap))
        if f.getlength(text) <= w:
            return cap
        cap *= 0.86
    return cap


def spec(v, seed=0):
    """값 묶음 → 배치안.

    격자를 세우고 그 칸에 덩어리를 놓되, «어디에» 마디가 시키는 자리에 가깝게
    고른다. 전에는 빈 칸에 무작위로 흩뿌렸고 그래서 뽑을 때 맞던 관계가 그리고
    나면 부호까지 뒤집혔다. 뇌에 자리가 없었기 때문이다.
    """
    rnd = np.random.RandomState(seed)
    for k in ('마진좌', '마진우', '마진상', '마진하', '덮음', '블록수',
              '단수', '활자폭', '행간비', '밝기', '색수', '채도'):
        if not np.isfinite(v.get(k, float('nan'))):
            raise ValueError(f'값이 비었다: {k}')

    mL, mR = float(v['마진좌']) * W, float(v['마진우']) * W
    mT, mB = float(v['마진상']) * H, float(v['마진하']) * H
    tw, th = max(60, W - mL - mR), max(80, H - mT - mB)
    cols = int(np.clip(round(v['단수']), 1, 5))
    nblk = int(np.clip(round(v['블록수']), 2, 14))
    ratio = float(np.clip(v['행간비'], 1.15, 2.0))
    span = float(np.clip(v['활자폭'], 1.5, 30))
    target = float(np.clip(v['덮음'], 0.03, 0.75)) * W * H

    gx = float(np.clip(v.get('무게x', 0.47), 0.12, 0.88))
    gy = float(np.clip(v.get('무게y', 0.52), 0.12, 0.88))
    sy = float(np.clip(v.get('퍼짐y', 0.17), 0.02, 0.42))
    axs = float(np.clip(v.get('축공유', 0.36), 0.0, 1.0))
    band = float(np.clip(v.get('빈띠', 0.06), 0.0, 0.5))

    gut = GUTTER * W
    cw = (tw - gut * (cols - 1)) / cols
    unit = max(9.0, th / 46)                 # 행간 격자 단위 (R2)
    rows = max(6, int(th // unit))
    cap_body = unit / ratio
    cap_big = min(cap_body * span, th * 0.34)
    mult = max(2, int(round(cap_big * ratio / unit)))
    lead_big, cap_big = unit * mult, unit * mult / ratio

    used = np.zeros((cols, rows), bool)
    main_col = int(np.clip(round(gx * cols - 0.5), 0, cols - 1))

    # 빈 가로 띠를 미리 잡아 둔다 — 판을 위아래로 가르는 그 틈
    if band > 0.04:
        h0 = int(np.clip(round(band * H / unit), 1, max(1, rows - 3)))
        r0 = int(np.clip(round(gy * rows - h0 / 2), 1, rows - h0 - 1))
        used[:, r0:r0 + h0] = True

    def score(c, r, h):
        """시킨 자리에 얼마나 가까운가. 낮을수록 좋다."""
        cyn = (mT + (r + h / 2) * unit) / H
        cxn = (mL + c * (cw + gut) + cw / 2) / W
        return abs(cyn - gy) * 2.0 + abs(cxn - gx) * 1.3

    def place(nlines, lead, cap, text, prefer=None, jitter=0.0):
        h = int(np.ceil((lead * (nlines - 1) + cap + unit * 0.6) / unit))
        # 글이 단 폭을 넘으면 옆 단까지 먹는다. 먹는 만큼 미리 잡아야 안 겹친다.
        f = _font(_size_for_cap(cap))
        tw_ = max(f.getlength(t) for t in text)
        span_c = int(np.clip(np.ceil((tw_ + 1) / (cw + gut)), 1, cols))
        spots = [(c, r) for c in range(cols - span_c + 1) for r in range(rows - h + 1)
                 if not used[c:c + span_c, r:r + h].any()]
        if not spots:
            return None
        if prefer is not None:
            spots = [(c, r) for c, r in spots if c == prefer] or spots
        elif rnd.rand() <= axs:                 # 축을 지키는 덩어리는 주 단으로
            spots = [(c, r) for c, r in spots if c == main_col] or spots
        if not spots:
            return None
        w = np.array([score(c, r, h) for c, r in spots], float)
        w = w + rnd.normal(0, jitter + 0.02, len(w))
        c, r = spots[int(np.argmin(w))]
        used[c:c + span_c, r:r + h] = True
        return dict(text=text, cap=cap, lead=lead, col=c,
                    x=mL + c * (cw + gut), w=cw, base0=mT + r * unit + cap)

    out = []
    tl = TITLE[rnd.randint(len(TITLE))]
    # 표제 폭은 단 하나가 아니라 판면 전체다. 활자폭(최대/최소)이 그 크기를 말한다.
    cap_big = _fitcap(tl, tw, cap_big)
    b = place(1, lead_big, cap_big, [tl], prefer=0)
    if b:
        out.append(dict(role='표제', **b))

    def area_of(x):
        f = _font(_size_for_cap(x['cap']))
        return max(f.getlength(t) for t in x['text']) * (x['lead'] * (len(x['text']) - 1) + x['cap'])

    area = sum(area_of(x) for x in out)
    guard = 0
    while len(out) < nblk * 1.6 and area < target and guard < 120:
        guard += 1
        n = int(rnd.randint(1, 7))
        src = NAMES if rnd.rand() < 0.35 else LINES
        txt = [src[rnd.randint(len(src))] for _ in range(n)]
        if cols > 1 and rnd.rand() < 0.35:       # 더러는 두 단을 걸친다
            txt = [t + '  ' + src[rnd.randint(len(src))] for t in txt]
        b = place(n, unit, cap_body, txt, jitter=sy)
        if not b:
            break
        b = dict(role='본문', **b)
        out.append(b)
        area += area_of(b)
    return dict(canvas=[W, H], margins=[mL, mR, mT, mB], cols=cols, unit=unit,
                target_area=target / (W * H), want=dict(무게x=gx, 무게y=gy, 퍼짐y=sy,
                축공유=axs, 빈띠=band), blocks=out)


def _palette(v, rnd):
    """밝기·색수·최빈색으로 바탕과 잉크를 정한다."""
    val = float(np.clip(v['밝기'], 0.05, 0.97))
    sat = float(np.clip(v['채도'], 0.0, 0.9))
    nc = int(np.clip(round(v['색수']), 2, 8))
    dark = val < 0.5
    g = int(val * 255)
    if sat < 0.14:                                  # 무채색 판
        ground = (g, g, g)
    else:
        h = rnd.rand()
        import colorsys
        r, gg, bb = colorsys.hsv_to_rgb(h, min(sat * 1.4, 0.95), val)
        ground = (int(r * 255), int(gg * 255), int(bb * 255))
    ink = (245, 245, 242) if dark else (18, 18, 20)
    accent = None
    if nc >= 4:
        import colorsys
        h = (rnd.rand() * 0.15 + (0.02 if not dark else 0.55)) % 1.0
        r, gg, bb = colorsys.hsv_to_rgb(h, 0.82, 0.92 if dark else 0.78)
        accent = (int(r * 255), int(gg * 255), int(bb * 255))
    return ground, ink, accent


def render(v, seed=0, path=None):
    rnd = np.random.RandomState(seed + 1)
    S = spec(v, seed)
    ground, ink, accent = _palette(v, rnd)
    im = Image.new('RGB', (W, H), ground)
    d = ImageDraw.Draw(im)
    for i, b in enumerate(S['blocks']):
        f = _font(_size_for_cap(b['cap']))
        col = accent if (accent and b['role'] == '표제') else ink
        for j, t in enumerate(b['text']):
            y = b['base0'] + b['lead'] * j
            d.text((b['x'], y), t, font=f, fill=col, anchor='ls')
    if path:
        im.save(path)
    return im, S
