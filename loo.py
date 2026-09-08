"""파이프라인이 «아무것도 안 재고 하는 것» 보다 나은가 — 283장 leave-one-out.

머리대머리(docs/head_to_head.json)는 증명이 아니었다. 내가 양쪽을 다 짰고,
비교 항목도 내가 골랐고, 판이 한 장이었다.

여기서는 판 하나를 빼고 «내용» 만 준 뒤 배치 값을 맞힌다. 규칙은 나머지
282장에서만 세운다. 항목·비교군·예측은 돌리기 전에 못 박았다
(docs/loo_preregister.json).

    A 중앙값   나머지의 중앙값. 아무것도 안 재는 바닥
    B 통념     교과서 권장값 (행간 1.4em · 마진 10% · 색 3)
    C 규칙     잰 관계를 이 판의 내용에 적용

핵심은 A다. **A를 크게 못 이기면 파이프라인은 값비싼 장식이다.**
"""
import json
import os

import numpy as np

XH_EM = 0.52        # 활자 x높이 ÷ em. 서체의 성질이지 우리 규칙이 아니다
CONV_LEAD_EM = 1.40  # 통념 — 행간은 활자 크기의 1.4배
CONV_MARGIN = 0.10   # 통념 — 여백은 사방 10%
CONV_COLORS = 3      # 통념 — 바탕 · 본문 · 강조


def rows_of(raw, fills=None):
    """원자료 → 한 판마다 필요한 값. 못 재는 판은 빠진다."""
    out = []
    for k, r in raw.items():
        sz, rg = r.get('size'), r.get('region')
        bs = r.get('blocks') or []
        if not sz or not rg or abs(r.get('angle', 0)) >= 1 or len(bs) < 3:
            continue
        W, H = float(sz[0]), float(sz[1])
        if W <= 0 or H <= 0:
            continue
        xh = [b['xh'] for b in bs if b.get('xh')]
        ld = [(b.get('lead_measured') or b.get('lead')) for b in bs
              if (b.get('lead_measured') or b.get('lead')) and b.get('n', 0) >= 3]
        lines = sum((b.get('n') or 0) for b in bs)
        if not xh or lines < 3:
            continue
        wid = [(b['x2'] - b['x1']) / W for b in bs]
        out.append(dict(
            key=k, W=W, H=H,
            xh=float(np.median(xh)) / H,          # 판높이 대비
            lead=(float(np.median(ld)) / H if ld else None),
            폭=float(np.median(wid)),
            줄=int(lines), 덩어리=len(bs),
            좌=rg[0] / W, 우=(W - rg[2]) / W, 상=rg[1] / H, 하=(H - rg[3]) / H,
            색수=float((r.get('color') or {}).get('n_colors') or np.nan),
            참함=(fills or {}).get(k)))
    return out


def _med(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else None


# ── 예측기 ────────────────────────────────────────────────
# A 는 나머지의 중앙값, C 는 나머지에서 «비» 를 잡아 이 판의 내용에 곱한다.

def pred_lead(rest, p, mode):
    if mode == 'A':
        return _med([r['lead'] for r in rest])
    if mode == 'B':
        return CONV_LEAD_EM * p['xh'] / XH_EM      # 통념도 활자 크기를 쓴다
    k = _med([r['lead'] / r['xh'] for r in rest if r['lead'] and r['xh']])
    return None if k is None else k * p['xh']


def pred_xh(rest, p, mode):
    if mode == 'A':
        return _med([r['xh'] for r in rest])
    if mode == 'B':
        return None                                # 통념에 값이 없다
    # 줄이 많으면 작아진다 — 같은 높이에 더 많이 담아야 하므로
    k = _med([r['xh'] * r['줄'] for r in rest])
    return None if k is None else k / p['줄']


def pred_width(rest, p, mode):
    if mode == 'A':
        return _med([r['폭'] for r in rest])
    if mode == 'B':
        return None
    k = _med([r['폭'] / r['xh'] for r in rest if r['xh']])
    return None if k is None else k * p['xh']


def pred_margin(side):
    def f(rest, p, mode):
        if mode == 'B':
            return CONV_MARGIN
        return _med([r[side] for r in rest])        # A 와 C 가 같다 — 규칙이 없다
    return f


def pred_colors(rest, p, mode):
    if mode == 'B':
        return float(CONV_COLORS)
    return _med([r['색수'] for r in rest])


def pred_fill(rest, p, mode):
    if mode == 'B':
        return None
    return _med([r['참함'] for r in rest])


ITEMS = [('행간', 'lead', pred_lead), ('활자크기', 'xh', pred_xh),
         ('덩어리폭', '폭', pred_width),
         ('마진좌', '좌', pred_margin('좌')), ('마진우', '우', pred_margin('우')),
         ('마진상', '상', pred_margin('상')), ('마진하', '하', pred_margin('하')),
         ('색수', '색수', pred_colors), ('줄참함', '참함', pred_fill)]


def run(rows):
    """항목마다 A·B·C 의 오차 분포를 낸다."""
    out = {}
    for name, key, fn in ITEMS:
        err = {m: [] for m in 'ABC'}
        both = []
        for i, p in enumerate(rows):
            t = p.get(key)
            if t is None or not np.isfinite(t):
                continue
            rest = rows[:i] + rows[i + 1:]
            e = {}
            for m in 'ABC':
                q = fn(rest, p, m)
                e[m] = None if q is None else abs(q - t)
                if e[m] is not None:
                    err[m].append(e[m])
            if e.get('A') is not None and e.get('C') is not None:
                both.append(0 if e['C'] == e['A'] else (1 if e['C'] < e['A'] else -1))
        row = dict(n=len(err['A']))
        for m in 'ABC':
            v = np.array(err[m], float)
            row[m] = (None if not len(v) else
                      dict(중앙=float(np.median(v)),
                           사분위=[float(np.percentile(v, 25)), float(np.percentile(v, 75))]))
        if row['A'] and row['C']:
            row['C÷A'] = round(row['C']['중앙'] / max(row['A']['중앙'], 1e-12), 3)
            # 동점을 «졌다» 로 세면 안 된다. C 와 A 가 같은 항목(규칙 없음)에서
            # 부호검정 z 가 −15.9 로 나왔는데 그것은 결과가 아니라 셈의 잘못이다.
            w = sum(1 for x in both if x > 0)
            l = sum(1 for x in both if x < 0)
            t = sum(1 for x in both if x == 0)
            row['C가 더 가까움'] = f'{w}/{w + l}'
            row['동점'] = t
            if w + l:
                n = w + l
                row['부호검정 z'] = round(float((w - n / 2) / np.sqrt(n / 4)), 2)
            else:
                row['부호검정 z'] = None
        out[name] = row
    return out
