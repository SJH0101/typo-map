"""깨끗한 세트 생성 검증 · 사람 확인용 표본 이미지 — 사전등록 docs/clean_preregister.json (4c06aa4).

    python eval/clean_check.py --dir ~/.typo-mcp/clean --manifest docs/clean_manifest.json \\
        --prereg docs/clean_preregister.json --out docs/clean_check.json --review-dir ~/.typo-mcp/clean/review

정답 필드를 믿지 않고 줄 잉크 상자에서 다시 계산한다.
  ① 전 쌍 잉크 겹침 0  ② 블록 안 이웃 줄 잉크 겹침 0  ③ 모든 줄 잉크가 판 안 · 제 단 안 (단 사이 겹침 0)
  ④ 실제 여유 ≥ 목표 여유  ⑤ 층 · 수준별 수
표본: 9층에서 한 장씩. c_in 쌍과 c 4.0 쌍을 둘 다 가진 판을 먼저 고른다. 둘 다 가진 판이 없는 층은 c_in 이 든 판과
c 4.0 이 든 판을 한 장씩 넣는다 (수정 1). 수정 1 검증: 판 안 원자 반복 0 · 빌린 줄 · 글자 집합과 최대 윗끝 · 아래끝 ·
층별 판 채움 · 층 × 수준 쌍 수.
표본 이미지는 원본(2배 최근접) 옆에 블록 상자와 쌍 수준을 그린 판을 붙인다. Surya · VLM 은 돌리지 않는다.
"""
import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict

import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clean_phrases as CP   # noqa: E402
import clean_gen as CG       # noqa: E402  층별 기대 장수 (수정 2)

LEVELS = ['c_in', '0.5', '1.0', '1.5', '2.0', '2.5', '3.0', '4.0']


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def check_poster(t):
    bad = defaultdict(list)
    W, H = t['canvas']
    cols = t['columns_x_px']
    idx = {b['id']: b for b in t['blocks']}
    for b in t['blocks']:
        ls = b['lines']
        for a, c in zip(ls, ls[1:]):
            if not (c['ink_box'][1] - a['ink_box'][3] > 0):
                bad['블록 안 겹침'].append((b['id'], round(c['ink_box'][1] - a['ink_box'][3], 3)))
        lo, hi = cols[b['column']]
        prev_hi = cols[b['column'] - 1][1] if b['column'] > 0 else 0.0
        next_lo = cols[b['column'] + 1][0] if b['column'] + 1 < len(cols) else W
        for ln in ls:
            x1, y1, x2, y2 = ln['ink_box']
            if x1 < 0 or y1 < 0 or x2 > W or y2 > H:
                bad['판 밖 잉크'].append((b['id'], [round(v, 2) for v in ln['ink_box']]))
            if x1 <= prev_hi or x2 >= next_lo:
                bad['단 사이 겹침'].append((b['id'], [round(x1, 2), round(x2, 2)], [prev_hi, next_lo]))
    over = []
    for b in t['blocks']:
        lo, hi = cols[b['column']]
        for ln in b['lines']:
            over.append(max(lo - ln['ink_box'][0], ln['ink_box'][2] - hi, 0.0))
    rows = []
    for p in t['pairs']:
        u, l = idx[p['upper']], idx[p['lower']]
        gap = l['lines'][0]['ink_box'][1] - u['lines'][-1]['ink_box'][3]
        if not gap > 0:
            bad['쌍 겹침'].append((p['upper'], p['lower'], p['level'], round(gap, 3)))
        placed = l['lines'][0]['baseline_y'] - u['lines'][-1]['baseline_y']
        xh = u['xh_px']
        actual = (placed * 4 - p['min_distance_exact_master']) / (xh * 4)
        if actual + 1e-9 < p['clearance_target_xh'] - 1e-3:
            bad['여유 부족'].append((p['upper'], p['lower'], p['level'], round(actual, 4), p['clearance_target_xh']))
        rows.append(dict(upper=p['upper'], lower=p['lower'], level=p['level'], ink_gap_px=round(gap, 3),
                         placed_px=round(placed, 3), clearance_actual_xh=round(actual, 4),
                         y=round(u['lines'][-1]['baseline_y'], 2)))
    return bad, rows, (max(over) if over else 0.0)


