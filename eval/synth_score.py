"""합성 포스터 채점 — 사전등록 docs/synth_preregister.json 의 «종속변인 · 채점 정의» 그대로.

    python eval/synth_score.py --dir ~/.typo-mcp/synth --manifest docs/synth_manifest.json \
        --prereg docs/synth_preregister.json --cache-dir ~/.typo-mcp --out docs/synth_result.json

셀마다 (1) 파이프라인으로 잰다 — Surya 줄 → detect_surya.group → measure/ground.py,
measure_corpus.measure_items 그대로 (skew=False: 기울기 0° 로 그렸고 EasyOCR 각은 안 쓴다).
캐시 ~/.typo-mcp/synth-{셀}.json (provenance synthetic). 있으면 다시 안 잰다 (--remeasure).
(2) 정답과 짝지어 베이스라인 오차 · 재현율을 낸다. (3) 규칙 채택 정오 셋 — rules.derive ·
격자 공유 AUC (eval/series_check.grid_sharing) · check_layout (eval/series_check.judge).

새 지표를 더하지 않는다. 문턱을 두지 않는다 (AUC_MIN 은 discrim 의 것).
"""
import argparse
import hashlib
import json
import os
import random
import sys
import tempfile
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'eval'))
import detector_score as DSc      # noqa: E402  iou · held · inside (같은 정의를 쓴다)
import discrim                    # noqa: E402
import measure_corpus as MC       # noqa: E402
import rules                      # noqa: E402
import series_check as SC         # noqa: E402  grid_sharing · judge

IOU_MIN = DSc.IOU_MIN             # 0.5
INSIDE = DSc.INSIDE               # 0.5
LINE_TOL = 0.2                    # 줄 재현: |오차| ≤ 0.2·행간
MATCH_WIN = 0.5                   # 줄 짝짓기 창: 0.5·행간
NULL_SEED = SC.SEED               # 20260911
KEY = 'lead_over_cap'

# 사전등록의 예상 (정오를 세는 항목만)
EXPECT = {
    'shared_grid':  dict(adopt=True,  auc_ge=True,  pass_a=1.0, viol_a=None),
    'independent':  dict(adopt=True,  auc_ge=False, pass_a=1.0, viol_a=None),
    'random':       dict(adopt=None,  auc_ge=False, pass_a=None, viol_a=1.0),
}


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def _lead_of(tb):
    """한 줄 블록은 lead_px 가 없다 — 템플릿 정의대로 2·x높이(= g) 를 쓴다."""
    return tb['lead_px'] if tb.get('lead_px') else 2.0 * tb['xh_px']


# ── 재기 ────────────────────────────────────────────────────────

def measure_cell(cell, cond, items, cache, remeasure):
    if os.path.exists(cache) and not remeasure:
        d = json.load(open(cache))
        if set(d['raw']) >= {k for k, _ in items}:
            return d['raw'], d.get('provenance')
    raw, failed = MC.measure_items(items, skew=False, batch=8, log=lambda *a, **k: None)
    prov = MC.provenance(f'eval/synth_score.py — {cell}', len(raw))
    prov.update(synthetic=True, cell=cell, condition=cond, skew='안 잼 (기울기 0° 로 그림)',
                failed=[(os.path.basename(p), w) for p, w in failed])
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(dict(raw=raw, rules={}, source=f'synth/{cell}', detector='surya', provenance=prov),
              open(cache, 'w'), ensure_ascii=False)
    return raw, prov


# ── 짝짓기 · 오차 ───────────────────────────────────────────────

def match_blocks(truth_blocks, meas_blocks):
    T = [tb['ink_box'] for tb in truth_blocks]
    P = [[b['x1'], b['y1'], b['x2'], b['y2']] for b in meas_blocks]
    mr, mp = DSc.match(T, P)
    merged = sum(1 for j, p in enumerate(P)
                 if sum(1 for r in T if DSc.held(p, r) >= INSIDE) >= 2)
    split = sum(1 for j, p in enumerate(P)
                if j not in mp and any(DSc.inside(p, r) >= INSIDE for r in T))
    return mr, merged, split


