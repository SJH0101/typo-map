"""검출기 상자를 참조 상자(사람 v2)와 견준다 — docs/detector_preregister.json 의 정의 그대로.

    python detector_compare.py score   →  docs/detector_compare.json

«정확도» 가 아니라 «참조 상자와의 일치도» 다. 참조는 라벨러 한 명이 그었다.
"""
import hashlib
import json
import os
import random
from collections import Counter

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BOXES = os.path.join(HERE, 'boxes')
OUT = os.path.join(HERE, 'docs', 'detector_compare.json')

IOU_MIN = 0.5      # 1:1 짝으로 인정하는 IoU
INSIDE = 0.5       # «안에 들었다» 로 보는 넓이 몫
TOUCH = 0.1        # «범위 어긋남» 으로 보는 최소 IoU
N_BOOT = 2000
SEED = 20260911
F1_GAP = 0.05      # 사용자 지정 — 이보다 가까우면 재현성으로 고른다

SOURCES = ['EasyOCR', 'Surya', 'VLM']
RUNS = {'EasyOCR': ('easyocr_run1', 'easyocr_run2'),
        'Surya': ('surya_run1', 'surya_run2'),
        'VLM': ('vlm_pass1', 'vlm_pass2')}
LOCAL = {'EasyOCR': True, 'Surya': True, 'VLM': False}


# ── 상자 셈 ───────────────────────────────────────────────────

def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def iou(a, b):
    i = inter(a, b)
    u = area(a) + area(b) - i
    return i / u if u > 0 else 0.0


def held(p, r):
    """r 넓이 중 p 가 덮은 몫."""
    return inter(p, r) / area(r) if area(r) else 0.0


def inside(p, r):
    """p 넓이 중 r 안에 든 몫."""
    return inter(p, r) / area(p) if area(p) else 0.0


def clean(boxes, W, H):
    """판 안으로 자르고 꼭짓점 순서를 맞춘다. 자른 수를 함께 준다."""
    out, cut = [], 0
    for b in boxes:
        x1, y1, x2, y2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        c = (max(0.0, x1), max(0.0, y1), min(float(W), x2), min(float(H), y2))
        if c != (x1, y1, x2, y2):
            cut += 1
        if area(c) > 0:
            out.append(c)
    return out, cut


def match(R, P):
    """IoU 큰 순서로 1:1 탐욕 매칭. {참조 i: 출처 j}, {출처 j: 참조 i}."""
    pairs = sorted(((iou(r, p), i, j) for i, r in enumerate(R) for j, p in enumerate(P)),
                   key=lambda t: -t[0])
    mr, mp = {}, {}
    for v, i, j in pairs:
        if v < IOU_MIN:
            break
        if i in mr or j in mp:
            continue
        mr[i], mp[j] = j, i
    return mr, mp


def classify(R, P, mr, mp):
    pk = {}
    for j, p in enumerate(P):
        if j in mp:
            pk[j] = '맞음'
        elif sum(1 for r in R if held(p, r) >= INSIDE) >= 2:
            pk[j] = '과병합'
        elif any(inside(p, r) >= INSIDE for r in R):
            pk[j] = '과분할 조각'
        elif any(iou(p, r) >= TOUCH for r in R):
            pk[j] = '범위 어긋남'
        else:
            pk[j] = '헛것'
    rk = {}
    for i, r in enumerate(R):
        if i in mr:
            rk[i] = '맞음'
            continue
        merged = any(held(p, r) >= INSIDE and
                     sum(1 for r2 in R if held(p, r2) >= INSIDE) >= 2 for p in P)
        pieces = sum(1 for j, p in enumerate(P) if j not in mp and inside(p, r) >= INSIDE)
        if merged:
            rk[i] = '과병합'
        elif pieces >= 2:
            rk[i] = '과분할'
        elif any(iou(p, r) >= TOUCH for p in P) or pieces == 1:
            rk[i] = '범위 어긋남'
        else:
            rk[i] = '놓침'
    return rk, pk


def dark_bg(gray, r):
    """참조 상자 안이 어두운 바탕인가 — 재는 쪽(measure/ink.polarity)과 같은 판정."""
    from measure import ink
    x1, y1, x2, y2 = [int(round(v)) for v in r]
    sub = gray[max(0, y1):y2, max(0, x1):x2]
    if sub.size == 0:
        return False
    return ink.polarity(sub) is not sub


