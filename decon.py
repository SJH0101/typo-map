"""포스터 한 장을 뜯어 «규칙» 을 뽑고, 그 규칙만으로 다시 세워 견준다.

작가를 가르는 일은 그만둔다. 오늘 지표 63개를 시험했고 대부분 죽었으며,
살아남은 것도 일감 구성으로 설명될 수 있었다. 더 재서 나아지지 않는다.

대신 원래 물음으로 돌아간다 — **한 장을 끝까지 이해했나.**

이해했다는 것의 뜻을 하나로 못 박는다. **규칙만으로 다시 세울 수 있으면
이해한 것이다.** 상자를 그대로 다시 그리는 것은 베끼기지 이해가 아니므로,
규칙을 먼저 뽑고 원자료를 버린 다음 규칙에서 자리를 만든다. 그리고 실제
자리와 얼마나 어긋나는지 잰다.

    ① 격자     왼쪽 모서리들이 몇 단에 서나, 피치는 얼마인가
    ② 세로      베이스라인들이 어떤 단위의 정수배인가
    ③ 계층      x높이가 몇 단계인가
    ④ 다시 세움  각 덩어리를 «가장 가까운 단 · 가장 가까운 격자선» 으로
    ⑤ 어긋남    실제 자리에서 얼마나 벗어났나

어긋남이 작으면 격자가 그 판을 설명한 것이고, 크면 격자로 설명 안 되는
무엇이 있는 것이다. 둘 다 결과다.
"""
import numpy as np


def _cluster(v, tol):
    """가까운 값들을 묶어 대표값을 낸다."""
    v = sorted(v)
    g = [[v[0]]]
    for x in v[1:]:
        (g[-1] if x - g[-1][-1] <= tol else g.append([x]) or g[-1]).append(x) \
            if x - g[-1][-1] <= tol else None
    # 위 한 줄이 헷갈리므로 다시 쓴다
    g = [[v[0]]]
    for x in v[1:]:
        if x - g[-1][-1] <= tol:
            g[-1].append(x)
        else:
            g.append([x])
    return [float(np.mean(c)) for c in g], [len(c) for c in g]


def columns(blocks, W, tol_frac=0.02):
    """왼쪽 모서리 → 단. 피치가 일정하면 그 값도 낸다."""
    xs = [b['x1'] for b in blocks]
    cen, cnt = _cluster(xs, W * tol_frac)
    d = np.diff(cen)
    d = d[d > W * 0.03]                      # 너무 붙은 것은 같은 단으로 본다
    pitch = float(np.median(d)) if len(d) else None
    return dict(축=[round(c, 1) for c in cen], 판수=cnt,
                피치=(round(pitch, 1) if pitch else None),
                피치흔들림=(round(float(np.std(d) / pitch), 3)
                       if pitch and len(d) > 1 else None))


def grid(blocks, tol=0.08):
    """베이스라인들이 어떤 단위의 정수배인가. 벗어남이 가장 작은 단위를 고른다."""
    b = sorted({v for x in blocks for v in x['bases']})
    if len(b) < 6:
        return None
    b = np.array(b, float)
    best = None
    for u in np.arange(4.0, 60.0, 0.25):
        r = (b - b.min()) / u
        dev = float(np.mean(np.abs(r - np.round(r))))
        if best is None or dev < best[1]:
            best = (float(u), dev)
    return dict(단위=round(best[0], 2), 벗어남=round(best[1], 4),
                기준선=round(float(b.min()), 1), n=len(b))


def levels(blocks, tol=0.15):
    """x높이 계층."""
    xh = [b['xh'] for b in blocks if b.get('xh')]
    if not xh:
        return []
    v = sorted(xh)
    g = [[v[0]]]
    for x in v[1:]:
        if (x - g[-1][-1]) / max(g[-1][-1], 1e-9) <= tol:
            g[-1].append(x)
        else:
            g.append([x])
    return [dict(xh=round(float(np.median(c)), 1), n=len(c)) for c in g]


