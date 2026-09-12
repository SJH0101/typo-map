"""실물 브로크만의 블록 간 세로 간격을 g 단위로 — 합성 템플릿의 간격(1~2g)이 그 안에 드는가.

탐색용 · 사전등록 없음 · 논문 수치 아님. 템플릿과 detect_surya.Y_GAP 을 고치지 않는다.

    python eval/synth_gap_context.py --cache ~/.typo-mcp/brockmann.json --human boxes/human_v2.json \
        --out docs/synth_gap_context.json

두 자료를 나란히 둔다.
  캐시   surya+ground 블록. 묶기(group)를 거친 뒤라 «묶여 버린 틈» 은 여기 없다 — 아래가
         잘린 분포다. 남은 쌍의 틈은 «묶기가 가르는 틈» 의 하한을 보여준다.
  사람   boxes/human_v2.json (송준혁 1인, 26장 · 130개, 브로크만 7장). 묶기와 무관한 틈.
         g 는 그 상자와 겹치는 캐시 블록(IoU ≥ 0.3)의 행간에서 빌린다 — 없으면 px 만 적는다.
쌍의 정의: 가로로 겹치고(좁은 쪽 폭의 15% 넘게, group 의 X_OVER 와 같은 뜻), 아래위로 이웃하며
(둘 사이에 다른 블록이 없음), 아래 상자 y1 ≥ 위 상자 y2 − 2.
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import detect_surya as DS   # noqa: E402  X_OVER · Y_GAP 을 읽기만 한다

X_OVER = DS.X_OVER


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > X_OVER * min(a[2] - a[0], b[2] - b[0])


def _between(u, l, others):
    for o in others:
        if o is u or o is l:
            continue
        if _overlap(o['box'], u['box']) and o['box'][1] >= u['box'][3] - 2 and o['box'][3] <= l['box'][1] + 2:
            return True
    return False


def pairs(items):
    out = []
    for u in items:
        for l in items:
            if l is u or not _overlap(u['box'], l['box']) or l['box'][1] < u['box'][3] - 2:
                continue
            if _between(u, l, items):
                continue
            out.append((u, l))
    return out


def _q(a, ps=(10, 25, 50, 75, 90)):
    a = np.asarray(a, float)
    return {} if a.size == 0 else {p: round(float(np.percentile(a, p)), 2) for p in ps}


def cache_gaps(raw):
    rows = []
    for k, v in raw.items():
        if v.get('skewed'):
            continue
        bl = [dict(box=[b['x1'], b['y1'], b['x2'], b['y2']], b=b) for b in v['blocks'] if b.get('bases')]
        leads = [b['lead'] for b in v['blocks'] if b['n'] >= 3 and b.get('lead')]
        if not leads:
            continue
        g = min(leads)
        for u, l in pairs(bl):
            ub, lb = u['b'], l['b']
            base_gap = lb['bases'][0] - ub['bases'][-1]
            box_gap = lb['y1'] - ub['y2']
            rows.append(dict(poster=k, base_gap_px=base_gap, box_gap_px=box_gap, g=g, base_gap_g=base_gap / g,
                             u_lead=(ub['lead'] if ub['n'] >= 3 else None),
                             base_gap_ulead=(base_gap / ub['lead'] if ub['n'] >= 3 and ub.get('lead') else None),
                             u_xh=ub.get('xh'), box_gap_uxh=(box_gap / ub['xh'] if ub.get('xh') else None)))
    return rows


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i or 1)


def human_gaps(H, raw, corpus='브로크만'):
    rows = []
    for p in H['posters']:
        if corpus and p['corpus'] != corpus:
            continue
        key = next((k for k in raw if k.endswith(p['file'])), None)
        v = raw.get(key) if key else None
        leads = [b['lead'] for b in v['blocks'] if b['n'] >= 3 and b.get('lead')] if v else []
        g = min(leads) if leads else None
        items = [dict(box=b['box']) for b in p['boxes']]
        for u, l in pairs(items):
            box_gap = l['box'][1] - u['box'][3]
            ulead = uxh = None
            if v:
                cand = [(_iou(u['box'], [b['x1'], b['y1'], b['x2'], b['y2']]), b) for b in v['blocks']]
                cand = [c for c in cand if c[0] >= 0.3]
                if cand:
                    b = max(cand, key=lambda c: c[0])[1]
                    ulead = b['lead'] if b['n'] >= 3 else None
                    uxh = b.get('xh')
            rows.append(dict(poster=p['file'], box_gap_px=box_gap, g=g,
                             box_gap_g=(box_gap / g if g else None),
                             box_gap_ulead=(box_gap / ulead if ulead else None),
                             box_gap_uxh=(box_gap / uxh if uxh else None)))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--human', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    raw = json.load(open(os.path.expanduser(a.cache)))['raw']
    H = json.load(open(a.human))
    c = cache_gaps(raw)
    h_b = human_gaps(H, raw, '브로크만')
    h_all = human_gaps(H, raw, None)
    # 템플릿 간격 (베이스라인 사이, g 단위): T→A 4 · A→C 3 · B→E 1 · E→D 2. 상자 사이는 그보다 캡+디센더만큼 작다
    tpl = dict(T_A=4, A_C=3, B_E=1, E_D=2)
    res = dict(
        무엇='실물 블록 간 세로 간격 (g 단위) — 합성 템플릿 간격의 자리 확인',
        용도='탐색용 · 사전등록 없음 · 논문 수치 아님. 템플릿 · Y_GAP 을 고치지 않는다',
        묶기_상수=dict(Y_GAP=list(DS.Y_GAP), X_OVER=DS.X_OVER, H_RATIO=list(DS.H_RATIO)),
        캐시=dict(설명='surya+ground 블록 쌍. 묶기를 거친 뒤라 작은 틈은 이미 합쳐져 없다 (잘린 분포)',
                 판=len({r['poster'] for r in c}), 쌍=len(c),
                 베이스라인_간격_g=_q([r['base_gap_g'] for r in c]),
                 베이스라인_간격_위블록행간=_q([r['base_gap_ulead'] for r in c if r['base_gap_ulead']]),
                 상자_틈_px=_q([r['box_gap_px'] for r in c]),
                 상자_틈_위블록x높이=_q([r['box_gap_uxh'] for r in c if r['box_gap_uxh']]),
                 g_이하_몫=round(float(np.mean([r['base_gap_g'] <= 1.0 for r in c])), 3),
                 _2g_이하_몫=round(float(np.mean([r['base_gap_g'] <= 2.0 for r in c])), 3),
                 _4g_이하_몫=round(float(np.mean([r['base_gap_g'] <= 4.0 for r in c])), 3)),
        사람_브로크만=dict(설명='사람 상자 v2 (송준혁 1인) 브로크만 7장. 묶기와 무관',
                      판=len({r['poster'] for r in h_b}), 쌍=len(h_b),
                      상자_틈_px=_q([r['box_gap_px'] for r in h_b]),
                      상자_틈_g=_q([r['box_gap_g'] for r in h_b if r['box_gap_g'] is not None]),
                      상자_틈_위블록x높이=_q([r['box_gap_uxh'] for r in h_b if r['box_gap_uxh']]),
                      g_있는_쌍=sum(1 for r in h_b if r['box_gap_g'] is not None)),
        사람_4작가=dict(판=len({r['poster'] for r in h_all}), 쌍=len(h_all),
                     상자_틈_px=_q([r['box_gap_px'] for r in h_all]),
                     상자_틈_g=_q([r['box_gap_g'] for r in h_all if r['box_gap_g'] is not None]),
                     상자_틈_위블록x높이=_q([r['box_gap_uxh'] for r in h_all if r['box_gap_uxh']])),
        템플릿=dict(베이스라인_간격_g=tpl,
                  상자_틈_g_어림='베이스라인 간격 − (아래 블록 캡 0.69g + 위 블록 디센더 0.15g) ≈ 간격 − 0.84g: T_A 3.2 · A_C 2.2 · B_E 0.16 · E_D 1.16',
                  상자_틈_x높이_어림='x높이 8 · g 16 기준: T_A 6.3 · A_C 4.3 · B_E 0.3 · E_D 2.3'),
        쌍_캐시=c, 쌍_사람_브로크만=h_b)
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    for k in ('캐시', '사람_브로크만', '사람_4작가'):
        print(k, json.dumps({kk: vv for kk, vv in res[k].items() if kk != '설명'}, ensure_ascii=False))
    print('→', a.out)


if __name__ == '__main__':
    main()