def tighten(gray, boxes, drop):
    """표 B — measure/region.measure 의 box_ink 로 조인다."""
    from measure import region
    out = []
    for b in boxes:
        m = region.measure(gray, b)
        if m.get('n_lines', 0) > 0:
            x1, y1, x2, y2 = m['box_ink']
            out.append((float(x1), float(y1), float(x2), float(y2)))
        elif not drop:
            out.append(tuple(b))
    return out


# ── 읽기 ──────────────────────────────────────────────────────

def load(name):
    path = os.path.join(BOXES, name + '.json')
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d, {p['file']: p for p in d['posters']}


def _paths():
    import detector_compare as DC
    return {f: p for _c, f, p, _W, _H in DC.posters()}


# ── 채점 ──────────────────────────────────────────────────────

def prf(rows):
    tp = sum(r['tp'] for r in rows)
    nr = sum(r['n_ref'] for r in rows)
    npred = sum(r['n_pred'] for r in rows)
    rec = tp / nr if nr else 0.0
    pre = tp / npred if npred else 0.0
    f1 = 2 * pre * rec / (pre + rec) if pre + rec else 0.0
    return rec, pre, f1


def score(ref, pred, grays, table):
    rows, rk_all, pk_all = [], Counter(), Counter()
    miss_bg, ref_bg, ious, cut = Counter(), Counter(), [], 0
    for f, rp in ref.items():
        W, H = rp['img_w'], rp['img_h']
        g = grays[f]
        R, _ = clean([b['box'] for b in rp['boxes']], W, H)
        P, c = clean([b['box'] for b in pred[f]['boxes']] if f in pred else [], W, H)
        cut += c
        if table == 'B':
            R = tighten(g, R, drop=False)
            P = tighten(g, P, drop=True)
        mr, mp = match(R, P)
        rk, pk = classify(R, P, mr, mp)
        for i, r in enumerate(R):
            bg = '어두운 바탕' if dark_bg(g, r) else '밝은 바탕'
            ref_bg[bg] += 1
            if rk[i] == '놓침':
                miss_bg[bg] += 1
        rk_all.update(rk.values())
        pk_all.update(pk.values())
        ious += [iou(R[i], P[j]) for i, j in mr.items()]
        rows.append(dict(file=f, corpus=rp['corpus'], tp=len(mr), n_ref=len(R), n_pred=len(P)))
    rec, pre, f1 = prf(rows)
    by_corpus = {}
    for c in sorted({r['corpus'] for r in rows}):
        _r, _p, _f = prf([r for r in rows if r['corpus'] == c])
        by_corpus[c] = dict(재현율=round(_r, 3), 정밀도=round(_p, 3), F1=round(_f, 3),
                            장=sum(1 for r in rows if r['corpus'] == c))
    return dict(
        재현율=round(rec, 3), 정밀도=round(pre, 3), F1=round(f1, 3),
        맞은짝=sum(r['tp'] for r in rows), 참조상자=sum(r['n_ref'] for r in rows),
        출처상자=sum(r['n_pred'] for r in rows),
        장당상자=round(sum(r['n_pred'] for r in rows) / len(rows), 2),
        맞은짝_IoU_중앙값=(round(float(np.median(ious)), 3) if ious else None),
        참조쪽=dict(rk_all), 출처쪽=dict(pk_all),
        놓침_바탕=dict(miss_bg), 참조_바탕=dict(ref_bg),
        판밖으로_자른_상자=cut, 코퍼스별=by_corpus), rows


def boot(rows_by, seed=SEED):
    """포스터를 다시 뽑아 F1 구간과 출처 쌍의 F1 차이 구간."""
    names = list(rows_by)
    files = [r['file'] for r in rows_by[names[0]]]
    idx = {n: {r['file']: r for r in rows_by[n]} for n in names}
    rng = random.Random(seed)
    f1s = {n: [] for n in names}
    diffs = {(a, b): [] for i, a in enumerate(names) for b in names[i + 1:]}
    for _ in range(N_BOOT):
        pick = [files[rng.randrange(len(files))] for _ in files]
        v = {n: prf([idx[n][f] for f in pick])[2] for n in names}
        for n in names:
            f1s[n].append(v[n])
        for a, b in diffs:
            diffs[(a, b)].append(v[a] - v[b])
    q = lambda xs: [round(float(np.percentile(xs, 2.5)), 3), round(float(np.percentile(xs, 97.5)), 3)]
    return ({n: q(x) for n, x in f1s.items()},
            {f'{a} − {b}': q(x) for (a, b), x in diffs.items()})


