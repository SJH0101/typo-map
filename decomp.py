"""자유도를 항목별로 가른다 — 원본 값을 하나씩 바꿔 넣는 분해.

못 박은 것: docs/decomp_preregister.json

바꿔 넣은 값 자체를 재면 돈다 — 마진을 넣고 마진 오차가 0 이 됐다고
말하면 아무것도 안 잰 것이다. 그래서 «넣는 것» 과 «재는 것» 을 가른다.

    넣는 것   M 마진 · S 활자 크기 · X 가로 자리 · Y 세로 자리
    재는 것   덩어리 네 모서리가 실제로 떨어진 자리의 오차

항목 넷의 부분집합 16개를 전부 그리고 샤플리 값으로 가른다. 넣는 순서에
따라 기여가 달라지는데, 그 순서를 내가 고르지 않는다.

**이 몫은 «교리가 안 정한 자유» 가 아니라 «우리 규칙이 다시 못 세우는 것»
이다.** 규칙이 멍청하면 몫이 커진다. 자유도의 상한으로 읽는다.
"""
import itertools
import math

import numpy as np

LEAD = 2.00                      # 행간 ÷ x높이 — docs/loo_block_confirm.json
ITEMS = ('M', 'S', 'X', 'Y')
NAMES = {'M': '마진', 'S': '활자 크기', 'X': '가로 자리', 'Y': '세로 자리'}


def poster(r):
    """캐시 한 판 → 생성기 입력. 못 쓰면 None. 좌표는 판 크기로 나눈다."""
    sz, bs = r.get('size'), r.get('blocks') or []
    if not sz or abs(r.get('angle', 0)) >= 1 or len(bs) < 3:
        return None
    W, H = float(sz[0]), float(sz[1])
    if W <= 0 or H <= 0:
        return None
    B = []
    for b in bs:
        if not b.get('xh') or not b.get('n') or b['x2'] <= b['x1']:
            continue
        y2 = b['y2']
        if y2 <= b['y1']:
            # 캐시 버그 — 위끝은 맞고 아래끝이 쓰레기인 덩어리가 있다 (브로크만
            # 1,693개 중 259개). 마지막 베이스라인을 아래끝으로 쓴다. 베이스라인도
            # 없으면 이 덩어리는 믿을 수 없으므로 뺀다.
            bases = [v for v in (b.get('bases') or []) if v is not None]
            if not bases or max(bases) <= b['y1']:
                continue
            y2 = max(bases)
        B.append(dict(x1=b['x1'] / W, y1=b['y1'] / H, x2=b['x2'] / W, y2=y2 / H,
                      xh=b['xh'] / H, n=int(b['n']),
                      wu=(b['x2'] - b['x1']) / b['xh']))    # 폭 ÷ x높이 — 브리프
    if len(B) < 3:
        return None
    B.sort(key=lambda b: (b['y1'], b['x1']))                 # 읽는 순서 — 브리프
    return dict(B=B, aspect=W / H,
                ml=min(b['x1'] for b in B), mt=min(b['y1'] for b in B))


def generate(P, sub, rule):
    """sub = 원본 값으로 바꿔 넣을 항목. rule = 나머지 판에서 낸 값."""
    ml = P['ml'] if 'M' in sub else rule['ml']
    mt = P['mt'] if 'M' in sub else rule['mt']
    out, ycur = [], mt
    for b in P['B']:
        xh = b['xh'] if 'S' in sub else rule['xh']
        w = b['wu'] * xh / P['aspect']          # 폭은 활자 크기를 따라간다
        h = b['n'] * LEAD * xh                  # 높이는 확인된 규칙으로만
        x1 = b['x1'] if 'X' in sub else ml       # 규칙: 전부 왼쪽 마진에
        y1 = b['y1'] if 'Y' in sub else ycur     # 규칙: 읽는 순서대로 쌓기
        ycur = y1 + h + LEAD * xh
        out.append((x1, y1, x1 + w, y1 + h))
    return out


def error(P, boxes):
    return float(np.mean([(abs(g[0] - b['x1']) + abs(g[1] - b['y1'])
                           + abs(g[2] - b['x2']) + abs(g[3] - b['y2'])) / 4.0
                          for g, b in zip(boxes, P['B'])]))


def shapley(P, rule):
    """(아무것도 안 넣은 오차, 다 넣은 오차, 항목별 몫)."""
    v = {}
    for k in range(len(ITEMS) + 1):
        for S in itertools.combinations(ITEMS, k):
            v[frozenset(S)] = error(P, generate(P, set(S), rule))
    n = len(ITEMS)
    phi = {i: 0.0 for i in ITEMS}
    for i in ITEMS:
        rest = [j for j in ITEMS if j != i]
        for k in range(n):
            for S in itertools.combinations(rest, k):
                S = frozenset(S)
                wgt = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                phi[i] += wgt * (v[S] - v[S | {i}])      # 넣어서 줄어든 오차
    return v[frozenset()], v[frozenset(ITEMS)], phi


def rules_without(posters, skip):
    """판 하나를 뺀 나머지에서 규칙 값을 낸다 — 새는 것을 막는다."""
    rest = [p for j, p in enumerate(posters) if j != skip]
    return dict(ml=float(np.median([p['ml'] for p in rest])),
                mt=float(np.median([p['mt'] for p in rest])),
                xh=float(np.median([b['xh'] for p in rest for b in p['B']])))
