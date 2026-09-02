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

INK = 15.0        # 크롭 안 «잉크 대비» (오츠로 가른 두 무리의 밝기 차, 0~255).
                  # 이보다 낮으면 검출기가 낸 상자를 안 믿는다.
                  #
                  # 처음에는 상자 높이 비율로 걸렀다 — 진짜 글줄 76~93% ·
                  # 헛것 4~12% 라 사이가 텅 비어 보였다. 그런데 그 76% 는
                  # «이미 한 줄을 잘라낸» 크롭에서 잰 값이다. 판 전체에서는
                  # 글줄이 높이의 2~5% 라 전부 부스러기로 걸렸고 다섯 판이
                  # 모두 깊이 0 에서 «그림» 이 됐다.
                  #
                  # 대비는 크기에 안 딸린다. 빈 회색 바탕 3.4 · 사진 44.6 ·
                  # 진짜 글줄 55.8~97.2. 잡음만 걸러 낸다.
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


def build(path, det, box=(0.0, 0.0, 1.0, 1.0), id='r', depth=0, log=None):
    log = log if log is not None else []
    im = Image.open(path).convert('RGB')
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
    if ink < INK:
        n.kind, n.why = '그림', f'잉크 대비가 {ink:.1f} 뿐이다 — 상자 {len(lines)}개는 잡음이다'
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
            kn, log = build(path, det, kb, f'{id}.{i}', depth + 1, log)
        n.kids.append(kn)

    # 덮음 검사 — 자식들이 부모의 «잉크» 를 얼마나 가져갔나.
    # 검출기가 작은 크롭에서 불안정해 조각만 내는 일이 있다. 그러면 나머지가
    # 조용히 사라진다. 남은 몫을 적어 두고, 많이 남으면 그림 마디로 만든다.
    n.덮음 = _ink_cover(c, [k[:4] for k in kids])
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