def rebuild(blocks, W, seed=20260831, n_null=400):
    """**한 덩어리를 빼고** 나머지로 규칙을 세워 그 덩어리를 맞힌다.

    규칙을 전체에서 뽑아 전체를 맞히면 순환이다 — 축은 그 x1 들의 무리
    중심이므로 당연히 가깝다. 처음 재보니 가로 어긋남이 1.0px 였는데 그것은
    「무리가 촘촘하다」는 말이지 「격자가 자리를 설명한다」가 아니다.

    빼고 맞히면 다르다. 남은 덩어리들이 만든 격자가 «못 본» 덩어리의 자리를
    맞히면, 그때 격자가 자리를 «예측한다» 고 말할 수 있다.

    귀무도 붙인다. 같은 수의 축을 판 안에 무작위로 놓고 같은 일을 시킨다.
    축이 여덟 개면 아무렇게나 놓아도 판폭 566 에서 평균 18px 안에 든다.
    """
    rnd = np.random.RandomState(seed)
    got, null = [], []
    for i, b in enumerate(blocks):
        rest = blocks[:i] + blocks[i + 1:]
        if len(rest) < 3:
            continue
        ax = columns(rest, W)['축']
        got.append(min(abs(c - b['x1']) for c in ax))
        for _ in range(max(1, n_null // len(blocks))):
            ra = rnd.uniform(0, W, len(ax))
            null.append(min(abs(c - b['x1']) for c in ra))
    return np.array(got, float), np.array(null, float)


def grid_null(blocks, seed=20260831, n_null=400):
    """격자 단위가 «진짜 단위» 인가 — 베이스라인을 흩뿌린 귀무와 견준다.

    단위가 작으면 무엇이든 가까우므로 벗어남만 봐서는 안 된다. 같은 개수의
    베이스라인을 같은 범위에 무작위로 놓고 같은 방식으로 단위를 찾아 벗어남을
    잰다. 진짜 격자면 실제 벗어남이 귀무보다 뚜렷하게 작다.
    """
    b = sorted({v for x in blocks for v in x['bases']})
    if len(b) < 6:
        return None
    b = np.array(b, float)
    lo, hi = b.min(), b.max()

    def dev(v):
        best = 1e9
        for u in np.arange(4.0, 60.0, 0.25):
            r = (v - v.min()) / u
            best = min(best, float(np.mean(np.abs(r - np.round(r)))))
        return best

    got = dev(b)
    rnd = np.random.RandomState(seed)
    nl = [dev(np.sort(rnd.uniform(lo, hi, len(b)))) for _ in range(n_null // 8)]
    nl = np.array(nl)
    return dict(벗어남=round(got, 4), 귀무=round(float(nl.mean()), 4),
                분위=round(float((nl <= got).mean()), 3), n=len(b))


def analyse(e):
    """원자료 한 장 → 규칙 + 다시 세운 자리 + 어긋남."""
    bs = [b for b in (e.get('blocks') or []) if b.get('bases')]
    if len(bs) < 3:
        # 마디가 셋도 안 되면 격자를 말할 수 없다. 빈 규칙을 낸다 — None 을
        # 내면 부르는 쪽이 매번 방어해야 하고, «규칙이 없다» 와 «잴 수 없다» 가
        # 구분되지 않는다.
        W, H = e.get('size', [0, 0])
        return dict(크기=[W, H], 단=dict(축=[], 판수=[], 피치=None, 피치흔들림=None),
                    격자=None, 계층=levels(bs), n블록=len(bs),
                    맞힘=None, 격자검사=None,
                    왜=f'글줄 마디가 {len(bs)}개뿐이라 격자를 잴 수 없다')
    W, H = e['size']
    r = dict(크기=[W, H], 단=columns(bs, W), 격자=grid(bs), 계층=levels(bs),
             n블록=len(bs))
    got, null = rebuild(bs, W)
    # 어긋남이 0 에 가까우면 배수가 터진다 (4.4e+10 이 나왔다). None 으로 둔다.
    r['맞힘'] = dict(
        어긋남중앙=round(float(np.median(got)), 2),
        귀무중앙=round(float(np.median(null)), 2),
        배수=(None if float(np.median(got)) < 0.5 else
            round(float(np.median(null)) / float(np.median(got)), 2)),
        판폭대비=round(float(np.median(got)) / W, 4), n=len(got))
    r['격자검사'] = grid_null(bs)
    return r
