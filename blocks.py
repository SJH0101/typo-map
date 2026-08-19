import numpy as np
from PIL import Image
from scipy import ndimage

EPS        = 2      # 측정 오차 (안티에일리어싱 2~3px). 절대 하한으로 쓴다.
GAP_RATIO  = 1.5    # 행간이 중앙값의 1.5배 넘으면 자름
SIZE_RATIO = 0.25   # 활자 높이가 25% 넘게 변하면 자름
XSTART_EPS = EPS    # 정렬 축이 오차 이상 움직이면 자름

def polarity(g):
    """어두운 바탕에 밝은 활자면 뒤집어 돌려준다.

    아래의 모든 판정이 「잉크는 배경보다 어둡다」(g < th) 를 전제한다.
    극성을 여기서 한 번 맞춰두면 나머지 코드는 그대로 쓸 수 있다.

    활자는 화면의 소수파다. 그래서 중앙값에서 먼 쪽이 활자다.
    밝은 꼬리가 어두운 꼬리보다 길면 활자가 밝은 것으로 본다.
    절대 밝기로 자르지 않는 이유: 회색 바탕 포스터는 중앙값만 보면
    어느 쪽인지 알 수 없다. 코어 108장 중 13장이 그런 중간톤이었다.
    """
    lo, med, hi = np.percentile(g, (5, 50, 95))
    return 255.0 - g if (hi - med) > (med - lo) else g


def threshold(g):
    bg = np.median(g)
    return bg * 0.72          # 배경 밝기 기준 (회색 활자 대응)

def trim(g, th, frac=0.8, max_fringe=3):
    """스캔 테두리 제거.
       1) 폭의 frac 이상이 어두운 가장자리 = 테두리
       2) 그 안쪽으로 잉크가 0이 될 때까지 = 안티에일리어싱 띠 (최대 max_fringe px)
       테두리가 없으면 아무것도 자르지 않는다."""
    m = g < th
    def cut(vals):
        i = 0
        while i < len(vals) and vals[i] > frac: i += 1
        if i == 0: return 0, 0
        f = 0
        while f < max_fringe and i + f < len(vals) and vals[i + f] > 0: f += 1
        return i, f
    cw = [m[:, x].mean() for x in range(g.shape[1])]
    ch = [m[y, :].mean() for y in range(g.shape[0])]
    L, Lf = cut(cw); R, Rf = cut(cw[::-1])
    T, Tf = cut(ch); B, Bf = cut(ch[::-1])
    box = (L + Lf, T + Tf, g.shape[1] - R - Rf, g.shape[0] - B - Bf)
    log = dict(left=(L, Lf), right=(R, Rf), top=(T, Tf), bottom=(B, Bf),
               capped=[k for k, (b, f) in
                       dict(left=(L, Lf), right=(R, Rf), top=(T, Tf), bottom=(B, Bf)).items()
                       if b > 0 and f == max_fringe])
    return box, log

def check_trim(g, th, box, limit=0.35):
    """자르고 난 뒤 가장자리에 테두리 잔재가 남았는지 본다.
       글자는 한 열을 다 채우지 않으므로, 가장자리 열이 limit 넘게 어두우면 실패."""
    x0, y0, x1, y1 = box
    m = (g[y0:y1, x0:x1] < th)
    e = dict(left=m[:, 0].mean(), right=m[:, -1].mean(),
             top=m[0, :].mean(), bottom=m[-1, :].mean())
    bad = {k: round(float(v), 3) for k, v in e.items() if v > limit}
    return (len(bad) == 0), bad

COL_FRAC = 0.13     # 단 사이 빈 띠 판정. 그 영역 최대 잉크의 이 비율 이하를 빈 것으로 본다.
                    # 코어 108장 스윕 (표본 n / 블록 수)
                    #   0.00  58 / 901     0.15  75 / 1022
                    #   0.10  69 / 960     0.18  74 / 1084
                    #   0.13  69 / 985     0.25  66 / 1190
                    #                      0.35  72 / 1335
                    # 총량만 보면 0.15 가 낫다. 그런데 0.15 는 1952 Die Gute
                    # Form 의 오른쪽 정렬 5줄 블록을 쪼갠다 (n 5 → 1). 눈으로
                    # 확인한 블록이다. 오른쪽 정렬은 왼쪽 끝이 들쭉날쭉하므로
                    # 블록 안에 잉크가 적은 세로 띠가 생기고, 문턱이 높으면
                    # 그것을 단 경계로 오인한다. 0.13 이 그 블록을 지키는
                    # 최대값이다. 회귀 검사가 잡았다.

