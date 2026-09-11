"""스스로 판면을 훑어 덩어리를 찾는다 — 비교 대상(baseline).

이것이 원래 경로였고 지금은 «짚어주는 쪽» 과 견주기 위해 남겨 둔다.
찾기와 재기를 한 함수가 하므로 찾기가 틀리면 재기가 아무리 정확해도
소용이 없다. 오페라하우스 두 점을 IDML 가이드로 대조하니 한 덩어리를
17개·12개로 쪼갰고, 코퍼스 전체로는 헛것 92 · 놓침 52 였다.

재는 일은 하지 않는다 — measure/ink.py 를 불러 쓴다. 의존은 한 방향이다.
"""
import numpy as np
from PIL import Image          # run() 이 경로를 받으면 쓴다 — 빠져 있어 NameError 가 났다
from scipy import ndimage

from measure.ink import polarity, threshold, lines
from measure.grid import apply_grid


EPS        = 2      # 측정 오차 (안티에일리어싱 2~3px). 절대 하한으로 쓴다.
GAP_RATIO  = 1.5    # 행간이 중앙값의 1.5배 넘으면 자름
SIZE_RATIO = 0.25   # 활자 높이가 25% 넘게 변하면 자름
XSTART_EPS = EPS    # 정렬 축이 오차 이상 움직이면 자름

COL_FRAC = 0.13     # 단 사이 빈 띠 판정. 그 영역 최대 잉크의 이 비율 이하를 빈 것으로 본다.
                    # 코어 108장 스윕 (표본 n / 블록 수)
                    #   0.00  58 / 901     0.15  75 / 1022
                    #   0.10  69 / 960     0.18  74 / 1084
                    #   0.13  69 / 985     0.25  66 / 1190
                    #                      0.35  72 / 1335
                    # 총량만 보면 0.15 가 낫다. 그런데 0.15 는 1952 Die Gute
                    # Form 의 오른쪽 정렬 5줄 블록을 쪼갠다 (n 5 → 1). 눈으로
                    # 확인한 블록이다. 오른쪽 정렬은 왼쪽 끝이 들쭉날쭉하므로
                    # 블록 안에 잉크가 적은 세로 띠가 생기고, 문턱이 높으면
                    # 그것을 단 경계로 오인한다. 0.13 이 그 블록을 지키는
                    # 최대값이다. 회귀 검사가 잡았다.

STRATA_RATIO = 3.0  # 성분 높이가 중앙값의 이 배를 넘으면 다른 크기 계층으로 본다.
                    # 36장 스윕: 분리 없음 n=8, 2.5~12배 n=14~17 로 평평하다.
                    # 값이 아니라 분리하느냐 마느냐가 결정적이다. 3.0 은 얕은 봉우리.

COL_GAP_FRAC = 0.5   # 단을 가르는 최소 틈을 그 계층 활자 높이의 이 배로 잡는다.
                     # 0 (=6px 고정) 이면 제목의 자간이 단 경계로 잡힌다.
                     # 오페라하우스 18점 스윕: 0 에서 헛검출 34, 0.3~2.0 은
                     # 25~28 로 평평하다. 0.5 가 베이스라인 재현율 최고(98%).

BAND_STEP = 48.0  # 바탕 밝기가 이만큼(0~255) 달라지면 다른 바탕으로 본다.
                  # 낮추면 그러데이션이 계단으로 잡혀 띠가 잘게 부서진다.
                  # 오페라하우스 18점 스윕: 10 에서 포스터당 띠 10.7 개,
                  # 헛검출 119. 44~52 구간은 전부 같은 점수로 평평하다.
BAND_MIN = 48     # 이보다 얇은 띠는 가르지 않는다. 계단 판정의 창 크기도
                  # 겸한다. 45~49 평평하고 52 부터 제목 재현율이 86%→75%
                  # 로 떨어진다 — 제목 띠(약 250px) 가 본문과 합쳐진다.

