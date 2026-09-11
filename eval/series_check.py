"""시리즈 단위 판별 시험 — 탐색용. 결과는 논문 수치로 쓰지 않는다.

정의는 docs/series_check_preregister.json (3ad7830, 추가 9ebe894) 그대로다.
채택 범위와 문턱은 바꾸지 않는다. rules · check_layout · place_text 를 고치지
않고 부른다.

    python eval/series_check.py --cache ~/.typo-mcp/brockmann.json --series Musica_Viva \\
        --other 로제=~/.typo-mcp/rose.json --other 루더=~/.typo-mcp/ruder.json --other 호프만=~/.typo-mcp/corpus.json \\
        --hand-lines 손찍기_lines.csv --hand-blocks 손찍기_blocks.csv \\
        --hand-poster "1958_Musica viva - Dienstag, den 7. Januar 1958" --hand-poster "1958_Végh-Quartett - Musica Viva" \\
        --prereg docs/series_check_preregister.json --out docs/series_check.json

경로는 모두 인자로 받는다. 한 번에 다시 돌리는 명령은 eval/run_all.py 다.

    통과율    조건마다 블록이 통과 · 보류 · 위반인 몫 (기본 호출 / layer=1)
    거부율    뺀 시리즈에서 통과한 블록의 변형이 보류 + 위반으로 잡힌 몫
              (a) 전체 배율 b_i' = b_0 + i·g·f + r_i      — 비율 규칙을 시험
              (b) 한 줄 · 두 줄을 ±1/±2/±3px 옮김          — 행간 일정 규칙을 시험
    격자 공유  한 판 안 블록 위상이 공통 격자에 서는 정도 R, 블록 세로 위치만
              옮긴 귀무와 AUC. 블록 안 행간 일정성은 측정 검산용으로만 낸다
"""
import argparse
import hashlib
import itertools
import json
import math
import os
import random
import sys
import tempfile
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import discrim                     # noqa: E402
import rules                       # noqa: E402
from tools import layout           # noqa: E402

FACTORS = (0.8, 0.9, 1.1, 1.2)
SHIFTS = (-3, -2, -1, 1, 2, 3)
N_NULL = 200
SEED = 20260911
MODES = (('기본 호출', None), ('layer=1', 1))
KEY = 'lead_over_cap'


def _load(path):
    p = os.path.expanduser(path)
    d = json.load(open(p))
    return d, hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _rule_summary(R):
    e = (R['rules'].get(KEY) or R['not_rules'].get(KEY))
    ls = e.get('layers') or [e]
    return dict(대표={k: e.get(k) for k in ('median', 'lo', 'hi', 'cv', 'n', 'verdict')},
                계층=[{k: x.get(k) for k in ('label', 'verdict', 'median', 'lo', 'hi', 'min', 'max', 'n')}
                    for x in ls])


# ── 블록 ─────────────────────────────────────────────────────

def test_blocks(raw):
    """skewed 가 아닌 판의 3줄 이상 · 캡이 잡힌 블록."""
    out = []
    for k, v in raw.items():
        if v.get('skewed'):
            continue
        for i, b in enumerate(v['blocks']):
            if b['n'] < 3:
                continue
            cs = [base - c for c, base in zip(b['caps'], b['bases']) if c is not None]
            if not cs:
                continue
            out.append(dict(key=k, i=i, cap=float(np.median(cs)),
                            bases=sorted(float(x) for x in b['bases'])))
    return out


def judge(cache, cap, bases, layer):
    """블록 하나를 check_layout 에 넣어 통과 · 보류 · 위반과 위반 종류."""
    args = dict(cache=cache, blocks=[dict(id='b', cap_height=cap,
                                          lines=[dict(baseline=x) for x in bases])])
    if layer is not None:
        args['layer'] = layer
    r = layout.check_layout(args)
    assert 'violations' in r, r
    kinds = []
    for v in r['violations']:
        if v.get('block') == 'b':
            kinds.append(v['rule'] if v['rule'] in ('줄 겹침', '블록 내 행간 일정') else '계층 밖')
        else:
            kinds.append('블록 밖 지표')
    if kinds:
        return '위반', sorted(set(kinds))
    if any(h.get('block') == 'b' for h in r['held']):
        return '보류', ['보류']
    return '통과', []


def scale(bases, f):
    """(a) 격자 성분에만 f. 간격 중앙값이 g·f 가 되고 간격끼리의 편차는 그대로다."""
    b = sorted(bases)
    g = float(np.median(np.diff(b)))
    return [b[0] + i * g * f + (x - (b[0] + i * g)) for i, x in enumerate(b)]


def shift(bases, idx, d):
    """(b) 고른 줄만 d px 옮긴다."""
    return [x + d if i in idx else x for i, x in enumerate(sorted(bases))]


# ── 통과율 · 거부율 ──────────────────────────────────────────

