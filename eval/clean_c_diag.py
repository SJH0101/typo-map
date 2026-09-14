"""깨끗한 세트 C 과분할 진단 — 사전등록 docs/clean_c_diag_preregister.json (9298cef).

    python eval/clean_c_diag.py --dir ~/.typo-mcp/clean --manifest docs/clean_manifest.json \\
        --lines ~/.typo-mcp/clean-lines.json --result docs/clean_result.json \\
        --prereg docs/clean_c_diag_preregister.json --out docs/clean_c_diag.json

원인 파악용 진단 · C 조정 근거 아님. group_gap 의 elements · chains · runs · _owners 를 group_gap.group_gap 과 같은
인자로 불러 요소마다 (사슬, run) 을 다시 만든다. 280장 모두 줄 소속 · 출처가 group_gap.group_gap 출력과 같고
C 과분할 블록 수가 docs/clean_result.json 과 같을 때만 진단을 적는다. C 의 정의 · 문턱은 부르기만 한다.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import group_gap as GG      # noqa: E402
import group_score as GS    # noqa: E402

LEVELS = list(GS.CLEAN_LEVELS)
MIN_CELL = 20                # 정답 블록이 이보다 적은 칸은 비율을 적지 않는다 (사전등록 ①)


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def trace(gray, lines, pad_rule):
    """group_gap.group_gap 을 같은 함수로 다시 밟으며 중간값을 남긴다."""
    tau = GG.TAU
    els, per_line = GG.elements(gray, lines, pad_rule)
    chs = GG.chains(els, tau)
    # 앞 요소 후보 · 차지 — GG.chains 안의 식과 같다. 아래에서 사슬을 다시 엮어 GG.chains 출력과 대조한다
    order = sorted(range(len(els)), key=lambda k: (els[k]['b'], els[k]['xs']))
    pred = {}
    for k in order:
        e = els[k]; best = None
        for q in order:
            p = els[q]
            if e['b'] - p['b'] <= tau:
                break
            ov = GG._xover(e, p)
            if ov is None:
                continue
            key = (p['b'], ov)
            if best is None or key > best[0]:
                best = (key, q, ov)
        if best is not None:
            pred[k] = (best[1], best[2])
    claim = {}
    for k, (q, ov) in pred.items():
        cand = (ov, -els[k]['b'], -els[k]['xs'])
        if q not in claim or cand > claim[q][0]:
            claim[q] = (cand, k)
    succ = {q: k for q, (_c, k) in claim.items()}
    linked = set(succ.values())
    rebuilt = []
    for k in order:
        if k in linked:
            continue
        ch = [k]
        while ch[-1] in succ:
            ch.append(succ[ch[-1]])
        rebuilt.append(ch)
    stats = Counter(); info = {}; blk = {}; meta = []
    for ci, ch in enumerate(chs):
        b = [els[k]['b'] for k in ch]
        gaps = [b[i + 1] - b[i] for i in range(len(b) - 1)]
        rs = GG.runs(gaps, tau)
        pat = [r for r, (s, e) in enumerate(rs) if e - s + 1 >= 2]
        own = GG._owners(ch, els, tau, stats)
        meta.append(dict(gaps=gaps, rs=rs))
        for pos, (k, r) in enumerate(zip(ch, own)):
            info[k] = dict(chain=ci, pos=pos, run=r, cov=[q for q in pat if rs[q][0] <= pos <= rs[q][1] + 1])
            blk[k] = None if r is None else (ci, r)
    by_line = defaultdict(Counter)
    for k, e in enumerate(els):
        by_line[e['line']][blk.get(k)] += 1
    n = len(lines)
    asg, src, key_of, ids, leftover = [None] * n, [None] * n, [None] * n, {}, []
    for i in range(n):
        c = by_line.get(i)
        pats = [(m, key) for key, m in (c or {}).items() if key is not None]
        if pats:
            m, key = max(pats, key=lambda t: (t[0], -t[1][0], -t[1][1]))
            if m >= c.get(None, 0):
                asg[i] = ids.setdefault(key, len(ids)); src[i] = 'C'; key_of[i] = key
                continue
        leftover.append(i)
    if leftover:
        sub = [lines[i] for i in leftover]
        boxes = [bb[:4] for bb in GG.DS.group(sub)]
        for i, box in zip(leftover, sub):
            best, bv = None, 0.0
            for j, bb in enumerate(boxes):
                v = GG._overlap(box, bb)
                if v > bv:
                    best, bv = j, v
            if best is not None:
                asg[i] = len(ids) + best; src[i] = 'A'
    return dict(els=els, per_line=per_line, chains=chs, chains_rebuilt_same=(sorted(map(tuple, rebuilt)) == sorted(map(tuple, chs))),
                pred=pred, succ=succ, info=info, blk=blk, meta=meta, asg=asg, src=src, key_of=key_of)


def a_subtype(T, x):
    ks = [k for k, e in enumerate(T['els']) if e['line'] == x]
    if not ks:
        return 'a 요소 없음'
    if any(T['blk'][k] is not None for k in ks):
        return 'd 패턴 요소가 None 보다 적음'
    if any(len(T['info'][k]['cov']) >= 2 for k in ks):
        return 'c 공유 자리 가르지 못함'
    return 'b 패턴 run 에 안 덮임'


def deciding(T, i):
    ks = [k for k, e in enumerate(T['els']) if e['line'] == i and T['blk'][k] == T['key_of'][i]]
    return min(ks, key=lambda k: T['els'][k]['b'])


def truth_base(t, e):
    best = None
    for tb in t['blocks']:
        for li, ln in enumerate(tb['lines']):
            if min(e['xe'], ln['ink_box'][2]) - max(e['xs'], ln['ink_box'][0]) <= 0:
                continue
            d = e['b'] - ln['baseline_y']
            if best is None or abs(d) < abs(best[0]):
                best = (d, tb['id'], li)
    return None if best is None else dict(차=round(best[0], 2), 블록=best[1], 줄=best[2])


def box_info(t, box):
    ins = sum(1 for tb in t['blocks'] for ln in tb['lines']
              if box[1] <= (ln['ink_box'][1] + ln['ink_box'][3]) / 2 <= box[3]
              and min(box[2], ln['ink_box'][2]) - max(box[0], ln['ink_box'][0]) > 0)
    return dict(높이=round(box[3] - box[1], 1), 든_정답줄=ins)


def classify(T, t, lines, i, j):
    src = T['src']; els = T['els']; info = T['info']
    row = dict(줄=[i, j], 상자=[box_info(t, lines[i]), box_info(t, lines[j])])
    if src[i] == 'A' or src[j] == 'A':
        sides = {'위': (a_subtype(T, i) if src[i] == 'A' else 'C'), '아래': (a_subtype(T, j) if src[j] == 'A' else 'C')}
        det = {}
        for side, x in (('위', i), ('아래', j)):
            if src[x] != 'A':
                continue
            items = []
            for k in (k for k, e in enumerate(els) if e['line'] == x):   # 출처 A 인 줄은 요소 전부 (사전등록 ②)
                inf = info[k]; m = T['meta'][inf['chain']]; pos = inf['pos']
                win = m['gaps'][max(0, pos - 3):pos + 3]
                items.append(dict(b=els[k]['b'], xh=round(els[k]['xh'], 2), 정답=truth_base(t, els[k]), 사슬_길이=len(m['gaps']) + 1,
                                  자리=pos, 간격_창=win, 창_최대_최소=(max(win) - min(win) if win else None), 덮은_패턴_run=len(inf['cov'])))
            det[side] = items
        row.update(분류='1 A 폴백', 하위=sides, 양쪽_A=(src[i] == src[j] == 'A'), A_줄_요소=det)
        return row
    ki, kj = deciding(T, i), deciding(T, j)
    if els[ki]['b'] > els[kj]['b']:
        ki, kj = kj, ki
    row['요소'] = [dict(b=els[k]['b'], xh=round(els[k]['xh'], 2), 정답=truth_base(t, els[k])) for k in (ki, kj)]
    ci, cj = info[ki]['chain'], info[kj]['chain']
    if ci != cj:
        if kj not in T['pred']:
            s = 'a 앞 요소 후보 없음'
        elif T['pred'][kj][0] != ki:
            q = T['pred'][kj][0]
            s = 'b 앞 요소 후보가 다른 요소' + (' (위 줄의 다른 요소)' if els[q]['line'] == els[ki]['line'] else '')
        elif T['succ'].get(ki) != kj:
            s = 'c 차지 경쟁'
        else:
            s = 'd 기타'
        row.update(분류='2 사슬 끊김', 하위=s)
        return row
    ri, rj = info[ki]['run'], info[kj]['run']
    if ri == rj:
        row.update(분류='5 기타', 하위='같은 (사슬, run) 인데 다른 묶음')
        return row
    m = T['meta'][ci]; gaps, rs = m['gaps'], m['rs']
    pi, pj = info[ki]['pos'], info[kj]['pos']
    row['간격_창'] = gaps[max(0, pi - 3):pj + 3]
    if len(info[ki]['cov']) >= 2 or len(info[kj]['cov']) >= 2:
        row.update(분류='3 공유 요소 판정', 하위='위 요소 공유' if len(info[ki]['cov']) >= 2 else '아래 요소 공유')
        return row
    s, e = rs[ri]
    ext = gaps[s:e + 2]
    row.update(분류='4 run 끊김', 하위='run 끝난 뒤 간격이 τ 밖',
               끝난_run_간격=gaps[s:e + 1], 끝낸_간격=(gaps[e + 1] if e + 1 < len(gaps) else None),
               넣었을_때_최대_최소=(max(ext) - min(ext) if e + 1 < len(gaps) else None))
    return row


def block_measure(T, tb, s, over):
    """탐색 (사전등록 밖): 정답 줄마다 가로로 겹치고 베이스라인이 ±3px 안인 가장 가까운 요소의 b 로 블록 안 간격을 잰다."""
    els = T['els']; bs = []
    for ln in tb['lines']:
        c = [(abs(e['b'] - ln['baseline_y']), e['b']) for e in els
             if min(e['xe'], ln['ink_box'][2]) - max(e['xs'], ln['ink_box'][0]) > 0 and abs(e['b'] - ln['baseline_y']) <= 3]
        bs.append(min(c)[1] if c else None)
    gaps = [b2 - b1 for b1, b2 in zip(bs, bs[1:]) if b1 is not None and b2 is not None]
    return dict(xh=s[1], over=int(over), 다_잡음=(None not in bs), 간격_최대_최소=(max(gaps) - min(gaps) if len(gaps) >= 2 else None),
                정답_베이스라인_소수=round(tb['lines'][0]['baseline_y'] % 1, 2),
                잰_b_빼기_정답=[None if b is None else round(b - ln['baseline_y'], 2) for b, ln in zip(bs, tb['lines'])])


def explore(bm):
    out = dict(설명='결과를 본 뒤 더한 기술 통계 — 사전등록 밖, 탐색용. 정답 줄에 가장 가까운 요소 베이스라인으로 잰 블록 안 간격의 최대 − 최소, '
                  '그리고 정답 첫 베이스라인의 소수 자리(블록 안 행간이 정수 px 라 블록 안에서 같다)별 C 과분할률')
    for x in (5, 8, 12):
        sub = [b for b in bm if b['xh'] == x]
        spread = lambda o: [b['간격_최대_최소'] for b in sub if b['over'] == o and b['간격_최대_최소'] is not None]
        fr = defaultdict(lambda: [0, 0])
        for b in sub:
            fr[b['정답_베이스라인_소수']][0] += b['over']; fr[b['정답_베이스라인_소수']][1] += 1
        diffs = Counter(d for b in sub for d in b['잰_b_빼기_정답'] if d is not None)
        out[str(x)] = dict(블록=len(sub), 간격_최대_최소_과분할=q(spread(1)), 간격_최대_최소_그외=q(spread(0)),
                           정답_소수별_과분할={str(k): dict(과분할=v[0], 블록=v[1], 비율=round(v[0] / v[1], 3)) for k, v in sorted(fr.items())},
                           잰_b_빼기_정답_전체=dict(sorted(diffs.items())))
    return out


def _rate(over, tot):
    return round(over / tot, 4) if tot >= MIN_CELL else None


def table(blocks, keyfn):
    c = defaultdict(lambda: [0, 0])
    for b in blocks:
        for k in keyfn(b):
            c[k][0] += b['over']; c[k][1] += 1
    return {str(k): dict(과분할=v[0], 정답블록=v[1], 과분할률=_rate(*v)) for k, v in sorted(c.items(), key=lambda kv: str(kv[0]))}


def q(v):
    v = [x for x in v if x is not None]
    if not v:
        return dict(n=0)
    return dict(n=len(v), 최소=round(float(np.min(v)), 2), 중앙=round(float(np.median(v)), 2), 최대=round(float(np.max(v)), 2),
                값별=dict(sorted(Counter(round(float(x), 2) for x in v).items())))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True); ap.add_argument('--manifest', required=True); ap.add_argument('--lines', required=True)
    ap.add_argument('--result', required=True, help='docs/clean_result.json — C 과분할 블록 수 대조')
    ap.add_argument('--prereg', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--c-pad-rule', default='neighbor_half', choices=GG.PAD_RULES)
    a = ap.parse_args(argv)
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    L = json.load(open(os.path.expanduser(a.lines)))['lines']
    R = json.load(open(a.result))
    expected = sum(v['과분할'] for v in R['줄단위_재기']['C_과분할_네칸_합계'].values())
    res = dict(무엇='깨끗한 세트 C 과분할 원인 진단', 성격='원인 파악용 진단 · C 조정 근거 아님 (C 의 정의 · 문턱 · 파라미터를 바꾸지 않았다)',
               사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg), manifest=a.manifest, manifest_sha256=_sha(a.manifest),
               참조결과=a.result, 참조결과_sha256=_sha(a.result), group_gap_sha256=_sha(os.path.join(ROOT, 'group_gap.py')),
               pad_rule=a.c_pad_rule, tau=GG.TAU, 정의=dict(
                   C_과분할_블록='정답 블록의 Surya 줄(오라클 소속)이 C 묶음 둘 이상에 흩어진 블록',
                   갈린_자리='그 블록 안에서 y 순으로 이웃한 (묶음이 있는) 두 Surya 줄이 다른 C 묶음에 든 자리',
                   분류_순서='1 A 폴백 → 2 사슬 끊김 → 3 공유 요소 판정 → 4 run 끊김 → 5 기타',
                   정답_베이스라인='요소와 가로로 겹치는 정답 줄 가운데 잰 베이스라인과 가장 가까운 줄. 차 = 잰 b − 정답 baseline_y (정답은 연속 좌표 — 평평한 글자 바닥이 행 baseline_y−1 에서 끝난다). 좌표 약속을 맞추지 않은 날 차이라 절댓값보다 자리 사이 차이를 본다'))
    blocks, rows, mismatch, blocks_meas = [], [], [], []
    for it in M['items']:
        k = str(it['seed']); p = os.path.join(D, it['image'])
        if _sha(p) != it['image_sha256'] or L[k]['sha256'] != it['image_sha256']:
            sys.exit(f'manifest 와 다른 이미지 또는 줄 캐시: {p}')
        t = json.load(open(p[:-4] + '.json')); lines = L[k]['lines']
        g = np.asarray(Image.open(p).convert('L')).astype(float)
        T = trace(g, lines, a.c_pad_rule)
        ref_asg, ref_d = GG.group_gap(g, lines, pad_rule=a.c_pad_rule)
        if T['asg'] != ref_asg or T['src'] != ref_d['source'] or not T['chains_rebuilt_same']:
            mismatch.append(k); continue
        s = (t['condition']['columns'], t['condition']['xh_px_at_800'])
        orc = GS.groups_oracle(lines, t)
        lower_of = {q_['lower']: q_['level'] for q_ in t['pairs']}
        upper_of = {q_['upper']: q_['level'] for q_ in t['pairs']}
        for bi, tb in enumerate(t['blocks']):
            mine = sorted((i for i, o in enumerate(orc) if o == bi), key=lambda i: (lines[i][1], lines[i][0]))
            seq = [i for i in mine if T['asg'][i] is not None]
            over = len({T['asg'][i] for i in seq}) >= 2
            up, dn = lower_of.get(tb['id']), upper_of.get(tb['id'])
            near = min([v for v in (up, dn) if v is not None], key=LEVELS.index, default=None)
            blocks.append(dict(seed=int(k), 층=GS._sname(s), 단=s[0], xh=s[1], n=tb['n'], 위_쌍=up or '없음', 아래_쌍=dn or '없음',
                               좁은_쌍=near or '없음', over=int(over), 블록=tb['id']))
            blocks_meas.append(block_measure(T, tb, s, over))
            if not over:
                continue
            for i, j in zip(seq, seq[1:]):
                if T['asg'][i] != T['asg'][j]:
                    row = classify(T, t, lines, i, j)
                    row.update(seed=int(k), 층=GS._sname(s), xh=s[1], 블록=tb['id'], n=tb['n'])
                    rows.append(row)
    n_over = sum(b['over'] for b in blocks)
    res['재구성_검증'] = dict(장=len(M['items']), 다른_장=mismatch, 통과=not mismatch)
    res['대상_수'] = dict(다시_센_C_과분할_블록=n_over, 참조결과=expected, 같음=(n_over == expected))
    if mismatch or n_over != expected or any(r['분류'] == '5 기타' for r in rows):
        res['멈춤'] = '재구성이 group_gap 과 다르거나 대상 수가 다르거나 «5 기타» 가 나왔다 — 진단을 적지 않는다 (사전등록 ②)'
        res['기타_자리'] = [r for r in rows if r['분류'] == '5 기타'][:20]
        json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
        print(json.dumps({k: res[k] for k in ('재구성_검증', '대상_수', '멈춤')}, ensure_ascii=False, indent=1))
        sys.exit(1)
    res['① 분해'] = dict(
        층=table(blocks, lambda b: [b['층']]), 단_수=table(blocks, lambda b: [b['단']]), x높이=table(blocks, lambda b: [b['xh']]),
        x높이_단순평균={str(x): (round(float(np.mean(v)), 4) if v else None) for x in (5, 8, 12)
                     for v in [[b_['과분할률'] for s_, b_ in table(blocks, lambda b: [b['층']]).items()
                                if s_.endswith(f'·{x}px') and b_['과분할률'] is not None]]},
        블록_줄수=table(blocks, lambda b: [b['n']]), 층_블록_줄수=table(blocks, lambda b: [(b['층'], b['n'])]),
        위_쌍_수준=table(blocks, lambda b: [b['위_쌍']]), 아래_쌍_수준=table(blocks, lambda b: [b['아래_쌍']]),
        좁은_쌍_수준=table(blocks, lambda b: [b['좁은_쌍']]), x높이_좁은_쌍_수준=table(blocks, lambda b: [(b['xh'], b['좁은_쌍'])]),
        이웃_쌍_수준_분모='그 수준의 쌍을 위(또는 아래)에 가진 정답 블록. «없음» 은 단의 첫(마지막) 블록',
        비율을_적지_않은_칸=f'정답 블록 < {MIN_CELL}')
    by = defaultdict(Counter); sub = defaultdict(Counter); blk_cat = defaultdict(set)
    for r in rows:
        by[str(r['xh'])][r['분류']] += 1
        hs = r['하위'] if isinstance(r['하위'], str) else ' · '.join(f'{k_} {v_}' for k_, v_ in r['하위'].items())
        sub[str(r['xh'])][f"{r['분류']} | {hs}"] += 1
        blk_cat[(r['seed'], r['블록'])].add(r['분류'])
    xh_of = {(b['seed'], b['블록']): b['xh'] for b in blocks}
    blocks_by = defaultdict(Counter)
    for key, cats in blk_cat.items():
        for c in cats:
            blocks_by[str(xh_of[key])][c] += 1
    runs_ = [r for r in rows if r['분류'] == '4 run 끊김']
    res['② 단계'] = dict(
        갈린_자리=len(rows), 과분할_블록=len(blk_cat),
        자리_분류_x높이={x: dict(v) for x, v in sorted(by.items())},
        자리_하위_x높이={x: dict(sorted(v.items())) for x, v in sorted(sub.items())},
        블록_분류_x높이={x: dict(v) for x, v in sorted(blocks_by.items())},
        블록_분류_세는_법='한 블록에 여러 분류의 자리가 있으면 분류마다 한 번씩 센다')
    res['③ run 끊김'] = {str(x): dict(
        자리=sum(1 for r in runs_ if r['xh'] == x),
        넣었을_때_최대_최소=q([r['넣었을_때_최대_최소'] for r in runs_ if r['xh'] == x]),
        끝난_run_간격=q([g_ for r in runs_ if r['xh'] == x for g_ in r['끝난_run_간격']]),
        끝낸_간격=q([r['끝낸_간격'] for r in runs_ if r['xh'] == x]),
        잰_b_빼기_정답=q([e['정답']['차'] for r in runs_ if r['xh'] == x for e in r['요소'] if e['정답']]),
        상자_높이=q([bx['높이'] for r in runs_ if r['xh'] == x for bx in r['상자']]),
        두_정답줄_이상_덮은_상자=sum(1 for r in runs_ if r['xh'] == x for bx in r['상자'] if bx['든_정답줄'] >= 2))
        for x in (5, 8, 12)}
    afb = [r for r in rows if r['분류'] == '1 A 폴백']
    ael = lambda x: [e for r in afb if r['xh'] == x for side in r['A_줄_요소'].values() for e in side]
    res['③ A 폴백'] = {str(x): dict(
        자리=sum(1 for r in afb if r['xh'] == x),
        요소=len(ael(x)),
        간격_창_최대_최소=q([e['창_최대_최소'] for e in ael(x)]),
        잰_b_빼기_정답=q([e['정답']['차'] for e in ael(x) if e['정답']]),
        사슬_길이=q([e['사슬_길이'] for e in ael(x)]),
        A_줄_상자_높이=q([r['상자'][0 if s_ == '위' else 1]['높이'] for r in afb if r['xh'] == x for s_ in r['A_줄_요소']]),
        두_정답줄_이상_덮은_A_줄_상자=sum(1 for r in afb if r['xh'] == x for s_ in r['A_줄_요소']
                                  if r['상자'][0 if s_ == '위' else 1]['든_정답줄'] >= 2))
        for x in (5, 8, 12)}
    res['탐색 (사전등록 밖, 결과를 본 뒤 더함)'] = explore(blocks_meas)
    res['③ 사슬 끊김'] = {str(x): dict(Counter(r['하위'] for r in rows if r['분류'] == '2 사슬 끊김' and r['xh'] == x)) for x in (5, 8, 12)}
    top8 = blocks_by.get('8', Counter()).most_common()
    res['요약'] = dict(x높이_8_블록_분류=top8, x높이_8_자리_분류=by.get('8', Counter()).most_common(),
                     읽는_법='원인 후보로만 읽는다. 고칠 방법은 제안하지 않는다 (사전등록 ③)')
    res['자리'] = rows
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('재구성_검증', '대상_수', '② 단계', '요약')}, ensure_ascii=False, indent=1))
    print('→', a.out)


if __name__ == '__main__':
    main()
