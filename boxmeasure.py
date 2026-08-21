"""region-scoped measurement — 상자 하나를 받아 그 안을 잰다.

어디를 잴지는 부르는 쪽이 정하고, 이 파일은 재기만 한다.
typographic metrology 의 «재는» 쪽이다. 짚는 쪽은 VLM 이 맡는다.

왜 나눴나 (judgment–measurement separation). 덩어리를 «찾는» 일과 그 안을
«재는» 일은 잘하는 쪽이 다르다. 오페라하우스 두 장을 IDML 가이드로 대조해
그 경계를 실측했다.

    덩어리 찾기   VLM 6/6 맞음         ·  blocks.run() 은 17개·12개로 쪼갬
    상자 위치     VLM 여덟 변 중 일곱이 ±1px
    행간 재기     VLM +24% 편향        ·  이 파일은 21.0px (정답 21px)
    정렬 판정     —                    ·  왼쪽 흩어짐 0.0px 대 오른쪽 39.6px

경계가 «상자를 짚는 일» 과 «상자 안을 재는 일» 사이에 있다. 짚기는 추정이
허용되고 재기는 허용되지 않는다 — 재는 값이 행간/활자높이 같은 비율이라
24% 편향이 규칙 채택을 통째로 바꾸기 때문이다.

blocks.run() 처럼 스스로 판면을 훑지 않으므로, 도형을 글자로 오인하거나
검은 바탕의 흰 글자를 놓치는 실패가 구조적으로 생기지 않는다 — 잴 자리를
이미 받았기 때문이다.

    from boxmeasure import measure
    measure(path, (x1, y1, x2, y2))   # 좌표는 원본 픽셀
"""
import numpy as np
from PIL import Image
import blocks

PAD = 3          # 상자 가장자리의 획이 잘리지 않게 조금 넓혀 잡는다
ALIGN_EPS = 3.0  # 정렬로 인정하는 흩어짐 (px). 왼쪽은 이보다 훨씬 고르다


def _align(xs, xe):
    """왼쪽·오른쪽·가운데 중 어느 축이 가장 고른가. 판단이 아니라 측정이다."""
    if len(xs) < 2:
        return None, {}
    c = [(a + b) / 2 for a, b in zip(xs, xe)]
    sp = {'left': float(np.std(xs)), 'right': float(np.std(xe)),
          'center': float(np.std(c))}
    k = min(sp, key=sp.get)
    return (k if sp[k] <= ALIGN_EPS else 'none'), {a: round(b, 2) for a, b in sp.items()}


def measure(src, box):
    """box = (x1, y1, x2, y2), 원본 픽셀 좌표. 못 재면 n_lines 0 으로 돌려준다."""
    g = (src.astype(float) if isinstance(src, np.ndarray)
         else np.asarray(Image.open(src).convert('L')).astype(float))
    H, W = g.shape
    x1, y1, x2, y2 = box
    x1 = max(0, int(x1) - PAD); y1 = max(0, int(y1) - PAD)
    x2 = min(W, int(x2) + PAD); y2 = min(H, int(y2) + PAD)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return dict(n_lines=0, why='상자가 너무 작다')

    sub = g[y1:y2, x1:x2]
    gp = blocks.polarity(sub)            # 밝은 활자/어두운 바탕을 여기서 뒤집는다
    th = blocks.threshold(gp)
    ls = blocks.lines(gp, th, 0, x2 - x1)
    if not ls:
        return dict(n_lines=0, why='줄을 찾지 못했다')

    ink = (gp < th).sum(axis=1).astype(float)
    ls, lead, resid = blocks.apply_grid(ls, ink)

    base = [int(l['base']) + y1 for l in ls]
    xs = [int(l['xs']) + x1 for l in ls]
    xe = [int(l['xe']) + x1 for l in ls]
    cap = [None if l['cap'] is None else int(l['cap']) + y1 for l in ls]
    xh = [float(l['xh']) for l in ls]
    gaps = [base[i + 1] - base[i] for i in range(len(base) - 1)]
    al, spread = _align(xs, xe)

    return dict(
        n_lines=len(ls),
        baselines=base,
        x_tops=[int(l['x_top']) + y1 for l in ls],
        caps=cap,
        x_heights=xh,
        xh_median=round(float(np.median(xh)), 1),
        lead=None if lead is None else round(float(lead), 2),
        lead_measured=None if not gaps else round(float(np.median(gaps)), 1),
        lead_over_xh=(None if not gaps or not np.median(xh)
                      else round(float(np.median(gaps) / np.median(xh)), 3)),
        grid_resid=round(float(resid), 2),
        align=al, align_spread=spread,
        x_starts=xs, x_ends=xe,
        box_ink=(min(xs), min(int(l['top']) + y1 for l in ls), max(xe), max(base)),
    )
