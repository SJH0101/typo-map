"""포스터를 «자동으로» 재귀해 잰 트리로 읽는다.

멈춤 조건을 지어내지 않는다. **검출기가 대신 답한다.**

    상자 0개              멈춤 · 그림 (글자가 없다)
    상자 1개가 크롭을 채움   멈춤 · 글줄 (더 쪼갤 것이 없다)
    상자 여럿             묶어서 자식으로 만들고 한 단계 내려간다

한 줄을 잘라서 확대해도 검출기는 낱말로 쪼개지 않는다 — 실제로 재보니
정보 한 줄 1개, 제목 한 줄 1개였다. 그래서 이 규칙은 저절로 멈춘다.
「판면의 0.3% 미만」이나 「깊이 4」 같은 지어낸 수가 필요 없다.

그림은 재귀로 «찾지» 않는다. 자식들이 덮지 못하고 남은 자리가 그림이다.
빈 회색 바탕을 잘라서 검출기에 넣으면 잡음에서 상자 13개를 만들어 낸다
(대비 3.4). 그런 자리에 애초에 안 들어가는 것이 맞다.

각 마디를 재는 것은 measure/ground.py 가 한다. 짚기와 재기는 여전히 갈라져
있고, 달라진 것은 짚기가 사람 눈에서 검출기로 옮겨간 것뿐이다.
"""
import numpy as np
from PIL import Image

import detect_surya as DS
from measure import ground as G

INK_R = 0.15      # 크롭 대비가 «그 판 전체 대비» 의 이 비율에 못 미치면
                  # 검출기가 낸 상자를 안 믿는다 (잉크가 없는 자리로 본다).
                  #
                  # 두 번 틀리고 세 번째다.
                  #   INK = 15.0        절대 밝기차. 우리 포스터 다섯 곳에서
                  #                     눈대중으로 골랐다. 스캔이 바뀌면 무너진다.
                  #   INK_K × 잡음바닥   판마다 «가장 평평한 칸» 으로 바닥을 재려
                  #                     했다. 판 전체가 사진인 포스터에는 평평한
                  #                     칸이 없다 — 분위2 가 55.5 였고 그 3배가
                  #                     판 전체 대비(111.9)를 넘어 온 판이 «그림»
                  #                     이 됐다.
                  #
                  # 지금은 무차원 비율이다. 스캔 품질·종이·조명이 바뀌면 분자와
                  # 분모가 «함께» 움직이므로 값이 따라간다. 다만 0.15 라는 수
                  # 자체는 여전히 우리가 넣은 것이다 — 이것까지 없애려면 「잉크가
                  # 있나」를 대비가 아닌 다른 것으로 물어야 한다.
MIN_PX = 16       # 이보다 작은 크롭은 검출기에 넣지 않는다 (모델 입력 하한)
MAX_DEPTH = 8     # 안전장치. 규칙이 아니다 — 걸리면 «깊이제한» 으로 기록한다


class Node:
    def __init__(self, id, box, kind='묶음', why=None):
        self.id, self.box, self.kind, self.why = id, box, kind, why
        self.kids, self.m, self.n_boxes, self.덮음 = [], None, None, None

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()

    def dict(self):
        d = dict(id=self.id, 종류=self.kind, 상자=[round(v, 4) for v in self.box],
                 상자수=self.n_boxes)
        if self.덮음 is not None:
            d['덮음'] = self.덮음
        if self.why:
            d['왜'] = self.why
        if self.m:
            d['잰것'] = self.m
        if self.kids:
            d['자식'] = [k.dict() for k in self.kids]
        return d


def noise_floor(im, n=24):
    """이 판의 «잡음 바닥» — 가장 평평한 자리들의 대비.

    **지금 쓰지 않는다.** 판 전체가 사진인 포스터에는 평평한 칸이 없어서
    바닥이 내용과 구분되지 않는다 (사진 격자 판의 분위2 가 55.5). 왜 안
    되는지를 남겨 두려고 지우지 않았다.
    """
    g = np.asarray(im.convert('L'), float)
    H, W = g.shape
    s = max(8, int(min(H, W) / np.sqrt(n)))
    vs = []
    for y in range(0, H - s + 1, s):
        for x in range(0, W - s + 1, s):
            t = g[y:y + s, x:x + s]
            m = float(np.percentile(t, 50))
            lo, hi = t[t <= m], t[t > m]
            if lo.size and hi.size:
                vs.append(float(hi.mean() - lo.mean()))
    if not vs:
        return 1.0
    return max(0.5, float(np.percentile(vs, 10)))


