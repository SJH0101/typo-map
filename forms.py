"""포스터를 색으로 나눠 형태 후보를 찾는다.

파트 2 의 첫 조각이다. easyocr 와 무관한 신호라야 순환하지 않는다 —
「글자가 아닌 것」 을 「글자 검출이 실패한 곳」 으로 정의하면, 검출이 실패하는
경우를 고치는 데 쓸 수 없다. 색은 그 고리를 끊는다.

스위스 포스터는 평면 원색을 겹쳐 짠 것이 많아 색 분할이 잘 듣는다.
1986 Bach-Chor 의 붉은 「B」 는 한 색 계급의 단일 성분으로 100% 떨어지고,
1953 Stadt Casino 의 주황 삼각형, 1958 Musica viva 의 검은 원도 갈린다.
연속 계조 사진(1975 BAU)은 여러 계급에 흩어지지만, 닫기 연산 뒤에는
덩어리 몇 개로 뭉친다.

아직 하지 않는 것: 어느 계급이 글자이고 어느 계급이 그림인지 판정.
성분 통계만으로는 「큰 글자」 와 「그림」 이 갈리지 않는다는 것을 코어
28장에서 확인했다 (상위3 비중으로 가르면 글자의 42% 를 잘못 잡는다).
분리까지가 이 모듈의 일이고, 판정은 근거를 더 모은 뒤에 붙인다.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

N_COLORS = 10       # 팔레트 크기. 넉넉히 뽑고 가까운 것끼리 합친다
MERGE_DIST = 26     # 이보다 가까운 색은 같은 색으로 본다 (RGB 유클리드)
MIN_SHARE = 0.002   # 판면의 이 비율 미만인 색 계급은 보지 않는다
CLOSE = 3           # 닫기 커널. 스캔 텍스처가 낸 구멍을 메운다
MIN_AREA = 0.0004   # 판면의 이 비율 미만인 성분은 부스러기로 버린다


def segment(path_or_image, n_colors=N_COLORS, work=300):
    """색 계급마다 마스크와 성분 통계를 낸다.

    work 로 줄여서 본다. 형태는 큰 구조라 해상도가 필요 없고, 줄이면
    스캔 얼룩이 함께 줄어든다.
    """
    im = (Image.open(path_or_image) if isinstance(path_or_image, str)
          else path_or_image).convert('RGB')
    small = im.copy()
    small.thumbnail((work, work))
    q = small.quantize(colors=n_colors, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = np.array(q.getpalette()[:n_colors * 3]).reshape(-1, 3)
    idx = np.asarray(q)

    # 양자화가 스캔 그라데이션 때문에 한 색을 여러 계급으로 쪼갠다. 먼저 합친다 —
    # 안 합치면 Stadt Casino 의 보라 배경이 네 계급으로 갈려 형태가 흩어진다.
    groups, seen = [], set()
    for a in range(n_colors):
        if a in seen:
            continue
        g = [a]; seen.add(a)
        for b in range(a + 1, n_colors):
            if b in seen:
                continue
            if np.linalg.norm(pal[a].astype(float) - pal[b].astype(float)) < MERGE_DIST:
                g.append(b); seen.add(b)
        groups.append(g)

    out = []
    for g in groups:
        m = np.isin(idx, g)
        if m.mean() < MIN_SHARE:
            continue
        c = g[0]
        m = ndimage.binary_closing(m, np.ones((CLOSE, CLOSE)))
        lab, n = ndimage.label(m)
        if n == 0:
            continue
        objs = ndimage.find_objects(lab)
        area = np.array([(lab[o] == i + 1).sum() for i, o in enumerate(objs)], float)
        keep = area >= max(12, MIN_AREA * m.size)
        if not keep.any():
            continue
        m = m & ~np.isin(lab, np.where(~keep)[0] + 1)
        area = area[keep]
        boxes = np.array([(o[0].stop - o[0].start) * (o[1].stop - o[1].start)
                          for o, k in zip(objs, keep) if k], float)
        order = np.argsort(-area)
        out.append(dict(
            color=tuple(int(v) for v in pal[c]),
            share=round(float(m.mean()), 4),
            n_comp=int(keep.sum()),
            top1=round(float(area[order][0] / area.sum()), 3),
            top3=round(float(area[order][:3].sum() / area.sum()), 3),
            solidity=round(float(np.median(area / np.maximum(boxes, 1))), 3),
            mask=m))
    out.sort(key=lambda d: -d['share'])
    return dict(size=small.size, orig_size=im.size, classes=out)


def render(path_or_image, seg=None, scale=3):
    """분할 결과를 색으로 칠해 돌려준다. 눈으로 확인하는 용도."""
    seg = seg or segment(path_or_image)
    w, h = seg['size']
    a = np.full((h, w, 3), 250, np.uint8)
    for cl in seg['classes']:
        a[cl['mask']] = cl['color']
    im = Image.fromarray(a)
    return im.resize((w * scale, h * scale), Image.NEAREST)