def pass_rates(cache, blocks):
    out = {}
    for mode, layer in MODES:
        c, kinds = Counter(), Counter()
        for b in blocks:
            j, ks = judge(cache, b['cap'], b['bases'], layer)
            c[j] += 1
            if j == '위반':
                kinds.update(ks)
        n = len(blocks)
        out[mode] = dict(판=len({b['key'] for b in blocks}), 블록=n,
                         통과=c['통과'], 보류=c['보류'], 위반=c['위반'],
                         통과율=round(c['통과'] / n, 3) if n else None,
                         보류율=round(c['보류'] / n, 3) if n else None,
                         위반율=round(c['위반'] / n, 3) if n else None,
                         위반_종류=dict(kinds))
    return out


def rejection(cache, blocks):
    out = {}
    for mode, layer in MODES:
        passed = [b for b in blocks if judge(cache, b['cap'], b['bases'], layer)[0] == '통과']
        tallies = {}

        def add(key, j, ks):
            t = tallies.setdefault(key, dict(변형=0, 보류=0, 위반=0, 종류=Counter()))
            t['변형'] += 1
            if j != '통과':
                t[j] += 1
                t['종류'].update(ks)

        for b in passed:
            n = len(b['bases'])
            for f in FACTORS:
                j, ks = judge(cache, b['cap'], scale(b['bases'], f), layer)
                add(f'(a) 배율 ×{f}', j, ks)
            for d in SHIFTS:
                for i in range(n):
                    j, ks = judge(cache, b['cap'], shift(b['bases'], (i,), d), layer)
                    add(f'(b) 한 줄 {d:+d}px', j, ks)
                    add(f'(b) 한 줄 ±{abs(d)}px', j, ks)
                for pair in itertools.combinations(range(n), 2):
                    j, ks = judge(cache, b['cap'], shift(b['bases'], pair, d), layer)
                    add(f'(b) 두 줄 {d:+d}px', j, ks)
                    add(f'(b) 두 줄 ±{abs(d)}px', j, ks)
        for t in tallies.values():
            t['거부'] = t['보류'] + t['위반']
            t['거부율'] = round(t['거부'] / t['변형'], 3) if t['변형'] else None
            t['종류'] = dict(t['종류'])
        out[mode] = dict(대상_블록=len(passed), 대상_판=len({b['key'] for b in passed}), 변형=tallies)
    return out


# ── 격자 공유 ────────────────────────────────────────────────

def grid_score(block_bases, g):
    """블록마다 베이스라인 목록 → (R, 공통 위상에서 떨어진 평균 원형거리 px)."""
    ph = []
    for bs in block_bases:
        a = np.asarray(bs, float) % g * 2 * np.pi / g
        ph.append(math.atan2(float(np.sin(a).mean()), float(np.cos(a).mean())))
    z = np.exp(1j * np.asarray(ph))
    m = z.mean()
    dist = np.abs(np.angle(z * np.exp(-1j * np.angle(m)))) * g / (2 * np.pi)
    return float(abs(m)), float(dist.mean())


def grid_sharing(raw, rnd):
    real_R, null_R, real_d, null_d, nblocks = [], [], [], [], []
    for k, v in raw.items():
        if v.get('skewed'):
            continue
        bs = [b for b in v['blocks'] if b.get('bases')]
        leads = [float(np.median(np.diff(sorted(b['bases'])))) for b in bs if b['n'] >= 3]
        leads = [x for x in leads if x > 0]
        if not leads or len(bs) < 2:
            continue
        g = min(leads)
        R, d = grid_score([b['bases'] for b in bs], g)
        real_R.append(R); real_d.append(d); nblocks.append(len(bs))
        H = float(v['size'][1])
        for _ in range(N_NULL):
            moved = []
            for b in bs:
                h = b['y2'] - b['y1']
                top = rnd.randint(0, max(0, int(H - h)))
                moved.append([x + (top - b['y1']) for x in b['bases']])
            R0, d0 = grid_score(moved, g)
            null_R.append(R0); null_d.append(d0)
    if not real_R:
        return dict(판=0)
    v = discrim._auc(real_R, null_R)
    return dict(판=len(real_R), 블록수_중앙=float(np.median(nblocks)),
                R_중앙=round(float(np.median(real_R)), 3), 귀무_R_중앙=round(float(np.median(null_R)), 3),
                원형거리_중앙_px=round(float(np.median(real_d)), 2),
                귀무_원형거리_중앙_px=round(float(np.median(null_d)), 2),
                AUC=round(v, 3), AUC_방향무관=round(max(v, 1 - v), 3),
                AUC_MIN_넘음=max(v, 1 - v) >= discrim.AUC_MIN)


def within_block(raw):
    """측정 검산용 — 3줄 이상 블록의 간격 편차."""
    sp = []
    for v in raw.values():
        if v.get('skewed'):
            continue
        for b in v['blocks']:
            if b['n'] >= 3 and len(b['bases']) >= 3:
                g = np.diff(sorted(b['bases']))
                sp.append(float(g.max() - g.min()))
    if not sp:
        return dict(블록=0)
    return dict(블록=len(sp), 편차_중앙_px=round(float(np.median(sp)), 2),
                편차_1px_이하_몫=round(float(np.mean(np.array(sp) <= 1)), 3))


