"""묶기 방식 비교 — 채점. 사전등록 docs/group_preregister.json (57f5dbe) 의 «채점» 그대로.

세 단계다.
    detect  Surya 줄을 한 번 검출해 저장         python eval/group_score.py detect --dir D --manifest M --lines L
    som     VLM 에 보일 번호 이미지(2배)를 그린다  python eval/group_score.py som --dir D --manifest M --lines L --som-dir S
    score   A · VLM · 오라클을 채점한다           python eval/group_score.py score --dir D --manifest M --lines L
                                                   [--vlm pass1.json --vlm pass2.json] --prereg P --out O
줄 번호는 y1 → x1 순으로 1 부터. C 는 group_gap.group_gap (사전등록 수정 1). A 는 detect_surya.group 그대로, 줄 소속은 나온 블록 상자에
줄 상자가 가장 많이 든 것으로 정한다. 오라클은 줄마다 잉크 상자가 가장 많이 겹치는 정답 블록.
새 지표를 더하지 않는다.
"""
import argparse
import hashlib
import itertools
import json
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import detect_surya as DS          # noqa: E402
import detector_score as DSc       # noqa: E402  iou · held · inside · match
import measure_corpus as MC        # noqa: E402  provenance
from measure import ground as G    # noqa: E402
import group_gap as GG             # noqa: E402  방식 C (사전등록 수정 1)

MAIN_LEVELS = (1.5, 2.0, 3.0, 5.0)
LOW_LEVELS = (0.5, 1.0)


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def _key(seed):
    return f'{seed:03d}'


def _items(D, M):
    return [(_key(it['seed']), os.path.join(D, it['image']), it) for it in M['items']]


def _overlap(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


# ── detect ──────────────────────────────────────────────────────

def detect(a):
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    from surya.detection import DetectionPredictor
    det = DetectionPredictor()
    out = {}
    items = _items(D, M)
    for i in range(0, len(items), 8):
        chunk = items[i:i + 8]
        imgs = [Image.open(p).convert('RGB') for _k, p, _it in chunk]
        res = det(imgs)
        for (k, p, it), r, im in zip(chunk, res, imgs):
            ls = sorted(([float(v) for v in b.bbox] for b in r.bboxes), key=lambda b: (b[1], b[0]))
            nb = None
            if a.order == 'columns':
                ls, nb = order_columns(ls)
            out[k] = dict(size=list(im.size), lines=ls, sha256=_sha(p), order=a.order, columns_found=nb)
        print(f'  {min(i + 8, len(items))}/{len(items)}', flush=True)
    prov = MC.provenance('eval/group_score.py detect', len(out)); prov['synthetic'] = True
    json.dump(dict(lines=out, provenance=prov, order=a.order,
                   note=('줄 번호 = 목록 순서 + 1. order yx = 판 전체 y1 → x1, columns = 단 단위 (order_columns)')),
              open(os.path.expanduser(a.lines), 'w'), ensure_ascii=False)
    print('→', a.lines)


# ── som ─────────────────────────────────────────────────────────

SOM_FONT = ('/System/Library/Fonts/Helvetica.ttc', 15, 1)   # 딱지 글꼴 (파일, 크기, index=Bold)
SOM_LABEL_H = 18


def order_columns(lines):
    """단 단위 줄 순서 — 사전등록 docs/clean_preregister.json 수정 1.

    Surya 줄 상자들의 가로 범위를 모두 합친 구간이 서로 떨어진 자리(틈 > 0)에서 단을 나누고, 줄은 가로
    중심이 든 단에 넣는다. 단은 왼쪽부터, 단 안에서는 위(y1) → 왼쪽(x1). 정답을 쓰지 않는다.
    """
    bands = []
    for x1, x2 in sorted((b[0], b[2]) for b in lines):
        if bands and x1 <= bands[-1][1]:
            bands[-1][1] = max(bands[-1][1], x2)
        else:
            bands.append([x1, x2])

    def band(b):
        c = (b[0] + b[2]) / 2
        return next((i for i, (u, v) in enumerate(bands) if u <= c <= v), len(bands))
    return sorted(lines, key=lambda b: (band(b), b[1], b[0])), len(bands)


def draw_som(im, lines, out_path=None):
    """SoM 이미지 — 2배로 키워 줄 상자(빨강)와 번호 딱지(R2)를 그린다. 번호 = 줄 순서 + 1.

    R2: 모든 딱지를 제 상자 왼쪽 위 바로 옆에 같은 글꼴 · 높이 · 색으로 둔다. 이웃을 보고 옮기지 않는다
    (홀수 왼쪽 · 짝수 오른쪽이던 옛 규칙은 단 사이에서 딱지끼리 겹쳤다). 딱지 상자 목록을 돌려준다.
    """
    W, H = im.size
    big = im.convert('RGB').resize((W * 2, H * 2), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(big)
    font = ImageFont.truetype(SOM_FONT[0], SOM_FONT[1], index=SOM_FONT[2])
    for x1, y1, x2, y2 in lines:
        d.rectangle([x1 * 2, y1 * 2, x2 * 2, y2 * 2], outline=(220, 30, 30), width=2)
    rects = []
    for i, (x1, y1, x2, y2) in enumerate(lines, 1):
        lab = str(i); tw = d.textlength(lab, font=font) + 6; th = SOM_LABEL_H
        bx = max(0, x1 * 2 - tw - 3); by = max(0, min(H * 2 - th, y1 * 2 - 1))
        d.rectangle([bx, by, bx + tw, by + th], fill=(255, 255, 255), outline=(30, 60, 220), width=1)
        d.text((bx + 3, by + 1), lab, font=font, fill=(30, 60, 220))
        rects.append((bx, by, bx + tw, by + th))
    if out_path:
        big.save(out_path)
    return rects


def label_overlaps(rects, lines):
    """못 읽는 딱지 (다른 딱지와 넓이 25% 넘게 겹침) · 다른 줄 글자를 가린 딱지 (다른 줄 상자와 25% 넘게) 수."""
    def inter(a, b):
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])
    boxes = [tuple(v * 2 for v in b) for b in lines]
    bad = sum(1 for i, r in enumerate(rects) if any(i != j and inter(r, q) > 0.25 * area(r) for j, q in enumerate(rects)))
    cover = sum(1 for i, r in enumerate(rects) if any(i != j and inter(r, q) > 0.25 * area(r) for j, q in enumerate(boxes)))
    return bad, cover