def pick_review(truths):
    """층마다 c_in · 4.0 을 둘 다 가진 가장 작은 seed. 없으면 c_in 이 든 판과 4.0 이 든 판을 한 장씩."""
    by = defaultdict(list)
    for s, t in sorted(truths.items()):
        by[(t['condition']['columns'], t['condition']['xh_px_at_800'])].append(s)
    out = []
    for key in sorted(by):
        ss = by[key]
        lv = {s: {p['level'] for p in truths[s]['pairs']} for s in ss}
        both = [s for s in ss if {'c_in', '4.0'} <= lv[s]]
        if both:
            out.append((key, both[0], 'c_in · 4.0 둘 다'))
            continue
        picked = []
        for want in ('c_in', '4.0'):
            has = [s for s in ss if want in lv[s]]
            if has and has[0] not in picked:
                picked.append(has[0]); out.append((key, has[0], f'{want} 이 든 판'))
        if not picked:
            out.append((key, ss[0], 'c_in · 4.0 이 든 판 없음'))
    return out


def phrase_and_glyph(truths):
    probe = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 1000, index=0)
    bank = set(CP.charset())
    per_poster_max, block_max, borrowed, repeated, short, lines = [], [], 0, 0, 0, 0
    used_chars = set()
    for t in truths.values():
        cnt = Counter()
        for b in t['blocks']:
            bc = Counter(a for ln in b['lines'] for a in ln['atoms'])
            block_max.append(max(bc.values()))
            cnt.update(bc)
            for ln in b['lines']:
                used_chars |= {ch for ch in ln['text'] if not ch.isspace()}
                borrowed += int(ln['role_used'] != ln['role']); repeated += int(ln['repeated'])
                short += int(ln['fill'] < 0.6); lines += 1
        per_poster_max.append(max(cnt.values()))
    ext = next(iter(truths.values()))['font_extents']
    top = max(-probe.getbbox(c, anchor='ls')[1] for c in used_chars) / 1000.0
    bot = max(probe.getbbox(c, anchor='ls')[3] for c in used_chars) / 1000.0
    return dict(판_안_원자_최대_횟수=max(per_poster_max), 블록_안_원자_최대_횟수=max(block_max),
                반복으로_대체한_줄=repeated, 빌린_줄=borrowed, 줄=lines, 단폭_60퍼센트_미만_줄=short), \
        dict(주머니_밖_글자=sorted(used_chars - bank), 쓰인_글자_최대_윗끝_em=top, 쓰인_글자_최대_아래끝_em=bot,
             font_extents_윗끝=ext['max_ascent_em'], font_extents_아래끝=ext['max_descender_em'],
             최소거리_안에_듦=(top <= ext['max_ascent_em'] + 1e-9 and bot <= ext['max_descender_em'] + 1e-9))


def fill_of(t):
    H = t['canvas'][1]
    vals = []
    for ci in range(len(t['columns_x_px'])):
        bs = [b for b in t['blocks'] if b['column'] == ci]
        if not bs:
            continue
        top = min(b['ink_box'][1] for b in bs); bot = max(b['ink_box'][3] for b in bs)
        vals.append((bot - top) / (H * 0.98 - top))
    return float(np.mean(vals))


