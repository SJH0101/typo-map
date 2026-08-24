"""짚기 도우미 — 대충 준 상자 안의 «잉크 띠» 를 훑어 보여준다.

짚는 일이 눈대중이라 자꾸 틀린다. 실제로 부딪힌 것 둘.

    판 테두리   흰 판 안의 활자를 짚었는데 회색 바탕과의 경계가 상자에
                들어오면, 그 경계가 판 전체 폭의 «글줄» 로 잡힌다.
    이웃 디센더  위 블록의 g·j 꼬리가 아래 상자에 걸치면 폭이 좁은 조각이
                한 줄로 선다.

둘 다 눈으로는 잘 안 보이고 n_lines 가 하나 늘어난 뒤에야 알게 된다.
그래서 재기 전에 띠를 먼저 보여준다 — 어느 y 에서 어느 x 까지 잉크가
있는지 보면 어디를 잘라야 하는지 바로 안다.

**상자를 제안하지는 않는다.** 한 번 지어봤다가 지웠다 — 띠를 묶어 블록을
내려면 바탕이 바뀌는 자리를 알아야 하고, 그것을 행 밝기로 찾으려니 큰
활자가 지나가는 행이 바탕 경계로 잡혔다. 결국 baseline/detect.py 를 다시
짓고 있었고, 그것이 실패한다는 것이 이 경로가 있는 이유다.
짚는 일은 보는 쪽이 한다. 이 파일은 어디를 자를지 «보여주기만» 한다.

    from measure.probe import bands
    bands('poster.jpg', (0.05, 0.34, 0.92, 0.40))
"""
import numpy as np
from PIL import Image

from measure import ink
from measure.region import PAD


def bands(path, box, coords='norm', min_h=2):
    """상자 안의 잉크 띠 목록. 판 전체 폭을 덮는 띠는 테두리로 의심한다."""
    img = Image.open(path)
    W, H = img.size
    g = np.asarray(img.convert('L')).astype(float)
    x1, y1, x2, y2 = box
    if coords == 'norm':
        x1, x2, y1, y2 = x1 * W, x2 * W, y1 * H, y2 * H
    x1 = max(0, int(min(x1, x2)) - PAD); x2 = min(W, int(max(x1, x2)) + PAD)
    y1 = max(0, int(min(y1, y2)) - PAD); y2 = min(H, int(max(y1, y2)) + PAD)

    sub = g[y1:y2, x1:x2]
    gp = ink.polarity(sub)
    th = ink.threshold(gp)
    m = gp < th
    rows = m.sum(axis=1).astype(float)
    peak = np.percentile(rows[rows > 0], 90) if (rows > 0).any() else 0.0
    on = rows > max(np.percentile(rows, 5), ink.INK_FRAC * peak)

    out, s = [], None
    for i, v in enumerate(on):
        if v and s is None: s = i
        if (not v) and s is not None:
            if i - s >= min_h: out.append((s, i))
            s = None
    if s is not None and len(on) - s >= min_h: out.append((s, len(on)))

    span = x2 - x1
    res = []
    for a, b in out:
        cols = np.where(m[a:b].sum(axis=0) > 0)[0]
        w = cols[-1] - cols[0] + 1
        cov = len(cols) / w
        res.append(dict(y1=a + y1, y2=b + y1, h=b - a,
                        x1=int(cols[0] + x1), x2=int(cols[-1] + x1), w=int(w),
                        fill=round(float(cov), 2),
                        of_box=round(float(w / span), 2)))
    return dict(window=[x1, y1, x2, y2], size=[W, H], bands=res)


def show(path, box, coords='norm'):
    r = bands(path, box, coords)
    x1, y1, x2, y2 = r['window']
    print(f"창 x {x1}~{x2} · y {y1}~{y2}   (원본 {r['size'][0]}x{r['size'][1]})")
    print(f"{'y':>12s} {'높이':>4s} {'x범위':>12s} {'폭':>5s} {'상자폭대비':>7s} {'칸덮음':>6s}  의심")
    for b in r['bands']:
        why = []
        if b['of_box'] >= 0.95: why.append('판 테두리?')
        if b['fill'] <= 0.35: why.append('조각/디센더?')
        if b['h'] <= 3: why.append('너무 얇음')
        print(f"{b['y1']:5d}~{b['y2']:<5d} {b['h']:4d} {b['x1']:5d}~{b['x2']:<5d} "
              f"{b['w']:5d} {b['of_box']:7.2f} {b['fill']:6.2f}  {' '.join(why)}")
    return r
