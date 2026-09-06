"""**결정도** — 내용이 주어졌을 때 배치가 얼마나 정해져 있나.

여태 「누가 만들었나」를 물었고 네 종류의 물음에서 계속 아니라고 나왔다.
「공유된 체계다」는 브로크만 본인이 쓴 말이라 확인해도 아무도 안 놀란다.

뒤집는다. **체계가 공유되고 빡빡하다면 배치는 내용에서 거의 유도된다.**
얼마나 유도되는지는 아무도 안 쟀다. 90% 면 거의 기계적이고 40% 면 교리가
느슨하고 개인이 채운다. 그리고 생성하려면 이 수가 필요하다.

한 덩어리를 빼고 나머지로 규칙을 세워 그 덩어리를 맞힌다 (decon.rebuild
와 같은 얼개 — 전체로 규칙을 뽑아 전체를 맞히면 순환이다).

**두 물음을 갈라서 묻는다. 그 사이가 이 연구가 좇던 자리다.**

    ① 좁힘   격자가 «연속» 을 «몇 개의 칸» 으로 좁히나
             actual 과 가장 가까운 칸의 거리를, 칸을 아무 데나 놓았을
             때와 견준다. 교리가 정하는 몫이다.

    ② 고름   그 칸 «중에서» 어느 것인지 맞힐 수 있나
             간단한 규칙이 옳은 칸을 고르는 비율을, 아무 칸이나 찍는
             비율(1/칸수)과 견준다. 교리가 안 정한 자리다.

①과 ②는 귀무가 달라야 한다. ①은 「칸 여덟 중 가장 가까운 것」과 견주고
②는 「칸 여덟 중 하나를 찍기」와 견딘다. 같은 귀무를 쓰면 ②가 늘 진다 —
처음에 그렇게 짜서 맞힘 결정도가 전부 0 으로 나왔다.

남은 자유도를 비트로 적는다. 칸이 여덟이면 3비트, 규칙이 맞히는 만큼
줄어든다. 「이 판의 가로 자리는 3비트 중 1.2비트가 남는다」가 답이다.
"""
import numpy as np

import decon

MIN_BLOCKS = 5      # 하나 빼고 규칙을 세우려면 넷이 남아야 한다
N_NULL = 60


def _slots_x(rest, W):
    return sorted(decon.columns(rest, W)['축'])


def _slots_y(rest, H):
    """나머지 세로 자리에서 격자 칸을 낸다.

    간격을 «잔차가 가장 작은 것» 으로 고르면 안 된다. 간격이 작을수록
    잔차는 언제나 준다 — 극단으로 1px 간격이면 잔차가 0이다. 처음에
    그렇게 짜서 칸이 40개로 나왔다.

    잣대를 무차원으로 바꾼다. 간격 p 에서 «아무렇게나 놓은» 자리의 기대
    잔차는 p/4 다. 실제 잔차를 그것으로 나누면 간격에 안 딸린다. 그 비가
    가장 작은 간격을 고른다.
    """
    ys = np.sort(np.array([b['y1'] for b in rest], float))
    if len(ys) < 3:
        return []
    d = np.diff(ys); d = d[d > 1]
    if not len(d):
        return []
    best = (None, 1e18)
    for p in np.unique(np.round(d, 1)):
        if p < H * 0.02:
            continue
        r = np.abs((ys - ys[0]) % p); r = np.minimum(r, p - r)
        score = float(r.mean()) / (p / 4.0)      # 무차원
        if score < best[1]:
            best = (float(p), score)
    p = best[0]
    if not p:
        return []
    return list(np.arange(ys[0] % p, H, p))


def _slots_size(rest):
    return sorted({round(z['xh'], 1) for z in rest if z.get('xh')})


def _near(slots, v):
    return int(np.argmin([abs(s - v) for s in slots]))