def review_image(img_path, t, out_path):
    im = Image.open(img_path).convert('RGB')
    W, H = im.size
    raw = im.resize((W * 2, H * 2), Image.Resampling.NEAREST)
    ann = raw.copy(); d = ImageDraw.Draw(ann)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 20, index=1)
        small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 16, index=1)
    except Exception:
        font = small = ImageFont.load_default()
    for b in t['blocks']:
        x1, y1, x2, y2 = [v * 2 for v in b['ink_box']]
        d.rectangle([x1, y1, x2, y2], outline=(40, 90, 220), width=2)
        tw = d.textlength(b['id'], font=small)
        d.text((max(0, x1 - tw - 4), y1), b['id'], font=small, fill=(40, 90, 220))
    idx = {b['id']: b for b in t['blocks']}
    cols = t['columns_x_px']
    for p in t['pairs']:
        u, l = idx[p['upper']], idx[p['lower']]
        yb = u['lines'][-1]['ink_box'][3] * 2; yt = l['lines'][0]['ink_box'][1] * 2
        xr = cols[u['column']][1] * 2 + 4
        col = (220, 30, 30) if p['level'] in ('c_in', '4.0') else (230, 120, 0)
        d.line([xr, yb, xr, yt], fill=col, width=4)
        d.line([xr - 8, yb, xr + 8, yb], fill=col, width=3); d.line([xr - 8, yt, xr + 8, yt], fill=col, width=3)
        label = f"c {p['level']}"
        tw = d.textlength(label, font=font)
        lx = min(xr + 10, W * 2 - tw - 4); ly = (yb + yt) / 2 - 10
        d.rectangle([lx - 2, ly - 1, lx + tw + 2, ly + 21], fill=(255, 255, 255))
        d.text((lx, ly), label, font=font, fill=col)
    sheet = Image.new('RGB', (W * 4 + 20, H * 2), (180, 180, 180))
    sheet.paste(raw, (0, 0)); sheet.paste(ann, (W * 2 + 20, 0))
    sheet.save(out_path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True); ap.add_argument('--manifest', required=True)
    ap.add_argument('--prereg', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--review-dir', required=True)
    ap.add_argument('--human-check', default='[]', help='사람 확인 기록 목록 (JSON) — eval/refs.json 의 clean.human_check')
    ap.add_argument('--human-check-pending', default=None)
    ap.add_argument('--new-from-seed', type=int, default=None, help='이 seed 부터를 추가 생성 판으로 보고 표본을 더 고른다 (수정 2)')
    ap.add_argument('--new-samples', type=int, default=0)
    ap.add_argument('--new-strata', default=None,
                    help='«단:x높이» 를 쉼표로 (예 1:8,2:12). 주면 층마다 한 판씩 고른다 (수정 3 사람 확인 3차)')
    a = ap.parse_args(argv)
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    truths = {}
    for it in M['items']:
        p = os.path.join(D, it['image'])
        if _sha(p) != it['image_sha256'] or _sha(p[:-4] + '.json') != it['truth_sha256']:
            raise SystemExit(f'manifest 와 다른 파일: {p}')
        truths[it['seed']] = json.load(open(p[:-4] + '.json'))
    bad_all = defaultdict(list); rows_all = []; max_over = 0.0
    for s, t in truths.items():
        bad, rows, ov = check_poster(t)
        for k, v in bad.items():
            bad_all[k] += [(s, *x) for x in v]
        rows_all += [dict(seed=s, xh=t['condition']['xh_px_at_800'], cols=t['condition']['columns'], **r) for r in rows]
        max_over = max(max_over, ov)
    strata = Counter((t['condition']['columns'], t['condition']['xh_px_at_800']) for t in truths.values())
    per_level = Counter(r['level'] for r in rows_all)
    per_level_xh = Counter((r['level'], r['xh']) for r in rows_all)
    ink = defaultdict(list); act = defaultdict(list)
    for r in rows_all:
        ink[(r['level'], r['xh'])].append(r['ink_gap_px']); act[r['level']].append(r['clearance_actual_xh'])
    q = lambda v: [round(float(np.min(v)), 3), round(float(np.median(v)), 3), round(float(np.max(v)), 3)]
    blocks = [b for t in truths.values() for b in t['blocks']]
    fills = [ln['fill'] for b in blocks for ln in b['lines']]
    checks = {k: len(bad_all.get(k, [])) for k in ('쌍 겹침', '블록 안 겹침', '판 밖 잉크', '단 사이 겹침', '여유 부족')}
    phr, gly = phrase_and_glyph(truths)
    expected = Counter((CG.condition(sd)['columns'], CG.condition(sd)['xh_px_at_800']) for sd in CG.SEEDS)
    ok = (all(v == 0 for v in checks.values()) and strata == expected
          and phr['판_안_원자_최대_횟수'] == 1 and not gly['주머니_밖_글자'] and gly['최소거리_안에_듦'])
    page_fill = defaultdict(list)
    for t in truths.values():
        page_fill[(t['condition']['columns'], t['condition']['xh_px_at_800'])].append(fill_of(t))
    level_stratum = Counter((r['level'], r['cols'], r['xh']) for r in rows_all)
    os.makedirs(os.path.expanduser(a.review_dir), exist_ok=True)
    review = []
    picks = pick_review(truths)
    if a.new_from_seed is not None and a.new_strata:
        for key in [tuple(int(v) for v in s.split(':')) for s in a.new_strata.split(',')]:
            ss = [sd for sd in sorted(truths) if sd >= a.new_from_seed
                  and (truths[sd]['condition']['columns'], truths[sd]['condition']['xh_px_at_800']) == key]
            lv = {sd: {p['level'] for p in truths[sd]['pairs']} for sd in ss}
            both = [sd for sd in ss if {'c_in', '4.0'} <= lv[sd]]
            cin = [sd for sd in ss if 'c_in' in lv[sd]]
            if both:
                picks.append((key, both[0], f'추가 생성 판 (seed {a.new_from_seed} 이상, 층마다 한 판, c_in · 4.0 둘 다)'))
            elif cin:
                picks.append((key, cin[0], f'추가 생성 판 (seed {a.new_from_seed} 이상, 층마다 한 판, c_in 만)'))
    elif a.new_from_seed is not None and a.new_samples:
        new = [sd for sd in sorted(truths) if sd >= a.new_from_seed
               and {'c_in', '4.0'} <= {p['level'] for p in truths[sd]['pairs']}]
        for sd in new[:a.new_samples]:
            c = truths[sd]['condition']
            picks.append(((c['columns'], c['xh_px_at_800']), sd, f'추가 생성 판 (seed {a.new_from_seed} 이상, c_in · 4.0 둘 다)'))
    for key, s, why in picks:
        t = truths[s]
        op = os.path.join(os.path.expanduser(a.review_dir), f'{s}_review.png')
        review_image(os.path.join(D, f'{s}.jpg'), t, op)
        review.append(dict(층=f'{key[0]}단 · x높이 {key[1]}', seed=s, 고른_까닭=why, 이미지=os.path.join(D, f'{s}.jpg'),
                           블록수=len(t['blocks']), 쌍수=len(t['pairs']), 줄수=sum(b['n'] for b in t['blocks']),
                           검토판=op, 블록=len(t['blocks']),
                           쌍=[dict(위=p['upper'], 아래=p['lower'], 여유=p['level'], 잉크틈_px=round(p['ink_gap_px'], 2),
                                   배치거리_px=p['placed_distance_px'], 위_마지막_베이스라인=u_base)
                              for p, u_base in ((p, next(b for b in t['blocks'] if b['id'] == p['upper'])['lines'][-1]['baseline_y'])
                                                for p in t['pairs'])]))
    res = dict(
        무엇='깨끗한 세트 생성 검증과 사람 확인용 표본',
        사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg), manifest=a.manifest, manifest_sha256=_sha(a.manifest),
        장=len(truths), 블록=len(blocks), 쌍=len(rows_all),
        문구=phr, 글자=gly,
        층별_판채움_중앙_최소={f'{c}단 · x높이 {x}': [round(float(np.median(v)), 3), round(float(np.min(v)), 3)] for (c, x), v in sorted(page_fill.items())},
        층_수준별_쌍={f'{c}단 · x높이 {x}': {lv: level_stratum.get((lv, c, x), 0) for lv in LEVELS} for (c, x) in sorted(strata)},
        층별_가장_얇은_칸={f'{c}단 · x높이 {x}': min(((lv, level_stratum.get((lv, c, x), 0)) for lv in LEVELS), key=lambda t: t[1])
                     for (c, x) in sorted(strata)},
        층별_기대_장수={f'{c}단 · x높이 {x}': n for (c, x), n in sorted(expected.items())},
        검증=dict(위반_수=checks, 통과=ok, 위반_예=({k: v[:5] for k, v in bad_all.items()} or None),
                 줄_잉크가_제_단_밖으로_나간_최대_px=round(max_over, 3)),
        층별_장수={f'{c}단 · x높이 {x}': n for (c, x), n in sorted(strata.items())},
        수준별_쌍=dict((lv, per_level.get(lv, 0)) for lv in LEVELS),
        수준_x높이별_쌍={lv: {str(x): per_level_xh.get((lv, x), 0) for x in (5, 8, 12)} for lv in LEVELS},
        실제_여유_x높이_최소_중앙_최대={lv: q(act[lv]) for lv in LEVELS if act[lv]},
        잉크틈_px_최소_중앙_최대={f'{lv} · x높이 {x}': q(ink[(lv, x)]) for lv in LEVELS for x in (5, 8, 12) if ink[(lv, x)]},
        블록당_줄수=dict(sorted(Counter(b['n'] for b in blocks).items())),
        판당_블록=dict(sorted(Counter(len(t['blocks']) for t in truths.values()).items())),
        판당_쌍=dict(sorted(Counter(len(t['pairs']) for t in truths.values()).items())),
        줄_채움_60퍼센트_미만=sum(1 for f in fills if f < 0.6), 줄=len(fills),
        표본=review,
        사람_확인=dict(기록=json.loads(a.human_check), 대기=a.human_check_pending,
                    기록_위치='eval/refs.json 의 clean.human_check · human_check_pending (run_all 이 인자로 넘긴다)'))
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ('표본', '잉크틈_px_최소_중앙_최대', '층_수준별_쌍', '수준_x높이별_쌍')}, ensure_ascii=False, indent=1))
    print('표본', [(r['층'], r['seed'], r['고른_까닭']) for r in review])
    print('→', a.out)


if __name__ == '__main__':
    main()