def columns(g, th, min_gap=6):
    """세로로 빈 띠를 찾아 단을 가른다.

    「잉크가 정확히 0」 을 요구하면 얼룩·그래픽·스캔 노이즈가 띠를 메워 단이
    갈리지 않는다. lines() 는 같은 문제를 이미 상대 비율(INK_FRAC)로 풀고
    있었는데 여기만 절대 0 이었다.
    """
    col = (g < th).sum(axis=0)
    peak = np.percentile(col[col > 0], 90) if (col > 0).any() else 0.0
    empty = col <= COL_FRAC * peak
    gaps = []; s = None
    for x, v in enumerate(empty):
        if v and s is None: s = x
        if (not v) and s is not None:
            if x - s >= min_gap: gaps.append((s, x))
            s = None
    out = []; prev = 0
    for s, e in gaps + [(g.shape[1], g.shape[1])]:
        if s - prev > 10:
            idx = np.where(col[prev:s] > 0)[0]
            if len(idx): out.append((prev + idx[0], prev + idx[-1] + 1))
        prev = e
    return out

STRATA_RATIO = 3.0  # 성분 높이가 중앙값의 이 배를 넘으면 다른 크기 계층으로 본다.
                    # 36장 스윕: 분리 없음 n=8, 2.5~12배 n=14~17 로 평평하다.
                    # 값이 아니라 분리하느냐 마느냐가 결정적이다. 3.0 은 얕은 봉우리.

INK_FRAC = 0.06     # 그 단 최대 잉크의 이 비율 이하는 얼룩으로 본다. 스윕 결과 0.02~0.10 평평, 0.20부터 줄 소실


def lines(g, th, x0, x1, min_h=2, body_h=4, mask=None):
    """min_h 로 잘게 자른 뒤, 몸통 위의 작은 조각을 발음기호로 흡수한다"""
    m = (g[:, x0:x1] < th) if mask is None else mask
    ink = m.sum(axis=1).astype(float)
    # 절대량이 아니라 비율로 판정한다. 얼룩·테두리·안티에일리어싱은
    # 잉크량이 글자 몸통의 몇 %에 불과하므로 이 규칙 하나로 함께 걸러진다.
    peak = np.percentile(ink[ink > 0], 90) if (ink > 0).any() else 0.0
    on = ink > max(np.percentile(ink, 5), INK_FRAC * peak)
    segs = []; s = None
    for i, v in enumerate(on):
        if v and s is None: s = i
        if (not v) and s is not None:
            if i - s >= min_h: segs.append((s, i))
            s = None
    if s is not None and len(on) - s >= min_h: segs.append((s, len(on)))

    def span(s, e):
        c = np.where(m[s:e].sum(axis=0) > 0)[0]
        return c[0], c[-1] + 1

    out = []
    for s, e in segs:
        h = e - s
        out.append(dict(s=s, e=e, h=h, span=span(s, e), dia=False))

    res = []
    i = 0
    while i < len(out):
        cur = out[i]
        if cur['h'] < body_h and i + 1 < len(out):
            nxt = out[i + 1]
            gap = nxt['s'] - cur['e']
            inside = cur['span'][0] >= nxt['span'][0] - 1 and cur['span'][1] <= nxt['span'][1] + 1
            if gap <= max(3, nxt['h'] * 0.6) and inside and cur['h'] <= nxt['h'] * 0.5:
                nxt['s'] = cur['s']; nxt['mark'] = True
                i += 1; continue
        if cur['h'] >= body_h:
            res.append(cur)
        i += 1

    ls = []
    for r in res:
        base, raw = baseline(ink, r['s'], r['e'])
        desc_row = descender(m, raw, r['span'])
        f = split_marks(m, r['s'], r['e'], r['span'], base)
        f['desc'] = desc_row
        ls.append(dict(base=base, cap=f['cap'], x_top=f['x_top'], mark_top=f['mark'],
                       n_mark=f['n_mark'], desc=f['desc'], cap_kind=f['kind'],
                       top=f['cap'] if f['cap'] is not None else f['x_top'],
                       xh=base - f['x_top'], ink_top=r['s'],
                       xs=x0 + r['span'][0], xe=x0 + r['span'][1]))
    return ls


BASE_OFFSET = 1     # 사람은 글자가 끝난 첫 행에 찍고, 잉크는 마지막 행에서 끝난다.
                    # 1958 Musica Viva 25줄 대조에서 +1px 로 일정 (평균 +1.08, 범위 0~2).