def som(a):
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    L = json.load(open(os.path.expanduser(a.lines)))['lines']
    S = os.path.expanduser(a.som_dir); os.makedirs(S, exist_ok=True)
    rows = []
    for k, p, it in _items(D, M):
        if not it.get('vlm_subset'):
            continue
        op = os.path.join(S, f'{k}_som.png')
        rects = draw_som(Image.open(p), L[k]['lines'], op)
        bad, cover = label_overlaps(rects, L[k]['lines'])
        rows.append(dict(file=f'{k}_som.png', path=op, n_lines=len(L[k]['lines']), unreadable=bad, occluding=cover))
    lst = os.path.join(S, 'list.md')
    with open(lst, 'w') as f:
        f.write(f'## 이미지 {len(rows)}장\n')
        for r in rows:
            f.write(f'- file: {r["file"]}\n  path: {r["path"]}\n  상자 수: {r["n_lines"]}\n')
    json.dump(rows, open(os.path.join(S, 'list.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(rows)}장 → {S} (목록 {lst}) · 못 읽는 딱지 합 {sum(r["unreadable"] for r in rows)} · 글자 가림 합 {sum(r["occluding"] for r in rows)}')


# ── score ───────────────────────────────────────────────────────

def assign_to_boxes(lines, boxes):
    """줄마다 가장 많이 겹치는 상자 번호 (겹침 0 이면 None)."""
    out = []
    for l in lines:
        best, bv = None, 0.0
        for j, b in enumerate(boxes):
            v = _overlap(l, b)
            if v > bv:
                best, bv = j, v
        out.append(best)
    return out


def groups_A(lines):
    blocks = DS.group(lines)
    asg = assign_to_boxes(lines, [b[:4] for b in blocks])
    return asg


def groups_oracle(lines, truth):
    return assign_to_boxes(lines, [tb['ink_box'] for tb in truth['blocks']])


def groups_vlm(lines, entry):
    """VLM 묶음 → 줄 소속. 빠진 번호는 홑 묶음, 두 번 나온 번호는 먼저 것, 없는 번호는 버린다."""
    n = len(lines)
    asg = [None] * n
    bad = dup = 0
    gi = 0
    for grp in (entry or {}).get('groups', []):
        used = False
        for v in grp:
            try:
                i = int(v) - 1
            except (TypeError, ValueError):
                bad += 1; continue
            if not 0 <= i < n:
                bad += 1; continue
            if asg[i] is not None:
                dup += 1; continue
            asg[i] = gi; used = True
        if used:
            gi += 1
    missing = 0
    for i in range(n):
        if asg[i] is None:
            asg[i] = gi; gi += 1; missing += 1
    return asg, dict(bad=bad, dup=dup, missing=missing)


def boxes_of(lines, asg):
    g = defaultdict(list)
    for l, j in zip(lines, asg):
        if j is not None:
            g[j].append(l)
    out = []
    for j in sorted(g):
        ls = g[j]
        out.append((j, [min(l[0] for l in ls), min(l[1] for l in ls), max(l[2] for l in ls), max(l[3] for l in ls), len(ls)]))
    return out


def score_method(name, items, L, truths, asg_fn, measure=True, src_fn=None):
    rows_blk = []; pair_rows = []; meas_rows = []
    tot = Counter()
    for k, p, it in items:
        lines = L[k]['lines']; t = truths[k]
        asg = asg_fn(k, lines, t)
        src = src_fn(k) if src_fn else None
        boxes = boxes_of(lines, asg)
        P = [b[1][:4] for b in boxes]
        T = [tb['ink_box'] for tb in t['blocks']]
        mr, mp = DSc.match(T, P)
        merged = sum(1 for j, pb in enumerate(P) if sum(1 for r in T if DSc.held(pb, r) >= DSc.INSIDE) >= 2)
        split = sum(1 for j, pb in enumerate(P) if j not in mp and any(DSc.inside(pb, r) >= DSc.INSIDE for r in T))
        tot['참조'] += len(T); tot['출처'] += len(P); tot['맞음'] += len(mr); tot['과병합'] += merged; tot['과분할'] += split
        gsrc = {}
        if src is not None:
            for i, j in enumerate(asg):
                if j is not None:
                    gsrc.setdefault(j, src[i])
            for gid, _bx in boxes:
                tot['묶음_' + str(gsrc.get(gid))] += 1
            for _i, jj in mr.items():
                tot['맞음_' + str(gsrc.get(boxes[jj][0]))] += 1
            for i, j in enumerate(asg):
                tot['줄_' + str(src[i] if j is not None else None)] += 1
        # 쌍
        orc = groups_oracle(lines, t)
        by_truth = defaultdict(list)
        for i, tb_i in enumerate(orc):
            if tb_i is not None:
                by_truth[tb_i].append(i)
        idx = {tb['id']: i for i, tb in enumerate(t['blocks'])}
        for q in t['pairs']:
            u, l = idx[q['upper']], idx[q['lower']]
            gu = Counter(asg[i] for i in by_truth.get(u, []) if asg[i] is not None)
            gl = Counter(asg[i] for i in by_truth.get(l, []) if asg[i] is not None)
            ps = '판정불가'
            if not gu or not gl:
                dec = None
            else:
                a_, b_ = gu.most_common(1)[0][0], gl.most_common(1)[0][0]
                dec = (a_ == b_)
                if src is not None:
                    su, sl = gsrc.get(a_), gsrc.get(b_)
                    ps = 'C 기전' if su == sl == 'C' else ('A 폴백' if su == sl == 'A' else '혼합')
            row = dict(seed=int(k), **{kk: q[kk] for kk in ('gap_level', 'size_ratio', 'column', 'bumped', 'upper_n', 'lower_n')},
                       columns=t['condition']['columns'], xh=t['condition']['xh_px_at_800'], merged=dec)
            if src is not None:
                row['src'] = ps
            pair_rows.append(row)
        # 재기
        if measure and P:
            W, H = t['canvas']
            norm = [[max(0, b[0] - 2) / W, max(0, b[1] - 2) / H, min(W, b[2] + 2) / W, min(H, b[3] + 2) / H] for b in P]
            e, _ = G.entry(p, norm, coords='norm')
            for i, j in mr.items():
                tb, mb = t['blocks'][i], e['blocks'][j]
                cs = [b - c for b, c in zip(mb['bases'], mb['caps']) if c is not None]
                meas_rows.append(dict(seed=int(k), block=tb['id'], n=tb['n'], xh=t['condition']['xh_px_at_800'],
                                      lead_err=(None if tb['lead_px'] is None or not mb.get('lead') else mb['lead'] - tb['lead_px']),
                                      lead_px=tb['lead_px'],
                                      cap_err=(None if not cs else float(np.median(cs)) - tb['cap_px'])))
        rows_blk.append(dict(seed=int(k), n_truth=len(T), n_pred=len(P), hit=len(mr), merged=merged, split=split))
    R = tot['맞음'] / tot['참조'] if tot['참조'] else None
    Pp = tot['맞음'] / tot['출처'] if tot['출처'] else None
    F = 2 * R * Pp / (R + Pp) if R and Pp else None
    blocks = dict(판=len(items), 참조=tot['참조'], 출처=tot['출처'], 맞음=tot['맞음'],
                  재현율=round(R, 4) if R is not None else None, 정밀도=round(Pp, 4) if Pp is not None else None,
                  F1=round(F, 4) if F else None, 과병합=tot['과병합'], 과분할=tot['과분할'])
    if src_fn:
        blocks['출처별'] = dict(묶음_C기전=tot['묶음_C'], 묶음_A폴백=tot['묶음_A'],
                              맞음_C기전=tot['맞음_C'], 맞음_A폴백=tot['맞음_A'],
                              줄_C기전=tot['줄_C'], 줄_A폴백=tot['줄_A'], 줄_소속없음=tot['줄_None'])
    return dict(blocks=blocks, pairs=pair_rows, meas=meas_rows)


def pair_table(rows, levels, by=('size_ratio',)):
    out = {}
    for lv in levels:
        sub = [r for r in rows if r['gap_level'] == lv]
        cell = {}
        keys = sorted({tuple(r[b] for b in by) for r in sub})
        for kk in keys:
            s2 = [r for r in sub if tuple(r[b] for b in by) == kk]
            dec = [r['merged'] for r in s2 if r['merged'] is not None]
            cell['·'.join(str(x) for x in kk)] = dict(쌍=len(s2), 판정불가=len(s2) - len(dec),
                                                    병합률=(round(float(np.mean(dec)), 3) if dec else None))
        dec = [r['merged'] for r in sub if r['merged'] is not None]
        cell['전체'] = dict(쌍=len(sub), 판정불가=len(sub) - len(dec), 병합률=(round(float(np.mean(dec)), 3) if dec else None))
        out[str(lv)] = cell
    return out


def meas_summary(rows):
    le = [r['lead_err'] for r in rows if r['lead_err'] is not None]
    lp = [100 * r['lead_err'] / r['lead_px'] for r in rows if r['lead_err'] is not None]
    ce = [r['cap_err'] for r in rows if r['cap_err'] is not None]
    q = lambda a, p: (round(float(np.percentile(a, p)), 3) if len(a) else None)
    return dict(짝지은_블록=len(rows), 행간_n=len(le),
                행간오차_px=dict(중앙=q(le, 50), 절대중앙=q([abs(x) for x in le], 50), 절대p90=q([abs(x) for x in le], 90)),
                행간오차_pct=dict(절대중앙=q([abs(x) for x in lp], 50), 절대p90=q([abs(x) for x in lp], 90)),
                캡오차_px=dict(n=len(ce), 중앙=q(ce, 50), 절대중앙=q([abs(x) for x in ce], 50), 절대p90=q([abs(x) for x in ce], 90)))


def pass_agreement(items, L, v1, v2):
    agree = []; blkF = Counter()
    for k, p, it in items:
        lines = L[k]['lines']
        a1, _ = groups_vlm(lines, v1.get(k)); a2, _ = groups_vlm(lines, v2.get(k))
        n = len(lines)
        if n >= 2:
            same = [ (a1[i] == a1[j]) == (a2[i] == a2[j]) for i, j in itertools.combinations(range(n), 2)]
            agree.append(float(np.mean(same)))
        P1 = [b[1][:4] for b in boxes_of(lines, a1)]; P2 = [b[1][:4] for b in boxes_of(lines, a2)]
        mr, _ = DSc.match(P1, P2)
        blkF['맞음'] += len(mr); blkF['1'] += len(P1); blkF['2'] += len(P2)
    R = blkF['맞음'] / blkF['1'] if blkF['1'] else 0; Pp = blkF['맞음'] / blkF['2'] if blkF['2'] else 0
    return dict(판=len(items), 줄쌍_일치율_중앙=round(float(np.median(agree)), 3) if agree else None,
                줄쌍_일치율_평균=round(float(np.mean(agree)), 3) if agree else None,
                블록_F1=round(2 * R * Pp / (R + Pp), 3) if R and Pp else None, 블록수_1=blkF['1'], 블록수_2=blkF['2'])


def load_vlm(path):
    d = json.load(open(os.path.expanduser(path)))
    m = {}
    for e in d.get('posters', []):
        k = os.path.basename(e['file']).split('_')[0]
        m[k] = e
    return m, dict(model=d.get('model'), files_opened=len(d.get('files_opened', [])), notes=d.get('notes'),
                   sha256=_sha(path), n_posters=len(m))


def score(a):
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    L = json.load(open(os.path.expanduser(a.lines)))
    Lp, L = L.get('provenance'), L['lines']
    items = _items(D, M)
    for k, p, it in items:
        if _sha(p) != it['image_sha256'] or L[k]['sha256'] != it['image_sha256']:
            sys.exit(f'manifest 와 다른 이미지 또는 줄 캐시: {p}')
    truths = {k: json.load(open(p[:-4] + '.json')) for k, p, it in items}
    sub = [x for x in items if x[2].get('vlm_subset')]
    vlms = []
    for vp in a.vlm or []:
        vlms.append(load_vlm(vp))
    res = dict(무엇='묶기 방식 비교 — A(현재 규칙) · VLM Set-of-Mark · 오라클, 합성 240장 (VLM 120장)',
               사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg), manifest=a.manifest, manifest_sha256=_sha(a.manifest),
               줄_provenance=Lp, VLM=[v[1] for v in vlms], 경위=a.note or [],
               정의=dict(블록='IoU ≥ 0.5 1:1 (detector_score.match), 과병합·과분할 같은 정의', 쌍='위·아래 블록의 Surya 줄이 가장 많이 든 묶음이 같으면 병합. 한쪽에 줄이 없으면 판정 불가',
                       주곡선='간격 ≥ 1.5g', 별도표='≤ 1g', 재기='짝지은 블록의 measure/ground 행간·캡 − 정답'))
    methods = {}
    def run_all(items_, tag):
        out = {}
        out['A'] = score_method('A', items_, L, truths, lambda k, ls, t: groups_A(ls))
        out['오라클'] = score_method('오라클', items_, L, truths, lambda k, ls, t: groups_oracle(ls, t))
        out['C'] = score_method('C', items_, L, truths, lambda k, ls, t: C[k], src_fn=lambda k: Cdiag[k]['source'])
        if tag == '120장_VLM표본':          # VLM 은 표본 120장만 있다
            for i, (vm, vinfo) in enumerate(vlms, 1):
                out[f'VLM{i}'] = score_method(f'VLM{i}', items_, L, truths, lambda k, ls, t, vm=vm: groups_vlm(ls, vm.get(k))[0])
        return out
    # 방식 C — 240장을 두 번 돌려 줄 소속이 같은지 본다
    C, Cdiag, c_same = {}, {}, True
    for k, p, it in items:
        g = np.asarray(Image.open(p).convert('L')).astype(float)
        a1, d1 = GG.group_gap(g, L[k]['lines'], pad_rule=a.c_pad_rule)
        a2, _d2 = GG.group_gap(g, L[k]['lines'], pad_rule=a.c_pad_rule)
        c_same = c_same and (a1 == a2)
        C[k], Cdiag[k] = a1, d1
    # 결정론 확인: A · 오라클 두 번
    a1 = score_method('A', items[:20], L, truths, lambda k, ls, t: groups_A(ls), measure=False)
    a2 = score_method('A', items[:20], L, truths, lambda k, ls, t: groups_A(ls), measure=False)
    res['A_결정론_20장'] = (a1['blocks'] == a2['blocks'] and a1['pairs'] == a2['pairs'])
    res['C_결정론_240장'] = c_same
    res['정의']['C'] = ('group_gap.group_gap (사전등록 수정 1 · ef0cf65): 줄 상자마다 region.measure → X_OVER 세로 사슬 → '
                       '간격 run (최대 − 최소 ≤ 1px) · 3줄 이상 = 패턴 블록 · 공유 요소는 x높이 · 남은 줄은 detect_surya.group 폴백')
    res['정의']['C_pad_rule'] = a.c_pad_rule
    res['정의']['3줄이상'] = '위 · 아래 블록이 모두 3줄 이상인 쌍만 (C 기전이 적용될 수 있는 쌍)'
    res['정의']['쌍_출처'] = '위 · 아래 블록의 다수 묶음이 둘 다 C 기전 → C 기전, 둘 다 A 폴백 → A 폴백, 아니면 혼합'
    res['정의']['폴백_범위'] = '폴백 비중이 크면 «C 를 제안한다» 는 주장의 범위가 그만큼 좁아진다 — 출처별 몫을 함께 읽는다'
    def _gainloss(its):
        c = Counter()
        for k, p, it in its:
            tl = [l['ink_box'] for b in truths[k]['blocks'] for l in b['lines']]
            for box, n in zip(L[k]['lines'], Cdiag[k]['per_line_measured']):
                ins = sum(1 for ib in tl if box[1] <= (ib[1] + ib[3]) / 2 <= box[3] and min(box[2], ib[2]) - max(box[0], ib[0]) > 0)
                c['상자'] += 1
                c['같음' if n == ins else ('늘어남' if n > ins else '빠짐')] += 1
                c['정답 줄 없는 상자'] += (ins == 0)
                c['못 잰 상자'] += (n == 0)
        return dict(c)
    res['줄단위_재기_늘어남빠짐'] = {'240장': _gainloss(items), '120장_VLM표본': _gainloss(sub)}
    tie = Counter()
    for d_ in Cdiag.values():
        tie.update(d_['ties'])
    res['C_진단_240장'] = dict(요소=sum(d_['n_elements'] for d_ in Cdiag.values()),
                             패턴블록=sum(d_['n_pattern_blocks'] for d_ in Cdiag.values()),
                             폴백묶음=sum(d_['n_fallback_blocks'] for d_ in Cdiag.values()),
                             남은줄=sum(d_['n_leftover_lines'] for d_ in Cdiag.values()),
                             공유요소=dict(tie))
    for tag, its in (('240장', items), ('120장_VLM표본', sub)):
        out = run_all(its, tag)
        block = {}
        for m, r in out.items():
            block[m] = dict(**r['blocks'],
                            쌍_주곡선=pair_table(r['pairs'], MAIN_LEVELS),
                            쌍_주곡선_단수별=pair_table(r['pairs'], MAIN_LEVELS, by=('columns',)),
                            쌍_주곡선_x높이별=pair_table(r['pairs'], MAIN_LEVELS, by=('xh',)),
                            쌍_1g이하=pair_table(r['pairs'], LOW_LEVELS, by=('size_ratio', 'bumped')),
                            재기=meas_summary(r['meas']),
                            쌍_주곡선_3줄이상=pair_table([x for x in r['pairs'] if x['upper_n'] >= 3 and x['lower_n'] >= 3], MAIN_LEVELS),
                            쌍_1g이하_3줄이상=pair_table([x for x in r['pairs'] if x['upper_n'] >= 3 and x['lower_n'] >= 3], LOW_LEVELS, by=('size_ratio', 'bumped')))
            if m == 'C':
                block[m]['쌍_출처_몫'] = dict(Counter(x['src'] for x in r['pairs']))
                block[m]['쌍_출처별_주곡선'] = pair_table(r['pairs'], MAIN_LEVELS, by=('src', 'size_ratio'))
                block[m]['쌍_출처별_1g이하'] = pair_table(r['pairs'], LOW_LEVELS, by=('src', 'size_ratio'))
        res[tag] = block
        if tag == '120장_VLM표본':
            vparse = {}
            for i, (vm, vinfo) in enumerate(vlms, 1):
                c = Counter()
                for k, p, it in sub:
                    _, info = groups_vlm(L[k]['lines'], vm.get(k))
                    for kk, v in info.items(): c[kk] += v
                    c['없는 장'] += (k not in vm)
                vparse[f'VLM{i}'] = dict(c)
            res['VLM_파싱'] = vparse
            if len(vlms) >= 2:
                res['VLM_패스간_일치'] = pass_agreement(sub, L, vlms[0][0], vlms[1][0])
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    def _curve(tbl):
        return ', '.join(f"{lv}g: {tbl[lv]['전체']['병합률']}" for lv in tbl)
    for tag in ('240장', '120장_VLM표본'):
        print(f'\n== {tag}')
        for m, r in res[tag].items():
            print(f"  {m:6s} F1 {r['F1']} 재현 {r['재현율']} 정밀 {r['정밀도']} 과병합 {r['과병합']} 과분할 {r['과분할']} | "
                  f"주곡선 {{{_curve(r['쌍_주곡선'])}}} | ≤1g {{{_curve(r['쌍_1g이하'])}}} | "
                  f"행간 |err| 중앙 {r['재기']['행간오차_px']['절대중앙']} 캡 {r['재기']['캡오차_px']['절대중앙']}")
    if 'VLM_패스간_일치' in res: print('패스 간', res['VLM_패스간_일치'])
    if 'VLM_파싱' in res: print('파싱', res['VLM_파싱'])
    print('→', a.out)


# ── score-clean (깨끗한 세트, docs/clean_preregister.json) ───────────

CLEAN_LEVELS = ('c_in', '0.5', '1.0', '1.5', '2.0', '2.5', '3.0', '4.0')


def _stratum(t):
    return (t['condition']['columns'], t['condition']['xh_px_at_800'])


def _sname(s):
    return f'{s[0]}단·{s[1]}px'


def _pool(vals, prop=True):
    """층별 {층: (값, n)} → 같은 가중 (단순 평균). 값이 None 이거나 n = 0 인 층은 빼고 적는다.
    비율이면 SE = (1/k) · √Σ p(1−p)/n (사전등록 수정 1, k = 넣은 층 수)."""
    ok = {s: (p, n) for s, (p, n) in vals.items() if p is not None and n}
    out = dict(값=None, 층수=len(ok), 뺀_층=[_sname(s) for s in vals if s not in ok])
    if ok:
        out['값'] = round(float(np.mean([p for p, _n in ok.values()])), 4)
        if prop:
            out['SE'] = round(math.sqrt(sum(p * (1 - p) / n for p, n in ok.values())) / len(ok), 4)
    return out


def _q(v):
    v = [x for x in v if x is not None]
    if not v:
        return dict(n=0)
    return dict(n=len(v), 중앙=round(float(np.median(v)), 3), p25=round(float(np.percentile(v, 25)), 3),
                p75=round(float(np.percentile(v, 75)), 3))


def clean_method(items, L, truths, asg_of, src_of=None):
    """판마다 블록 수 · 쌍 판정 · 정답 블록이 묶음 둘 이상에 흩어졌는지. 정의는 score_method 와 같다."""
    per = {}
    for k, p, it in items:
        lines = L[k]['lines']; t = truths[k]; asg = asg_of[k]
        src = src_of[k] if src_of else None
        boxes = boxes_of(lines, asg)
        P = [b[1][:4] for b in boxes]
        T = [tb['ink_box'] for tb in t['blocks']]
        mr, mp = DSc.match(T, P)
        c = Counter(참조=len(T), 출처=len(P), 맞음=len(mr),
                    과병합=sum(1 for pb in P if sum(1 for r in T if DSc.held(pb, r) >= DSc.INSIDE) >= 2),
                    과분할=sum(1 for j, pb in enumerate(P) if j not in mp and any(DSc.inside(pb, r) >= DSc.INSIDE for r in T)))
        gsrc = {}
        if src is not None:
            for i, j in enumerate(asg):
                if j is not None:
                    gsrc.setdefault(j, src[i])
            for gid, _bx in boxes:
                c['묶음_' + str(gsrc.get(gid))] += 1
            for _i, jj in mr.items():
                c['맞음_' + str(gsrc.get(boxes[jj][0]))] += 1
            for i, j in enumerate(asg):
                c['줄_' + str(src[i] if j is not None else None)] += 1
        orc = groups_oracle(lines, t)
        by_truth = defaultdict(list)
        for i, ti in enumerate(orc):
            if ti is not None:
                by_truth[ti].append(i)
        idx = {tb['id']: i for i, tb in enumerate(t['blocks'])}
        pairs = []
        for q in t['pairs']:
            u, l = idx[q['upper']], idx[q['lower']]
            gu = Counter(asg[i] for i in by_truth.get(u, []) if asg[i] is not None)
            gl = Counter(asg[i] for i in by_truth.get(l, []) if asg[i] is not None)
            dec, ps = None, '판정불가'
            if gu and gl:
                a_, b_ = gu.most_common(1)[0][0], gl.most_common(1)[0][0]
                dec = (a_ == b_)
                if src is not None:
                    su, sl = gsrc.get(a_), gsrc.get(b_)
                    ps = 'C 기전' if su == sl == 'C' else ('A 폴백' if su == sl == 'A' else '혼합')
            pairs.append(dict(level=q['level'], merged=dec, src=(ps if src is not None else None)))
        spread = [len({asg[i] for i in by_truth.get(bi, []) if asg[i] is not None}) >= 2 for bi in range(len(t['blocks']))]
        per[k] = dict(c=c, pairs=pairs, spread=spread, by_truth=dict(by_truth), stratum=_stratum(t))
    return per


def clean_curves(per, strata, levels):
    tot, dec = Counter(), defaultdict(list)
    for r in per.values():
        for q in r['pairs']:
            key = (r['stratum'], q['level']); tot[key] += 1
            if q['merged'] is not None:
                dec[key].append(q['merged'])
    rate = lambda s, lv: (float(np.mean(dec[(s, lv)])) if dec[(s, lv)] else None, len(dec[(s, lv)]))
    by_s = {_sname(s): {lv: dict(쌍=tot[(s, lv)], 판정불가=tot[(s, lv)] - len(dec[(s, lv)]),
                                병합률=(round(rate(s, lv)[0], 4) if rate(s, lv)[0] is not None else None))
                        for lv in levels} for s in strata}
    pooled = {lv: _pool({s: rate(s, lv) for s in strata}) for lv in levels}
    xh = {str(x): {lv: _pool({s: rate(s, lv) for s in strata if s[1] == x}) for lv in levels}
          for x in sorted({s[1] for s in strata})}
    return dict(층별=by_s, 층_가중_합산=pooled, x높이별_단순평균=xh)


def clean_blocks(per, strata):
    agg = defaultdict(Counter)
    for r in per.values():
        agg[r['stratum']].update(r['c'])
    by_s, F, R_, P_, OM, OS = {}, {}, {}, {}, {}, {}
    for s in strata:
        c = agg[s]
        R = c['맞음'] / c['참조'] if c['참조'] else None
        Pp = c['맞음'] / c['출처'] if c['출처'] else None
        f = 2 * R * Pp / (R + Pp) if R and Pp else (0.0 if R == 0 or Pp == 0 else None)
        by_s[_sname(s)] = dict(참조=c['참조'], 출처=c['출처'], 맞음=c['맞음'], 재현율=R and round(R, 4),
                               정밀도=Pp and round(Pp, 4), F1=(round(f, 4) if f is not None else None),
                               과병합=c['과병합'], 과분할=c['과분할'],
                               과병합_정답블록당=round(c['과병합'] / c['참조'], 4), 과분할_정답블록당=round(c['과분할'] / c['참조'], 4))
        F[s] = (f, c['참조']); R_[s] = (R, c['참조']); P_[s] = (Pp, c['출처'])
        OM[s] = (c['과병합'] / c['참조'], c['참조']); OS[s] = (c['과분할'] / c['참조'], c['참조'])
    xh = {str(x): dict(과분할_정답블록당=_pool({s: OS[s] for s in strata if s[1] == x}, prop=False)['값'],
                       과병합_정답블록당=_pool({s: OM[s] for s in strata if s[1] == x}, prop=False)['값'],
                       F1=_pool({s: F[s] for s in strata if s[1] == x}, prop=False)['값'])
          for x in sorted({s[1] for s in strata})}
    return dict(층별=by_s, 층_가중_합산=dict(F1=_pool(F, False)['값'], 재현율=_pool(R_, False)['값'], 정밀도=_pool(P_, False)['값'],
                                           과병합_정답블록당=_pool(OM, False)['값'], 과분할_정답블록당=_pool(OS, False)['값']),
                x높이별_단순평균=xh,
                합계=dict(sum((agg[s] for s in strata), Counter())))


def _box_of_line(boxes, ib):
    """정답 줄 → 줄 잉크 세로 중심이 들고 가로로 겹치는 Surya 상자 (여럿이면 가로 겹침이 가장 긴 것)."""
    cy = (ib[1] + ib[3]) / 2
    cand = [(min(b[2], ib[2]) - max(b[0], ib[0]), j) for j, b in enumerate(boxes) if b[1] <= cy <= b[3]]
    cand = [(v, j) for v, j in cand if v > 0]
    return max(cand)[1] if cand else None


def score_clean(a):
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    LL = json.load(open(os.path.expanduser(a.lines)))
    Lp, L = LL.get('provenance'), LL['lines']
    items = _items(D, M)
    for k, p, it in items:
        if _sha(p) != it['image_sha256'] or L[k]['sha256'] != it['image_sha256']:
            sys.exit(f'manifest 와 다른 이미지 또는 줄 캐시: {p}')
    truths = {k: json.load(open(p[:-4] + '.json')) for k, p, it in items}
    levels = list(a.levels)
    strata = sorted({_stratum(t) for t in truths.values()})
    vlms = [load_vlm(vp) for vp in a.vlm or []]
    # 방식별 줄 소속
    A1 = {k: groups_A(L[k]['lines']) for k, _p, _it in items}
    A2 = {k: groups_A(L[k]['lines']) for k, _p, _it in items}
    C, Cdiag, c_same = {}, {}, True
    for k, p, it in items:
        g = np.asarray(Image.open(p).convert('L')).astype(float)
        c1, d1 = GG.group_gap(g, L[k]['lines'], pad_rule=a.c_pad_rule)
        c2, d2 = GG.group_gap(g, L[k]['lines'], pad_rule=a.c_pad_rule)
        c_same = c_same and c1 == c2 and d1 == d2
        C[k], Cdiag[k] = c1, d1
    asg = {'A': A1, 'C': C, '오라클': {k: groups_oracle(L[k]['lines'], truths[k]) for k, _p, _it in items}}
    vparse = {}
    for i, (vm, _info) in enumerate(vlms, 1):
        asg[f'VLM{i}'] = {}
        cnt = Counter()
        for k, _p, _it in items:
            asg[f'VLM{i}'][k], info = groups_vlm(L[k]['lines'], vm.get(k))
            cnt.update(info); cnt['없는 장'] += (k not in vm); cnt['invalid 표시 장'] += int(vm.get(k, {}).get('valid') is False)
        vparse[f'VLM{i}'] = dict(cnt)
    order = ['A'] + [f'VLM{i}' for i in range(1, len(vlms) + 1)] + ['C', '오라클']
    per = {m: clean_method(items, L, truths, asg[m], src_of=({k: Cdiag[k]['source'] for k in C} if m == 'C' else None))
           for m in order}
    res = dict(무엇='깨끗한 세트 묶기 비교 — A · VLM(Opus 5, 2패스) · C · 오라클, 280장',
               사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg), manifest=a.manifest, manifest_sha256=_sha(a.manifest),
               줄_provenance=Lp, 줄_순서=LL.get('order'), VLM=[v[1] for v in vlms], VLM_파싱=vparse, 경위=a.note or [],
               층별_장수={_sname(s): sum(1 for t in truths.values() if _stratum(t) == s) for s in strata},
               정의=dict(쌍='위 · 아래 블록의 Surya 줄이 가장 많이 든 묶음이 같으면 병합. 한쪽에 Surya 줄이 없으면 판정 불가',
                       층_가중='수준마다 층별 병합률의 단순 평균, 판정 가능한 쌍이 0 인 층은 빼고 적는다. SE = (1/k) · √Σ p(1−p)/n',
                       x높이별='x높이마다 단 층 셋의 단순 평균',
                       블록='IoU ≥ 0.5 1:1 (detector_score.match). 과병합 = 정답 블록 둘 이상을 절반 넘게 덮은 묶음, 과분할 = 짝 못 지은 묶음 중 한 정답 블록 안에 절반 넘게 든 것. 층별 값의 단순 평균',
                       C=f'group_gap.group_gap τ {GG.TAU}px · pad_rule {a.c_pad_rule} · 3줄 미만 조각은 detect_surya.group 폴백',
                       판정='예측 정오는 점추정으로 가른다. SE 를 함께 적는다'))
    res['주_결과_병합률'] = {m: clean_curves(per[m], strata, levels) for m in order}
    res['블록'] = {m: clean_blocks(per[m], strata) for m in order}
    res['A_결정론_280장'] = (A1 == A2)
    res['C_결정론_280장'] = c_same
    # VLM 패스 간
    if len(vlms) >= 2:
        ps = {}
        for s in strata:
            its = [x for x in items if _stratum(truths[x[0]]) == s]
            ps[s] = pass_agreement(its, L, vlms[0][0], vlms[1][0])
        res['VLM_패스간_일치'] = dict(층별={_sname(s): v for s, v in ps.items()},
                                   층_가중_합산=dict(줄쌍_일치율_평균=_pool({s: (v['줄쌍_일치율_평균'], 1) for s, v in ps.items()}, False)['값'],
                                                   블록_F1=_pool({s: (v['블록_F1'], 1) for s, v in ps.items()}, False)['값']),
                                   전체_모아서=pass_agreement(items, L, vlms[0][0], vlms[1][0]))
    # C 폴백 몫
    fb = {}
    for s in strata:
        c = sum((r['c'] for r in per['C'].values() if r['stratum'] == s), Counter())
        pr = Counter(q['src'] for r in per['C'].values() if r['stratum'] == s for q in r['pairs'])
        nl = c['줄_C'] + c['줄_A'] + c['줄_None']; ng = c['묶음_C'] + c['묶음_A']; nm = c['맞음_C'] + c['맞음_A']; npr = sum(pr.values())
        fb[s] = dict(줄=nl, 줄_A폴백=c['줄_A'], 줄_소속없음=c['줄_None'], 묶음=ng, 묶음_A폴백=c['묶음_A'],
                     짝지은_블록=nm, 짝지은_블록_A폴백=c['맞음_A'], 쌍=npr, 쌍_출처=dict(pr),
                     몫=dict(줄_A폴백=round(c['줄_A'] / nl, 4) if nl else None, 묶음_A폴백=round(c['묶음_A'] / ng, 4) if ng else None,
                            짝지은_블록_A폴백=round(c['맞음_A'] / nm, 4) if nm else None,
                            쌍_C기전밖=round((pr['혼합'] + pr['A 폴백']) / npr, 4) if npr else None,
                            쌍_판정불가=round(pr['판정불가'] / npr, 4) if npr else None))
    keys = ('줄_A폴백', '묶음_A폴백', '짝지은_블록_A폴백', '쌍_C기전밖', '쌍_판정불가')
    tie = Counter()
    for d_ in Cdiag.values():
        tie.update(d_['ties'])
    res['C_폴백_몫'] = dict(층별={_sname(s): v for s, v in fb.items()},
                          층_가중_합산={kk: _pool({s: (v['몫'][kk], 1) for s, v in fb.items()}, False)['값'] for kk in keys},
                          진단=dict(요소=sum(d_['n_elements'] for d_ in Cdiag.values()),
                                  패턴블록=sum(d_['n_pattern_blocks'] for d_ in Cdiag.values()),
                                  폴백묶음=sum(d_['n_fallback_blocks'] for d_ in Cdiag.values()),
                                  남은줄=sum(d_['n_leftover_lines'] for d_ in Cdiag.values()), 공유요소=dict(tie)))
    # 줄 단위 재기 늘어남 · 빠짐과 C 과분할
    gl_s = defaultdict(Counter); cells = Counter(); cell_s = defaultdict(Counter)
    for k, p, it in items:
        t = truths[k]; boxes = L[k]['lines']; s = _stratum(t)
        tl = [ln['ink_box'] for b in t['blocks'] for ln in b['lines']]
        kind = []
        for box, n in zip(boxes, Cdiag[k]['per_line_measured']):
            ins = sum(1 for ib in tl if box[1] <= (ib[1] + ib[3]) / 2 <= box[3] and min(box[2], ib[2]) - max(box[0], ib[0]) > 0)
            kk = '같음' if n == ins else ('늘어남' if n > ins else '빠짐')
            kind.append(kk)
            gl_s[s]['상자'] += 1; gl_s[s][kk] += 1; gl_s[s]['정답 줄 없는 상자'] += (ins == 0); gl_s[s]['못 잰 상자'] += (n == 0)
        r = per['C'][k]
        for bi, sp_ in enumerate(r['spread']):
            ks = {kind[i] for i in r['by_truth'].get(bi, [])}
            cell = ('늘어남' if '늘어남' in ks else '늘어남없음', '빠짐' if '빠짐' in ks else '빠짐없음')
            for cc in (cells, cell_s[s]):
                cc[cell + ('블록',)] += 1; cc[cell + ('과분할',)] += int(sp_)
    def _rate(cc, pick):
        n = sum(v for kk, v in cc.items() if kk[2] == '블록' and pick(kk)); x = sum(v for kk, v in cc.items() if kk[2] == '과분할' and pick(kk))
        return (x / n if n else None, n)
    sel = {'늘어남 있음': lambda kk: kk[0] == '늘어남', '늘어남 없음': lambda kk: kk[0] == '늘어남없음',
           '빠짐 있음': lambda kk: kk[1] == '빠짐', '빠짐 없음': lambda kk: kk[1] == '빠짐없음'}
    res['줄단위_재기'] = dict(
        늘어남빠짐_층별={_sname(s): dict(gl_s[s]) for s in strata},
        늘어남빠짐_합계=dict(sum(gl_s.values(), Counter())),
        C_과분할_정의='정답 블록의 Surya 줄(오라클 소속)이 C 묶음 둘 이상에 흩어지면 «C 과분할 블록»',
        C_과분할_네칸_합계={f'{a_} · {b_}': dict(블록=cells[(a_, b_, '블록')], 과분할=cells[(a_, b_, '과분할')])
                        for a_ in ('늘어남', '늘어남없음') for b_ in ('빠짐', '빠짐없음')},
        C_과분할률_모아서={nm_: (round(_rate(cells, f)[0], 4) if _rate(cells, f)[0] is not None else None, _rate(cells, f)[1]) for nm_, f in sel.items()},
        C_과분할률_층_가중={nm_: _pool({s: _rate(cell_s[s], f) for s in strata}, False) for nm_, f in sel.items()},
        C_과분할_블록률_층별={_sname(s): _rate(cell_s[s], lambda kk: True)[0] for s in strata})
    # 분석용 쌍 기록
    head = ['seed', '층', 'level', 'ink_gap_px', 'ink_gap_over_xh', 'ink_gap_over_inner', 'box_gap_px', 'upper_box_h_med_px',
            'upper_box_h_med_over_xh', 'box_gap_over_h', '상자_판정불가'] + order + ['C_출처']
    rows = []; hvar = defaultdict(list)
    for k, p, it in items:
        t = truths[k]; boxes = L[k]['lines']; s = _stratum(t); xh = t['condition']['xh_px_at_800']
        hs = [b[3] - b[1] for b in boxes]
        if hs:
            hvar[s].append((max(hs) - min(hs), float(np.percentile(hs, 90) - np.percentile(hs, 10)), xh))
        bb = {tb['id']: [_box_of_line(boxes, ln['ink_box']) for ln in tb['lines']] for tb in t['blocks']}
        for pi, q in enumerate(t['pairs']):
            ub, lb = bb[q['upper']], bb[q['lower']]
            gap = hmed = ratio = None; why = None
            if ub[-1] is None or lb[0] is None:
                why = '상자 없음'
            elif {j for j in ub if j is not None} & {j for j in lb if j is not None}:
                why = '한 상자가 두 블록 줄을 덮음'
            else:
                gap = boxes[lb[0]][1] - boxes[ub[-1]][3]
                hmed = float(np.median([boxes[j][3] - boxes[j][1] for j in {j for j in ub if j is not None}]))
                ratio = gap / hmed if hmed else None
            rows.append([int(k), _sname(s), q['level'], q['ink_gap_px'], q['ink_gap_over_xh'], q['ink_gap_over_inner'],
                         None if gap is None else round(gap, 3), None if hmed is None else round(hmed, 3),
                         None if hmed is None else round(hmed / xh, 4), None if ratio is None else round(ratio, 4), why]
                        + [per[m][k]['pairs'][pi]['merged'] for m in order] + [per['C'][k]['pairs'][pi]['src']])
    col = {h: i for i, h in enumerate(head)}
    res['분석용_쌍_요약'] = dict(
        상자_판정불가=dict(Counter(r[col['상자_판정불가']] for r in rows)),
        수준별_상자틈_나누기_상자높이={lv: _q([r[col['box_gap_over_h']] for r in rows if r[col['level']] == lv]) for lv in levels},
        층_수준별_상자틈_나누기_상자높이_중앙={_sname(s): {lv: _q([r[col['box_gap_over_h']] for r in rows if r[col['level']] == lv and r[col['층']] == _sname(s)]).get('중앙') for lv in levels} for s in strata},
        수준별_잉크틈_나누기_x높이={lv: _q([r[col['ink_gap_over_xh']] for r in rows if r[col['level']] == lv]) for lv in levels},
        층별_상자높이_x높이당_중앙={_sname(s): _q([r[col['upper_box_h_med_over_xh']] for r in rows if r[col['층']] == _sname(s)]).get('중앙') for s in strata},
        판_내_상자높이_변동={_sname(s): dict(최대_최소_px=_q([v[0] for v in hvar[s]]), p10_p90_px=_q([v[1] for v in hvar[s]]),
                                        최대_최소_x높이당=_q([v[0] / v[2] for v in hvar[s]])) for s in strata})
    # A 갈림 분석
    ag = {}
    for lv in levels:
        rs = [r for r in rows if r[col['level']] == lv and r[col['A']] is not None and r[col['box_gap_over_h']] is not None]
        sp_ = [r for r in rs if r[col['A']] is False]; mg = [r for r in rs if r[col['A']] is True]
        ag[lv] = dict(가른_쌍=len(sp_), 병합한_쌍=len(mg), 둘_다_5쌍_이상=(len(sp_) >= 5 and len(mg) >= 5),
                      위_상자높이_px=dict(가름=_q([r[col['upper_box_h_med_px']] for r in sp_]), 병합=_q([r[col['upper_box_h_med_px']] for r in mg])),
                      위_상자높이_x높이당=dict(가름=_q([r[col['upper_box_h_med_over_xh']] for r in sp_]), 병합=_q([r[col['upper_box_h_med_over_xh']] for r in mg])),
                      상자틈_나누기_상자높이=dict(가름=_q([r[col['box_gap_over_h']] for r in sp_]), 병합=_q([r[col['box_gap_over_h']] for r in mg])),
                      가른_쌍_층=dict(Counter(r[col['층']] for r in sp_)), 병합한_쌍_층=dict(Counter(r[col['층']] for r in mg)))
    res['A_갈림_분석'] = ag
    res['예측_정오'] = clean_verdicts(res, json.load(open(a.prereg)), json.load(open(a.check)) if a.check else None, order)
    res['분석용_쌍_기록'] = dict(열=head, 행=rows)
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    for m in order:
        cv = res['주_결과_병합률'][m]['층_가중_합산']
        print(f"  {m:4s} F1 {res['블록'][m]['층_가중_합산']['F1']} | " + ' '.join(f"{lv}:{cv[lv]['값']}" for lv in levels))
    for v in res['예측_정오']:
        print(' ', v['판정'], '·', v['항목'])
    print('→', a.out)