def match_lines(tlines, tlead, bases, caps, xtops):
    """정답 줄 ↔ 측정 base. 차가 0.5·행간 이내인 가장 가까운 것, 1:1 (차 작은 순)."""
    pairs = sorted(((abs(mb - tl['baseline_y']), i, j)
                    for i, tl in enumerate(tlines) for j, mb in enumerate(bases)),
                   key=lambda t: t[0])
    mi, mj, out = {}, {}, []
    for dlt, i, j in pairs:
        if dlt > MATCH_WIN * tlead:
            break
        if i in mi or j in mj:
            continue
        mi[i] = j; mj[j] = i
        tl = tlines[i]
        out.append(dict(i=i, j=j, err=bases[j] - tl['baseline_y'],
                        cap_err=(None if caps[j] is None else caps[j] - tl['cap_y']),
                        xtop_err=(None if xtops[j] is None else xtops[j] - tl['xtop_y'])))
    return out


def score_poster(t, m):
    """한 장: 줄 오차 목록 · 재현 · 블록 짝."""
    mr, merged, split = match_blocks(t['blocks'], m['blocks'])
    rows, n_truth, n_hit = [], 0, 0
    per_block = {}
    for i, tb in enumerate(t['blocks']):
        lead = _lead_of(tb)
        n_truth += tb['n']
        if i not in mr:
            per_block[tb['id']] = None
            continue
        mb = m['blocks'][mr[i]]
        got = match_lines(tb['lines'], lead, mb['bases'], mb['caps'], mb['xtops'])
        for g in got:
            g.update(block=tb['id'], lead=lead, pct=100.0 * g['err'] / lead,
                     err800=g['err'] / t['scale_from_800'])
            if abs(g['err']) <= LINE_TOL * lead:
                n_hit += 1
        rows += got
        per_block[tb['id']] = dict(j=mr[i], bases=list(mb['bases']),
                                   caps=list(mb['caps']), n=mb['n'])
    n_meas = sum(len(b['bases']) for b in m['blocks'])
    return dict(rows=rows, n_truth=n_truth, n_hit=n_hit, n_meas=n_meas,
                n_matched=len(rows), blocks_hit=len(mr), blocks=len(t['blocks']),
                merged=merged, split=split, per_block=per_block)


def _q(a, ps):
    a = np.asarray([x for x in a if x is not None], float)
    if a.size == 0:
        return {p: None for p in ps}
    return {p: round(float(np.percentile(a, p)), 3) for p in ps}