SEED_PAD = 4     # 씨앗 상자를 이만큼 넓혀 본다

SHADOW_PAD = 5      # 큰 블록의 상자를 이만큼 넓혀 그 안에 드는지 본다
SHADOW_H = 0.45     # 큰 블록 상자 높이의 이 비율 이하면 조각으로 본다.
                    # 예전에는 글줄 높이(h) 로 견줬는데, 그것은 상자 높이가
                    # 아니라 줄 하나의 높이라 두 줄짜리 큰 블록에서 문턱이
                    # 절반으로 줄었다 — Wiener Blut 의 「Wiener Blut」 상자는
                    # 48px 인데 h 가 22.5 라, 8px 짜리 획 조각이 6.75 문턱을
                    # 넘어 살아남았다.
SHADOW_W = 0.45     # 폭도 함께 본다. 조각은 큰 글줄의 일부라 좁다.

def _measured(bl):
    """베이스라인 간격의 중앙값. 격자 맞추기와 무관한 «잰 값» 이다.

    격자값(lead)은 자기상관이 봉우리를 못 찾으면 None 이 된다. 창이 5~60px
    이라 82px 행간의 표제 블록은 아예 닿지 못하고, 단 전체의 잉크 프로파일을
    쓰기 때문에 다른 블록이 섞여 봉우리가 뭉개지기도 한다. 그때 멀쩡한 실측값
    까지 함께 버려지고 있었다 — 브로크만 코어에서 6줄 크레딧 블록의 실측
    간격이 14.0 인데 lead 는 None 이었다.

    measure/grid.py 첫머리에 「측정값은 건드리지 않는다, 격자는 별도 열로만
    남긴다」고 적어 두었는데 지표가 격자값을 쓰고 있었다. 원칙대로 나눈다.
    """
    b = sorted(l['base'] for l in bl)
    if len(b) < 2:
        return None
    return round(float(np.median(np.diff(b))), 1)


def trim(g, th, frac=0.8, max_fringe=3):
    """스캔 테두리 제거.
       1) 폭의 frac 이상이 어두운 가장자리 = 테두리
       2) 그 안쪽으로 잉크가 0이 될 때까지 = 안티에일리어싱 띠 (최대 max_fringe px)
       테두리가 없으면 아무것도 자르지 않는다."""
    m = g < th
    def cut(vals):
        i = 0
        while i < len(vals) and vals[i] > frac: i += 1
        if i == 0: return 0, 0
        f = 0
        while f < max_fringe and i + f < len(vals) and vals[i + f] > 0: f += 1
        return i, f
    cw = [m[:, x].mean() for x in range(g.shape[1])]
    ch = [m[y, :].mean() for y in range(g.shape[0])]
    L, Lf = cut(cw); R, Rf = cut(cw[::-1])
    T, Tf = cut(ch); B, Bf = cut(ch[::-1])
    box = (L + Lf, T + Tf, g.shape[1] - R - Rf, g.shape[0] - B - Bf)
    log = dict(left=(L, Lf), right=(R, Rf), top=(T, Tf), bottom=(B, Bf),
               capped=[k for k, (b, f) in
                       dict(left=(L, Lf), right=(R, Rf), top=(T, Tf), bottom=(B, Bf)).items()
                       if b > 0 and f == max_fringe])
    return box, log

def columns(g, th, min_gap=6):
    """세로로 빈 띠를 찾아 단을 가른다.

    「잉크가 정확히 0」 을 요구하면 얼룩·그래픽·스캔 노이즈가 띠를 메워 단이
    갈리지 않는다. lines() 는 같은 문제를 이미 상대 비율(INK_FRAC)로 풀고
    있었는데 여기만 절대 0 이었다.
    """
    col = (g < th).sum(axis=0)
    peak = np.percentile(col[col > 0], 90) if (col > 0).any() else 0.0
    empty = col <= COL_FRAC * peak
    gaps = []; s = None
    for x, v in enumerate(empty):
        if v and s is None: s = x
        if (not v) and s is not None:
            if x - s >= min_gap: gaps.append((s, x))
            s = None
    out = []; prev = 0
    for s, e in gaps + [(g.shape[1], g.shape[1])]:
        if s - prev > 10:
            idx = np.where(col[prev:s] > 0)[0]
            if len(idx): out.append((prev + idx[0], prev + idx[-1] + 1))
        prev = e
    return out

