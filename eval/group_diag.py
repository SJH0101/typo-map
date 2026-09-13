"""묶기 비교 진단 — 탐색용 · 사전등록 밖 · 논문 수치 아님.

docs/group_result.json 에서 사전등록과 어긋난 두 가지를 가른다. 채점 정의는 바꾸지 않는다.
  (1) A 가 크기 비 2.5 쌍을 병합한 것 — Surya 줄 상자가 두 블록에 걸쳤나 / group 이 묶었나 / 소속 배정 탓인가
  (2) 크기 비 1.5 · 2.5 병합률을 방향(큰→작은 / 작은→큰)으로 가른 것 — g 를 위 블록 행간으로 잡았으므로
      같은 «Ng» 라도 방향에 따라 눈에 보이는 틈이 다르다
  (3) 오라클 상한 — Surya 줄이 하나라도 배정된 정답 블록의 몫, 오라클 과병합 가운데 걸친 줄로 설명되는 몫
  (4) 방식 C 가 등크기 1g 쌍을 가른 원인 — 사전등록 수정 1 의 예측(병합 ≥ 0.90)이 틀린 자리. 원인을
      차례로 가른다: 두 블록의 Surya 줄 가운데 줄 단위 재기가 줄을 늘리거나 뺀 것이 있나 → 위 블록 끝 요소와
      아래 블록 첫 요소가 다른 세로 사슬인가 → 경계 간격이 위 블록 안쪽 행간과 τ 넘게 다른가 → 기타

    python eval/group_diag.py --dir D --manifest M --lines L --vlm V1 --vlm V2 --out docs/group_diag.json
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import detect_surya as DS        # noqa: E402
import detector_score as DSc     # noqa: E402
import group_score as GS         # noqa: E402

SPAN = 0.25     # 줄 상자 넓이의 이 몫 넘게 두 정답 블록 각각에 들면 «두 블록에 걸친 줄»


def decisions(lines, t, asg):
    orc = GS.groups_oracle(lines, t)
    by = defaultdict(list)
    for i, j in enumerate(orc):
        if j is not None:
            by[j].append(i)
    idx = {tb['id']: i for i, tb in enumerate(t['blocks'])}
    out = []
    for q in t['pairs']:
        u, l = idx[q['upper']], idx[q['lower']]
        gu = Counter(asg[i] for i in by.get(u, []) if asg[i] is not None)
        gl = Counter(asg[i] for i in by.get(l, []) if asg[i] is not None)
        dec = None if not gu or not gl else gu.most_common(1)[0][0] == gl.most_common(1)[0][0]
        mu, ml = t['blocks'][u]['xh_mult'], t['blocks'][l]['xh_mult']
        d = '같음' if mu == ml else ('큰→작은' if mu > ml else '작은→큰')
        out.append(dict(q=q, u=u, l=l, merged=dec, dir=d))
    return out, by


def spans(lines, T, u, l):
    return any(DSc.inside(ln, T[u]) > SPAN and DSc.inside(ln, T[l]) > SPAN for ln in lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True); ap.add_argument('--manifest', required=True)
    ap.add_argument('--lines', required=True); ap.add_argument('--vlm', action='append', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    L = json.load(open(os.path.expanduser(a.lines)))['lines']
    V = [GS.load_vlm(v)[0] for v in a.vlm]
    items = GS._items(D, M)
    truths = {k: json.load(open(p[:-4] + '.json')) for k, p, it in items}

    why = Counter(); ceil = Counter(); orc_merge = Counter()
    rates = defaultdict(lambda: defaultdict(list))   # method → (level, ratio, dir) → [merged]
    for k, p, it in items:
        lines = L[k]['lines']; t = truths[k]
        T = [tb['ink_box'] for tb in t['blocks']]
        blocks = DS.group(lines)
        boxes = [b[:4] for b in blocks]
        methods = {'A': GS.groups_A(lines)}
        if it.get('vlm_subset'):
            for i, vm in enumerate(V, 1):
                methods[f'VLM{i}'] = GS.groups_vlm(lines, vm.get(k))[0]
        for name, asg in methods.items():
            dec, by = decisions(lines, t, asg)
            for d in dec:
                if d['merged'] is None:
                    continue
                if name == 'A' and not it.get('vlm_subset'):
                    pass
                key = (d['q']['gap_level'], d['q']['size_ratio'], d['dir'])
                if name != 'A' or it.get('vlm_subset'):
                    rates[name if name != 'A' else 'A120'][key].append(d['merged'])
                if name == 'A':
                    rates['A240'][key].append(d['merged'])
                if name == 'A' and d['merged'] and d['q']['size_ratio'] == 2.5:
                    u, l = d['u'], d['l']
                    if spans(lines, T, u, l):
                        why['Surya 줄이 두 블록에 걸침'] += 1
                    elif any(DSc.held(b, T[u]) >= 0.5 and DSc.held(b, T[l]) >= 0.5 for b in boxes):
                        why['group 이 두 블록을 한 상자로 묶음'] += 1
                    else:
                        why['소속 배정 (줄이 이웃 상자와 더 겹침)'] += 1
                    why['간격_' + str(d['q']['gap_level'])] += 1
        # 오라클 상한
        orc = GS.groups_oracle(lines, t)
        got = {j for j in orc if j is not None}
        ceil['정답블록'] += len(T); ceil['줄이_하나라도'] += len(got)
        if it.get('vlm_subset'):
            ceil['정답블록_120'] += len(T); ceil['줄이_하나라도_120'] += len(got)
        for j, bx in GS.boxes_of(lines, orc):
            hit = [r for r, tb in enumerate(T) if DSc.held(bx[:4], tb) >= DSc.INSIDE]
            if len(hit) >= 2:
                orc_merge['과병합'] += 1
                own = [i for i, x in enumerate(orc) if x == j]
                if any(sum(DSc.inside(lines[i], T[r]) > SPAN for r in hit) >= 2 for i in own):
                    orc_merge['걸친 줄 포함'] += 1

    # (4) C 가 등크기 1g 쌍을 가른 원인
    import numpy as np
    from PIL import Image
    import group_gap as GG
    c4 = Counter()
    for k, p, it in items:
        t = truths[k]; lines = L[k]['lines']
        if not any(q['gap_level'] == 1.0 and q['size_ratio'] == 1.0 for q in t['pairs']):
            continue
        g = np.asarray(Image.open(p).convert('L')).astype(float)
        asg, _dg = GG.group_gap(g, lines)
        els, per_line = GG.elements(g, lines)
        ch_of = {kk: ci for ci, ch in enumerate(GG.chains(els)) for kk in ch}
        dec, by = decisions(lines, t, asg)
        tl = [ln['ink_box'] for b in t['blocks'] for ln in b['lines']]
        ins = [sum(1 for ib in tl if bx[1] <= (ib[1] + ib[3]) / 2 <= bx[3] and min(bx[2], ib[2]) - max(bx[0], ib[0]) > 0)
               for bx in lines]
        for d in dec:
            q = d['q']
            if q['gap_level'] != 1.0 or q['size_ratio'] != 1.0 or d['merged'] is None:
                continue
            tag = '두 블록 3줄 이상' if q['upper_n'] >= 3 and q['lower_n'] >= 3 else '짧은 블록 포함'
            c4[(tag, '판정 가능 쌍')] += 1
            if d['merged']:
                continue
            lu, ll = by.get(d['u'], []), by.get(d['l'], [])
            if any(per_line[i] != ins[i] for i in lu + ll):
                cause = '줄 단위 재기 늘어남 · 빠짐'
            else:
                eu = [kk for kk, e in enumerate(els) if e['line'] in lu]
                el = [kk for kk, e in enumerate(els) if e['line'] in ll]
                if not eu or not el:
                    cause = '기타'
                else:
                    last = max(eu, key=lambda kk: els[kk]['b']); first = min(el, key=lambda kk: els[kk]['b'])
                    if ch_of.get(last) != ch_of.get(first):
                        cause = '세로 사슬 끊김'
                    else:
                        bu = sorted(els[kk]['b'] for kk in eu)
                        inner = [bu[i + 1] - bu[i] for i in range(len(bu) - 1)]
                        gap = els[first]['b'] - els[last]['b']
                        if inner and abs(gap - float(np.median(inner))) > GG.TAU:
                            cause = '경계 간격이 안쪽 행간과 τ 넘게 다름'
                        else:
                            cause = '기타 (run 나눔 · 폴백)'
            c4[(tag, '분리 · ' + cause)] += 1

    tbl = {}
    for name, d in rates.items():
        for (lv, sr, dr), v in sorted(d.items()):
            if sr == 1.0:
                continue
            tbl.setdefault(name, {})[f'{lv}g · 비 {sr} · {dr}'] = dict(쌍=len(v), 병합률=round(sum(v) / len(v), 3))
    res = dict(무엇='묶기 비교 진단', 용도='탐색용 · 사전등록 밖 · 논문 수치 아님. 채점 정의 · group 파라미터를 바꾸지 않는다',
               A_크기비2_5_병합_원인=dict(why), 오라클_상한=dict(
                   줄_있는_정답블록_몫_240=round(ceil['줄이_하나라도'] / ceil['정답블록'], 4),
                   줄_있는_정답블록_몫_120=round(ceil['줄이_하나라도_120'] / ceil['정답블록_120'], 4),
                   **{f'오라클_{k}_240': v for k, v in orc_merge.items()}),
               방향별_병합률=tbl,
               C_등크기1g_분리_원인={f'{a} · {b}': v for (a, b), v in sorted(c4.items())}, 정의=dict(걸친_줄=f'줄 상자 넓이의 {SPAN} 넘게 두 정답 블록 각각에 듦',
                                     방향='위 블록 x높이 배수 > 아래 → 큰→작은'))
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != '방향별_병합률'}, ensure_ascii=False, indent=1))
    for name in ('A120', 'VLM1', 'VLM2'):
        print(name, {k: (v['병합률'], v['쌍']) for k, v in tbl.get(name, {}).items()})
    print('→', a.out)


if __name__ == '__main__':
    main()
