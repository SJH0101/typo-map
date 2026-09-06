"""판을 나눈다 — 활자와 활자 아닌 것.

**2026-09-07 에 크게 물렸다.** 아래 네 갈래(활자·색면·사진·바탕)를 12장에
띄워 놓고 보니 대부분이 틀렸다.

    활자   검출 상자를 «통째로» 칠하고 있었다. 상자 안은 대부분 빈 자리다.
           Juni-Festwochen 1965 는 0.472 로 셌는데 획은 0.139 였다.
           Gewerbemuseum 1954 는 0.567 대 0.025 — 스무 배.
    사진   두 색 선그림(Kunsthalle 1956)이 «사진» 0.50 으로 나왔다.
           사진이 없는 판(Lohse 1970)에 사진이 붙었다.
    색면   사진 한 장(VOLG 1957)이 색면과 사진으로 반씩 쪼개졌다.
    바탕   크림색 바탕(Gewerbemuseum 1954 · Juni 1953)이 색면으로 갔다.

그래서 이렇게 나눈다.

    ① 활자   고쳤다. 상자가 아니라 «획» 을 센다 (measure/ink.strokes).
             바탕색에서 먼 화소를 오츠로 가른다 — 밝기가 아니다.
    ② 색면·사진·바탕   **보류한다.** 대조할 기준이 없다. 손라벨이 있어야
             고쳤는지 알 수 있고, 그때까지 적는 것은 틀린 값을 자신 있게
             적는 일이다. split() 은 남겨 두되 결과에 쓰지 않는다.

활자몫에서 나온 값도 그대로 못 쓴다. 상자 172개 중 37개는 거르개가 «못
정함» 이다 (성분이 셋 미만이면 높이CV 를 못 낸다). 그 몫을 따로 낸다 —
활자몫 하나가 아니라 [확실, 확실+미정] 두 수로 적는다.

거르개 후보를 획 마스크 위에서 다시 재봤다. 나아지지 않았다.

    높이CV 0.779 · 너비CV 0.705 · 밑선몫 0.699 · 획몫 0.586
    세로가로 0.573 · 성분수 0.558 · 성분당넓이 0.507

「한 줄짜리 글자 상자는 세로보다 가로가 길다」도 (0.573) 「글자 성분은 몇
개 안 되는 밑선에 앉는다」도 (0.699) 높이CV(0.779)를 못 이겼다. 지난번
넓이·오츠 때와 같다 — 짐작한 것이 또 다 졌다.
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

import color.fields as fields
from measure import ink

WORK = 300         # 이 크기로 줄여서 본다 (fields.segment 와 같게)
WIN = 9            # 다양도·결을 보는 창. 300px 판에서 3%
DIV_HI = 2.5       # 창 안 계급 수가 이보다 많으면 사진 쪽
TEX_HI = 0.055     # 국소 표준편차(0~1)가 이보다 크면 사진 쪽
FILL = 9           # 사진 후보를 이 크기로 닫고 구멍을 메운다. 다양도는 계급
                   # «경계» 에서 터지므로 그냥 두면 면이 아니라 윤곽만 남는다 —
                   # 첫 판에서 붓자국·만화·삽화가 전부 테두리로만 잡혔다.
                   # 15 로 두었더니 이번엔 떨어진 것들을 이어 붙였다.
SOLID = 0.22       # 색면이 제 외접상자를 채우는 최소 몫. 낮게 둔다 —
                   # «평면 색인가» 는 모양이 아니라 속이 평평한가로 물어야 한다.
                   # 0.55 로 두었더니 빗살 모양 검정 막대(1957 Musica Viva)와
                   # 렌즈꼴 초록면(1953 Juni-Festwochen)이 전부 사진으로 넘어갔다.
                   # 부스러기만 거르는 몫이다.
DIV_IN = 1.6       # 색면 «안» 의 평균 계급 수. 한 색이면 창 전체가 한 계급이다.
                   # 솔리디티 대신 이것이 사진과 색면을 가른다.
TEX_LO = 0.035     # 색면 «안» 은 이보다 평평하다. 인쇄된 평면 색은 흔들리지 않는다
BIMODAL = 0.55     # 상자 안 명도를 오츠로 둘로 가른 뒤 «집단간 분산 / 전체 분산».
                   # 글자는 잉크와 종이 두 무리뿐이라 높고, 사진은 계조가
                   # 이어져 낮다. 이 아래면 활자가 아니라 그림으로 본다 —
                   # The Family of Man 의 소년 사진이 통째로 활자로 잡혔다.
                   #
                   # 처음에는 «가장 어둡거나 밝은 20% 의 몫» 으로 쟀는데 그것은
                   # 잉크가 검을 때만 맞는 검사였다. 루더 1962 의 회색 글자 +
                   # 크림 바탕은 정규화하면 회색이 0.45 — 한가운데다. 큰 글자
                   # 넷이 전부 «활자 아님» 으로 물려 사진으로 넘어갔다. 봉우리가
                   # 양 끝에 있느냐가 아니라 봉우리가 둘이냐를 물어야 한다.
MIN_BLOCK = 0.02   # 판면의 이 비율보다 큰 활자 상자만 위 검사를 건다. 작은
                   # 상자는 표본이 모자라 히스토그램을 믿을 수 없다.
MIN_REGION = 0.01  # 판면의 1% 미만인 덩어리는 이름 붙이지 않는다
TYPE_PAD = 1       # 활자 상자를 조금 넓혀 덮는다 (획 가장자리)
GROUND_BBOX = 0.60 # 평평한 덩어리의 외접상자가 판의 이 비율 이상을 덮으면 «바탕».
                   # 변에 닿는지로 묻지 않는다 — 스캔에 흰 테두리가 있으면 바탕이
                   # 가장자리에 안 닿아서 Opernhaus 의 회색 바탕(39%)이 «1변» 으로
                   # 나왔다. 바탕은 다른 것에 뚫려 있어도 판 전체를 두른다.

KINDS = ['활자', '색면', '사진', '바탕']


def _labels(seg):
    """계급 마스크들 → 픽셀마다 계급 번호 (0 = 어디에도 안 든 곳)."""
    h, w = seg['classes'][0]['mask'].shape
    lab = np.zeros((h, w), np.int16)
    for i, c in enumerate(seg['classes']):
        lab[c['mask'] & (lab == 0)] = i + 1
    return lab


def _diversity(lab, win=WIN):
    """창 안의 «서로 다른 계급 수». 계급마다 최대필터를 돌려 더한다."""
    k = np.ones((win, win), bool)
    d = np.zeros(lab.shape, np.float32)
    for v in range(1, int(lab.max()) + 1):
        d += ndimage.binary_dilation(lab == v, k).astype(np.float32)
    return d


def _texture(im, win=WIN):
    """국소 표준편차. 사진은 계급 안에서도 흔들린다."""
    g = np.asarray(im.convert('L'), np.float32) / 255.0
    m = ndimage.uniform_filter(g, win)
    m2 = ndimage.uniform_filter(g * g, win)
    return np.sqrt(np.maximum(m2 - m * m, 0))


def _bimodal(g, box):
    """상자 안 명도가 두 무리로 갈리나 — 오츠의 집단간 분산 비.

    1 에 가까울수록 «잉크와 종이» 두 무리로 깨끗이 갈린다. 사진은 계조가
    이어져 어디서 잘라도 집단 안 분산이 남는다. 잉크가 검든 회색이든
    상관없다 — 두 봉우리의 «위치» 가 아니라 «둘로 갈리는가» 를 본다.
    """
    y1, y2, x1, x2 = box
    v = g[max(0, y1):y2, max(0, x1):x2].ravel()
    if v.size < 40:
        return 1.0
    tot = float(v.var())
    if tot < 1e-9:
        return 1.0
    h, edges = np.histogram(v, bins=64, range=(float(v.min()), float(v.max())))
    p = h / h.sum()
    mids = (edges[:-1] + edges[1:]) / 2.0
    w0 = np.cumsum(p)
    m0 = np.cumsum(p * mids)
    mt = m0[-1]
    ok = (w0 > 0) & (w0 < 1)
    if not ok.any():
        return 1.0
    between = (mt * w0 - m0) ** 2 / (w0 * (1 - w0))
    return float(np.max(between[ok]) / tot)


def _type_mask(blocks, size, work, gray=None, full=None):
    """원본 좌표의 활자 상자 → 축소판 마스크. 그림인 상자는 뺀다.

    두 번째 값으로 «활자가 아니라고 판정한 상자» 를 함께 낸다. 조용히
    빼면 검출기가 무엇을 틀렸는지 알 수 없다.
    """
    W, H = size
    w, h = work
    m = np.zeros((h, w), bool)
    rejected = []
    if not (W and H):
        return m, rejected
    for b in blocks:
        x1 = int(b['x1'] * w / W) - TYPE_PAD; x2 = int(b['x2'] * w / W) + TYPE_PAD
        y1 = int(b['y1'] * h / H) - TYPE_PAD; y2 = int(b['y2'] * h / H) + TYPE_PAD
        box = (y1, y2, x1, x2)
        big = (x2 - x1) * (y2 - y1) > MIN_BLOCK * w * h
        # 원본 해상도로 본다. 300px 에서는 작은 글자가 안티에일리어싱으로
        # 중간톤이 되어, 빽빽한 본문이 통째로 «사진» 으로 넘어갔다.
        src = full if full is not None else gray
        fb = ((int(b['y1']), int(b['y2']), int(b['x1']), int(b['x2']))
              if full is not None else box)
        if src is not None and big and _bimodal(src, fb) < BIMODAL:
            rejected.append(dict(box=[b['x1'], b['y1'], b['x2'], b['y2']],
                                 몫=round((x2 - x1) * (y2 - y1) / float(w * h), 4),
                                 극단비=round(_bimodal(src, fb), 3)))
            continue
        m[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = True
    return m, rejected


EDGE_BAND = 4      # 가장자리를 이만큼 안쪽까지 «변» 으로 본다
EDGE_SHARE = 0.25  # 그 띠의 이 비율 이상을 차지해야 그 변에 닿은 것으로 센다


def _touches(m, band=EDGE_BAND, share=EDGE_SHARE):
    """네 변 중 몇 변에 닿나.

    맨 바깥 줄을 보면 안 된다. fields.segment 의 닫기 연산이 배열 바깥을
    False 로 보고 침식하므로 가장자리 한 줄이 늘 비어 있다 — 그래서 처음에
    모든 성분이 «0변» 으로 나왔고 바탕을 한 장도 못 찾았다. 안쪽 띠를 본다.
    """
    b = band
    return (int(m[b:b + b, :].mean() >= share) + int(m[-b - b:-b, :].mean() >= share)
            + int(m[:, b:b + b].mean() >= share) + int(m[:, -b - b:-b].mean() >= share))


def split(path, blocks=(), work=WORK):
    """포스터 한 장 → 네 가지 마스크와 그 몫.

    **결과에 쓰지 말 것.** 색면·사진·바탕 판정이 12장 중 대부분에서 눈으로
    틀렸다 (모듈 첫머리 참조). 손라벨로 대조하기 전까지는 그림 그리는
    용도로만 둔다. 활자몫이 필요하면 typeset() 을 쓴다.
    """
    seg = fields.segment(path, work=work)
    if not seg['classes']:
        return None
    lab = _labels(seg)
    h, w = lab.shape
    im = Image.open(path).convert('RGB')
    small = im.copy(); small.thumbnail((work, work))
    small = small.resize((w, h))

    gray = np.asarray(small.convert('L'), np.float32) / 255.0
    div = _diversity(lab)
    tex = _texture(small)
    full = np.asarray(im.convert('L'), np.float32) / 255.0
    typ, rejected = _type_mask(blocks, seg['orig_size'], (w, h), gray, full)

    rest = ~typ
    # ── 평평한 덩어리를 «먼저» 모은다 ──────────────────────────
    # 사진을 먼저 찾으면 다양도가 색면 가장자리에서도 터져 색면을 삼킨다 —
    # 첫 판에서 Opernhaus 의 분홍 패널이 통째로 사진이 됐다. 평면 판정이
    # 훨씬 정밀하다: 한 계급 · 속이 평평 · 속에 계급이 하나.
    #
    # 활자를 빼기 «전» 의 계급 마스크로 본다. 활자 띠가 바탕을 조각내면
    # 바탕이 통째로 색면으로 넘어간다 (Musica Viva 1960, 종이 33%).
    flats = []
    for c in seg['classes']:
        cl, n = ndimage.label(c['mask'])
        for i in range(1, n + 1):
            m = cl == i
            a = int(m.sum())
            if a < MIN_REGION * lab.size:
                continue
            ys, xs = np.where(m)
            bb = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
            inner = ndimage.binary_erosion(m, np.ones((5, 5)))
            if not inner.any():
                continue
            if (a / bb >= SOLID and float(tex[inner].mean()) < TEX_LO
                    and float(div[inner].mean()) < DIV_IN):
                flats.append([bb / float(lab.size), a, m])

    # ── 바탕 ── 외접상자가 판을 가장 넓게 두르는 평면
    ground = np.zeros(rest.shape, bool)
    cand = [f for f in flats if f[0] >= GROUND_BBOX]
    if cand:
        g = max(cand, key=lambda f: f[1])
        ground = g[2]
        flats = [f for f in flats if f is not g]
    field = np.zeros_like(rest)
    for _bb, _a, m in flats:
        field |= m
    field &= rest & ~ground
    ground = ground & rest

    # ── 사진 ── 남은 곳 중 계급이 잘게 섞이는 데
    left = rest & ~field & ~ground
    edge = left & ((div >= DIV_HI) | (tex >= TEX_HI))
    edge = ndimage.binary_opening(edge, np.ones((3, 3)))
    photo = ndimage.binary_closing(edge, np.ones((FILL, FILL)))
    photo = ndimage.binary_fill_holes(photo) & left
    photo = _drop_small(photo, MIN_REGION * lab.size)
    ground = ground | (left & ~photo)          # 이름 못 붙인 나머지는 바탕으로

    tot = float(lab.size)
    return dict(size=(w, h), orig_size=seg['orig_size'], 활자아님=rejected,
                masks=dict(활자=typ, 색면=field, 사진=photo, 바탕=ground),
                몫={k: round(float(v.sum()) / tot, 4) for k, v in
                    dict(활자=typ, 색면=field, 사진=photo, 바탕=ground).items()})


def _drop_small(m, min_px):
    lab, n = ndimage.label(m)
    if not n:
        return m
    ar = ndimage.sum(m, lab, range(1, n + 1))
    bad = np.where(ar < min_px)[0] + 1
    return m & ~np.isin(lab, bad)


COLORS = {'활자': (220, 40, 40), '색면': (40, 90, 220),
          '사진': (30, 170, 80), '바탕': (225, 225, 225)}


def render(path, blocks=(), work=WORK, alpha=0.55):
    """나눈 결과를 색으로 덮어 눈으로 확인한다."""
    s = split(path, blocks, work)
    if not s:
        return None
    w, h = s['size']
    im = Image.open(path).convert('RGB'); im.thumbnail((work, work))
    im = im.resize((w, h))
    a = np.asarray(im).astype(float)
    ov = a.copy()
    for k, m in s['masks'].items():
        ov[m] = np.array(COLORS[k], float)
    out = (a * (1 - alpha) + ov * alpha).astype(np.uint8)
    return Image.fromarray(out), s


def paths(root):
    """캐시 열쇠 → 실제 경로.

    열쇠는 대개 «폴더__파일» 인데, 나중에 다른 판형으로 더 넣은 것들은
    «..__폴더__파일» 처럼 상대경로가 그대로 남아 있다 (로제 9장). 그래서
    파일 이름만으로도 찾을 수 있게 둔다 — 이름이 겹치면 첫 것을 쓴다.
    """
    import glob
    out = {}
    for f in glob.glob(os.path.join(os.path.expanduser(root), '**', '*.*'),
                       recursive=True):
        if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        out[os.path.basename(os.path.dirname(f)) + '__' + os.path.basename(f)] = f
        out.setdefault(os.path.basename(f), f)
    return out


def resolve(raw, root):
    """캐시 열쇠 목록 → {열쇠: 경로}. 못 찾은 것은 빠진다."""
    P = paths(root)
    out = {}
    for k in raw:
        # 열쇠에는 «/» 가 없다. 폴더 구분자가 «__» 이므로 마지막 것 뒤가 파일
        # 이름이다 — os.path.basename 은 열쇠를 통째로 돌려준다.
        p = P.get(k) or P.get(k.rsplit('__', 1)[-1])
        if p:
            out[k] = p
    return out


ROOTS = {'brockmann': '~/Documents/연구2/브로크만 정리',
         'corpus': '~/Documents/연구2/호프만정리',
         'rose': '~/Documents/연구2/로제정리',
         'ruder': '~/Documents/연구2/루더정리'}


# ── 관계 ─────────────────────────────────────────────────────
# 몫은 색 지표가 이미 알고 있었다 (바탕↔최빈색 +0.50, 사진↔색수 +0.43).
# 나눔의 값어치는 나누기 «전에는 물을 수 없던 것» 에 있다.
#
# 「엄격한 격자」는 활자끼리의 얘기가 아니다. **색면 끝과 글줄 끝이 같은
# 선에 서느냐** 가 브로크만 Opernhaus 시리즈가 하는 일이고, 우리는 그것을
# 한 번도 못 물어봤다. 활자만 있을 때는 물을 수가 없었다.
REL_TOL = 0.012    # 판 너비/높이의 이 비율 안이면 같은 선에 선 것으로 본다
REL_NULL = 40      # 활자 상자를 흩뿌려 보는 횟수. 우연히 맞는 몫을 뺀다


def _edges(mask, min_px):
    """덩어리마다 외접상자의 네 모서리. (세로선들, 가로선들)"""
    lab, n = ndimage.label(mask)
    V, Hh = [], []
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < min_px:
            continue
        ys, xs = np.where(m)
        V += [xs.min(), xs.max()]
        Hh += [ys.min(), ys.max()]
    return V, Hh


def _hit(vals, lines, tol):
    """vals 중 lines 의 어느 선과 tol 안에 있는 것의 몫."""
    if not len(vals) or not len(lines):
        return None
    L = np.asarray(lines, float)
    return float(np.mean([np.min(np.abs(L - v)) <= tol for v in vals]))


def relations(path, blocks=(), work=WORK, seed=20260830):
    """활자와 «활자 아닌 것» 사이의 관계. split 을 한 번 더 부르지 않는다."""
    s = split(path, blocks, work)
    if not s:
        return None
    w, h = s['size']
    W, H = s['orig_size']
    M = s['masks']
    mn = MIN_REGION * w * h
    fv, fh = _edges(M['색면'], mn)
    pv, ph = _edges(M['사진'], mn)
    V, Hh = fv + pv, fh + ph                      # 색면·사진의 모서리 전부
    tol_x, tol_y = w * REL_TOL, h * REL_TOL

    bs = [(b['x1'] * w / W, b['y1'] * h / H, b['x2'] * w / W, b['y2'] * h / H)
          for b in blocks if b['x2'] > b['x1'] and b['y2'] > b['y1']]
    out = {}
    if not bs:
        return dict(관계=None, 사진위=None)

    def share(boxes):
        xs = [c for b in boxes for c in (b[0], b[2])]
        ys = [c for b in boxes for c in (b[1], b[3])]
        return _hit(xs, V, tol_x), _hit(ys, Hh, tol_y)

    gx, gy = share(bs)
    # 귀무 — 상자 크기는 그대로 두고 자리만 흩는다 (discrim 과 같은 모형)
    rnd = np.random.RandomState(seed)
    nx, ny = [], []
    for _ in range(REL_NULL):
        rb = []
        for x1, y1, x2, y2 in bs:
            bw, bh = x2 - x1, y2 - y1
            x = rnd.uniform(0, max(1e-6, w - bw)); y = rnd.uniform(0, max(1e-6, h - bh))
            rb.append((x, y, x + bw, y + bh))
        a, b = share(rb)
        if a is not None:
            nx.append(a)
        if b is not None:
            ny.append(b)

    out['면맞음x'] = gx
    out['면맞음y'] = gy
    # «여유» — 우연히 맞는 몫을 뺀 것. 이것이 지표다.
    out['면여유x'] = (gx - float(np.mean(nx))) if (gx is not None and nx) else None
    out['면여유y'] = (gy - float(np.mean(ny))) if (gy is not None and ny) else None

    # 활자가 무엇 «위» 에 앉았나 — 상자 둘레를 본다.
    # 마스크끼리 겹쳐 보면 안 된다. 활자를 빼고 나머지를 나눴으므로 활자와
    # 사진은 정의상 겹치지 않는다 — 처음에 사진위가 전부 0 에 붙었다.
    ring = max(2, int(0.02 * min(w, h)))
    tot = 0.0
    on = {'사진': 0.0, '색면': 0.0, '바탕': 0.0}
    for x1, y1, x2, y2 in bs:
        a = (x2 - x1) * (y2 - y1)
        X1, Y1 = int(max(0, x1 - ring)), int(max(0, y1 - ring))
        X2, Y2 = int(min(w, x2 + ring)), int(min(h, y2 + ring))
        box = np.zeros((h, w), bool)
        box[int(y1):int(y2), int(x1):int(x2)] = True
        out_ = np.zeros((h, w), bool)
        out_[Y1:Y2, X1:X2] = True
        r = out_ & ~box
        n = float(r.sum())
        if n <= 0:
            continue
        tot += a
        best = max(on, key=lambda k: (M[k] & r).sum())
        if (M[best] & r).sum() / n >= 0.4:
            on[best] += a
    if tot > 0:
        for k, v in on.items():
            out[k + '위'] = float(v / tot)
    return out


# ── 활자몫 ───────────────────────────────────────────────────

def typeset(path, blocks):
    """판 한 장 → 활자가 «획으로» 덮은 몫.

    세 갈래로 낸다. 거르개(blockgate.높이CV)가 못 정하는 상자가 있고,
    그것을 조용히 한쪽에 넣으면 안 된다.

        확실   거르개가 «글자» 라고 한 상자의 획
        미정   거르개가 못 정한 상자의 획 (성분 셋 미만)
        버림   거르개가 «아님» 이라고 한 상자

    활자몫은 하나가 아니라 [확실, 확실+미정] 사이 어디다. 두 수가 크게
    벌어지면 그 판은 아직 못 잰 것이다.
    """
    import blockgate
    im = Image.open(path).convert('RGB')
    rgb = np.asarray(im); H, W = rgb.shape[:2]
    g = np.asarray(im.convert('L'), np.float32)
    sure, undec, drop = [], [], []
    for b in blocks:
        box = (b['x1'], b['y1'], b['x2'], b['y2'])
        v = blockgate.height_cv(g, box)
        (drop if (v is not None and v > blockgate.HCV)
         else (sure if v is not None else undec)).append(b)
    def cover(bs):
        m = np.zeros((H, W), bool)
        for b in bs:
            s, (x1, y1, x2, y2) = ink.strokes(rgb, (b['x1'], b['y1'], b['x2'], b['y2']))
            if s is not None:
                m[y1:y2, x1:x2] |= s
        return m
    ms, mu = cover(sure), cover(undec)
    lo = float(ms.mean()); hi = float((ms | mu).mean())
    return dict(활자몫=round(lo, 4), 활자몫상한=round(hi, 4),
                미정폭=round(hi - lo, 4),
                상자=dict(확실=len(sure), 미정=len(undec), 버림=len(drop)),
                마스크=ms | mu)