def shares_axis(a, b, eps=None):
    """두 줄이 같은 정렬 축을 공유하는가.

    정렬 방식을 코드가 정하지 않는다. 왼쪽·오른쪽·가운데 중 어느 축이든
    하나만 맞으면 같은 블록으로 본다. 셋 다 어긋날 때만 자른다.

    왼쪽 축만 보던 때는 왼쪽 정렬 격자를 전제하는 것이었다. 그 전제는
    조판 방식을 코드에 박는 것이고, 오른쪽 정렬이나 가운데 정렬로 짠
    블록은 줄마다 좌측 끝이 수십 px 씩 움직이므로 전부 낱줄로 흩어졌다.
    """
    eps = XSTART_EPS if eps is None else eps   # 기본 인자로 두면 정의 시점에 굳는다
    return (abs(a['xs'] - b['xs']) <= eps or                       # 왼쪽
            abs(a['xe'] - b['xe']) <= eps or                       # 오른쪽
            abs((a['xs'] + a['xe']) - (b['xs'] + b['xe'])) <= 2 * eps)   # 가운데

def scale_strata(m, ratio=None):
    """잉크를 크기 계층으로 가른다.

    행간은 크기 계층 안에서만 정의된다. 자기 키의 수십 배인 성분이 같은
    가로 스캔에 섞이면, 그 성분의 잉크가 모든 행에 걸쳐 작은 활자의 줄
    경계를 덮는다. 호프만은 활자로 그림을 그리므로 이 일이 자주 일어난다.
    Bach-Chor 포스터에서는 x높이 464px 의 「B」 하나가 8px 활자 6줄을
    통째로 삼켰다.

    큰 글자를 배제하는 것이 아니다. 자기 계층에서 따로 측정될 뿐이고,
    낱글자라면 잴 행간이 없을 뿐이다.
    """
    ratio = STRATA_RATIO if ratio is None else ratio   # 기본 인자로 두면 정의 시점에 굳는다
    lab, n = ndimage.label(m)
    if n == 0:
        return [m]
    hs = np.array([o[0].stop - o[0].start for o in ndimage.find_objects(lab)])
    body = hs[hs >= 2]
    if body.size == 0:
        return [m]
    big = np.where(hs > ratio * float(np.median(body)))[0] + 1
    if big.size == 0:
        return [m]
    tall = np.isin(lab, big)
    return [m & ~tall, tall]

def body_height(m):
    """그 마스크의 성분 높이 중앙값. 활자 크기의 대용값."""
    lab, n = ndimage.label(m)
    if n == 0: return 0.0
    hs = np.array([o[0].stop - o[0].start for o in ndimage.find_objects(lab)])
    b = hs[hs >= 2]
    return float(np.median(b)) if b.size else 0.0

def columns_mask(m, min_gap=6):
    """columns() 와 같은 논리를 이진 마스크 위에서 돌린다."""
    col = m.sum(axis=0)
    peak = np.percentile(col[col > 0], 90) if (col > 0).any() else 0.0
    empty = col <= COL_FRAC * peak
    gaps = []; s = None
    for x, v in enumerate(empty):
        if v and s is None: s = x
        if (not v) and s is not None:
            if x - s >= min_gap: gaps.append((s, x))
            s = None
    out = []; prev = 0
    for s, e in gaps + [(m.shape[1], m.shape[1])]:
        if s - prev > 10:
            idx = np.where(col[prev:s] > 0)[0]
            if len(idx): out.append((prev + idx[0], prev + idx[-1] + 1))
        prev = e
    return out