def baseline(ink, s, e, frac=0.5):
    """베이스라인 = 글자 몸통이 살아 있는 마지막 행.
       디센더는 획이 적어 잉크가 확 줄므로 몸통 기준선을 흔들지 못한다.
       그 아래로 잉크가 남으면 디센더 바닥으로 본다."""
    seg = ink[s:e]
    nz = seg[seg > 0]
    if len(nz) == 0: return s, None
    med = np.median(nz[nz >= np.percentile(nz, 50)])
    ok = np.where(seg >= frac * med)[0]
    if len(ok) == 0: return s, None
    raw = s + int(ok[-1])              # 잉크가 끝나는 행
    return raw + BASE_OFFSET, raw      # 디센더는 2차원 모양으로 따로 판정한다


def descender(m, raw, span, min_h=2, depth=6):
    """디센더는 잉크 양이 아니라 세로로 이어지는 길이로 가른다.

    800px 해상도에서 9px 활자의 디센더는 2px 이므로 잉크량이
    안티에일리어싱 잔여와 구별되지 않는다. 그러나 잔여는 한 행에만
    얇게 깔리고 디센더는 세로획이라 2행 이상 이어진다.
    1958 Musica Viva 10줄에서 이 기준이 디센더 유무를 정확히 갈랐다.
    """
    sub = m[raw + 1:raw + 1 + depth, span[0]:span[1]]
    if sub.size == 0 or not sub.any():
        return None
    lab, n = ndimage.label(sub, structure=np.ones((3, 3)))
    bottom = None
    for i in range(1, n + 1):
        ys = np.where((lab == i).any(axis=1))[0]
        if ys[-1] - ys[0] + 1 < min_h:          # 세로로 안 이어지면 잔여
            continue
        b = raw + 1 + int(ys[-1])
        bottom = b if bottom is None else max(bottom, b)
    return None if bottom is None else bottom + BASE_OFFSET


def split_marks(m, s, e, span, base):
    """한 줄의 세로 기준선을 전부 뽑는다.
       mark   몸통 위에 뜬 조각 (i·j 점, 움라우트, 악센트)
       cap    어센더 / 대문자 꼭대기 — 없으면 None
       x_top  소문자 몸통 꼭대기 — 항상 있음
       desc   디센더 바닥 — 없으면 None
    """
    sub = m[s:e, span[0]:span[1]]
    prof = sub.sum(axis=1).astype(float)
    if prof.max() == 0:
        return dict(cap=None, x_top=s, mark=None, n_mark=0, desc=None, kind='none')

    lab, n = ndimage.label(sub, structure=np.ones((3, 3)))
    comps = []
    for i in range(1, n + 1):
        rows = np.where((lab == i).any(axis=1))[0]
        comps.append((s + rows[0], s + rows[-1]))

    # x 높이 어깨: 잉크가 최댓값의 절반을 넘는 첫 행 (몸통이 시작되는 자리)
    xh = s + int(np.argmax(prof >= 0.5 * prof.max()))

    mark, n_mark, body = None, 0, []
    for top, bot in comps:
        if bot < xh:                       # 몸통까지 안 내려옴 = 뜬 조각
            mark = top if mark is None else min(mark, top)
            n_mark += 1
        else:
            body.append((top, bot))
    if not body:
        return dict(cap=None, x_top=xh, mark=mark, n_mark=n_mark, desc=None, kind='none')

    x_top = xh
    tops = [t for t, b in body]
    cap = min(tops)
    # 몸통 조각 대다수가 x 높이에서 시작하면 어센더 없음
    kind = 'ascender' if (xh - cap) >= 2 else 'x_only'
    if kind == 'x_only':
        cap = None
    return dict(cap=cap, x_top=x_top, mark=mark, n_mark=n_mark, desc=None, kind=kind)


