"""깨끗한 세트 — 정답을 보고 최적화한 A. 사전등록 docs/clean_a_sweep_preregister.json (3acb98e).

    python eval/clean_a_sweep.py --dir ~/.typo-mcp/clean --manifest docs/clean_manifest.json \\
        --lines ~/.typo-mcp/clean-lines.json --result docs/clean_result.json \\
        --prereg docs/clean_a_sweep_preregister.json --out docs/clean_a_sweep.json

detect_surya.group 의 문턱 Y_GAP 상한 · H_RATIO · X_OVER 를 훑어, 층 가중 블록 F1 이 가장 높은 조합을 고른다.
문턱은 이 프로세스(와 일꾼 프로세스) 안에서만 detect_surya 의 모듈 상수로 바꿔 부른다 — detect_surya.py 는 고치지
않고, 파이프라인 기본값도 바꾸지 않는다. 채점 정의는 eval/group_score.py 의 clean_method · clean_blocks ·
clean_curves 그대로. C · VLM 은 docs/clean_result.json 에서 옮기기만 한다.
"""
import argparse
import hashlib
import itertools
import json
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import detect_surya as DS   # noqa: E402
import group_score as GS    # noqa: E402

LABEL = '정답을 보고 최적화한 A'
ORIG = dict(y_hi=DS.Y_GAP[1], h_lo=DS.H_RATIO[0], h_hi=DS.H_RATIO[1], x_over=DS.X_OVER)   # 1.60 · 0.60 · 1.70 · 0.15
Y_LO = DS.Y_GAP[0]                                                                       # −0.40 그대로
Y_HI = [round(0.05 * i, 2) for i in range(61)]                                           # 0.00 ~ 3.00
H_LO = [0.40, 0.50, 0.60, 0.70, 0.80]
H_HI = [1.30, 1.50, 1.70, 2.00, 2.50]
X_OV = [0.00, 0.05, 0.15, 0.30, 0.50]

_G = {}


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def _load(a):
    D = os.path.expanduser(a['dir']); M = json.load(open(a['manifest']))
    L = json.load(open(os.path.expanduser(a['lines'])))['lines']
    items = GS._items(D, M)
    for k, p, it in items:
        if _sha(p) != it['image_sha256'] or L[k]['sha256'] != it['image_sha256']:
            sys.exit(f'manifest 와 다른 이미지 또는 줄 캐시: {p}')
    truths = {k: json.load(open(p[:-4] + '.json')) for k, p, it in items}
    strata = sorted({GS._stratum(t) for t in truths.values()})
    return items, L, truths, strata


def _init(a):
    _G['items'], _G['L'], _G['truths'], _G['strata'] = _load(a)


def _set(cfg):
    DS.Y_GAP = (Y_LO, cfg['y_hi']); DS.H_RATIO = (cfg['h_lo'], cfg['h_hi']); DS.X_OVER = cfg['x_over']


def _per(cfg):
    _set(cfg)
    items, L, truths = _G['items'], _G['L'], _G['truths']
    asg = {k: GS.groups_A(L[k]['lines']) for k, _p, _it in items}
    return GS.clean_method(items, L, truths, asg)


def _f1(per, keep=None):
    sub = per if keep is None else {k: v for k, v in per.items() if keep(k)}
    return GS.clean_blocks(sub, _G['strata'])['층_가중_합산']['F1']


def _eval(cfg):
    per = _per(cfg)
    return dict(**cfg, F1=_f1(per), F1_홀=_f1(per, lambda k: int(k) % 2 == 1), F1_짝=_f1(per, lambda k: int(k) % 2 == 0))


def _dist(c):
    return (abs(c['y_hi'] - ORIG['y_hi']), abs(c['h_lo'] - ORIG['h_lo']) + abs(c['h_hi'] - ORIG['h_hi']), abs(c['x_over'] - ORIG['x_over']))


def _best(rows, key='F1'):
    """F1 소수 넷째 자리까지 최대, 같으면 원래 문턱에 가까운 조합 (사전등록 «판정»)."""
    top = max(round(r[key], 4) for r in rows if r[key] is not None)
    return min((r for r in rows if r[key] is not None and round(r[key], 4) == top), key=_dist)


def _cfg(r):
    return {k: r[k] for k in ('y_hi', 'h_lo', 'h_hi', 'x_over')}