# ── 참고: place_text ─────────────────────────────────────────

def place_ref(cache, lines, blocks_csv, posters):
    import loo_place_text as LP
    out = {}
    for prefix in posters:
        _pid, blocks, skipped = LP.hand_blocks(lines, blocks_csv, prefix)
        e = LP.errors(blocks, LP.place(cache, blocks, None))
        out[prefix] = {bid: dict(행간=x['행간'], 오차_중앙_px=x['오차_중앙_px'], 오차_최대_px=x['오차_최대_px'])
                       for bid, x in e.items()}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='시리즈 단위 판별 시험 (탐색용). 경로는 모두 인자로 받는다.')
    ap.add_argument('--cache', required=True)
    ap.add_argument('--series', required=True, help='뺄 시리즈 (캐시 열쇠 앞 폴더 이름)')
    ap.add_argument('--other', action='append', default=[], metavar='이름=캐시')
    ap.add_argument('--hand-lines')
    ap.add_argument('--hand-blocks')
    ap.add_argument('--hand-poster', action='append', default=[])
    ap.add_argument('--prereg', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)

    d, sha = _load(a.cache)
    raw = d['raw']
    held = {k: v for k, v in raw.items() if k.startswith(a.series + '__')}
    rest = {k: v for k, v in raw.items() if not k.startswith(a.series + '__')}
    others = {}
    for s in a.other:
        name, path = s.split('=', 1)
        od, osha = _load(path)
        others[name] = (path, osha, od)

    R_out, R_in = rules.derive(rest), rules.derive(raw)
    res = dict(
        무엇='시리즈 단위 판별 시험 — 뺀 시리즈 통과율 · 변형 거부율 · 블록 간 격자 공유',
        용도='탐색용. 채택 범위와 문턱을 바꾸지 않았다. 논문 수치로 쓰지 않는다',
        사전등록=a.prereg,
        사전등록_sha256=hashlib.sha256(open(a.prereg, 'rb').read()).hexdigest(),
        입력=dict(cache=a.cache, cache_sha256=sha, cache_provenance=d.get('provenance'),
                뺀_시리즈=a.series, 뺀_시리즈_판=len(held),
                뺀_시리즈_기울어진_판=sum(1 for v in held.values() if v.get('skewed')),
                다른_디자이너={n: dict(cache=p, sha256=s_, 판=len(od['raw']),
                                  기울어진_판=sum(1 for v in od['raw'].values() if v.get('skewed')))
                          for n, (p, s_, od) in others.items()}),
        규칙=dict(시리즈_밖=_rule_summary(R_out), in_sample=_rule_summary(R_in)))

    with tempfile.TemporaryDirectory() as tmp:
        c_out, c_in = os.path.join(tmp, 'out.json'), os.path.join(tmp, 'in.json')
        rules.save(c_out, {}, R_out)      # check_layout · place_text 는 규칙만 읽는다
        rules.save(c_in, {}, R_in)
        tb_held = test_blocks(held)
        res['통과율'] = {
            f'{a.series} — 시리즈 밖 규칙 (뺀 시리즈)': pass_rates(c_out, tb_held),
            f'{a.series} — in-sample 규칙': pass_rates(c_in, tb_held),
            '브로크만 나머지 시리즈 — 시리즈 밖 규칙 (규칙을 뽑은 판)': pass_rates(c_out, test_blocks(rest)),
        }
        for n, (_p, _s, od) in others.items():
            res['통과율'][f'{n} — 시리즈 밖 규칙 (다른 디자이너)'] = pass_rates(c_out, test_blocks(od['raw']))
        res['거부율'] = rejection(c_out, tb_held)
        if a.hand_lines and a.hand_blocks and a.hand_poster:
            res['참고_place_text_시리즈밖'] = place_ref(c_out, a.hand_lines, a.hand_blocks, a.hand_poster)

    rnd = random.Random(SEED)
    conds = [(f'{a.series} (뺀 시리즈)', held), ('브로크만 나머지 시리즈', rest)] + \
            [(n, od['raw']) for n, (_p, _s, od) in others.items()]
    res['격자공유'] = {n: grid_sharing(r, rnd) for n, r in conds}
    res['블록안_행간일정_검산'] = {n: within_block(r) for n, r in conds}
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)

    print('규칙 시리즈 밖', res['규칙']['시리즈_밖']['계층'])
    print('\n통과율')
    for cond, m in res['통과율'].items():
        print(' ', cond, {k: (v['판'], v['블록'], v['통과율'], v['보류율'], v['위반율'], v['위반_종류']) for k, v in m.items()})
    print('\n거부율')
    for mode, m in res['거부율'].items():
        print(' ', mode, '대상 블록', m['대상_블록'])
        for k, t in m['변형'].items():
            if '±' in k or '(a)' in k:
                print('    ', k, t['변형'], t['거부율'], t['종류'])
    print('\n격자 공유', json.dumps(res['격자공유'], ensure_ascii=False))
    print('검산', json.dumps(res['블록안_행간일정_검산'], ensure_ascii=False))
    print('→', a.out)


if __name__ == '__main__':
    main()