def repeat(a, b):
    """같은 출처의 두 번. 첫째를 참조 삼아 같은 매칭으로 견준다."""
    rows, same = [], 0
    for f, pa in a.items():
        W, H = pa['img_w'], pa['img_h']
        A, _ = clean([x['box'] for x in pa['boxes']], W, H)
        B, _ = clean([x['box'] for x in b[f]['boxes']] if f in b else [], W, H)
        mr, _ = match(A, B)
        rows.append(dict(tp=len(mr), n_ref=len(A), n_pred=len(B)))
        if len(A) == len(B) and all(
                any(max(abs(u - v) for u, v in zip(x, y)) <= 1.0 for y in B) for x in A):
            same += 1
    return dict(F1=round(prf(rows)[2], 3), 똑같은_장=same, 장=len(rows))


def choose(table_a, rep):
    f1 = {s: table_a[s]['F1'] for s in table_a}
    order = sorted(f1, key=lambda s: -f1[s])
    best = order[0]
    if len(order) > 1 and f1[best] - f1[order[1]] > F1_GAP:
        return best, f'F1 차이 {f1[best] - f1[order[1]]:.3f} > {F1_GAP} — 일치도가 높은 쪽'
    near = [s for s in order if f1[best] - f1[s] <= F1_GAP]
    local = [s for s in near if LOCAL[s]] or near
    pick = sorted(local, key=lambda s: (-(rep.get(s) or {}).get('F1', -1), -f1[s]))[0]
    return pick, (f'최고 F1 에서 {F1_GAP} 안: {near} — 로컬·버전 고정 {local} 중 '
                  f'실행 간 일치가 높은 쪽')


def main():
    ref_doc, ref = load('human_v2')
    paths = _paths()
    grays = {f: np.asarray(Image.open(paths[f]).convert('L')).astype(float) for f in ref}
    out = dict(무엇='검출기 셋과 참조 상자(사람 v2, 라벨러 한 명)의 일치도 — 정확도가 아니다',
               사전등록='docs/detector_preregister.json',
               사전등록_sha256=hashlib.sha256(open(os.path.join(HERE, 'docs', 'detector_preregister.json'), 'rb').read()).hexdigest(),
               사전등록_커밋='정의는 실행 전 같은 세션에서 작성했으나 커밋은 실행 후에 했다',
               참조=ref_doc['source'], 출처={}, 표A={}, 표B={}, 재현성={})
    rows_a = {}
    for s in SOURCES:
        got = load(RUNS[s][0])
        if not got:
            out['출처'][s] = '파일 없음'
            continue
        doc, pred = got
        out['출처'][s] = doc['source']
        out['표A'][s], rows_a[s] = score(ref, pred, grays, 'A')
        out['표B'][s], _ = score(ref, pred, grays, 'B')
        second = load(RUNS[s][1])
        out['재현성'][s] = repeat(pred, second[1]) if second else None
    if len(rows_a) >= 2:
        out['F1_구간'], out['F1_차이_구간'] = boot(rows_a)
    out['선택'], out['선택_이유'] = choose(out['표A'], out['재현성'])
    ob, _ = choose(out['표B'], out['재현성'])
    out['표B로_골랐다면'] = ob
    out['표AB_엇갈림'] = ob != out['선택']
    second = load('vlm_pass2')
    if second:
        p2, _ = score(ref, second[1], grays, 'A')
        out['추가_사전등록밖'] = dict(
            무엇='VLM 둘째 패스를 참조에 댄 값 — 사전등록은 첫째만 채점에 쓰기로 했다. 선택에는 쓰지 않는다',
            VLM_pass2_표A=p2,
            VLM_pass1_에이전트_자기보고='164개라고 보고했으나 파일에는 127개 — 파일 값을 썼다')
    json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
    for t in ('표A', '표B'):
        print(f'\n{t}')
        for s, v in out[t].items():
            print(f"  {s:8s} R {v['재현율']:.3f}  P {v['정밀도']:.3f}  F1 {v['F1']:.3f}  "
                  f"장당 {v['장당상자']:5.2f}  IoU {v['맞은짝_IoU_중앙값']}  "
                  f"참조쪽 {v['참조쪽']}  출처쪽 {v['출처쪽']}  놓침바탕 {v['놓침_바탕']}")
    print('\n재현성', out['재현성'])
    print('F1 구간', out.get('F1_구간'), '\n차이 구간', out.get('F1_차이_구간'))
    print('선택', out['선택'], '—', out['선택_이유'], '| 표B로는', ob)
    print('→', OUT)
