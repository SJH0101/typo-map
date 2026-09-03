"""포스터를 «잰 트리» 로 읽는다 — 검출은 한 번, 나머지는 기하.

앞선 판(recurse_crop.py)은 마디마다 크롭을 떠서 검출기를 다시 불렀다. 잘라
확대하면 작은 글자가 잘 보인다는 생각이었고, 그 자체는 맞다. 그런데 대가가
컸다.

    검출기가 불안정하다   104x71 은 2개, 103x52 는 조각 1개
    형제를 가려야 한다     큰 쪽 안을 다시 보면 작은 쪽 글줄이 또 잡힌다
    가리다 나를 품는 형제까지 가려 크롭이 통째로 바탕이 됐다
    대비 문턱이 필요했다   빈 자리를 잘라 넣으면 잡음에서 상자를 지어낸다

하루에 붙인 패치 넷이 전부 재검출 때문에 생긴 문제였다. 그리고 그것으로도
283장 중 75장에서 트리가 두 마디에서 끝났다.

여기서는 검출기를 «한 번만» 부른다. 판 전체에서 줄을 받고, 그다음은 좌표만
가지고 나눈다.

    ① 줄을 받는다                      Surya, 판 전체에서 한 번
    ② 가장 큰 틈에서 둘로 가른다         끝까지. 이것이 덴드로그램이다
    ③ 마디마다 «한 행간인가» 를 묻는다    귀무모형. 예면 글줄 마디
    ④ 줄이 안 덮은 잉크가 그림이다        판 전체에서 한 번 계산

②에는 문턱이 없다. 「얼마나 벌어져야 자르나」를 묻지 않고 끝까지 자른다.
나무 전체가 답이고, 문턱은 나무를 «잘라» 평평한 군집을 만들 때만 필요한데
우리는 나무를 원한다.

없어진 문턱: INK_R · MIN_PX · SAME · FILL · FRAG · SPLIT_MIN · 깊이제한.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

MIN_AREA = 200        # 이보다 작은 줄상자는 부스러기로 본다 (검출기 산출물 정리)
N_NULL = 400          # 「이 틈이 두드러지나」를 물을 때 섞어 보는 횟수
ALPHA = 0.05          # 귀무 분위. 여느 판정과 같은 값을 쓴다
PIC_MIN = 0.02        # 줄이 안 덮은 잉크 덩어리가 판의 이 비율은 되어야 마디로
                      # 센다. 보고의 문턱이지 셈의 문턱이 아니다 — 값이 달라져도
                      # 측정이 아니라 트리에 적히는 마디 수만 는다.


class Node:
    def __init__(self, id, box, kind='묶음', why=None):
        self.id, self.box, self.kind, self.why = id, box, kind, why
        self.kids, self.m, self.lines = [], None, []

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()

    def dict(self):
        d = dict(id=self.id, 종류=self.kind, 상자=[round(v, 4) for v in self.box],
                 줄수=len(self.lines))
        if self.why:
            d['왜'] = self.why
        if self.m:
            d['잰것'] = self.m
        if self.kids:
            d['자식'] = [k.dict() for k in self.kids]
        return d


def _norm(b):
    x1, y1, x2, y2 = b
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _bbox(ls):
    return [min(b[0] for b in ls), min(b[1] for b in ls),
            max(b[2] for b in ls), max(b[3] for b in ls)]


def _widest_gap(ls):
    """가장 큰 틈 하나. (축, 자른 자리, 벌어진 정도)

    크기·세로·가로 셋을 같은 잣대로 잰다 — 틈 ÷ 이웃 간격의 중앙값. 잣대가
    같아야 어느 축으로 갈라야 할지 견줄 수 있다. 셋 다 틈이 없으면 None.
    """
    best = (None, None, 0.0)
    for ax, vals in (('크기', [b[3] - b[1] for b in ls]),
                     ('세로', [(b[1] + b[3]) / 2 for b in ls]),
                     ('가로', [b[0] for b in ls])):
        v = np.sort(np.asarray(vals, float))
        if len(v) < 2:
            continue
        d = np.diff(v)
        m = float(np.median(d))
        if m <= 0:
            m = float(d.max()) or 1.0
        i = int(np.argmax(d))
        score = float(d[i] / m)
        if score > best[2]:
            best = (ax, float((v[i] + v[i + 1]) / 2), score)
    return best


def _stands_out(vals, score, n_null=N_NULL, seed=20260903):
    """이 틈이 «우연보다» 두드러지나.

    「이웃의 2배 넘으면 가른다」 같은 배수를 쓰면 안 된다 — 그 배수가 어디서
    왔는지 말할 수 없고, 판마다 줄 수가 달라 같은 배수가 다른 뜻이 된다.
    줄 다섯 개의 최대 틈은 우연히도 이웃의 2배가 되지만, 여든 개면 그렇지
    않다.

    그래서 «같은 개수의 값을 같은 범위에 고르게 흩뿌렸을 때» 의 최대 틈과
    견준다. 실제 틈이 그 분포의 위쪽 5% 밖이면 두드러진 것이고, 아니면
    나눌 자리가 아니다.
    """
    v = np.sort(np.asarray(vals, float))
    if len(v) < 3:
        return len(v) == 2 and v[1] > v[0]      # 둘뿐이면 다르기만 하면 가른다
    lo, hi = v[0], v[-1]
    if hi <= lo:
        return False
    rnd = np.random.RandomState(seed)
    null = []
    for _ in range(n_null):
        r = np.sort(rnd.uniform(lo, hi, len(v)))
        d = np.diff(r)
        m = float(np.median(d)) or 1.0
        null.append(float(d.max() / m))
    return score >= float(np.percentile(null, 100 * (1 - ALPHA)))


def _split(ls, ax, cut):
    key = {'크기': lambda b: b[3] - b[1],
           '세로': lambda b: (b[1] + b[3]) / 2,
           '가로': lambda b: b[0]}[ax]
    a = [b for b in ls if key(b) <= cut]
    z = [b for b in ls if key(b) > cut]
    return [g for g in (a, z) if g]


def build(lines, size, id='r'):
    """줄상자 목록 → 덴드로그램. 이미지를 다시 보지 않는다."""
    W, H = size
    ls = [_norm(b) for b in lines]
    ls = [b for b in ls if (b[2] - b[0]) * (b[3] - b[1]) >= MIN_AREA]
    if not ls:
        return Node(id, [0, 0, 1, 1], '그림', '검출기가 줄을 내지 않았다')

    def go(g, nid):
        bx = _bbox(g)
        n = Node(nid, [bx[0] / W, bx[1] / H, bx[2] / W, bx[3] / H])
        n.lines = g
        if len(g) == 1:
            n.kind = '글줄'
            return n
        ax, cut, score = _widest_gap(g)
        if ax is None:
            n.kind, n.why = '글줄', '더 가를 틈이 없다'
            return n
        vals = {'크기': [b[3] - b[1] for b in g],
                '세로': [(b[1] + b[3]) / 2 for b in g],
                '가로': [b[0] for b in g]}[ax]
        if not _stands_out(vals, score):
            n.kind = '글줄'
            n.why = f'가장 큰 틈({ax}, 이웃의 {score:.1f}배)이 우연과 구분되지 않는다'
            return n
        parts = _split(g, ax, cut)
        if len(parts) < 2:
            n.kind, n.why = '글줄', '더 가를 틈이 없다'
            return n
        n.why = f'{ax} 틈에서 가름 (이웃의 {score:.1f}배)'
        for i, p in enumerate(parts, 1):
            n.kids.append(go(p, f'{nid}.{i}'))
        return n

    return go(ls, id)


def pictures(path, lines, root, min_share=PIC_MIN, work=400):
    """줄이 덮지 않은 잉크 덩어리 = 그림. 판 전체에서 «한 번만» 낸다.

    앞선 판은 마디마다 남은 잉크를 계산해 그림 마디를 붙였다. 마디가 겹치면
    같은 자리가 여러 번 그림이 됐다. 판 전체에서 한 번 내고 트리 밑에 단다.
    """
    im = Image.open(path).convert('RGB')
    W, H = im.size
    s = im.copy(); s.thumbnail((work, work))
    w, h = s.size
    g = np.asarray(s.convert('L'), float)
    t = float(np.percentile(g, 50))
    ink = g < t if g.mean() > t else g > t
    taken = np.zeros((h, w), bool)
    for b in lines:
        x1, y1, x2, y2 = _norm(b)
        taken[max(0, int(y1 / H * h)):int(y2 / H * h) + 1,
              max(0, int(x1 / W * w)):int(x2 / W * w) + 1] = True
    rest = ndimage.binary_closing(ink & ~taken, np.ones((5, 5)))
    lab, n = ndimage.label(rest)
    if not n:
        return []
    tot = float(ink.sum()) or 1.0
    out = []
    for i in range(1, n + 1):
        m = lab == i
        share = float((m & ink).sum() / tot)
        if share < min_share:
            continue
        ys, xs = np.where(m)
        out.append(Node(f'{root.id}.그림{len(out) + 1}',
                        [xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h],
                        '그림', f'줄이 덮지 않은 잉크 — 판 잉크의 {share:.0%}'))
    return sorted(out, key=lambda z: -(z.box[2] - z.box[0]) * (z.box[3] - z.box[1]))[:6]


def measure(root, path):
    """글줄 마디 안을 잰다. 묶음은 자식에서 굴려 올린다."""
    from measure import ground as G
    leaf = [x for x in root.walk() if x.kind == '글줄']
    if leaf:
        r = G.measure_boxes(path, [x.box for x in leaf], coords='norm')
        for x, m in zip(leaf, r['boxes']):
            x.m = dict(줄=m.get('n_lines'), xh=m.get('xh_median'),
                       행간=m.get('lead_measured'),
                       잉크상자=[round(v, 1) for v in (m.get('box_ink') or [])])
    for x in sorted(root.walk(), key=lambda z: -len(z.id)):
        if x.kids:
            ms = [k.m for k in x.walk() if k.m]
            xh = [m['xh'] for m in ms if m.get('xh')]
            x.m = dict(줄=sum((m.get('줄') or 0) for m in ms),
                       xh범위=[round(min(xh), 1), round(max(xh), 1)] if xh else None,
                       마디수=len(x.kids))
    return root


def read(path, det):
    """포스터 한 장 → 잰 트리. 검출기는 여기서 «한 번» 부른다."""
    im = Image.open(path).convert('RGB')
    lines = [[float(v) for v in b.bbox] for b in det([im])[0].bboxes]
    root = build(lines, im.size)
    root.kids += pictures(path, lines, root)
    measure(root, path)
    return root, lines


def summary(root):
    out = []
    for x in root.walk():
        m = x.m or {}
        b = []
        if m.get('줄'):
            b.append(f"줄 {m['줄']}")
        if m.get('xh'):
            b.append(f"xh {m['xh']:.1f}")
        if m.get('xh범위'):
            b.append(f"xh {m['xh범위'][0]}~{m['xh범위'][1]}")
        if m.get('행간'):
            b.append(f"행간 {m['행간']:.0f}")
        if x.kind == '그림' and x.why:
            b.append(x.why)
        out.append('  ' * x.id.count('.') + f"{x.id:<10}[{x.kind}] " + ' · '.join(b))
    return '\n'.join(out)
