"""검출 모델로 영역과 회전각을 얻고, 회전 보정 후 잉크 프로파일로 정밀 측정한다.
좌표는 회전 좌표계에서 재고, 원본 좌표계로 되돌려 함께 저장한다."""
import numpy as np
from PIL import Image
import blocks, rotate

PAD = 6
FLAT = 1.0          # 이보다 작은 각은 회전하지 않는다
MAX_SKEW = 10.0     # 이보다 큰 각은 스캔 기울기가 아니다. 회전하지 않는다.
                    # 회전 보정의 목적은 스캔 기울기를 펴는 것이지 디자인을
                    # 따라가는 것이 아니다. 호프만 코어에서 10° 이상으로
                    # 판정된 30장 중 16장을 눈으로 확인하니 15장이 똑바로
                    # 서 있었다. 전부 큰 사진·추상 도형·대각선 색면이 화면을
                    # 지배하는 포스터로, 뾰족함 탐색이 활자가 아니라 그
                    # 그래픽의 모서리 방향을 잡는다. 진짜로 기울어진 조판은
                    # 1장뿐이었고, 그런 포스터는 베이스라인 격자 자체가
                    # 없으므로 측정 대상에서 빠지는 편이 맞다.


def _boxes(img, reader):
    res = reader.readtext(np.array(img.convert('RGB')), detail=1, paragraph=False)
    return [(np.array(b, dtype=float), t, c) for b, t, c in res]


def _region(quads, W, H):
    if not quads: return None
    x1 = max(0, min(q[:, 0].min() for q in quads) - PAD)
    y1 = max(0, min(q[:, 1].min() for q in quads) - PAD)
    x2 = min(W, max(q[:, 0].max() for q in quads) + PAD)
    y2 = min(H, max(q[:, 1].max() for q in quads) + PAD)
    return int(x1), int(y1), int(x2), int(y2)


def estimate_angle(gray, quads, reader, top=8):
    """폭이 큰 상자 위주로 대략각을 구하고, 애매하면 글자 재인식으로 가린다."""
    q = sorted(quads, key=lambda b: -np.hypot(*(b[1] - b[0])))[:top]
    q = [b for b in q if np.hypot(*(b[1] - b[0])) >= rotate.MIN_W]
    if not q: return 0.0, 0.0
    raw = []
    for b in q:
        a = rotate.coarse_angle(rotate.crop(gray, b))
        if a is not None: raw.append(a)
    if not raw: return 0.0, 0.0
    A = np.array(raw)
    med = float(np.median(A))
    A = np.where(A - med > 45, A - 90, np.where(med - A > 45, A + 90, A))
    med = float(np.median(A))
    if abs(med) < FLAT: return 0.0, float(A.std())
    # 90도 모호성: 후보 두 개를 글자 인식으로 가린다
    best, score = med, -1.0
    for cand in (med, med + 90, med - 90):
        s = 0.0
        for b in q[:2]:
            r = reader.readtext(np.array(rotate.rotate(rotate.crop(gray, b), cand).convert('RGB')),
                                detail=1, paragraph=False)
            if r: s += max(x[2] * len(x[1]) for x in r)
        if s > score: best, score = cand, s
    if abs(best) > MAX_SKEW:   # 디자인 대각선으로 본다
        return 0.0, float(A.std())
    return float(best), float(A.std())


def back(x, y, ang, ow, oh, nw, nh):
    """회전 이미지 좌표 → 원본 좌표"""
    a = np.radians(ang)
    dx, dy = x - nw / 2.0, y - nh / 2.0
    return (np.cos(a) * dx - np.sin(a) * dy + ow / 2.0,
            np.sin(a) * dx + np.cos(a) * dy + oh / 2.0)


def measure(path, reader):
    img = Image.open(path).convert('RGB')
    ow, oh = img.size
    gray = np.asarray(img.convert('L')).astype(float)
    quads = [q for q, t, c in _boxes(img, reader)]
    if not quads: return dict(ok=False, why='모델이 글자를 못 찾음')

    ang, spread = estimate_angle(gray, quads, reader)
    if abs(ang) >= FLAT:
        fill = int(min(255, np.percentile(np.asarray(img.convert('L')), 95) + 30))
        rimg = img.rotate(ang, resample=Image.BICUBIC, expand=True,
                          fillcolor=(fill, fill, fill))
        rquads = [q for q, t, c in _boxes(rimg, reader)]
        if not rquads: return dict(ok=False, why='회전 후 글자를 못 찾음')
        work, wq = rimg, rquads
    else:
        work, wq = img, quads
    nw, nh = work.size
    region = _region(wq, nw, nh)
    if region is None: return dict(ok=False, why='영역 없음')

    tmp = '/tmp/_work.png'
    work.save(tmp)
    th, res = blocks.run(tmp, region)

    for b in res:
        # 블록 박스는 회전 좌표계의 수평 사각형이므로, 원본으로 되돌리면
        # 기울어진 사각형이 된다. 코너 4점(좌상·우상·우하·좌하)으로 낸다.
        b['corners'] = [back(x, y, ang, ow, oh, nw, nh) for x, y in
                        ((b['x1'], b['y1']), (b['x2'], b['y1']),
                         (b['x2'], b['y2']), (b['x1'], b['y2']))]
        for l in b['lines']:
            l['p_start'] = back(l['xs'], l['base'], ang, ow, oh, nw, nh)
            l['p_end'] = back(l['xe'], l['base'], ang, ow, oh, nw, nh)
            for k, xk in (('cap', 'cap'), ('x_top', 'x_top'),
                          ('desc', 'desc'), ('mark_top', 'mark_top')):
                v = l.get(xk)
                if v is not None:
                    l['p_' + k] = (back(l['xs'], v, ang, ow, oh, nw, nh),
                                   back(l['xe'], v, ang, ow, oh, nw, nh))
    return dict(ok=True, angle=round(ang, 2), angle_spread=round(spread, 2),
                region=region, n_model_boxes=len(wq), threshold=round(th, 1),
                blocks=res, n_lines=sum(b['n'] for b in res),
                orig_size=(ow, oh), work_size=(nw, nh))
