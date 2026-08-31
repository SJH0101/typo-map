"""활자를 뺀 나머지 — «그림» 의 형상을 잰다.

지금까지는 판을 활자·색면·사진·바탕 넷으로 «나누고» 몫을 셌다. 그 나눔이
오늘 하루 가장 많이 틀린 자리다 — 붓자국이 사진이 되고, Surya 가 못 읽은
큰 손글씨가 색면이 되고, 평면 색이 사진으로 새어 나갔다. 그리고 나눔이
맞아도 남는 것은 «얼마나» 뿐이었다. Das Plakat 의 붓자국과 손 사진이 둘 다
「사진 0.5」였다. 완전히 다른 물건인데.

그래서 나누기를 그만둔다.

    ① 활자를 뺀다        Surya 가 준 상자
    ② 남은 것이 «그림»    사진이든 색면이든 붓자국이든 가리지 않는다
    ③ 그 «형상» 을 잰다

**«색면이냐 사진이냐» 가 입력이 아니라 결과가 된다.** 사각 사진과 평면
색면은 모양이 같고 속 결이 다르다. 붓자국은 모양부터 다르다. 재고 나면
저절로 갈린다.

실패 지점이 셋에서 하나로 준다 — 활자 빼기가 정확해야 한다는 것 하나다.
그것은 이미 재고 있고(재현율) 고칠 방법도 안다.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

import color.fields as fields

WORK = 300
PAD = 1              # 활자 상자를 이만큼 넓혀 덮는다 (획 가장자리)
MIN_PART = 0.004     # 판면의 이 비율 미만인 덩어리는 부스러기
NEAR = 0.02          # 판 가장자리에서 이 비율 안이면 «가장자리에 닿았다»
WIN = 9              # 속 결을 보는 창

NAMES = ['그림몫', '채움도', '주축각', '길쭉함', '가장자리', '덩어리수',
         '그림x', '그림y', '가로지름', '속결', '속색수']


def _type_mask(blocks, size, work):
    W, H = size
    w, h = work
    m = np.zeros((h, w), bool)
    if not (W and H):
        return m
    for b in blocks:
        x1 = int(b['x1'] * w / W) - PAD; x2 = int(b['x2'] * w / W) + PAD
        y1 = int(b['y1'] * h / H) - PAD; y2 = int(b['y2'] * h / H) + PAD
        m[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = True
    return m


def _hull_area(m):
    """볼록껍질 넓이. 채움도의 분모다."""
    ys, xs = np.where(m)
    if len(xs) < 3:
        return float(m.sum())
    pts = np.stack([xs, ys], 1).astype(float)
    try:
        from scipy.spatial import ConvexHull
        return float(ConvexHull(pts).volume)      # 2차원에서 volume 이 넓이다
    except Exception:
        return float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))


def _axis(m):
    """관성모멘트의 주축. (각도°, 길쭉함)"""
    ys, xs = np.where(m)
    if len(xs) < 8:
        return None, None
    x = xs - xs.mean(); y = ys - ys.mean()
    C = np.cov(np.stack([x, y]))
    w, v = np.linalg.eigh(C)
    if w[1] <= 0:
        return None, None
    a = float(np.degrees(np.arctan2(v[1, 1], v[0, 1])))
    a = a - 180 if a > 90 else (a + 180 if a < -90 else a)
    el = float(np.sqrt(max(w[1], 1e-9) / max(w[0], 1e-9)))
    return round(a, 1), round(el, 3)


def measure(path, blocks=(), work=WORK):
    """포스터 한 장 → 그림의 형상."""
    seg = fields.segment(path, work=work)
    if not seg['classes']:
        return None
    h, w = seg['classes'][0]['mask'].shape
    im = Image.open(path).convert('RGB')
    small = im.copy(); small.thumbnail((work, work)); small = small.resize((w, h))
    g = np.asarray(small.convert('L'), np.float32) / 255.0

    typ = _type_mask(blocks, seg['orig_size'], (w, h))

    # ── 바탕을 뺀다 ── 가장 넓은 «그 판에서 평평한 편인» 계급이 바탕이다.
    # 바탕까지 그림으로 세면 모든 판이 「그림 90%」가 된다.
    #
    # 절대 문턱(0.035)을 쓰면 안 된다. Das Plakat 의 검은 바탕은 스캔 결이
    # 0.0439 라 「거침」으로 판정돼 바탕을 하나도 못 찾았고 그림몫이 0.96 이
    # 됐다. 스캔 상태는 판마다 다르다. **그 판 자신의 결과 견준다.**
    m0 = ndimage.uniform_filter(g, WIN)
    tex = np.sqrt(np.maximum(ndimage.uniform_filter(g * g, WIN) - m0 * m0, 0))
    flat_thr = float(np.median(tex))          # 이 판에서 «평평한 편» 의 기준
    ground = np.zeros((h, w), bool); best = 0
    for c in seg['classes']:
        cl, n = ndimage.label(c['mask'])
        for i in range(1, n + 1):
            mm = cl == i
            a = int(mm.sum())
            if a <= best or a < MIN_PART * mm.size:
                continue
            inner = ndimage.binary_erosion(mm, np.ones((5, 5)))
            if inner.any() and float(tex[inner].mean()) <= flat_thr:
                ground, best = mm, a

    pic = ~typ & ~ground
    pic = ndimage.binary_opening(pic, np.ones((3, 3)))
    lab, n = ndimage.label(pic)
    if not n:
        return dict(그림몫=0.0, 덩어리수=0)
    sizes = ndimage.sum(pic, lab, range(1, n + 1))
    keep = np.where(sizes >= MIN_PART * pic.size)[0] + 1
    if not len(keep):
        return dict(그림몫=0.0, 덩어리수=0)
    pic = np.isin(lab, keep)
    tot = float(pic.size)

    big = lab == keep[int(np.argmax(sizes[keep - 1]))]      # 가장 큰 덩어리
    ang, el = _axis(big)
    per = float(np.sum(ndimage.binary_dilation(big, np.ones((3, 3))) & ~big))
    ab = float(big.sum())
    inner = ndimage.binary_erosion(big, np.ones((5, 5)))

    # 속에 색이 몇 계급이나 드나 — 평면 색면이면 하나, 사진이면 여럿
    ncls = 0
    for c in seg['classes']:
        if inner.any() and (c['mask'] & inner).mean() > 0.02 * inner.mean():
            ncls += 1

    ys, xs = np.where(big)
    return dict(
        그림몫=round(float(pic.sum()) / tot, 4),
        채움도=round(ab / max(_hull_area(big), 1), 3),
        주축각=ang,
        길쭉함=el,
        가장자리=round(per * per / max(ab, 1), 2),
        덩어리수=int(len(keep)),
        그림x=round(float(xs.mean()) / w, 3),
        그림y=round(float(ys.mean()) / h, 3),
        가로지름=round(float((xs.max() - xs.min() + 1) / w), 3),
        속결=(round(float(tex[inner].mean()), 4) if inner.any() else None),
        속색수=ncls)


# ── 스케치인가 덩어리인가 ────────────────────────────────────────
# 형상 지표 11개 중 8개가 네 작가에게 같게 나왔다 — 덩어리 하나가 판을
# 가로지르고 가운데 있다. 그림을 통째로 한 덩어리로 보면 그럴 수밖에 없다.
#
# 그림 안에는 성질이 다른 두 가지가 섞여 있다.
#
#     선   붓자국·윤곽·가는 획      제 크기에 비해 «얇다»
#     면   색면·실루엣·사진        제 크기에 비해 «두껍다»
#
# 처음에는 열기 연산으로 갈랐다 — 반지름 r 로 열어 살아남으면 면, 지워지면
# 선. 안 됐다. 반지름이 고정이라 Das Plakat 의 «굵은» 붓자국이 통째로 면으로
# 살아남았고 선 비율이 어느 판에서나 0.01 언저리였다.
#
# 두께를 절대값이 아니라 **제 크기 대비**로 봐야 한다. 거리변환의 중앙값을
# √넓이로 나눈다. 꽉 찬 원판이면 0.5 근처, 가는 리본이면 0 에 가깝다.
#
#     붓자국 0.108 · 렌즈꼴 0.199 · 만화 0.237 · 삽화 0.293 · 사진 0.42~0.60
#
# 한 수로 스케치에서 사진까지 줄이 선다. 열기 방식이 못 하던 일이다.
MIN_INK = 0.002      # 그림 안에서 이 비율 미만의 잉크는 세지 않는다


def _pic(path, blocks, work=WORK):
    """활자와 바탕을 뺀 «그림» 마스크. measure() 와 같은 얼개를 나눠 쓴다."""
    seg = fields.segment(path, work=work)
    if not seg['classes']:
        return None
    h, w = seg['classes'][0]['mask'].shape
    im = Image.open(path).convert('RGB')
    small = im.copy(); small.thumbnail((work, work)); small = small.resize((w, h))
    g = np.asarray(small.convert('L'), np.float32) / 255.0
    typ = _type_mask(blocks, seg['orig_size'], (w, h))
    m0 = ndimage.uniform_filter(g, WIN)
    tex = np.sqrt(np.maximum(ndimage.uniform_filter(g * g, WIN) - m0 * m0, 0))
    flat = float(np.median(tex))
    ground = np.zeros((h, w), bool); best = 0
    for c in seg['classes']:
        cl, n = ndimage.label(c['mask'])
        for i in range(1, n + 1):
            mm = cl == i
            a = int(mm.sum())
            if a <= best or a < MIN_PART * mm.size:
                continue
            inner = ndimage.binary_erosion(mm, np.ones((5, 5)))
            if inner.any() and float(tex[inner].mean()) <= flat:
                ground, best = mm, a
    pic = ndimage.binary_opening(~typ & ~ground, np.ones((3, 3)))
    return pic, tex, seg, (w, h)


def sketch(path, blocks=(), work=WORK):
    """그림이 «스케치» 쪽인가 «덩어리» 쪽인가."""
    got = _pic(path, blocks, work)
    if not got:
        return None
    pic, tex, seg, (w, h) = got
    if pic.sum() < MIN_INK * pic.size:
        return dict(두께비=None, 조각두께=None, n조각=0)
    lab, n = ndimage.label(pic)
    sz = ndimage.sum(pic, lab, range(1, n + 1))
    keep = np.where(sz >= MIN_PART * pic.size)[0] + 1
    if not len(keep):
        return dict(두께비=None, 조각두께=None, n조각=0)

    def thick(m):
        d = ndimage.distance_transform_edt(m)
        return float(np.median(d[m])) * 2 / max(np.sqrt(m.sum()), 1e-9)

    big = lab == keep[int(np.argmax(sz[keep - 1]))]
    ts = [thick(lab == k) for k in keep]
    wts = np.array([sz[k - 1] for k in keep], float)
    inner = ndimage.binary_erosion(big, np.ones((5, 5)))
    return dict(
        두께비=round(thick(big), 3),                       # 가장 큰 조각
        조각두께=round(float(np.average(ts, weights=wts)), 3),  # 넓이로 가중한 평균
        n조각=int(len(keep)),
        속결=(round(float(tex[inner].mean()), 4) if inner.any() else None))


SKETCH_NAMES = ['두께비', '조각두께', 'n조각', '속결']