def summarize(posters):
    err = [r['err'] for p in posters for r in p['rows']]
    pct = [r['pct'] for p in posters for r in p['rows']]
    e800 = [r['err800'] for p in posters for r in p['rows']]
    ae = [abs(x) for x in err]
    apct = [abs(x) for x in pct]
    cap = [r['cap_err'] for p in posters for r in p['rows'] if r['cap_err'] is not None]
    xt = [r['xtop_err'] for p in posters for r in p['rows'] if r['xtop_err'] is not None]
    nt = sum(p['n_truth'] for p in posters); nh = sum(p['n_hit'] for p in posters)
    nm = sum(p['n_meas'] for p in posters); nmat = sum(p['n_matched'] for p in posters)
    bt = sum(p['blocks'] for p in posters); bh = sum(p['blocks_hit'] for p in posters)
    return dict(
        판=len(posters), 정답_줄=nt, 측정_줄=nm, 짝지은_줄=nmat,
        편향_px=dict(중앙=_q(err, (50,))[50], 구간_10_90=[_q(err, (10,))[10], _q(err, (90,))[90]]),
        절대오차_px=dict(중앙=_q(ae, (50,))[50], p90=_q(ae, (90,))[90], 구간_10_90=[_q(ae, (10,))[10], _q(ae, (90,))[90]]),
        절대오차_pct행간=dict(중앙=_q(apct, (50,))[50], p90=_q(apct, (90,))[90]),
        편향_pct행간_중앙=_q(pct, (50,))[50],
        절대오차_800기준_px=dict(중앙=_q([abs(x) for x in e800], (50,))[50], p90=_q([abs(x) for x in e800], (90,))[90]),
        줄_재현율=round(nh / nt, 4) if nt else None,
        줄_정밀도=round(nmat / nm, 4) if nm else None,
        블록_재현율=round(bh / bt, 4) if bt else None,
        과병합=sum(p['merged'] for p in posters), 과분할=sum(p['split'] for p in posters),
        캡_오차_px=dict(중앙=_q(cap, (50,))[50], 절대_중앙=_q([abs(x) for x in cap], (50,))[50], n=len(cap)),
        x높이선_오차_px=dict(중앙=_q(xt, (50,))[50], 절대_중앙=_q([abs(x) for x in xt], (50,))[50], n=len(xt)),
        줄_재현율_장별=[round(p['n_hit'] / p['n_truth'], 3) for p in posters])


# ── 규칙 채택 정오 ──────────────────────────────────────────────

def truth_raw(truths):
    """정답을 raw 모양으로 — 격자 공유 지표가 읽는 필드만 (size · blocks: bases · n · y1 · y2)."""
    out = {}
    for k, t in truths.items():
        out[k] = dict(size=t['canvas'], skewed=False,
                      blocks=[dict(n=tb['n'], bases=[l['baseline_y'] for l in tb['lines']],
                                   x1=tb['ink_box'][0], y1=tb['ink_box'][1],
                                   x2=tb['ink_box'][2], y2=tb['ink_box'][3])
                              for tb in t['blocks']])
    return out


def _rule_entry(R):
    e = R['rules'].get(KEY) or R['not_rules'].get(KEY)
    if not e:
        return dict(verdict='없음')
    return {k: e.get(k) for k in ('verdict', 'median', 'lo', 'hi', 'cv', 'n', 'n_all')}


def check_blocks(cache, truths, posters):
    """③ n≥3 정답 블록마다 (a) 정답 입력 (b) 측정 입력으로 check_layout."""
    res = {}
    for tag in ('a', 'b'):
        cnt, kinds, n_na = Counter(), Counter(), 0
        for k, t in truths.items():
            pb = posters[k]['per_block']
            for tb in t['blocks']:
                if tb['n'] < 3:
                    continue
                if tag == 'a':
                    cap, bases = tb['cap_px'], [l['baseline_y'] for l in tb['lines']]
                else:
                    mb = pb.get(tb['id'])
                    cs = ([b - c for b, c in zip(mb['bases'], mb['caps']) if c is not None] if mb else [])
                    if not mb or len(mb['bases']) < 3 or not cs:
                        n_na += 1
                        continue
                    cap, bases = float(np.median(cs)), sorted(float(x) for x in mb['bases'])
                verdict, ks = SC.judge(cache, cap, bases, None)
                cnt[verdict] += 1
                for x in ks:
                    kinds[x] += 1
        n = sum(cnt.values())
        res[tag] = dict(블록=n, 측정_불가=n_na,
                        통과율=round(cnt['통과'] / n, 4) if n else None,
                        보류율=round(cnt['보류'] / n, 4) if n else None,
                        위반율=round(cnt['위반'] / n, 4) if n else None,
                        위반_종류=dict(kinds))
    return res