def _contrast(c):
    """크롭 안 잉크 대비 — 오츠로 가른 두 무리의 밝기 차."""
    g = np.asarray(c.convert('L'), float)
    if g.size < 16:
        return 0.0
    t = float(np.percentile(g, 50))
    lo, hi = g[g <= t], g[g > t]
    if not lo.size or not hi.size:
        return 0.0
    return float(hi.mean() - lo.mean())


def _ink_cover(c, boxes):
    """자식 상자들이 크롭 안 잉크의 몇 %를 덮나."""
    g = np.asarray(c.convert('L'), float)
    t = float(np.percentile(g, 50))
    ink = g < t if g.mean() > t else g > t
    if not ink.any():
        return 1.0
    m = np.zeros(g.shape, bool)
    for b in boxes:
        x1, y1, x2, y2 = [int(v) for v in b]
        m[max(0, y1):y2, max(0, x1):x2] = True
    return round(float((ink & m).sum() / ink.sum()), 3)


def _leftover(c, boxes, min_share=0.05):
    """자식들이 덮지 않은 «잉크 덩어리» 들. 그림 마디가 된다.

    min_share 는 이 마디 잉크의 몇 %를 차지해야 마디로 세울지다. 작은 부스러기
    까지 마디로 만들면 트리가 지저분해진다. 문턱이지만 «셈» 이 아니라 «보고» 의
    문턱이다 — 값이 달라져도 측정이 달라지지 않고 트리에 적히는 마디 수만 는다.
    """
    g = np.asarray(c.convert('L'), float)
    t = float(np.percentile(g, 50))
    ink = g < t if g.mean() > t else g > t
    if not ink.any():
        return []
    taken = np.zeros(g.shape, bool)
    for b in boxes:
        x1, y1, x2, y2 = [int(v) for v in b]
        taken[max(0, y1):y2, max(0, x1):x2] = True
    rest = ink & ~taken
    if not rest.any():
        return []
    from scipy import ndimage as ndi
    rest = ndi.binary_closing(rest, np.ones((5, 5)))
    lab, n = ndi.label(rest)
    if not n:
        return []
    tot = float(ink.sum())
    out = []
    for i in range(1, n + 1):
        m = lab == i
        share = float((m & ink).sum() / tot)
        if share < min_share:
            continue
        ys, xs = np.where(m)
        out.append(([float(xs.min()), float(ys.min()),
                     float(xs.max() + 1), float(ys.max() + 1)], share))
    return sorted(out, key=lambda t: -t[1])[:4]


def _crop(im, box):
    W, H = im.size
    x1, y1, x2, y2 = [int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)]
    return im.crop((max(0, x1), max(0, y1), min(W, x2), min(H, y2)))