def _detail(cfg):
    per = _per(cfg)
    b = GS.clean_blocks(per, _G['strata']); c = GS.clean_curves(per, _G['strata'], list(GS.CLEAN_LEVELS))
    return dict(문턱=dict(Y_GAP=[Y_LO, cfg['y_hi']], H_RATIO=[cfg['h_lo'], cfg['h_hi']], X_OVER=cfg['x_over'], MIN_AREA=DS.MIN_AREA),
                블록=b, 병합률=c)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for n in ('--dir', '--manifest', '--lines', '--result', '--prereg', '--out'):
        ap.add_argument(n, required=True)
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = vars(ap.parse_args(argv))
    grid = [dict(y_hi=y, h_lo=hl, h_hi=hh, x_over=x) for hl, hh, x, y in itertools.product(H_LO, H_HI, X_OV, Y_HI)]
    with mp.get_context('spawn').Pool(a['workers'], initializer=_init, initargs=(a,)) as pool:
        rows = pool.map(_eval, grid, chunksize=25)
    _init(a)
    R = json.load(open(a['result']))
    best = _best(rows)
    y_only = [r for r in rows if (r['h_lo'], r['h_hi'], r['x_over']) == (ORIG['h_lo'], ORIG['h_hi'], ORIG['x_over'])]
    best_y = _best(y_only)
    orig = [r for r in y_only if r['y_hi'] == ORIG['y_hi']][0]
    at_best_hx = [r for r in rows if (r['h_lo'], r['h_hi'], r['x_over']) == (best['h_lo'], best['h_hi'], best['x_over'])]
    hx_table = {f"H {hl}~{hh} · X {x}": (lambda s: dict(Y_GAP상한=s['y_hi'], F1=s['F1']))(_best([r for r in rows if (r['h_lo'], r['h_hi'], r['x_over']) == (hl, hh, x)]))
                for hl, hh, x in itertools.product(H_LO, H_HI, X_OV)}
    x_at_best = {str(x): [r['F1'] for r in rows if (r['y_hi'], r['h_lo'], r['h_hi'], r['x_over']) == (best['y_hi'], best['h_lo'], best['h_hi'], x)][0] for x in X_OV}
    odd_pick = _best(rows, 'F1_홀'); even_pick = _best(rows, 'F1_짝')
    D_best, D_y, D_orig = _detail(_cfg(best)), _detail(_cfg(best_y)), _detail(ORIG)
    same_orig = abs(D_orig['블록']['층_가중_합산']['F1'] - R['블록']['A']['층_가중_합산']['F1']) < 1e-9
    methods = {f'{LABEL} (조합 최적)': D_best, f'{LABEL} (Y_GAP 상한만 최적)': D_y}
    table = {}
    for name, d in methods.items():
        table[name] = dict(블록=d['블록']['층_가중_합산'], 병합률={lv: v['값'] for lv, v in d['병합률']['층_가중_합산'].items()})
    for m, name in (('A', '원래 문턱의 A'), ('C', 'C'), ('VLM1', 'VLM 패스 1'), ('VLM2', 'VLM 패스 2')):
        table[name] = dict(블록=R['블록'][m]['층_가중_합산'], 병합률={lv: v['값'] for lv, v in R['주_결과_병합률'][m]['층_가중_합산'].items()})
    fb, fy, fc = best['F1'], best_y['F1'], R['블록']['C']['층_가중_합산']['F1']
    gap = fc - fb
    interp = '문턱 문제가 컸다' if gap <= 0.05 else ('접근 방식의 한계가 남는다' if gap >= 0.20 else '섞임')
    inrange = lambda v, lo, hi: lo <= v <= hi
    mb = D_best['병합률']['층_가중_합산']
    verdicts = [
        dict(항목='Y_GAP 만 훑을 때의 최적 상한 0.15 ~ 0.35', 판정=inrange(best_y['y_hi'], 0.15, 0.35), 값=best_y['y_hi']),
        dict(항목='Y_GAP 만 최적일 때 A 의 F1 0.65 ~ 0.85', 판정=inrange(fy, 0.65, 0.85), 값=fy),
        dict(항목='조합 최적 — Y_GAP 상한 0.15 ~ 0.35', 판정=inrange(best['y_hi'], 0.15, 0.35), 값=best['y_hi']),
        dict(항목='조합 최적 — H_RATIO 하한 ≤ 0.60 · 상한 ≥ 1.70', 판정=(best['h_lo'] <= 0.60 and best['h_hi'] >= 1.70), 값=[best['h_lo'], best['h_hi']]),
        dict(항목='조합 최적 — X_OVER 5값의 F1 차 ≤ 0.01', 판정=(max(x_at_best.values()) - min(x_at_best.values()) <= 0.01), 값=x_at_best),
        dict(항목='조합 최적일 때 A 의 F1 0.80 ~ 0.90', 판정=inrange(fb, 0.80, 0.90), 값=fb),
        dict(항목='조합 최적 A 의 F1 이 VLM 패스 1 (0.898) 을 넘지 않는다', 판정=(fb <= R['블록']['VLM1']['층_가중_합산']['F1']), 값=[fb, R['블록']['VLM1']['층_가중_합산']['F1']]),
        dict(항목='최적 A 의 c_in 병합률 ≥ 0.80', 판정=(mb['c_in']['값'] >= 0.80), 값=mb['c_in']['값']),
        dict(항목='최적 A 의 c 0.5 병합률 ≤ 0.50', 판정=(mb['0.5']['값'] <= 0.50), 값=mb['0.5']['값']),
        dict(항목='해석 — 조합 최적 F1 이 C 보다 0.20 이상 낮지 않다', 판정=(gap < 0.20), 값=dict(C=fc, 차=round(gap, 4), 해석=interp)),
        dict(항목='보조 — 한쪽에서 고른 조합의 다른 쪽 F1 이 조합 최적 F1 과 0.02 안', 판정=(abs(even_pick['F1_홀'] - fb) <= 0.02 and abs(odd_pick['F1_짝'] - fb) <= 0.02),
             값=dict(짝에서_고른_조합_홀_F1=even_pick['F1_홀'], 홀에서_고른_조합_짝_F1=odd_pick['F1_짝'])),
    ]
    for v in verdicts:
        v['판정'] = '맞음' if v['판정'] else '틀림'
    res = dict(
        무엇=f'깨끗한 세트 — {LABEL}. 층 가중 블록 F1 이 가장 높은 문턱 조합',
        표기=f'«{LABEL}» — 이 세트의 정답으로 문턱을 고른 A 에게 유리한 조건. 파이프라인 기본값이 아니다 (detect_surya.py 는 그대로)',
        조정하지_않은_것='C · VLM (docs/clean_result.json 값 그대로), 원래 문턱 A 의 결과',
        사전등록=a['prereg'], 사전등록_sha256=_sha(a['prereg']), manifest=a['manifest'], manifest_sha256=_sha(a['manifest']),
        참조결과=a['result'], 참조결과_sha256=_sha(a['result']), detect_surya_sha256=_sha(os.path.join(ROOT, 'detect_surya.py')),
        훑은_값=dict(Y_GAP상한=Y_HI, H_RATIO하한=H_LO, H_RATIO상한=H_HI, X_OVER=X_OV, Y_GAP하한_고정=Y_LO, MIN_AREA_고정=DS.MIN_AREA, 조합=len(rows)),
        원래_문턱_재현=dict(F1=D_orig['블록']['층_가중_합산']['F1'], clean_result_와_같음=same_orig),
        최적=dict(조합=dict(문턱=_cfg(best), F1=fb), Y_GAP상한만=dict(문턱=_cfg(best_y), F1=fy), 원래=dict(문턱=ORIG, F1=orig['F1'])),
        원래_값과의_차=dict(Y_GAP상한=round(best['y_hi'] - ORIG['y_hi'], 2), H_RATIO하한=round(best['h_lo'] - ORIG['h_lo'], 2),
                       H_RATIO상한=round(best['h_hi'] - ORIG['h_hi'], 2), X_OVER=round(best['x_over'] - ORIG['x_over'], 2),
                       F1=round(fb - orig['F1'], 4), Y_GAP상한만_F1=round(fy - orig['F1'], 4)),
        F1_곡선=dict(Y_GAP상한_원래_H_X={str(r['y_hi']): r['F1'] for r in y_only},
                   Y_GAP상한_최적_H_X={str(r['y_hi']): r['F1'] for r in at_best_hx}),
        H_X별_Y최적=hx_table, 조합최적의_X_OVER별_F1=x_at_best,
        나란히=table,
        최적_상세={f'{LABEL} (조합 최적)': D_best, f'{LABEL} (Y_GAP 상한만 최적)': D_y},
        보조_두쪽나눔=dict(설명='seed 홀짝으로 나눠 한쪽에서 고르고 다른 쪽에서 잰다 — 서술용',
                       홀에서_고른_조합=dict(문턱=_cfg(odd_pick), 홀_F1=odd_pick['F1_홀'], 짝_F1=odd_pick['F1_짝']),
                       짝에서_고른_조합=dict(문턱=_cfg(even_pick), 짝_F1=even_pick['F1_짝'], 홀_F1=even_pick['F1_홀'])),
        해석=dict(C와의_차=round(gap, 4), 판정=interp, 규칙='C 보다 0.05 이하로 낮거나 높으면 문턱 문제가 컸다 · 0.20 이상 낮으면 접근 한계가 남는다 · 그 사이 섞임'),
        예측_정오=verdicts,
        조합별=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows])
    json.dump(res, open(a['out'], 'w'), ensure_ascii=False, indent=1)
    print(f'조합 {len(rows)} · 원래 문턱 재현 {same_orig} → {a["out"]}')


if __name__ == '__main__':
    main()
