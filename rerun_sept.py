"""9월 검증 분석을 한 캐시 위에서 다시 낸다 — 옛 보관본과 새 캐시에 같은 함수로.

    python rerun_sept.py                      옛 보관본 · 새 캐시 둘 다
    python rerun_sept.py ~/.typo-mcp          한 캐시만

9월에는 결정도 · 예측 · 재확인 실행기가 스크래치패드에만 있었다. 캐시가
바뀌면 다시 낼 방법이 없었다. 여기 모은다. 기준은 docs/rerun_preregister.json.
"""
import json
import os
import sys

import numpy as np

import confirm
import decon
import determ
import distinct
import docs_build
import features
import linebreak
import loo
import surface

NAME = {'brockmann': '브로크만', 'corpus': '호프만', 'rose': '로제', 'ruder': '루더'}
ORDER = ['브로크만', '호프만', '로제', '루더']
OLD = os.path.expanduser('~/.typo-mcp/old-20260824')
NEW = os.path.expanduser('~/.typo-mcp')


def load(cache):
    return {c: docs_build.load_raw(c, cache) for c in surface.ROOTS}


def verdicts(R):
    """지표 21개 — 작가 판정. 42개 시험 보정."""
    vals = {n: {} for n in features.NAMES}
    for c, raw in R.items():
        X, _k, names = features.matrix(raw)
        for j, n in enumerate(names):
            v = X[:, j]
            vals[n][NAME[c]] = list(map(float, v[np.isfinite(v)]))
    out = {}
    for n in features.NAMES:
        g = [vals[n].get(w, []) for w in ORDER]
        if sum(len(x) >= 5 for x in g) < 3:
            continue
        e = distinct.explained(g, n_tests=42)
        out[n] = dict(배수=e['ratio'], 판정=e['scope'])
    return out


def lead_rule(cache):
    """행간 = k × x높이 — 9월과 같은 재확인."""
    B = confirm.blocks(cache)
    out = dict(덩어리=len(B))
    for fit, test, lab in ((('브로크만', '호프만'), ('로제', '루더'), '브+호→로+루'),
                           (('로제', '루더'), ('브로크만', '호프만'), '로+루→브+호')):
        out[lab] = confirm.score([r for r in B if r['작가'] in fit], [r for r in B if r['작가'] in test])
    keys = sorted({r['판'] for r in B})
    half = []
    for sd in range(5):
        p = np.random.RandomState(sd).permutation(keys)
        A = set(p[:len(p) // 2])
        half.append(confirm.score([r for r in B if r['판'] in A], [r for r in B if r['판'] not in A]))
    out['판 반 가르기'] = half
    out['작가 안에서'] = {w: confirm.fold([r for r in B if r['작가'] == w]) for w in ORDER}
    out['전체'] = confirm.fold(B)
    return out


def posters(raw):
    return [(r.get('blocks') or [], r['size'][0], r['size'][1]) for r in raw.values()
            if r.get('size') and abs(r.get('angle', 0)) < 1]


def determinacy(R):
    allp = [p for raw in R.values() for p in posters(raw)]
    tab = dict(전체=determ.corpus(allp), 작가별={NAME[c]: determ.corpus(posters(raw)) for c, raw in R.items()})
    # 가로 칸을 고르는 규칙 다섯
    hit = {k: [] for k in determ.RULES}
    chance = []
    for bs, W, H in allp:
        bs = [b for b in bs if b.get('x1') is not None]
        if len(bs) < determ.MIN_BLOCKS:
            continue
        for i, b in enumerate(bs):
            rest = bs[:i] + bs[i + 1:]
            if len(rest) < 4:
                continue
            ax = sorted(decon.columns(rest, float(W))['축'])
            if len(ax) < 2:
                continue
            j = determ._near(ax, b['x1'])
            chance.append(1.0 / len(ax))
            for k, f in determ.RULES.items():
                try:
                    q = f(rest, ax, b)
                except Exception:
                    q = None
                hit[k].append(np.nan if q is None else float(q == j))
    ch = float(np.mean(chance)) if chance else float('nan')
    tab['고르는 규칙'] = dict(우연=round(ch, 3), 블록=len(chance),
                         **{k: dict(정확=round(float(np.nanmean(v)), 3), 이득=round(float(np.nanmean(v)) / ch, 2))
                            for k, v in hit.items()})
    return tab


def loo_table(R):
    merged, fills = {}, {}
    for c, raw in R.items():
        P = surface.resolve(raw, surface.ROOTS[c])
        for k, r in raw.items():
            merged[k] = r
            p = P.get(k) or P.get(k.rsplit('__', 1)[-1])
            if not p or abs(r.get('angle', 0)) >= 1:
                continue
            try:
                v = [x for y in linebreak.fills(p, r.get('blocks') or []) for x in y['참함']]
                if v:
                    fills[k] = float(np.median(v))
            except Exception:
                pass
    rows = loo.rows_of(merged, fills)
    return dict(판=len(rows), 결과=loo.run(rows))


def run(cache):
    R = load(cache)
    return dict(캐시=cache, 판={NAME[c]: len(r) for c, r in R.items()},
                덩어리={NAME[c]: sum(len(e.get('blocks') or []) for e in r.values()) for c, r in R.items()},
                지표=verdicts(R), 행간규칙=lead_rule(cache), 결정도=determinacy(R), 판층예측=loo_table(R))


if __name__ == '__main__':
    caches = [os.path.expanduser(a) for a in sys.argv[1:]] or [OLD, NEW]
    out = {os.path.basename(c.rstrip('/')) or c: run(c) for c in caches}
    json.dump(out, open('docs/rerun_sept.json', 'w'), ensure_ascii=False, indent=1, default=float)
    print('저장 docs/rerun_sept.json')