def _abs(box, sub, cw, ch):
    """크롭 안 좌표 → 판 전체의 0~1 좌표."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    a, b, c, d = sub
    return [x1 + a / cw * w, y1 + b / ch * h, x1 + c / cw * w, y1 + d / ch * h]


def build(path, det, box=(0.0, 0.0, 1.0, 1.0), id='r', depth=0, log=None, floor=None):
    log = log if log is not None else []
    im = Image.open(path).convert('RGB')
    if floor is None:
        floor = _contrast(im)          # 이 판 전체의 대비. 아래에서 잣대로 쓴다
    n = Node(id, list(box))
    c = _crop(im, box)
    if c.width < MIN_PX or c.height < MIN_PX:
        n.kind, n.why = '글줄', '크롭이 모델 입력 하한보다 작다'
        return n, log
    if depth >= MAX_DEPTH:
        n.kind, n.why = '글줄', '깊이제한'
        log.append(f'{id} 깊이제한')
        return n, log

    lines = [DS._norm([float(v) for v in b.bbox]) for b in det([c])[0].bboxes]
    n.n_boxes = len(lines)
    if not lines:
        n.kind, n.why = '그림', '검출기가 상자를 내지 않았다'
        return n, log

    ink = _contrast(c)
    if ink < INK_R * floor:
        n.kind = '그림'
        n.why = (f'대비 {ink:.1f} 이 이 판 전체 대비 {floor:.1f} 의 '
                 f'{INK_R:.0%}({INK_R * floor:.1f})에 못 미친다')
        return n, log

    # 상자가 하나면 group() 이 자식 하나를 내고 아래에서 멈춘다. 「크롭의
    # 55% 를 채우면 한 줄」 같은 별도 문턱이 필요 없었다 — 지웠다.
    kids = DS.group(lines)

    # 묶기가 «하나» 를 냈으면 더 쪼갤 것이 없다는 뜻이다. 내려가면 안 된다.
    # 루더 1955 에서 group() 이 "Louis" 와 "Weber" 를 한 덩어리로 옳게 묶었는데,
    # 그 덩어리가 부모의 73% 라 SAME(0.85) 에 안 걸려 또 내려갔다. 그 살짝
    # 다른 크롭에서 검출기가 조각 하나(39x15, "ouis")만 냈고 나머지가 사라졌다.
    # 덮는 비율로 물을 일이 아니라 «쪼개졌나» 로 물을 일이다.
    if len(kids) == 1:
        k = kids[0]
        n.kind = '글줄'
        n.why = '묶기가 하나로 냈다 — 더 쪼개지지 않는다'
        n.box = _abs(box, k[:4], c.width, c.height)
        return n, log

    # 자식이 부모와 «정확히 같으면» 내려가지 않는다. 비율로 묻지 않는다 —
    # 「부모의 85% 이상」 같은 수는 우리 코퍼스에서 역추적한 것이라 다른
    # 코퍼스에서 무너진다. 여기서 물을 것은 「쪼개졌나」뿐이고, 그것은 위에서
    # group() 이 몇 개를 냈나로 이미 답했다. 이 등호는 무한재귀 안전장치다.
    for i, k in enumerate(kids, 1):
        kb = _abs(box, k[:4], c.width, c.height)
        if [round(v, 6) for v in kb] == [round(v, 6) for v in box]:
            kn = Node(f'{id}.{i}', kb, '글줄', '자식 상자가 부모와 정확히 같다')
        else:
            kn, log = build(path, det, kb, f'{id}.{i}', depth + 1, log, floor)
        n.kids.append(kn)

    # ── 덮음 검사 ─────────────────────────────────────────────
    # 자식들이 부모의 «잉크» 를 얼마나 가져갔나. 25장에서 재보니 중앙값이
    # 0.36 이었다 — 절반 넘게 어디론가 샜다. 새는 것이 사진·색면·도형이고,
    # 그것이 트리에 자리가 없어 그림 마디가 한 개도 안 나왔다.
    #
    # 남은 잉크를 «그림» 마디로 만든다. 재귀로 찾지 않는다 — 빈 자리를 잘라
    # 검출기에 넣으면 잡음에서 상자를 지어내기 때문이다. 자식들이 덮지 못하고
    # 남은 자리가 곧 그림이다.
    n.덮음 = _ink_cover(c, [k[:4] for k in kids])
    for j, (rb, share) in enumerate(_leftover(c, [k[:4] for k in kids]), 1):
        n.kids.append(Node(f'{id}.그림{j}', _abs(box, rb, c.width, c.height),
                           '그림', f'자식들이 덮지 않은 자리 — 이 마디 잉크의 {share:.0%}'))
    return n, log


def measure(root, path):
    """글줄 마디 안을 잰다. 묶음은 자식에서 굴려 올린다."""
    leaf = [x for x in root.walk() if x.kind == '글줄']
    if leaf:
        r = G.measure_boxes(path, [x.box for x in leaf], coords='norm')
        for x, m in zip(leaf, r['boxes']):
            x.m = dict(줄=m.get('n_lines'), xh=m.get('xh_median'),
                       행간=m.get('lead_measured'))
    for x in sorted(root.walk(), key=lambda z: -len(z.id)):
        if x.kids:
            ms = [k.m for k in x.walk() if k.m]
            xh = [m['xh'] for m in ms if m.get('xh')]
            x.m = dict(줄=sum((m.get('줄') or 0) for m in ms),
                       xh범위=[round(min(xh), 1), round(max(xh), 1)] if xh else None,
                       마디수=len(x.kids))
    return root


def summary(root):
    out = []
    for x in root.walk():
        m = x.m or {}
        bits = []
        if m.get('줄'):
            bits.append(f"줄 {m['줄']}")
        if m.get('xh'):
            bits.append(f"xh {m['xh']:.1f}")
        if m.get('xh범위'):
            bits.append(f"xh {m['xh범위'][0]}~{m['xh범위'][1]}")
        if m.get('행간'):
            bits.append(f"행간 {m['행간']:.0f}")
        if x.why and x.kind == '그림':
            bits.append(x.why)
        out.append('  ' * x.id.count('.') + f"{x.id:<12}[{x.kind}] " + ' · '.join(bits))
    return '\n'.join(out)
