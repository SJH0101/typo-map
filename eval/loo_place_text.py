"""place_text leave-one-out — 탐색용. 결과는 논문 수치로 쓰지 않는다.

한 장을 코퍼스에서 빼고 규칙을 다시 뽑는다. 그 규칙으로, 사람이 찍은 블록별
캡 높이 · 줄 수 · 블록 위 끝을 넣어 place_text 를 돌리고, 나온 베이스라인을
사람이 찍은 베이스라인과 견준다. 같은 계산을 빼지 않은 코퍼스(in-sample)로도
해서 나란히 둔다. place_text 는 tools/layout.py 의 것을 고치지 않고 부른다.

경로는 모두 인자로 받는다. 한 번에 다시 돌리는 명령은 eval/run_all.py 다.

    python eval/loo_place_text.py --lines 손찍기_lines.csv --blocks 손찍기_blocks.csv \\
        --cache ~/.typo-mcp/brockmann.json \\
        --poster "1958_Musica viva - Dienstag, den 7. Januar 1958" --poster "1958_Végh-Quartett - Musica Viva" \\
        --out docs/loo_place_text.json

--poster 는 손 찍기의 poster_id 와 캐시 열쇠의 파일 이름이 함께 시작하는 글자다.

좌표. 블록마다 베이스라인 선분의 기울기 중앙값을 재고, 그 방향에 수직인 축으로
점을 투영해 1차원으로 잰다. 똑바로 선 판에서는 그 축이 y 와 같다. 기울어진
판(1958 Végh-Quartett 은 약 45°)도 그 축에서 잰다 — place_text 는 줄 방향을
모르고 «위 끝 + 캡 높이 + i × 행간» 만 계산하므로 같은 산수다. 한 판의 글자
블록은 한 번에 넘긴다 (격자를 함께 쓴다).

규칙은 rules.derive(원자료) 로 뽑는다 (참조 코퍼스 없이 — 행간 대표값은 참조와
무관하다). 캐시에 저장된 규칙의 행간 대표값도 함께 적어 둔다.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import rules                      # noqa: E402
from tools import layout          # noqa: E402

KEY = 'lead_over_cap'


def _rows(path, prefix):
    return [r for r in csv.DictReader(open(os.path.expanduser(path), encoding='utf-8-sig'))
            if r['poster_id'].startswith(prefix)]


def _seg(r):
    return (float(r['x1']), float(r['y1'])), (float(r['x2']), float(r['y2']))


def _angle(seg):
    (x1, y1), (x2, y2) = seg
    if x2 < x1:
        x1, y1, x2, y2 = x2, y2, x1, y1
    return math.atan2(y2 - y1, x2 - x1)


def _s(p, th):
    """베이스라인 방향에 수직인 축 위의 좌표. th=0 이면 y 다."""
    return -math.sin(th) * p[0] + math.cos(th) * p[1]


def hand_blocks(lines_csv, blocks_csv, prefix):
    """손 찍기 한 판 → 글자 블록마다 (위 끝, 캡 높이, 줄 수, 사람 베이스라인들)."""
    L = _rows(lines_csv, prefix)
    B = [b for b in _rows(blocks_csv, prefix) if b['kind'] == 'text']
    pids = {r['poster_id'] for r in L}
    assert len(pids) == 1, (prefix, pids)
    out, skipped = [], []
    for b in B:
        rows = [r for r in L if r['block_id'] == b['block_id'] and r['pass'] == b['pass']]
        base = {int(r['line_no']): _seg(r) for r in rows if r['kind'] == 'baseline'}
        cap = {int(r['line_no']): (_seg(r), r['cap_kind']) for r in rows if r['kind'] == 'cap'}
        if not base:
            skipped.append(dict(id=b['block_id'], why='베이스라인 없음'))
            continue
        th = float(np.median([_angle(s) for s in base.values()]))
        mid = lambda s: ((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2)
        bs = sorted(_s(mid(s), th) for s in base.values())
        caps = [_s(mid(base[n]), th) - _s(mid(cs), th) for n, (cs, _k) in cap.items() if n in base]
        kinds = sorted({k for _s2, k in cap.values()})
        if not caps:
            skipped.append(dict(id=b['block_id'], why='캡선 없음'))
            continue
        corners = [(float(b[f'x{i}']), float(b[f'y{i}'])) for i in (1, 2, 3, 4)]
        out.append(dict(id=b['block_id'], 기울기_도=round(math.degrees(th), 1),
                        위끝=round(min(_s(p, th) for p in corners), 2),
                        캡높이=round(float(np.median(caps)), 2), 캡선종류=kinds,
                        줄수=len(bs), 사람베이스라인=[round(v, 2) for v in bs],
                        사람행간=(round(float(np.median(np.diff(bs))), 2) if len(bs) >= 2 else None)))
    return pids.pop(), out, skipped


def band_of(R, layer):
    b, err = layout._pick(R, layer)
    assert not err, err
    return {k: b.get(k) for k in ('median', 'lo', 'hi', 'cv', 'n', 'verdict')}


def place(cache_path, blocks, layer):
    args = dict(cache=cache_path,
                blocks=[dict(id=b['id'], y=b['위끝'], cap_height=b['캡높이'], n_lines=b['줄수'])
                        for b in blocks])
    if layer is not None:
        args['layer'] = layer
    r = layout.place_text(args)
    assert r.get('ok'), r
    return r


def errors(blocks, placed):
    by = {p['id']: p for p in placed['blocks']}
    out = {}
    for b in blocks:
        p = by[b['id']]
        e = np.array(p['baselines'], float) - np.array(b['사람베이스라인'], float)
        out[b['id']] = dict(격자=placed['grid_lead'], 행간=p['lead'], 행간비=p['lead_ratio'],
                            오차_중앙_px=round(float(np.median(np.abs(e))), 2),
                            오차_최대_px=round(float(np.max(np.abs(e))), 2),
                            오차_부호=[round(float(v), 1) for v in e])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='place_text leave-one-out (탐색용). 경로는 모두 인자로 받는다.')
    ap.add_argument('--lines', required=True, help='손 찍기 줄 CSV')
    ap.add_argument('--blocks', required=True, help='손 찍기 블록 CSV')
    ap.add_argument('--cache', required=True, help='코퍼스 캐시 (raw 와 rules)')
    ap.add_argument('--poster', action='append', required=True, help='poster_id·파일 이름 앞글자 (여러 번)')
    ap.add_argument('--layer', type=int, help='행간 계층 번호. 생략하면 대표 계층 (place_text 기본)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)

    cache = os.path.expanduser(a.cache)
    d = json.load(open(cache))
    raw = d['raw']
    stored = d.get('rules') or {}
    stored_e = (stored.get('rules') or {}).get(KEY) or (stored.get('not_rules') or {}).get(KEY) or {}
    R_in = rules.derive(raw)
    out = dict(
        무엇='place_text leave-one-out — 한 장을 빼고 뽑은 규칙으로 배치한 베이스라인과 사람이 찍은 베이스라인',
        용도='탐색용. 논문 수치로 쓰지 않는다',
        입력=dict(lines=a.lines, blocks=a.blocks, cache=a.cache,
                cache_sha256=hashlib.sha256(open(cache, 'rb').read()).hexdigest(),
                cache_provenance=d.get('provenance'), layer=a.layer,
                규칙='rules.derive(원자료), 참조 코퍼스 없이. 좌표는 블록 베이스라인에 수직인 축'),
        캐시에_저장된_행간규칙={k: stored_e.get(k) for k in ('median', 'lo', 'hi', 'n', 'verdict')},
        in_sample_행간규칙=band_of(R_in, a.layer),
        포스터={})
    with tempfile.TemporaryDirectory() as tmp:
        p_in = os.path.join(tmp, 'in.json')
        rules.save(p_in, raw, R_in)
        for prefix in a.poster:
            keys = [k for k in raw if k.split('__')[-1].startswith(prefix)]
            assert len(keys) == 1, (prefix, keys)
            k = keys[0]
            pid, blocks, skipped = hand_blocks(a.lines, a.blocks, prefix)
            raw_loo = {kk: v for kk, v in raw.items() if kk != k}
            R_loo = rules.derive(raw_loo)
            p_loo = os.path.join(tmp, 'loo.json')
            rules.save(p_loo, raw_loo, R_loo)
            bi, bl = band_of(R_in, a.layer), band_of(R_loo, a.layer)
            e_in = errors(blocks, place(p_in, blocks, a.layer))
            e_lo = errors(blocks, place(p_loo, blocks, a.layer))
            out['포스터'][k] = dict(
                손찍기_poster_id=pid,
                이_판이_규칙에_보탠_값=[round(v, 3) for v in rules.METRICS[KEY][0]({k: raw[k]})],
                행간규칙=dict(in_sample=bi, 뺀뒤=bl,
                          변화=dict(median=round(bl['median'] - bi['median'], 4),
                                  lo=round(bl['lo'] - bi['lo'], 4), hi=round(bl['hi'] - bi['hi'], 4),
                                  n=bl['n'] - bi['n'])),
                블록=[dict(b, in_sample=e_in[b['id']], 뺀뒤=e_lo[b['id']]) for b in blocks],
                뺀블록=skipped)
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)

    print('캐시 저장 규칙', out['캐시에_저장된_행간규칙'], '\nin-sample', out['in_sample_행간규칙'])
    for k, v in out['포스터'].items():
        print(f"\n{k[:60]}\n  보탠 값 {v['이_판이_규칙에_보탠_값']}  규칙 변화 {v['행간규칙']['변화']}  뺀 블록 {v['뺀블록']}")
        for b in v['블록']:
            i, l = b['in_sample'], b['뺀뒤']
            print(f"  블록 {b['id']:>2} 기울기 {b['기울기_도']:6.1f}° 줄 {b['줄수']:2d} 캡 {b['캡높이']:5.2f} {b['캡선종류']} "
                  f"사람행간 {b['사람행간']}  | in: 행간 {i['행간']} 오차 중앙 {i['오차_중앙_px']} 최대 {i['오차_최대_px']}"
                  f"  | 뺀뒤: 행간 {l['행간']} 오차 중앙 {l['오차_중앙_px']} 최대 {l['오차_최대_px']}")
    print('→', a.out)


if __name__ == '__main__':
    main()
