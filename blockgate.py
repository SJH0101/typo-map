"""검출된 상자가 «진짜 글자» 인가.

검출기는 영역 전체를 잉크 문턱으로 훑으므로 사진·색면·도형 위에서도
「줄」을 찾아낸다. 사람이 라벨한 199개 (글자 108 · 아님 64 · 애매 27) 로
재보니 **상자의 37% 가 글자가 아니었다.** 작가별로는 이렇다.

    브로크만 10%   로제 33%   호프만 52%   루더 53%

다섯 배 차이다. 상자에서 나오는 지표 — 덮음·블록수·무게중심·퍼짐·축공유 —
가 전부 이 잡음을 싣고 있었고, 작가마다 다른 양으로 싣고 있었다.
「호프만과 루더는 17개 지표 중 하나도 안 갈린다」던 것도 둘 다 절반이
잡음이면 당연하다.

무엇으로 가르나. 후보 여덟 개를 라벨에 대고 재보니 하나가 뚜렷했다.

    높이CV    0.808     성분 높이의 변동계수 (오츠 이진화 후)
    성분수     0.717
    줄        0.681
    xh        0.679
    잉크몫     0.657
    넓이몫     0.536     ← 크기로는 못 가른다
    오츠       0.531     ← 두 무리로 갈리는지로도 못 가른다

글자는 글자 높이가 고르고 그림은 제멋대로다. 당연한 것이 가장 잘 들었다.
두 특징을 섞어도 F1 이 0.857 → 0.865 밖에 안 올라 하나만 쓴다.

    5겹 교차검증 20회 (문턱은 훈련쪽에서만 정한다)
        정밀 82%  재현 87%  정확 80%
        안 거르면  정밀 63%  재현 100%

**이 문턱은 판정이지 측정이 아니다.** 사람이 라벨한 것에서 나왔고, 그
라벨은 한 사람이 달았다. 둘째 사람의 라벨이 있어야 이 82% 가 사람 사이
일치도와 견줄 수 있다.
"""
import numpy as np
from scipy import ndimage

HCV = 0.767      # 성분 높이 변동계수가 이보다 크면 글자가 아니다.
                 # 교차검증 문턱의 중앙값. 사분위는 0.660~0.767 이었다.
MIN_PX = 200     # 이보다 작은 상자는 히스토그램을 믿을 수 없다. 남긴다.
MIN_COMP = 2     # 높이 2px 미만 성분은 얼룩으로 본다


def _otsu(v):
    tot = float(v.var())
    if tot < 1e-9:
        return float(np.median(v))
    h, ed = np.histogram(v, bins=64)
    p = h / h.sum()
    mids = (ed[:-1] + ed[1:]) / 2.0
    w0 = np.cumsum(p)
    m0 = np.cumsum(p * mids)
    mt = m0[-1]
    ok = (w0 > 1e-6) & (w0 < 1 - 1e-6)
    bt = np.where(ok, (mt * w0 - m0) ** 2 / np.where(ok, w0 * (1 - w0), 1), 0)
    return float(mids[int(np.argmax(bt))])


def height_cv(gray, box):
    """상자 안 성분 높이의 변동계수. 못 재면 None."""
    x1, y1, x2, y2 = [int(v) for v in box]
    v = gray[max(0, y1):y2, max(0, x1):x2]
    if v.size < MIN_PX:
        return None
    t = _otsu(v)
    ink = v < t if v.mean() > t else v > t
    lab, n = ndimage.label(ink)
    if not n:
        return None
    hs = np.array([o[0].stop - o[0].start
                   for o in ndimage.find_objects(lab)], float)
    hs = hs[hs >= MIN_COMP]
    if len(hs) < 3:
        return None
    m = float(np.mean(hs))
    return float(np.std(hs) / m) if m > 0 else None


def is_type(gray, box, thr=HCV):
    """이 상자가 글자인가. 잴 수 없으면 True — 조용히 버리지 않는다."""
    v = height_cv(gray, box)
    return True if v is None else v <= thr


def filter_blocks(gray, blocks, thr=HCV):
    """(남길 블록, 버린 블록) 으로 가른다."""
    keep, drop = [], []
    for b in blocks:
        v = height_cv(gray, (b['x1'], b['y1'], b['x2'], b['y2']))
        (drop if (v is not None and v > thr) else keep).append(
            dict(b, height_cv=(None if v is None else round(v, 3))))
    return keep, drop
