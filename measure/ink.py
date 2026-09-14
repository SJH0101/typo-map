"""잉크 프로파일에서 글줄을 읽는다 — 재는 쪽의 바닥.

받은 자리를 잰다. 어디를 잴지는 정하지 않는다. 그 판단은 짚는 쪽(VLM)이나
비교 대상인 baseline/ 이 하고, 이 모듈은 그것을 받아 행 단위 잉크량으로
글줄·베이스라인·x높이·발음기호·디센더를 뽑는다.

추정이 들어가면 안 되는 자리다. 재는 값이 행간/활자높이 같은 «비» 라서
작은 편향이 규칙 채택을 통째로 바꾼다 — VLM 에게 같은 일을 시키면 +24%
편향이 나온다 (measure/region.py 참조).
"""
import numpy as np
from PIL import Image
from scipy import ndimage


FRAG_WIDE = 0.40    # 이웃 글줄 폭의 이 비율 이하로 좁으면 글줄이 아니라 조각으로 본다

FRAG_COVER = 0.35   # 제 폭 안에서 잉크가 든 칸이 이 비율 이하면 글줄이 아니라 조각이다.
                    # 폭만으로는 「musica viva」 의 i 점 두 개를 못 거른다 — 점이
                    # 멀리 떨어져 있어 폭이 몸통의 43%가 되고 FRAG_WIDE 를 넘긴다.
                    # 글줄은 제 폭을 거의 채우지만 점은 그 안이 비어 있다.
                    # 이 판에서 점은 0.12, 진짜 글줄은 0.63~0.92 로 갈렸다.

INK_FRAC = 0.06     # 그 단 최대 잉크의 이 비율 이하는 얼룩으로 본다. 스윕 결과 0.02~0.10 평평, 0.20부터 줄 소실

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

    # 조각 문턱은 그 계층에서 가장 큰 글줄에 비례시킨다. 4px 고정이면 8px
    # 본문에서는 맞지만 70px 제목에서는 움라우트 점(14px)이나 큰 글자의
    # 아래 가장자리(3px)가 저마다 글줄로 선다 — 「Opernhaus Zürich」 한 판에서
    # 부스러기 블록이 여덟 개 나왔다.
    # 글줄인지 조각인지는 높이가 아니라 폭으로 갈린다. 같은 블록 안에서
    # 글줄은 이웃 줄과 폭이 비슷하지만, 움라우트 점이나 큰 글자의 아래
    # 가장자리는 이웃의 일부만 덮는다. Zürich 의 ü 점은 폭이 7%, 높이는
    # 19% 다 — 높이만 보면 본문의 짧은 줄과 구분되지 않는다.
    def wide(o):
        return o['span'][1] - o['span'][0]

    def cover(o):
        a, b = o['span']
        if b <= a:
            return 1.0
        return float((m[o['s']:o['e'], a:b].sum(axis=0) > 0).mean())

    res = []
    i = 0
    while i < len(out):
        cur = out[i]
        best, bd = None, None
        for j in (i + 1, i - 1):
            if not (0 <= j < len(out)): continue
            nb = out[j]
            if nb['h'] <= cur['h']: continue
            gap = (nb['s'] - cur['e']) if j > i else (cur['s'] - nb['e'])
            inside = (cur['span'][0] >= nb['span'][0] - 1
                      and cur['span'][1] <= nb['span'][1] + 1)
            small = (cur['h'] <= nb['h'] * 0.5
                     and (wide(cur) <= FRAG_WIDE * max(wide(nb), 1)
                          or cover(cur) <= FRAG_COVER))
            if inside and small and gap <= max(3, nb['h'] * 0.6) and (bd is None or gap < bd):
                best, bd = j, gap
        if best is not None:
            nb = out[best]
            nb['s'] = min(nb['s'], cur['s']); nb['e'] = max(nb['e'], cur['e'])
            nb['h'] = nb['e'] - nb['s']
            if best > i: nb['mark'] = True
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
                       xh=base - f['x_top'], ink_top=r['s'], ink_bot=r['e'],
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

    # x 높이선: 베이스라인 마지막 잉크 행까지 내려오고 윗끝이 줄 잉크 중심 행보다 위인 덩어리들의
    # 윗끝 가운데 가장 낮은 것 (G1, 사전등록 docs/xheight_g1_preregister.json).
    # 숫자 · 어센더는 x 높이 글자와 따로 떨어진 덩어리라 이 값을 끌어올리지 못한다. 점 · 악센트는
    # 베이스라인에 닿지 않고, 마침표 · 하이픈은 중심 행 위로 올라가지 않거나 베이스라인에 닿지 않는다.
    # 행 프로파일의 «최댓값 절반» 어깨는 숫자가 많은 줄에서 숫자 윗끝(−6px)까지 올라갔다.
    # 해당하는 덩어리가 없으면 옛 어깨(잉크가 최댓값의 절반을 넘는 첫 행)로 되돌아간다.
    xh = s + int(np.argmax(prof >= 0.5 * prof.max()))
    raw = min(max(base - BASE_OFFSET - s, 1), len(prof) - 1)
    w = prof[:raw + 1]
    if w.sum() > 0:
        cen = s + float((np.arange(raw + 1) * w).sum() / w.sum())
        low = [t for t, b in comps if b >= s + raw and t <= cen]
        if low:
            xh = max(low)

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


