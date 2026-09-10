"""줄 «안» 의 축 — 낱말이 줄을 넘어 같은 x 에 서는가.

v1 을 원본 옆에 놓자 드러났다. 원본은 「leitung ⟶ robert f. denzler ⟶
solist ⟶ zino francescatti」처럼 한 줄이 여러 칸으로 나뉘고, 칸마다 줄을
넘어 같은 자리에 선다. 우리는 축을 «덩어리 왼끝» 에서만 쟀다.

    ① 낱말 나누기   줄 띠 안의 세로 잉크 프로파일에서 빈 칸의 폭을 모은다.
                   글자 사이 틈과 낱말 사이 틈은 두 무리다. 오츠로 가른다 —
                   문턱을 짓지 않는다.
    ② 맞춤 세기     낱말 시작점마다 «다른 줄의 낱말 시작점» 이 ±EPS 안에
                   있는지. 있으면 맞춘 것이다.
    ③ 귀무          줄마다 통째로 아무렇게나 옆으로 민다. 줄 안의 낱말 간격은
                   그대로 두고 «줄끼리의 맞춤» 만 부순다.

EPS 는 features.AXIS_EPS(2px, 안티에일리어싱 폭)를 그대로 쓴다.
"""
import numpy as np
from PIL import Image

import features

EPS = features.AXIS_EPS
N_NULL = 200


def _otsu(v):
    v = np.asarray(v, float)
    if len(v) < 4 or v.max() <= v.min():
        return None
    h, ed = np.histogram(v, bins=32)
    p = h / h.sum(); mids = (ed[:-1] + ed[1:]) / 2
    w0 = np.cumsum(p); m0 = np.cumsum(p * mids); mt = m0[-1]
    ok = (w0 > 1e-6) & (w0 < 1 - 1e-6)
    bt = np.where(ok, (mt * w0 - m0) ** 2 / np.where(ok, w0 * (1 - w0), 1), 0)
    return float(mids[int(np.argmax(bt))])


def lines_of(rgb, blocks):
    """덩어리의 줄마다 (y위, y아래, x1, x2, 잉크 여부 열)."""
    out = []
    for b in blocks:
        xs, xe = int(b['x1']), int(b['x2'])
        for base, top in zip(b.get('bases') or [], b.get('xtops') or []):
            if base is None or top is None or base - top < 3:
                continue
            y0 = max(0, int(top)); y1 = int(base) + 1
            band = rgb[y0:y1, xs:xe].astype(np.float32)
            if band.size == 0:
                continue
            bg = np.median(band.reshape(-1, 3), axis=0)
            d = np.sqrt(((band - bg) ** 2).sum(-1))
            t = _otsu(d.ravel())
            if t is None:
                continue
            col = (d > t).any(axis=0)
            out.append(dict(y0=y0, y1=y1, x1=xs, col=col, xh=float(base - top)))
    return out


def words(line):
    """한 줄 → 낱말 시작 x 들 (판 좌표). 틈의 폭 분포를 둘로 가른다."""
    col = line['col']
    runs, gaps, i, n = [], [], 0, len(col)
    while i < n:
        if col[i]:
            j = i
            while j < n and col[j]:
                j += 1
            runs.append((i, j)); i = j
        else:
            i += 1
    if len(runs) < 2:
        return [line['x1'] + r[0] for r in runs], None
    gaps = [runs[k + 1][0] - runs[k][1] for k in range(len(runs) - 1)]
    t = _otsu(gaps)
    if t is None:
        return [line['x1'] + runs[0][0]], None
    starts = [runs[0][0]] + [runs[k + 1][0] for k, g in enumerate(gaps) if g > t]
    return [line['x1'] + s for s in starts], t


def aligned(starts_by_line, eps=EPS):
    """낱말 시작점 중 «다른 줄» 의 시작점과 eps 안에 있는 것의 몫."""
    allp = [(li, x) for li, xs in enumerate(starts_by_line) for x in xs]
    if len(allp) < 4 or len(starts_by_line) < 2:
        return None
    hit = 0
    for li, x in allp:
        if any(lj != li and abs(x - y) <= eps for lj, y in allp):
            hit += 1
    return hit / len(allp)


def measure(path, blocks, seed=20260910):
    rgb = np.asarray(Image.open(path).convert('RGB'))
    W = rgb.shape[1]
    L = lines_of(rgb, blocks)
    S = [words(l)[0] for l in L]
    S = [s for s in S if s]
    got = aligned(S)
    if got is None:
        return None
    rnd = np.random.RandomState(seed); null = []
    for _ in range(N_NULL):
        sh = []
        for s in S:
            lo, hi = -min(s), W - max(s)
            off = rnd.uniform(lo, hi) if hi > lo else 0.0
            sh.append([x + off for x in s])
        null.append(aligned(sh))
    null = np.array(null, float)
    # 줄 안 칸나눔만 보려면 «덩어리 왼끝» 을 빼야 한다 — 그것은 이미 쟀다
    inner = [s[1:] for s in S if len(s) > 1]
    got_in = aligned([s for s in inner if s]) if sum(len(s) for s in inner) >= 4 else None
    return dict(줄=len(S), 낱말=sum(len(s) for s in S),
                맞춤=round(got, 3), 귀무=round(float(null.mean()), 3),
                배=round(got / max(float(null.mean()), 1e-9), 2),
                분위=round(float((null >= got).mean()), 4),
                안쪽맞춤=(None if got_in is None else round(got_in, 3)),
                starts=S, lines=L)