def group(ls):
    if not ls: return []
    if len(ls) < 2: return [ls]
    gaps = [ls[i+1]['base'] - ls[i]['base'] for i in range(len(ls)-1)]
    med  = np.median(gaps)
    blocks = [[ls[0]]]
    for i, gp in enumerate(gaps):
        a, b = ls[i], ls[i+1]
        # 크기는 이웃 한 줄이 아니라 지금까지 쌓인 블록의 중앙값과 견준다.
        # 한 줄만 보면 내용 때문에 x높이가 튀는 것을 크기 변화로 오인한다 —
        # 움라우트가 있는 줄(für), 숫자만 있는 줄(fr.1.10-3.30) 은 소문자
        # 줄보다 잉크가 높게 잡힌다. 1957 Musica Viva 에서 12줄 단이 7+5 로,
        # 7줄 단이 6+1 로 잘린 것이 전부 이 때문이었다.
        ref = float(np.median([l['xh'] for l in blocks[-1]]))

        def differs(x):
            return (abs(ref - x) > EPS and
                    abs(ref - x) / min(ref, x) > SIZE_RATIO)

        # 크기 변화는 이어져야 인정한다. 한 줄만 튀는 것은 내용 때문이다 —
        # 움라우트가 있는 줄(für)과 숫자만 있는 줄(fr.1.10-3.30)은 소문자
        # 줄보다 잉크가 높게 잡힌다. 활자 크기가 실제로 바뀌면 다음 줄도
        # 함께 바뀐다. 1957 Musica Viva 에서 12줄 단이 7+5 로, 7줄 단이
        # 6+1 로 잘린 것이 전부 한 줄짜리 튐 때문이었다.
        # 마지막 줄에는 「이어지는지」 볼 다음 줄이 없다. 증거가 없으면 자르지
        # 않는다 — 끝줄 하나가 튀는 것은 대개 내용 때문이다. 1957 Musica Viva
        # 의 karten / fr.1.10-3.30 이 그랬다 (숫자가 소문자보다 높게 잡힌다).
        nxt = ls[i+2] if i + 2 < len(ls) else None
        size_cut = differs(b['xh']) and nxt is not None and differs(nxt['xh'])

        cut  = (gp > GAP_RATIO * med
                or size_cut
                or not shares_axis(a, b))
        (blocks.append([b]) if cut else blocks[-1].append(b))
    return blocks

def box(bl):
    """블록 상자는 잉크 전체다 — 발음기호 위끝부터 디센더 아래끝까지.

    top~base 로 잡으면 ü 의 점과 j 의 꼬리가 상자 밖으로 나간다. top 은
    캡 높이고 base 는 베이스라인이라 둘 다 잉크의 끝이 아니다. 상자가
    글자를 자르면 마진과 덮음 면적이 그만큼 작게 나온다.

    ink_top/ink_bot 은 lines() 가 잉크 문턱으로 자른 띠의 양 끝이라
    디센더 검출(실패율이 높다)에 기대지 않는다.
    """
    return (min(l['xs'] for l in bl), min(l['ink_top'] for l in bl),
            max(l['xe'] for l in bl), max(l['ink_bot'] for l in bl))