def rule_checks(cell, cond, raw, truths, posters):
    R = rules.derive(raw)
    ex = EXPECT[cond['rule']]
    out = {'①_lead_over_cap': _rule_entry(R)}
    out['①_lead_over_cap']['채택'] = KEY in R['rules']
    out['①_lead_over_cap']['예상'] = ex['adopt']
    out['①_lead_over_cap']['정오'] = (None if ex['adopt'] is None
                                    else ('정' if (KEY in R['rules']) == ex['adopt'] else '오'))
    g_t = SC.grid_sharing(truth_raw(truths), random.Random(NULL_SEED))
    g_m = SC.grid_sharing(raw, random.Random(NULL_SEED))
    for name, g in (('정답', g_t), ('측정', g_m)):
        ok = g.get('AUC_MIN_넘음')
        g['예상_AUC_MIN_넘음'] = ex['auc_ge']
        g['정오'] = None if ok is None else ('정' if ok == ex['auc_ge'] else '오')
    out['②_격자공유'] = dict(정답=g_t, 측정=g_m)
    with tempfile.TemporaryDirectory() as tmp:
        c = os.path.join(tmp, 'rules.json')
        rules.save(c, {}, R)
        cb = check_blocks(c, truths, posters)
    a = cb['a']
    if ex['pass_a'] is not None:
        a['예상'] = f'통과율 {ex["pass_a"]}'
        a['정오'] = '정' if a['통과율'] == ex['pass_a'] else '오'
    elif ex['viol_a'] is not None:
        a['예상'] = f'위반율 {ex["viol_a"]} · 종류 블록 내 행간 일정'
        only = set(a['위반_종류']) <= {'블록 내 행간 일정'}
        a['정오'] = '정' if (a['위반율'] == ex['viol_a'] and only) else '오'
    out['③_check_layout'] = cb
    out['블록안_행간일정_검산_측정'] = SC.within_block(raw)
    return out


# ── 사전등록 예측 가운데 수치가 있는 것 ─────────────────────────

def predictions(S):
    b = S['base']
    P = {}
    if 'res_1600' in S:
        r = S['res_1600']
        P['해상도 1600 — 재현율 ±0.03 안'] = dict(
            줄_차=round(r['줄_재현율'] - b['줄_재현율'], 4), 블록_차=round(r['블록_재현율'] - b['블록_재현율'], 4),
            판정=('맞음' if abs(r['줄_재현율'] - b['줄_재현율']) <= 0.03 and abs(r['블록_재현율'] - b['블록_재현율']) <= 0.03 else '틀림'))
        P['해상도 1600 — 800 기준 |오차| 중앙이 준다'] = dict(
            기준=b['절대오차_800기준_px']['중앙'], _1600=r['절대오차_800기준_px']['중앙'],
            판정=('판단 불가' if None in (b['절대오차_800기준_px']['중앙'], r['절대오차_800기준_px']['중앙'])
                 else '맞음' if r['절대오차_800기준_px']['중앙'] < b['절대오차_800기준_px']['중앙'] else '틀림'))
    if 'xh_3' in S:
        r = S['xh_3']
        P['x높이 3 — 줄 재현율 크게 떨어짐 · 캡/x높이 오차 > 20% 행간'] = dict(
            줄_재현율=r['줄_재현율'], 기준=b['줄_재현율'],
            캡_절대오차_px=r['캡_오차_px']['절대_중앙'], x높이선_절대오차_px=r['x높이선_오차_px']['절대_중앙'],
            행간_px=6.0)
    if 'jpeg_95' in S and 'jpeg_45' in S:
        d95 = abs((S['jpeg_95']['절대오차_px']['중앙'] or 0) - (b['절대오차_px']['중앙'] or 0))
        P['JPEG — 95 vs 72 |오차| 중앙 차 ≤ 0.25px, 45 에서 커짐'] = dict(
            차_95=round(d95, 3), 중앙_45=S['jpeg_45']['절대오차_px']['중앙'], 중앙_72=b['절대오차_px']['중앙'],
            판정=('맞음' if d95 <= 0.25 and (S['jpeg_45']['절대오차_px']['중앙'] or 0) > (b['절대오차_px']['중앙'] or 0) else '틀림'))
    return P