# ── 획 마스크 ────────────────────────────────────────────────
# 「활자가 덮은 넓이」를 상자 넓이로 세면 안 된다. 상자 안은 대부분 빈
# 자리다. 큰 표제 한 줄의 상자는 판의 3% 를 덮지만 획은 그 안의 1/5 이다.
# 눈으로 보면 바로 드러난다 — 열쇠 기호 하나가 통째로 «활자» 로 칠해졌다.

def strokes(rgb, box, pad=1):
    """상자 안의 «획» 화소. 상자를 통째로 칠하지 않는다.

    잉크는 «어두운 것» 이 아니라 «바탕색에서 먼 것» 이다. 검은 바탕의 금색
    글자, 붉은 바탕의 분홍 글자 — 밝기로만 보면 8밖에 안 떨어진다. 그래서
    회색으로 바꾼 뒤 중앙값으로 가르는 방식이 세 판에 하나꼴로 뒤집혔다.

    바탕색은 상자 안 «채널별 중앙값» 으로 본다. 활자는 제 상자 안에서도
    소수라서 중앙값이 바탕에 앉는다. 그 색에서의 거리를 오츠로 둘로 가르고
    «먼 쪽» 이 획이다.

    문턱을 짓지 않는다 — 오츠가 집단간 분산이 최대인 자리를 고른다. 색이
    한 가지뿐이면(획이 없으면) 거리가 전부 0에 몰려 아무것도 안 남는다.
    """
    H, W = rgb.shape[:2]
    x1 = max(0, int(box[0]) - pad); y1 = max(0, int(box[1]) - pad)
    x2 = min(W, int(box[2]) + pad); y2 = min(H, int(box[3]) + pad)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None, (x1, y1, x2, y2)
    v = rgb[y1:y2, x1:x2].astype(np.float32)
    bg = np.median(v.reshape(-1, v.shape[-1]), axis=0)
    d = np.sqrt(((v - bg) ** 2).sum(-1))
    if float(d.max()) < 1e-6:
        return np.zeros(d.shape, bool), (x1, y1, x2, y2)
    return d > _otsu_t(d.ravel()), (x1, y1, x2, y2)


def _otsu_t(v):
    """오츠 문턱. 나눗셈이 0이 되는 자리를 비워 둔다."""
    h, ed = np.histogram(v, bins=64)
    p = h / max(h.sum(), 1)
    mids = (ed[:-1] + ed[1:]) / 2.0
    w0 = np.cumsum(p); m0 = np.cumsum(p * mids); mt = m0[-1]
    ok = (w0 > 1e-6) & (w0 < 1 - 1e-6)
    if not ok.any():
        return float(v.max()) + 1.0
    bt = np.where(ok, (mt * w0 - m0) ** 2 / np.where(ok, w0 * (1 - w0), 1.0), 0.0)
    return float(mids[int(np.argmax(bt))])


def stroke_mask(path, blocks, gate=True):
    """판 한 장 → 활자 획 마스크(원본 해상도)와 버린 상자.

    원본 해상도에서 잰다. 300px 로 줄이면 본문 획이 안티에일리어싱으로
    중간톤이 되어 통째로 사라진다.
    """
    import blockgate
    im = Image.open(path).convert('RGB')
    rgb = np.asarray(im)
    g = np.asarray(im.convert('L'), np.float32)
    keep, drop = (blockgate.filter_blocks(g, list(blocks)) if gate
                  else (list(blocks), []))
    m = np.zeros(rgb.shape[:2], bool)
    for b in keep:
        s, (x1, y1, x2, y2) = strokes(rgb, (b['x1'], b['y1'], b['x2'], b['y2']))
        if s is not None:
            m[y1:y2, x1:x2] |= s
    return m, keep, drop