def fit_grid(bases, ink, s0, s1):
    """블록의 베이스라인들을 등간격 격자에 맞춘다.
       행간은 자기상관으로 구하고, 위상은 잔차 제곱합 최소로 정한다.
       줄 하나가 글자 모양 때문에 1px 흔들려도 나머지가 위치를 잡아준다."""
    if len(bases) < 3:
        return bases, None, 0.0
    # 창을 잉크 배열 안으로 가둔다. apply_grid 는 첫 베이스라인에서 20px 위를
    # 창의 시작으로 잡는데, 블록이 단 상단에 가까우면 음수가 된다. numpy 는
    # 음수 시작을 뒤에서부터로 해석하므로 ink[-3:59] 가 빈 배열이 되어
    # np.correlate 가 죽었다. 코어 108장 중 2장이 이 때문에 빠져 있었다.
    s0 = max(0, int(s0))
    s1 = min(len(ink), int(s1))
    if s1 - s0 < 3:
        return bases, None, 0.0
    r = ink[s0:s1] - ink[s0:s1].mean()
    ac = np.correlate(r, r, 'full')[len(r)-1:]
    if ac[0] <= 0: return bases, None, 0.0
    ac = ac / ac[0]
    lo, hi = 5, min(len(ac) - 1, 60)
    if hi <= lo: return bases, None, 0.0
    seg = ac[lo:hi]
    peaks = [lo + i for i in range(1, len(seg) - 1)
             if seg[i] > seg[i-1] and seg[i] >= seg[i+1] and seg[i] > 0.25]
    if not peaks: return bases, None, 0.0
    lead = min(peaks)                  # 배수 봉우리를 피해 기본 주기를 고른다
    med = np.median(np.diff(bases)) if len(bases) > 1 else lead
    if abs(lead - med) > 2:            # 실측과 크게 다르면 신뢰하지 않음
        return bases, None, 0.0
    k = np.round((np.array(bases) - bases[0]) / lead)
    phase = float(np.mean(np.array(bases) - k * lead))
    fitted = [int(round(phase + i * lead)) for i in k]
    resid = float(np.mean(np.abs(np.array(fitted) - np.array(bases))))
    return fitted, lead, resid


def shares_axis(a, b, eps=XSTART_EPS):
    """두 줄이 같은 정렬 축을 공유하는가.

    정렬 방식을 코드가 정하지 않는다. 왼쪽·오른쪽·가운데 중 어느 축이든
    하나만 맞으면 같은 블록으로 본다. 셋 다 어긋날 때만 자른다.

    왼쪽 축만 보던 때는 왼쪽 정렬 격자를 전제하는 것이었다. 그 전제는
    조판 방식을 코드에 박는 것이고, 오른쪽 정렬이나 가운데 정렬로 짠
    블록은 줄마다 좌측 끝이 수십 px 씩 움직이므로 전부 낱줄로 흩어졌다.
    """
    return (abs(a['xs'] - b['xs']) <= eps or                       # 왼쪽
            abs(a['xe'] - b['xe']) <= eps or                       # 오른쪽
            abs((a['xs'] + a['xe']) - (b['xs'] + b['xe'])) <= 2 * eps)   # 가운데


def scale_strata(m, ratio=None):
    """잉크를 크기 계층으로 가른다.

    행간은 크기 계층 안에서만 정의된다. 자기 키의 수십 배인 성분이 같은
    가로 스캔에 섞이면, 그 성분의 잉크가 모든 행에 걸쳐 작은 활자의 줄
    경계를 덮는다. 호프만은 활자로 그림을 그리므로 이 일이 자주 일어난다.
    Bach-Chor 포스터에서는 x높이 464px 의 「B」 하나가 8px 활자 6줄을
    통째로 삼켰다.

    큰 글자를 배제하는 것이 아니다. 자기 계층에서 따로 측정될 뿐이고,
    낱글자라면 잴 행간이 없을 뿐이다.
    """
    ratio = STRATA_RATIO if ratio is None else ratio   # 기본 인자로 두면 정의 시점에 굳는다
    lab, n = ndimage.label(m)
    if n == 0:
        return [m]
    hs = np.array([o[0].stop - o[0].start for o in ndimage.find_objects(lab)])
    body = hs[hs >= 2]
    if body.size == 0:
        return [m]
    big = np.where(hs > ratio * float(np.median(body)))[0] + 1
    if big.size == 0:
        return [m]
    tall = np.isin(lab, big)
    return [m & ~tall, tall]


def group(ls):
    if not ls: return []
    if len(ls) < 2: return [ls]
    gaps = [ls[i+1]['base'] - ls[i]['base'] for i in range(len(ls)-1)]
    med  = np.median(gaps)
    blocks = [[ls[0]]]
    for i, gp in enumerate(gaps):
        a, b = ls[i], ls[i+1]
        # 크기는 이웃 한 줄이 아니라 지금까지 쌓인 블록의 중앙값과 견준다.
        # 한 줄만 보면 내용 때문에 x높이가 튀는 것을 크기 변화로 오인한다 —
        # 움라우트가 있는 줄(für), 숫자만 있는 줄(fr.1.10-3.30) 은 소문자
        # 줄보다 잉크가 높게 잡힌다. 1957 Musica Viva 에서 12줄 단이 7+5 로,
        # 7줄 단이 6+1 로 잘린 것이 전부 이 때문이었다.
        ref = float(np.median([l['xh'] for l in blocks[-1]]))

        def differs(x):
            return (abs(ref - x) > EPS and
                    abs(ref - x) / min(ref, x) > SIZE_RATIO)

        # 크기 변화는 이어져야 인정한다. 한 줄만 튀는 것은 내용 때문이다 —
        # 움라우트가 있는 줄(für)과 숫자만 있는 줄(fr.1.10-3.30)은 소문자
        # 줄보다 잉크가 높게 잡힌다. 활자 크기가 실제로 바뀌면 다음 줄도
        # 함께 바뀐다. 1957 Musica Viva 에서 12줄 단이 7+5 로, 7줄 단이
        # 6+1 로 잘린 것이 전부 한 줄짜리 튐 때문이었다.
        nxt = ls[i+2] if i + 2 < len(ls) else None
        size_cut = differs(b['xh']) and (nxt is None or differs(nxt['xh']))

        cut  = (gp > GAP_RATIO * med
                or size_cut
                or not shares_axis(a, b))
        (blocks.append([b]) if cut else blocks[-1].append(b))
    return blocks

