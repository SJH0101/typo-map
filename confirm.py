"""블록 층 규칙을 «맞춘 적 없는 자료» 에 건다.

행간 = k × (그 블록의 x높이). k 는 맞춤 자료에서만 잡고, 시험 자료는
건드리지 않는다. 못 박은 것은 docs/loo_block_preregister.json.

    A  맞춤 자료의 중앙값 행간 (÷판높이)      아무것도 안 재는 바닥
    B  통념 1.4em = 2.69 × x높이
    C  맞춤 자료에서 잡은 k × 이 블록의 x높이

기준: C÷A ≤ 0.8. 작가 남기기 두 방향이 둘 다 통과해야 한다.
"""
import json
import os

import numpy as np

CONV = 1.40 / 0.52      # 통념 — 행간 1.4em, 헬베티카 x높이 0.52em

NAME = {'brockmann': '브로크만', 'corpus': '호프만', 'rose': '로제', 'ruder': '루더'}


def blocks(cache):
    """블록 하나마다 (작가, 판, x높이, 행간). 판높이로 나눈 값."""
    import surface
    out = []
    for c in surface.ROOTS:
        raw = json.load(open(os.path.join(cache, c + '.json')))['raw']
        for k, r in raw.items():
            sz = r.get('size')
            if not sz or abs(r.get('angle', 0)) >= 1 or sz[1] <= 0:
                continue
            H = float(sz[1])
            for b in (r.get('blocks') or []):
                L = b.get('lead_measured') or b.get('lead')
                if L and b.get('xh') and b.get('n', 0) >= 3:
                    out.append(dict(작가=NAME[c], 판=k, xh=b['xh'] / H, lead=L / H))
    return out


def score(fit, test):
    """맞춤 자료로 규칙을 세우고 시험 자료에서 잰다.

    시험 자료에 최소 크기를 걸면 안 된다 — 판 단위 leave-one-out 에서
    한 판의 블록은 두셋뿐이라 통째로 걸러진다. 처음에 그렇게 짜서 작가
    안 검사가 「판 1」로 나왔다. 맞춤 자료에만 건다.
    """
    if len(fit) < 20 or not test:
        return None
    a = float(np.median([r['lead'] for r in fit]))
    k = float(np.median([r['lead'] / r['xh'] for r in fit if r['xh']]))
    eA = np.array([abs(a - r['lead']) for r in test])
    eB = np.array([abs(CONV * r['xh'] - r['lead']) for r in test])
    eC = np.array([abs(k * r['xh'] - r['lead']) for r in test])
    w = int((eC < eA).sum()); l = int((eC > eA).sum()); n = w + l
    return dict(k=round(k, 3), 시험블록=len(test),
                A=round(float(np.median(eA)), 5),
                B=round(float(np.median(eB)), 5),
                C=round(float(np.median(eC)), 5),
                비=round(float(np.median(eC) / max(np.median(eA), 1e-12)), 3),
                이김=f'{w}/{n}',
                z=(None if not n else round(float((w - n / 2) / np.sqrt(n / 4)), 2)),
                확인=(float(np.median(eC) / max(np.median(eA), 1e-12)) <= 0.8))


def fold(rows, key='판'):
    """하나씩 빼고 맞히기. 오차를 «블록» 단위로 모아 한 번에 잰다.

    판마다 따로 중앙값을 내면 판당 블록이 두셋뿐이라 값이 튄다. 폴드마다
    규칙만 새로 세우고 오차는 전부 모은다.
    """
    ks = sorted({r[key] for r in rows})
    eA, eB, eC, kk = [], [], [], []
    for k in ks:
        fit = [r for r in rows if r[key] != k]
        test = [r for r in rows if r[key] == k]
        s = score(fit, test)
        if not s:
            continue
        a = float(np.median([r['lead'] for r in fit]))
        kv = float(np.median([r['lead'] / r['xh'] for r in fit if r['xh']]))
        kk.append(kv)
        for r in test:
            eA.append(abs(a - r['lead']))
            eB.append(abs(CONV * r['xh'] - r['lead']))
            eC.append(abs(kv * r['xh'] - r['lead']))
    if not eA:
        return None
    eA, eB, eC = map(np.array, (eA, eB, eC))
    w = int((eC < eA).sum()); l = int((eC > eA).sum()); n = w + l
    return dict(k=round(float(np.median(kk)), 3), 블록=len(eA), 폴드=len(kk),
                A=round(float(np.median(eA)), 5), B=round(float(np.median(eB)), 5),
                C=round(float(np.median(eC)), 5),
                비=round(float(np.median(eC) / max(np.median(eA), 1e-12)), 3),
                이김=f'{w}/{n}',
                z=(None if not n else round(float((w - n / 2) / np.sqrt(n / 4)), 2)))