def clean_verdicts(res, prereg, check, order):
    """사전등록 «예측» 항마다 맞음 / 틀림 / 판단 불가. 기준은 예측 문장의 수치를 그대로 쓴다 (점추정)."""
    pred = prereg['예측 (돌리기 전에 적는다)']
    P = {m: res['주_결과_병합률'][m]['층_가중_합산'] for m in order}
    X = {m: res['주_결과_병합률'][m]['x높이별_단순평균'] for m in order}
    v = lambda m, lv: P[m][lv]['값']
    out = []

    def add(key, ok, basis, sub=None):
        out.append(dict(항목=key + (f' ({sub})' if sub else ''), 예측=pred[key],
                        판정={True: '맞음', False: '틀림', None: '판단 불가'}[ok], 근거=basis))

    def allv(ms, lvs):
        return all(v(m, lv) is not None for m in ms for lv in lvs)
    L8 = list(CLEAN_LEVELS)
    k = 'A · 병합률 > 0.5 인 구간'
    if allv(['A'], L8):
        ok = (all(v('A', lv) > 0.5 for lv in L8[:5]) and v('A', '3.0') < 0.5 and v('A', '4.0') < 0.5 and 0.3 <= v('A', '2.5') <= 0.7)
        add(k, ok, {lv: v('A', lv) for lv in L8})
    else:
        add(k, None, '빈 수준')
    k = 'VLM · 병합률 > 0.5 인 구간'
    for m in [x for x in order if x.startswith('VLM')]:
        if allv([m], L8):
            add(k, v(m, 'c_in') > 0.5 and v(m, '0.5') > 0.5 and all(v(m, lv) < 0.5 for lv in L8[2:]), {lv: v(m, lv) for lv in L8}, m)
        else:
            add(k, None, '빈 수준', m)
    if not any(x.startswith('VLM') for x in order):
        add(k, None, 'VLM 결과 없음')
    k = 'C · 병합률 > 0.5 인 구간'
    if allv(['C'], L8):
        xs = {x: {lv: X['C'][x][lv]['값'] for lv in L8[2:]} for x in X['C']}
        ok = v('C', 'c_in') >= 0.90 and all(v('C', lv) < 0.5 for lv in L8[1:]) and all(val is not None and val <= 0.10 for d in xs.values() for val in d.values())
        add(k, ok, dict(합산={lv: v('C', lv) for lv in L8}, x높이별_c1이상=xs))
    k = 'c_in 에서 세 방식이 모두 병합하나'
    need = dict(A=0.80, C=0.90, **{m: 0.90 for m in order if m.startswith('VLM')})
    if all(v(m, 'c_in') is not None for m in need):
        add(k, all(v(m, 'c_in') >= th for m, th in need.items()), {m: v(m, 'c_in') for m in need})
    k = 'x높이 5 · c 0.5 에서 C 가 τ 한계로 병합하나'
    x5, x8, x12 = (X['C'][x]['0.5']['값'] for x in ('5', '8', '12'))
    if None not in (x5, x8, x12):
        add(k, 0.10 <= x5 <= 0.50 and x8 <= 0.10 and x12 <= 0.10, {'5': x5, '8': x8, '12': x12})
    k = 'C 폴백 몫'
    fbp = res['C_폴백_몫']['층_가중_합산']
    add(k, fbp['줄_A폴백'] is not None and 0 < fbp['줄_A폴백'] <= 0.05 and fbp['쌍_C기전밖'] <= 0.10,
        dict(줄_A폴백=fbp['줄_A폴백'], 쌍_C기전밖=fbp['쌍_C기전밖']), '0 이 아님 · 줄 ≤ 5% · 쌍 ≤ 10%')
    ties = sum(res['C_폴백_몫']['진단']['공유요소'].values())
    add(k, True if ties == 0 else None, dict(공유요소_합=ties, 요소=res['C_폴백_몫']['진단']['요소'],
                                           까닭=(None if ties == 0 else '«거의 0» 의 수치 기준이 없다')), '공유 요소 거의 0')
    k = 'x높이 12 층 C 과분할'
    xo = {x: res['블록']['C']['x높이별_단순평균'][x]['과분할_정답블록당'] for x in ('5', '8', '12')}
    add(k, xo['12'] > xo['5'] and xo['12'] > xo['8'], xo)
    k = '늘어남 · 빠짐의 작용'
    rr = res['줄단위_재기']['C_과분할률_층_가중']
    g_, l_ = rr['늘어남 있음']['값'], rr['빠짐 있음']['값']
    add(k, None if g_ is None or l_ is None else l_ > g_,
        dict(빠짐_있음=rr['빠짐 있음'], 늘어남_있음=rr['늘어남 있음'], 모아서=res['줄단위_재기']['C_과분할률_모아서']))
    k = 'VLM 패스 간 블록 F1'
    if 'VLM_패스간_일치' in res:
        f = res['VLM_패스간_일치']['층_가중_합산']['블록_F1']
        add(k, f >= 0.90, f)
    else:
        add(k, None, 'VLM 두 패스 없음')
    k = '블록 F1'
    add(k, res['블록']['C']['층_가중_합산']['F1'] > res['블록']['A']['층_가중_합산']['F1'],
        {m: res['블록'][m]['층_가중_합산']['F1'] for m in order})
    k = 'A 갈림 분석'
    oks, basis = [], {}
    for lv in ('2.0', '2.5'):
        g = res['A_갈림_분석'][lv]
        if not g['둘_다_5쌍_이상']:
            oks.append(None); basis[lv] = dict(가른_쌍=g['가른_쌍'], 병합한_쌍=g['병합한_쌍'], 까닭='한쪽이 5쌍 미만'); continue
        px = g['위_상자높이_px']['가름']['중앙'] < g['위_상자높이_px']['병합']['중앙']
        xr = g['위_상자높이_x높이당']['가름']['중앙'] < g['위_상자높이_x높이당']['병합']['중앙']
        oks.append(px if px == xr else None)
        basis[lv] = dict(px=[g['위_상자높이_px']['가름']['중앙'], g['위_상자높이_px']['병합']['중앙']],
                         x높이당=[g['위_상자높이_x높이당']['가름']['중앙'], g['위_상자높이_x높이당']['병합']['중앙']],
                         기준='[가름, 병합] 중앙값. px 와 x높이당이 엇갈리면 판단 불가')
    add(k, (False if False in oks else (None if None in oks else True)), basis)
    add('C 결정론', res['C_결정론_280장'], res['C_결정론_280장'])
    if check:
        vv = check['검증']['위반_수']
        add('생성 검증', vv['쌍 겹침'] == 0 and vv['블록 안 겹침'] == 0, vv)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('score-clean', help='깨끗한 세트 채점 (docs/clean_preregister.json)')
    s.add_argument('--dir', required=True); s.add_argument('--manifest', required=True); s.add_argument('--lines', required=True)
    s.add_argument('--vlm', action='append'); s.add_argument('--prereg', required=True); s.add_argument('--out', required=True)
    s.add_argument('--check', help='docs/clean_check.json — 예측 «생성 검증» 항')
    s.add_argument('--note', action='append', help='실행 경위 (결과 파일 «경위» 에 그대로 싣는다)')
    s.add_argument('--c-pad-rule', default='neighbor_half', choices=GG.PAD_RULES)
    s.add_argument('--levels', nargs='*', default=CLEAN_LEVELS, help='주 곡선 수준 (쌍의 level 필드 값)')
    for name in ('detect', 'som', 'score'):
        s = sp.add_parser(name)
        s.add_argument('--dir', required=True); s.add_argument('--manifest', required=True); s.add_argument('--lines', required=True)
        if name == 'detect':
            s.add_argument('--order', default='yx', choices=('yx', 'columns'),
                           help='줄 순서 (= SoM 번호 순서). columns 는 단 단위 (깨끗한 세트 수정 1)')
        if name == 'som':
            s.add_argument('--som-dir', required=True)
        if name == 'score':
            s.add_argument('--vlm', action='append'); s.add_argument('--prereg', required=True); s.add_argument('--out', required=True)
            s.add_argument('--note', action='append', help='실행 경위 (결과 파일 «경위» 에 그대로 싣는다)')
            s.add_argument('--c-pad-rule', default='fixed', choices=GG.PAD_RULES,
                           help='방식 C 줄 단위 재기의 세로 pad (docs/measure_pad_preregister.json)')
    a = ap.parse_args(argv)
    {'detect': detect, 'som': som, 'score': score, 'score-clean': score_clean}[a.cmd](a)


if __name__ == '__main__':
    main()