def bands(g, step=None, min_h=None):
    """바탕이 바뀌는 자리에서 가로 띠를 가른다.

    한 판에 극성과 문턱을 하나씩만 쓰면, 회색 바탕의 흰 제목과 채도 높은
    색면 위의 검은 본문 중 한쪽이 반드시 깨진다. 오페라하우스 18점에서
    제목부를 따로 떼어 재면 아라벨라 가이드를 89% 맞히는데 통째로 재면
    44% 였다 — 코드가 아니라 자르는 범위의 문제였다.

    바탕은 행별 중앙값으로 본다. 활자는 행의 일부만 덮으므로 중앙값을
    거의 움직이지 않고, 색면이 바뀔 때만 계단이 생긴다.
    """
    step = BAND_STEP if step is None else step
    min_h = BAND_MIN if min_h is None else min_h
    H = g.shape[0]
    if H < 2 * min_h or g.shape[1] < 4:
        return [(0, H)]
    med = np.median(g, axis=1)
    d = np.zeros(H)
    for i in range(min_h, H - min_h):
        d[i] = abs(np.median(med[i:i+min_h]) - np.median(med[i-min_h:i]))
    cuts = []
    for i in np.argsort(-d):
        if d[i] < step: break
        if i < min_h or i > H - min_h: continue
        if any(abs(int(i) - c) < min_h for c in cuts): continue
        cuts.append(int(i))
    edges = [0] + sorted(cuts) + [H]
    return list(zip(edges[:-1], edges[1:]))

def seeded(g, seeds, covered):
    """줄을 하나도 못 찾은 씨앗 상자 안에서만 국소 극성으로 다시 찾는다.

    전역 극성은 한 판 안에서 극성이 뒤집히는 포스터를 못 읽는다. 그런데
    그런 자리도 검출기는 「글자가 있다」 까지는 안다 — 읽지는 못해도(신뢰도
    0.00) 위치는 짚는다. 그 좁은 띠 안에서 극성을 다시 정하면 읽힌다.

    보강이지 교체가 아니다. 씨앗 방식만 쓰면 검출기의 회수율 한계 때문에
    잘 되던 포스터에서 줄을 놓친다. 그래서 빈 자리에만 덧붙인다.

    오페라하우스 18점을 손으로 찍은 베이스라인 361개와 대조한 결과
    (회전 게이트를 함께 적용한 상태):

        보강 끔   재현율 26%  정밀도 49%  본문을 통째로 놓친 포스터 5점
        보강 켬   재현율 45%  정밀도 52%  통째로 놓친 포스터 0점
    """
    H, W = g.shape
    out = []
    for x0, y0, x1, y1 in seeds:
        x0 = max(0, int(x0) - SEED_PAD); x1 = min(W, int(x1) + SEED_PAD)
        y0 = max(0, int(y0) - SEED_PAD); y1 = min(H, int(y1) + SEED_PAD)
        if x1 - x0 < 8 or y1 - y0 < 6:
            continue
        if covered[y0:y1, x0:x1].any():        # 이미 찾은 줄이 있으면 건너뛴다
            continue
        crop = polarity(g[y0:y1, x0:x1].copy())
        try:
            ls = lines(crop, threshold(crop), 0, crop.shape[1])
        except Exception:
            continue
        for l in ls:
            d = dict(l)
            for k in ('base', 'top', 'x_top'):
                d[k] = l[k] + y0
            # ink_bot 이 이 목록에서 빠져 있었다. 창 안 행 번호로 남은 채 box() 의
            # 아래끝이 되어, 보강 덩어리의 y2 가 «창 안 행 + region 위끝» 이 됐다
            # (1950 Helmhaus: y1 542 인데 y2 502 = 465 + 37). 캐시 덩어리 289개가
            # 위끝은 맞고 아래끝만 뒤집혔던 원인이다.
            for k in ('cap', 'mark_top', 'desc', 'ink_top', 'ink_bot'):
                if d.get(k) is not None:
                    d[k] = l[k] + y0
            d['xs'] = l['xs'] + x0; d['xe'] = l['xe'] + x0
            out.append(d)
    return out