def one(blocks, W, H, rnd):
    """포스터 한 장 → 항목별 기록."""
    R = {k: dict(좁힘=[], 귀무=[], 맞음=[], 칸수=[]) for k in ('가로', '세로', '크기')}
    for i, b in enumerate(blocks):
        rest = blocks[:i] + blocks[i + 1:]
        if len(rest) < 4:
            continue
        for kind, slots, val, scale in (
                ('가로', _slots_x(rest, W), b.get('x1'), W),
                ('세로', _slots_y(rest, H), b.get('y1'), H),
                ('크기', _slots_size(rest), b.get('xh'),
                 (max(_slots_size(rest)) if _slots_size(rest) else None))):
            if val is None or not slots or len(slots) < 2 or not scale:
                continue
            n = len(slots)
            j = _near(slots, val)
            R[kind]['좁힘'].append(abs(slots[j] - val) / scale)
            R[kind]['칸수'].append(n)
            # ① 귀무 — 같은 수의 칸을 «진짜 칸이 놓인 범위 안» 에 아무렇게나
            # 놓고 가장 가까운 것. 판 전체에 뿌리면 안 된다 — 진짜 축은
            # 글자가 있는 데만 모여 있어서 그것만으로 유리해진다.
            lo, hi = float(min(slots)), float(max(slots)) + 1e-6
            if hi - lo < 1e-9:
                continue
            for _ in range(N_NULL):
                ra = rnd.uniform(lo, hi, n)
                R[kind]['귀무'].append(min(abs(c - val) for c in ra) / scale)
            # ② 고름 — 나머지가 «가장 많이» 쓰는 칸을 찍는다. 매개변수가 없다.
            cnt = np.zeros(n)
            for z in rest:
                v2 = z.get({'가로': 'x1', '세로': 'y1', '크기': 'xh'}[kind])
                if v2 is not None:
                    cnt[_near(slots, v2)] += 1
            R[kind]['맞음'].append(1.0 if int(np.argmax(cnt)) == j else 0.0)
    return R


def corpus(posters, seed=20260907):
    rnd = np.random.RandomState(seed)
    A = {k: dict(좁힘=[], 귀무=[], 맞음=[], 칸수=[]) for k in ('가로', '세로', '크기')}
    n = 0
    for bs, W, H in posters:
        bs = [b for b in bs if b.get('x1') is not None]
        if len(bs) < MIN_BLOCKS or not W or not H:
            continue
        r = one(bs, float(W), float(H), rnd)
        for k in A:
            for kk in A[k]:
                A[k][kk] += r[k][kk]
        n += 1
    out = dict(판=n)
    for k, d in A.items():
        if not d['좁힘']:
            continue
        nul = float(np.median(d['귀무'])); got = float(np.median(d['좁힘']))
        cells = float(np.median(d['칸수']))
        acc = float(np.mean(d['맞음'])); chance = float(np.mean(1.0 / np.array(d['칸수'])))
        bits = float(np.log2(cells))
        # 규칙이 맞히는 만큼 남은 자유도가 준다. 맞히면 0비트, 못 맞히면
        # 나머지 칸 중 하나이므로 log2(칸수-1) 이 남는다.
        left = acc * 0.0 + (1 - acc) * (np.log2(max(cells - 1, 1)) if cells > 1 else 0.0)
        out[k] = dict(칸수=round(cells, 1), 비트=round(bits, 2),
                      귀무=round(nul, 4), 좁힘=round(got, 4),
                      좁힘결정도=round(max(0.0, 1 - got / max(nul, 1e-9)), 3),
                      고름정확=round(acc, 3), 우연=round(chance, 3),
                      고름이득=round(acc / max(chance, 1e-9), 2),
                      남은비트=round(left, 2), n=len(d['좁힘']))
    return out


# ── 칸을 «고르는» 규칙들 ─────────────────────────────────────
# 「우연의 1.85배」가 교리의 성질인지 내 규칙이 약해서인지 갈라야 한다.
# 더 좋은 규칙이 있으면 남은 자유도는 그만큼 준다. 그래서 이 수는 언제나
# «우리가 아는 규칙으로는 여기까지» 라는 상한이다.
#
# 다섯을 걸어 봤다. 전부 1.36~1.85 배다 (블록 3,084개).
#
#   최빈칸 0.320 · 같은크기 0.300 · 맨왼쪽 0.267 · 바로위 0.265 ·
#   가장가까운이웃 0.236        우연 0.173 (칸 중앙 5.8개)
#
# 다섯 중 «하나라도» 맞으면 0.581 (3.36배) 이지만 그것은 규칙이 아니라
# 신탁이다 — 어느 규칙을 쓸지 아는 사람이 없다.

def _near(slots, v):
    return int(np.argmin([abs(s - v) for s in slots]))


RULES = {
    '최빈칸': lambda rest, ax, b: int(np.argmax(np.bincount(
        [_near(ax, z['x1']) for z in rest], minlength=len(ax)))),
    '맨왼쪽': lambda rest, ax, b: 0,
    '같은크기': lambda rest, ax, b: (
        _near(ax, min((z for z in rest if z.get('xh')),
                      key=lambda z: abs(z['xh'] - b['xh']))['x1'])
        if b.get('xh') and any(z.get('xh') for z in rest) else None),
    '바로위': lambda rest, ax, b: (
        _near(ax, max((z for z in rest if z['y1'] < b['y1']),
                      key=lambda z: z['y1'])['x1'])
        if any(z['y1'] < b['y1'] for z in rest) else None),
    '가장가까운이웃': lambda rest, ax, b: _near(
        ax, min(rest, key=lambda z: abs(z['y1'] - b['y1']))['x1']),
}