def main(argv=None):
    ap = argparse.ArgumentParser(description='합성 포스터 채점 — 경로는 모두 인자')
    ap.add_argument('--dir', required=True, help='이미지 · 정답 폴더')
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--prereg', required=True)
    ap.add_argument('--cache-dir', required=True, help='셀별 측정 캐시 폴더 (~/.typo-mcp)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--cells', nargs='*')
    ap.add_argument('--remeasure', action='store_true')
    a = ap.parse_args(argv)
    D = os.path.expanduser(a.dir)
    M = json.load(open(a.manifest))
    cells = a.cells or list(M['cells'])
    res = dict(무엇='합성 포스터 통제 실험 — 파이프라인이 정답을 얼마나 되찾는가',
               사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg),
               manifest=a.manifest, manifest_sha256=_sha(a.manifest),
               manifest_provenance=M.get('provenance'),
               정의=dict(블록_짝='IoU ≥ 0.5 · 1:1 탐욕 (detector_score.match)',
                       줄_짝='짝지은 블록 안, |측정 base − 정답 baseline_y| ≤ 0.5·행간, 가장 가까운 것 1:1',
                       줄_재현='|오차| ≤ 0.2·행간', 행간='블록 lead_px, 한 줄 블록은 2·x높이',
                       오차='측정 base − 정답 baseline_y (px), % 는 행간 대비',
                       격자공유='eval/series_check.grid_sharing · 귀무 200벌 seed 20260911',
                       check_layout='eval/series_check.judge 기본 호출(layer 없음), 규칙은 그 셀의 rules.derive'),
               셀={})
    prov = {}
    for cell in cells:
        cond = M['cells'][cell]
        seeds = [it['seed'] for it in M['items'] if it['cell'] == cell]
        items = [(f'{cell}/{s:03d}', os.path.join(D, cell, f'{s:03d}.jpg')) for s in seeds]
        for k, p in items:
            if _sha(p) != next(it['image_sha256'] for it in M['items'] if it['cell'] == cell and it['seed'] == int(k[-3:])):
                sys.exit(f'manifest 와 다른 이미지: {p}')
        cache = os.path.join(os.path.expanduser(a.cache_dir), f'synth-{cell}.json')
        raw, prov[cell] = measure_cell(cell, cond, items, cache, a.remeasure)
        truths = {k: json.load(open(p[:-4] + '.json')) for k, p in items}
        posters = {k: score_poster(truths[k], raw[k]) for k, _ in items if k in raw}
        failed = [k for k, _ in items if k not in raw]
        S = summarize(list(posters.values()))
        S['측정_실패_판'] = failed
        S['조건'] = cond
        S['규칙'] = rule_checks(cell, cond, {k: raw[k] for k in posters}, {k: truths[k] for k in posters}, posters)
        S['캐시'] = cache
        res['셀'][cell] = S
        print(f'{cell:18s} 줄재현 {S["줄_재현율"]}  블록재현 {S["블록_재현율"]}  |오차| 중앙 {S["절대오차_px"]["중앙"]}px '
              f'({S["절대오차_pct행간"]["중앙"]}%)  편향 {S["편향_px"]["중앙"]}  '
              f'① {S["규칙"]["①_lead_over_cap"]["정오"]} ② {S["규칙"]["②_격자공유"]["정답"]["정오"]}/{S["규칙"]["②_격자공유"]["측정"]["정오"]} '
              f'③a {S["규칙"]["③_check_layout"]["a"].get("정오")} 통과(b) {S["규칙"]["③_check_layout"]["b"]["통과율"]}', flush=True)
    res['측정_provenance'] = prov
    if 'base' in res['셀']:
        res['예측_수치_판정'] = predictions(res['셀'])
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('→', a.out)


if __name__ == '__main__':
    main()