def _panels(gb, thb):
    """측정 단위(단 × 크기계층)를 낸다.

    옛 순서는 단을 먼저 가르고 그 안에서 크기 계층을 갈랐다. 그러면 단을
    가르는 최소 틈을 활자 크기에 맞출 수 없다 — 큰 제목과 작은 본문이 한
    띠에 있으면 성분 높이의 중앙값이 작은 쪽으로 끌려간다. 6px 고정으로
    두면 제목의 자간이 단 경계로 잡혀 「Wiener Blut」 한 줄이 글자별로
    쪼개지고 15줄이 된다.
    """
    for sm in scale_strata(gb < thb):
        gap = max(6, int(COL_GAP_FRAC * body_height(sm)))
        for cx0, cx1 in columns_mask(sm, gap):
            yield cx0, cx1, sm[:, cx0:cx1]

def drop_shadows(res):
    """큰 글줄 바로 아래에 남는 한 줄짜리 부스러기를 버린다.

    획의 가장자리·잉크 번짐(2~4px), 움라우트 점(14px), 큰 활자의 획 조각이
    저마다 한 줄로 선다. 줄 수는 보지 않는다 — Wiener Blut 에서 폭 6px 에
    4줄짜리 조각이 나왔다. 크기 계층이 이것들을 큰 글자와 다른 계층으로 갈라 놓으므로
    lines() 의 조각 흡수가 닿지 않는다. 큰 블록의 상자 안에 통째로 들어가고
    높이가 그 일부에 불과하면 그 글줄의 부분이지 따로 선 글줄이 아니다.
    「Opernhaus Zürich」 한 판에서 이런 블록이 여섯 개 나왔다.
    """
    def box_h(b): return b['y2'] - b['y1']
    def box_w(b): return b['x2'] - b['x1']

    out = []
    for b in res:
        shadow = False
        for o in res:
            if o is b: continue
            if box_h(o) <= 0 or box_w(o) <= 0: continue
            # 상자가 더 커야 부모다
            if box_h(o) * box_w(o) <= box_h(b) * box_w(b): continue
            if box_h(b) > SHADOW_H * box_h(o): continue
            if box_w(b) > SHADOW_W * box_w(o): continue
            if (o['x1'] - SHADOW_PAD <= b['x1'] and b['x2'] <= o['x2'] + SHADOW_PAD
                    and o['y1'] - SHADOW_PAD <= b['y1'] and b['y2'] <= o['y2'] + SHADOW_PAD):
                shadow = True; break
        if not shadow:
            out.append(b)
    return out