def box(bl):
    return (min(l['xs'] for l in bl), min(l['top'] for l in bl),
            max(l['xe'] for l in bl), max(l['base'] for l in bl))

def apply_grid(ls, ink):
    if len(ls) < 3: return ls, None, 0.0
    bases = [l['base'] for l in ls]
    fitted, lead, resid = fit_grid(bases, ink, ls[0]['base'] - 20, ls[-1]['base'] + 8)
    # 측정값은 그대로 둔다. 격자는 별도 열로만 남긴다.
    for l, b0, b1 in zip(ls, bases, fitted):
        l['base_grid'] = b1
        l['shift'] = b1 - b0
    return ls, lead, resid


def run(src, region):
    """src 는 파일 경로 또는 회색조 배열. 배열을 받으면 디스크를 거치지 않는다.

    예전에는 호출하는 쪽이 고정 경로 /tmp/_work.png 에 저장해 넘겼다. 측정을
    두 개 동시에 돌리면 서로의 파일을 덮어써서 엉뚱한 이미지를 재고, 조용히
    틀린 값이 나온다. 포스터마다 PNG 를 인코딩·디코딩하는 값도 없다.
    """
    g = (src.astype(float) if isinstance(src, np.ndarray)
         else np.asarray(Image.open(src).convert('L')).astype(float))
    g = g[region[1]:region[3], region[0]:region[2]]
    g = polarity(g)           # 밝은 활자 / 어두운 배경을 여기서 정규화한다
    th = threshold(g)
    (tx0, ty0, tx1, ty1), _ = trim(g, th)
    g = g[ty0:ty1, tx0:tx1]
    region = (region[0]+tx0, region[1]+ty0, region[0]+tx1, region[1]+ty1)
    res = []
    cols = columns(g, th)
    for cx0, cx1 in cols:
      for sm in scale_strata(g[:, cx0:cx1] < th):
        ink_col = sm.sum(axis=1).astype(float)
        for bl in group(lines(g, th, cx0, cx1, mask=sm)):
            bl, lead, resid = apply_grid(bl, ink_col)
            x1, y1, x2, y2 = box(bl)
            res.append(dict(lead=lead, grid_resid=round(resid, 2),x1=x1+region[0], y1=y1+region[1], x2=x2+region[0], y2=y2+region[1],
                            n=len(bl), h=round(float(np.median([l['base']-l['top'] for l in bl])), 1),
                            xh=round(float(np.median([l['xh'] for l in bl])), 1),
                            lines=[dict(top=l['top']+region[1], base=l['base']+region[1],
                                        base_grid=(None if l.get('base_grid') is None
                                                   else l['base_grid']+region[1]),
                                        shift=l.get('shift', 0),
                                        x_top=l['x_top']+region[1],
                                        cap=None if l['cap'] is None else l['cap']+region[1],
                                        mark_top=None if l['mark_top'] is None else l['mark_top']+region[1],
                                        desc=None if l['desc'] is None else l['desc']+region[1],
                                        cap_kind=l['cap_kind'], n_mark=l['n_mark'],
                                        ink_top=l['ink_top']+region[1], xh=l['xh'],
                                        xs=l['xs']+region[0], xe=l['xe']+region[0]) for l in bl],
                            base=[l['base']+region[1] for l in bl]))
    return th, res, len(cols)

if __name__ == '__main__':
    th, res, n_cols = run('/mnt/user-data/uploads/1958_Musica_viva_-_Dienstag__den_7__Januar_1958_-_Schweizerische_.jpg',
                          (0, 630, 566, 795))
    print('threshold', round(th, 1))
    for i, b in enumerate(res, 1):
        print(f"{i}  box({b['x1']},{b['y1']})-({b['x2']},{b['y2']})  줄 {b['n']}  활자 {b['h']}px")
