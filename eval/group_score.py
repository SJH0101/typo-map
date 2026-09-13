"""묶기 방식 비교 — 채점. 사전등록 docs/group_preregister.json (57f5dbe) 의 «채점» 그대로.

세 단계다.
    detect  Surya 줄을 한 번 검출해 저장         python eval/group_score.py detect --dir D --manifest M --lines L
    som     VLM 에 보일 번호 이미지(2배)를 그린다  python eval/group_score.py som --dir D --manifest M --lines L --som-dir S
    score   A · VLM · 오라클을 채점한다           python eval/group_score.py score --dir D --manifest M --lines L
                                                   [--vlm pass1.json --vlm pass2.json] --prereg P --out O
줄 번호는 y1 → x1 순으로 1 부터. A 는 detect_surya.group 그대로, 줄 소속은 나온 블록 상자에
줄 상자가 가장 많이 든 것으로 정한다. 오라클은 줄마다 잉크 상자가 가장 많이 겹치는 정답 블록.
새 지표를 더하지 않는다.
"""
import argparse
import hashlib
import itertools
import json
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
            out[k] = dict(size=list(im.size), lines=ls, sha256=_sha(p))
        print(f'  {min(i + 8, len(items))}/{len(items)}', flush=True)
    prov = MC.provenance('eval/group_score.py detect', len(out)); prov['synthetic'] = True
    json.dump(dict(lines=out, provenance=prov, note='줄 번호 = 목록 순서 + 1 (y1 → x1)'),
              open(os.path.expanduser(a.lines), 'w'), ensure_ascii=False)
    print('→', a.lines)


# ── som ─────────────────────────────────────────────────────────

def som(a):
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    L = json.load(open(os.path.expanduser(a.lines)))['lines']
    S = os.path.expanduser(a.som_dir); os.makedirs(S, exist_ok=True)
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 15, index=1)
    rows = []
    for k, p, it in _items(D, M):
        if not it.get('vlm_subset'):
            continue
        im = Image.open(p).convert('RGB')
        W, H = im.size
        im = im.resize((W * 2, H * 2), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(im)
        for i, (x1, y1, x2, y2) in enumerate(L[k]['lines'], 1):
            X1, Y1, X2, Y2 = x1 * 2, y1 * 2, x2 * 2, y2 * 2
            d.rectangle([X1, Y1, X2, Y2], outline=(220, 30, 30), width=2)
            lab = str(i); tw = d.textlength(lab, font=font) + 6; th = 18
            # 딱지는 홀수 번호 왼쪽 · 짝수 번호 오른쪽 — 촘촘한 줄에서 딱지끼리 겹치지 않게
            if i % 2 == 1:
                bx = X1 - tw - 3
                if bx < 0: bx = X1 + 2
            else:
                bx = X2 + 3
                if bx + tw > W * 2: bx = X2 - tw - 2
            by = max(0, min(H * 2 - th, Y1 - 1))
            d.rectangle([bx, by, bx + tw, by + th], fill=(255, 255, 255), outline=(30, 60, 220), width=1)
            d.text((bx + 3, by + 1), lab, font=font, fill=(30, 60, 220))
        op = os.path.join(S, f'{k}_som.png')
        im.save(op)
        rows.append(dict(file=f'{k}_som.png', path=op, n_lines=len(L[k]['lines'])))
    lst = os.path.join(S, 'list.md')
    with open(lst, 'w') as f:
        f.write(f'## 이미지 {len(rows)}장\n')
        for r in rows:
            f.write(f'- file: {r["file"]}\n  path: {r["path"]}\n  상자 수: {r["n_lines"]}\n')
    json.dump(rows, open(os.path.join(S, 'list.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(rows)}장 → {S} (목록 {lst})')


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


def score_method(name, items, L, truths, asg_fn, measure=True):
    rows_blk = []; pair_rows = []; meas_rows = []
    tot = Counter()
    for k, p, it in items:
        lines = L[k]['lines']; t = truths[k]
        asg = asg_fn(k, lines, t)
        boxes = boxes_of(lines, asg)
        P = [b[1][:4] for b in boxes]
        T = [tb['ink_box'] for tb in t['blocks']]
        mr, mp = DSc.match(T, P)
        merged = sum(1 for j, pb in enumerate(P) if sum(1 for r in T if DSc.held(pb, r) >= DSc.INSIDE) >= 2)
        split = sum(1 for j, pb in enumerate(P) if j not in mp and any(DSc.inside(pb, r) >= DSc.INSIDE for r in T))
        tot['참조'] += len(T); tot['출처'] += len(P); tot['맞음'] += len(mr); tot['과병합'] += merged; tot['과분할'] += split
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
            if not gu or not gl:
                dec = None
            else:
                dec = (gu.most_common(1)[0][0] == gl.most_common(1)[0][0])
            pair_rows.append(dict(seed=int(k), **{kk: q[kk] for kk in ('gap_level', 'size_ratio', 'column', 'bumped', 'upper_n', 'lower_n')},
                                  columns=t['condition']['columns'], xh=t['condition']['xh_px_at_800'], merged=dec))
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
    return dict(blocks=dict(판=len(items), 참조=tot['참조'], 출처=tot['출처'], 맞음=tot['맞음'],
                            재현율=round(R, 4) if R is not None else None, 정밀도=round(Pp, 4) if Pp is not None else None,
                            F1=round(F, 4) if F else None, 과병합=tot['과병합'], 과분할=tot['과분할']),
                pairs=pair_rows, meas=meas_rows)


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
        if tag == '120장_VLM표본':          # VLM 은 표본 120장만 있다
            for i, (vm, vinfo) in enumerate(vlms, 1):
                out[f'VLM{i}'] = score_method(f'VLM{i}', items_, L, truths, lambda k, ls, t, vm=vm: groups_vlm(ls, vm.get(k))[0])
        return out
    # 결정론 확인: A · 오라클 두 번
    a1 = score_method('A', items[:20], L, truths, lambda k, ls, t: groups_A(ls), measure=False)
    a2 = score_method('A', items[:20], L, truths, lambda k, ls, t: groups_A(ls), measure=False)
    res['A_결정론_20장'] = (a1['blocks'] == a2['blocks'] and a1['pairs'] == a2['pairs'])
    for tag, its in (('240장', items), ('120장_VLM표본', sub)):
        out = run_all(its, tag)
        block = {}
        for m, r in out.items():
            block[m] = dict(**r['blocks'],
                            쌍_주곡선=pair_table(r['pairs'], MAIN_LEVELS),
                            쌍_주곡선_단수별=pair_table(r['pairs'], MAIN_LEVELS, by=('columns',)),
                            쌍_주곡선_x높이별=pair_table(r['pairs'], MAIN_LEVELS, by=('xh',)),
                            쌍_1g이하=pair_table(r['pairs'], LOW_LEVELS, by=('size_ratio', 'bumped')),
                            재기=meas_summary(r['meas']))
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


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    for name in ('detect', 'som', 'score'):
        s = sp.add_parser(name)
        s.add_argument('--dir', required=True); s.add_argument('--manifest', required=True); s.add_argument('--lines', required=True)
        if name == 'som':
            s.add_argument('--som-dir', required=True)
        if name == 'score':
            s.add_argument('--vlm', action='append'); s.add_argument('--prereg', required=True); s.add_argument('--out', required=True)
            s.add_argument('--note', action='append', help='실행 경위 (결과 파일 «경위» 에 그대로 싣는다)')
    a = ap.parse_args(argv)
    {'detect': detect, 'som': som, 'score': score}[a.cmd](a)


if __name__ == '__main__':
    main()