def run(src, region, seeds=None):
    """src 는 파일 경로 또는 회색조 배열. 배열을 받으면 디스크를 거치지 않는다.

    예전에는 호출하는 쪽이 고정 경로 /tmp/_work.png 에 저장해 넘겼다. 측정을
    두 개 동시에 돌리면 서로의 파일을 덮어써서 엉뚱한 이미지를 재고, 조용히
    틀린 값이 나온다. 포스터마다 PNG 를 인코딩·디코딩하는 값도 없다.
    """
    g = (src.astype(float) if isinstance(src, np.ndarray)
         else np.asarray(Image.open(src).convert('L')).astype(float))
    g = g[region[1]:region[3], region[0]:region[2]]
    gp = polarity(g)          # 밝은 활자 / 어두운 배경을 여기서 정규화한다
    th = threshold(gp)
    (tx0, ty0, tx1, ty1), _ = trim(gp, th)
    g = g[ty0:ty1, tx0:tx1]   # 이후로는 원본 밝기를 들고 다닌다
    region = (region[0]+tx0, region[1]+ty0, region[0]+tx1, region[1]+ty1)
    res = []
    n_cols = 0
    for b0, b1 in bands(g):
      gb = polarity(g[b0:b1])     # 띠마다 극성과 문턱을 다시 정한다
      thb = threshold(gb)
      # 판면의 단 수는 보고용 지표다. 측정 단위를 가르는 일은 _panels() 가
      # 크기 계층 안에서 따로 한다.
      n_cols = max(n_cols, len(columns(gb, thb)))
      oy = region[1] + b0
      for cx0, cx1, sm in _panels(gb, thb):
          ink_col = sm.sum(axis=1).astype(float)
          for bl in group(lines(gb, thb, cx0, cx1, mask=sm)):
            bl, lead, resid = apply_grid(bl, ink_col)
            x1, y1, x2, y2 = box(bl)
            res.append(dict(lead=lead, lead_measured=_measured(bl), grid_resid=round(resid, 2),x1=x1+region[0], y1=y1+oy, x2=x2+region[0], y2=y2+oy,
                            n=len(bl), h=round(float(np.median([l['base']-l['top'] for l in bl])), 1),
                            xh=round(float(np.median([l['xh'] for l in bl])), 1),
                            lines=[dict(top=l['top']+oy, base=l['base']+oy,
                                        base_grid=(None if l.get('base_grid') is None
                                                   else l['base_grid']+oy),
                                        shift=l.get('shift', 0),
                                        x_top=l['x_top']+oy,
                                        cap=None if l['cap'] is None else l['cap']+oy,
                                        mark_top=None if l['mark_top'] is None else l['mark_top']+oy,
                                        desc=None if l['desc'] is None else l['desc']+oy,
                                        cap_kind=l['cap_kind'], n_mark=l['n_mark'],
                                        ink_top=l['ink_top']+oy, xh=l['xh'],
                                        xs=l['xs']+region[0], xe=l['xe']+region[0]) for l in bl],
                            base=[l['base']+oy for l in bl]))

    res = drop_shadows(res)

    # ── 보강: 검출기가 글자를 짚었는데 줄을 못 찾은 자리 ──────────────
    if seeds:
        covered = np.zeros(g.shape, bool)
        for b in res:
            y0 = max(0, b['y1'] - region[1]); y1 = max(0, b['y2'] - region[1])
            x0 = max(0, b['x1'] - region[0]); x1 = max(0, b['x2'] - region[0])
            covered[y0:y1, x0:x1] = True
        loc = [(x0 - region[0], y0 - region[1], x1 - region[0], y1 - region[1])
               for x0, y0, x1, y1 in seeds]
        extra = seeded(g, loc, covered)
        if extra:
            for bl in group(sorted(extra, key=lambda d: d['base'])):
                x0b = min(l['xs'] for l in bl); x1b = max(l['xe'] for l in bl)
                ink_col = (g[:, max(0, x0b):max(1, x1b)] <
                           threshold(polarity(g[:, max(0, x0b):max(1, x1b)].copy()))).sum(1).astype(float)
                bl, lead, resid = apply_grid(bl, ink_col)
                x1_, y1_, x2_, y2_ = box(bl)
                res.append(dict(lead=lead, lead_measured=_measured(bl), grid_resid=round(resid, 2),
                                x1=x1_+region[0], y1=y1_+region[1],
                                x2=x2_+region[0], y2=y2_+region[1],
                                n=len(bl), seeded=True,
                                h=round(float(np.median([l['base']-l['top'] for l in bl])), 1),
                                xh=round(float(np.median([l['xh'] for l in bl])), 1),
                                lines=[dict(top=l['top']+region[1], base=l['base']+region[1],
                                            base_grid=(None if l.get('base_grid') is None
                                                       else l['base_grid']+region[1]),
                                            shift=l.get('shift', 0),
                                            x_top=l['x_top']+region[1],
                                            cap=None if l['cap'] is None else l['cap']+region[1],
                                            mark_top=None if l['mark_top'] is None else l['mark_top']+region[1],
                                            desc=None if l['desc'] is None else l['desc']+region[1],
                                            cap_kind=l['cap_kind'], n_mark=l['n_mark'],
                                            ink_top=l['ink_top']+region[1], xh=l['xh'],
                                            xs=l['xs']+region[0], xe=l['xe']+region[0]) for l in bl],
                                base=[l['base']+region[1] for l in bl]))
    return th, res, n_cols
