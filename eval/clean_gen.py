"""깨끗한 세트 생성기 — 겹침이 생길 수 없는 순서로 쌓는다.

사전등록 docs/clean_preregister.json (4c06aa4) · 수정 1 (4a763c8) · 수정 2 (e502d98) 그대로.

    python eval/clean_gen.py --out ~/.typo-mcp/clean --manifest docs/clean_manifest.json

앞 세트(eval/group_gen.py, 폐기)는 간격을 먼저 정하고 글자를 놓아 부딪침 검사를 한 번만 한 자리에서
잉크가 겹쳤다. 여기서는 순서를 뒤집는다.

    ① 최소 거리 D_min = (문구 주머니 글자의 가장 깊은 아래끝 + 가장 높은 윗끝) × 글자 크기, 마스터 px 올림
    ② 행간 2 × x높이 ≥ D_min 을 단언한다 — 블록 안 줄도 닿지 않는다
    ③ 블록 사이 배치 거리 D = D_min + c × x높이 (c_in 수준은 D = 행간)

한 판 안 모든 블록은 등크기 · 3~8줄. 렌더 · 정답 형식 · 좌표 약속은 eval/synth_gen.py 와 같다.

수정 1: 판당 블록 상한을 없앴다 (근거 없는 임의 제약이었다 — 쌓기는 판 높이가 멈춘다). 수준은 8수준을
섞어 쓰고 다 쓰면 다시 섞는다. 줄 글은 eval/clean_phrases.py 로 채우며 판 안에서 같은 원자를 다시 쓰지 않는다.
"""
import argparse
import datetime
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFont, features

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import clean_phrases as CP  # noqa: E402  문구 주머니 · 판 안 중복 금지
import synth_gen as SG      # noqa: E402

SEED0 = 3001
# 수정 2: 1단 · 12px 층만 21 → 60장. 층 배정 식은 그대로 두고 i ≡ 6 (mod 9) 을 3189 뒤로 이은 39장을 더한다
SEEDS = list(range(SEED0, SEED0 + 189)) + [3196 + 9 * k for k in range(39)]
# 수정 3: 층 × 수준 칸마다 25쌍 바닥 — 3538 뒤에서 층마다 그 층의 i (mod 9) 를 작은 것부터
SEEDS += ([3547 + 9 * k for k in range(20)]     # 1단 · 12px 60 → 80
          + [3544 + 9 * k for k in range(19)]   # 1단 · 8px 21 → 40
          + [3539 + 9 * k for k in range(12)]   # 2단 · 12px 21 → 33
          + [3540])                             # 3단 · 12px 21 → 22
COLS = (1, 2, 3)
XH = (5, 8, 12)
LEVELS = ('c_in', 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
LINES = (3, 8)
BOTTOM_PAD = SG.BOTTOM_PAD


def charset():
    return CP.charset()


def extents(fi):
    """주머니 글자의 가장 깊은 아래끝 · 가장 높은 윗끝 (em). 1000px 에서 잰다."""
    probe = ImageFont.truetype(fi['file'], 1000, index=fi['index'])
    cs = charset()
    top = {c: -probe.getbbox(c, anchor='ls')[1] for c in cs}
    bot = {c: probe.getbbox(c, anchor='ls')[3] for c in cs}
    a = max(top.values()); d = max(bot.values())
    return dict(charset=''.join(cs),
                max_ascent_em=a / 1000.0, max_ascent_chars=''.join(c for c in cs if top[c] == a),
                max_descender_em=d / 1000.0, max_descender_chars=''.join(c for c in cs if bot[c] == d))


def condition(seed):
    i = seed - SEED0
    return dict(columns=COLS[i % 3], xh_px_at_800=XH[(i // 3) % 3], resolution=800,
                polarity='white_black', jpeg_q=72, rule='clean_clearance', font='helvetica')


def distance(level, lead, dmin, xh_m):
    """배치 거리 (마스터 px). c_in 은 행간과 같다."""
    if level == 'c_in':
        return lead
    step = level * xh_m
    assert abs(step - round(step)) < 1e-9, (level, xh_m)
    return dmin + int(round(step))


def layout(seed, fi, ext):
    rnd = np.random.RandomState(seed)
    cond = condition(seed)
    xh_m = cond['xh_px_at_800'] * SG.MASTER
    size = xh_m / fi['xh_over_em']
    lead = int(round(SG.LEAD_RATIO * xh_m))
    asc_px, desc_px = ext['max_ascent_em'] * size, ext['max_descender_em'] * size
    dmin_exact = asc_px + desc_px
    dmin = math.ceil(dmin_exact)
    assert lead >= dmin, f'행간 {lead} < 최소 거리 {dmin} — 블록 안 줄이 닿을 수 있다'
    font = ImageFont.truetype(fi['file'], size, index=fi['index'])
    Wm, Hm = SG.W800 * SG.MASTER, SG.H800 * SG.MASTER
    mL = SG.MARGIN * Wm; gut = SG.GUTTER * Wm
    c = cond['columns']
    colw = (Wm - 2 * mL - gut * (c - 1)) / c
    for _try in range(20):
        queue = []                                   # 8수준을 섞어 쓰고 다 쓰면 다시 섞는다
        filler = CP.Filler(rnd)
        blocks, pairs = [], []
        for ci in range(c):
            x = mL + ci * (colw + gut)
            prev = None
            n_here = 0
            while True:                               # 판 높이가 멈춘다 — 블록 상한 없음
                n = int(rnd.randint(LINES[0], LINES[1] + 1))
                if prev is None:
                    level, D = None, None
                    base0 = 2 * lead + math.ceil(asc_px)
                else:
                    if len(pairs) >= len(queue):
                        queue += [LEVELS[k] for k in rnd.permutation(len(LEVELS))]
                    level = queue[len(pairs)]          # 놓일 때만 소비한다
                    D = distance(level, lead, dmin, xh_m)
                    base0 = prev['last'] + D
                last = base0 + lead * (n - 1)
                if last + math.ceil(desc_px) > Hm * (1 - BOTTOM_PAD):
                    break
                bases = [base0 + lead * i for i in range(n)]
                kind0 = rnd.randint(len(CP.ROLES))
                lines = []
                for i, b in enumerate(bases):
                    text, meta = filler.line((kind0 + i) % len(CP.ROLES), font, colw)
                    bb = font.getbbox(text, anchor='ls')
                    lines.append(dict(text=text, x=int(round(x)), baseline=b, fill=round(font.getlength(text) / colw, 3),
                                      ink=[int(round(x)) + bb[0], b + bb[1], int(round(x)) + bb[2], b + bb[3]],
                                      has_ascender=any(ch in 'bdfhklt0123456789ßÄÖÜ' or ch.isupper() for ch in text),
                                      has_descender=any(ch in 'gjpqy,;' for ch in text),
                                      has_mark=any(ch in 'ijäöüéîó' for ch in text), meta=meta))
                bid = f'{"ABC"[ci]}{n_here + 1}'
                blk = dict(id=bid, role='body', column=ci, n=n, font_px=size, xh_px=xh_m,
                           cap_px=size * fi['cap_over_em'], lead_px=lead,
                           gaps_px=[float(lead)] * (n - 1), on_grid=False,
                           font=font, lines=lines, last=bases[-1])
                if prev is not None:
                    pairs.append(dict(upper=prev['id'], lower=bid, column=ci, level=level, D=D,
                                      upper_n=prev['n'], lower_n=n))
                blocks.append(blk)
                prev = blk
                n_here += 1
        if len(blocks) >= 2:
            break
    return dict(canvas=[Wm, Hm], g=lead, grid=None, blocks=blocks, pairs=pairs, condition=cond,
                level_order=[str(v) for v in queue], phrase_stats=filler.stats, dmin=dmin, dmin_exact=dmin_exact, lead=lead, xh_m=xh_m,
                columns_x=[[mL + ci * (colw + gut), mL + ci * (colw + gut) + colw] for ci in range(c)])


def _inner(block):
    """블록 안 이웃 줄 잉크 틈 (마스터 px) 목록."""
    return [b['ink'][1] - a['ink'][3] for a, b in zip(block['lines'], block['lines'][1:])]


def truth(lay, seed, s, fi, ext, prov):
    t = SG.truth(lay, lay['condition'], 'clean', seed, s, fi, prov)
    k = SG.MASTER / s
    xh_m, lead = lay['xh_m'], lay['lead']
    idx = {b['id']: b for b in lay['blocks']}
    pairs = []
    for p in lay['pairs']:
        u, l = idx[p['upper']], idx[p['lower']]
        ink_gap = l['lines'][0]['ink'][1] - u['lines'][-1]['ink'][3]
        inner = float(np.median(_inner(u) + _inner(l)))
        target = (lead - lay['dmin_exact']) / xh_m if p['level'] == 'c_in' else float(p['level'])
        pairs.append(dict(
            upper=p['upper'], lower=p['lower'], column=p['column'], upper_n=p['upper_n'], lower_n=p['lower_n'],
            level=str(p['level']), clearance_target_xh=round(target, 4),
            min_distance_master=lay['dmin'], min_distance_exact_master=round(lay['dmin_exact'], 4),
            min_distance_px=lay['dmin'] / k,
            placed_distance_master=p['D'], placed_distance_px=p['D'] / k,
            clearance_actual_px=round((p['D'] - lay['dmin_exact']) / k, 4),
            clearance_actual_xh=round((p['D'] - lay['dmin_exact']) / xh_m, 4),
            baseline_gap_over_lead=round(p['D'] / lead, 4),
            ink_gap_px=ink_gap / k, ink_gap_over_xh=round(ink_gap / xh_m, 4),
            inner_ink_gap_px=inner / k, ink_gap_over_inner=(round(ink_gap / inner, 4) if inner > 0 else None)))
    t['pairs'] = pairs
    for tb, b in zip(t['blocks'], lay['blocks']):
        for tl, l in zip(tb['lines'], b['lines']):
            tl.update(role=l['meta']['role'], role_used=l['meta']['role_used'], atoms=l['meta']['atoms'],
                      repeated=l['meta']['repeated'])
    counts = {}
    for b in lay['blocks']:
        for l in b['lines']:
            for at in l['meta']['atoms']:
                counts[at] = counts.get(at, 0) + 1
    t['phrase_stats'] = dict(**lay['phrase_stats'], atoms=len(counts), max_atom_count=max(counts.values()) if counts else 0)
    t['template'] = None
    t['grid_note'] = '무작위 배치 — 격자 없음'
    t['font_extents'] = ext
    t['min_distance_xh'] = round((ext['max_ascent_em'] + ext['max_descender_em']) / fi['xh_over_em'], 4)
    t['levels'] = [str(v) for v in LEVELS]
    t['level_order'] = lay['level_order']
    t['columns_x_px'] = [[a / k, b / k] for a, b in lay['columns_x']]
    t['pairs_note'] = ('같은 단에서 세로로 이웃한 블록 둘. 거리는 위 블록 마지막 베이스라인 → 아래 블록 첫 베이스라인. '
                       'min_distance = 주머니 글자 최댓값 아래끝 + 윗끝이 닿는 거리 (마스터 px 올림). '
                       'clearance_actual = 배치 거리 − 올림 전 최소 거리. ink_gap = 아래 첫 줄 잉크 위 − 위 마지막 줄 잉크 아래. '
                       'inner_ink_gap = 두 블록 안 이웃 줄 잉크 틈의 중앙값')
    return t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--manifest')
    ap.add_argument('--seeds', nargs='*', type=int, default=SEEDS)
    ap.add_argument('--prereg', default='docs/clean_preregister.json')
    ap.add_argument('--font-helvetica', default=SG.FONTS['helvetica']['file'])
    a = ap.parse_args(argv)
    SG.FONTS['helvetica']['file'] = a.font_helvetica
    out = os.path.expanduser(a.out); os.makedirs(out, exist_ok=True)
    fi = SG._font_info('helvetica'); ext = extents(fi)
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT).decode().strip()
    except Exception:
        commit = None
    pp = os.path.join(ROOT, a.prereg)
    prov = dict(generator='eval/clean_gen.py', commit=commit, prereg=a.prereg,
                prereg_sha256=(SG._sha(pp) if os.path.exists(pp) else None),
                pillow=Image.__version__, freetype=features.version('freetype2'),
                date=datetime.date.today().isoformat(), synthetic=True)
    items = []
    for seed in a.seeds:
        lay = layout(seed, fi, ext)
        im, s = SG.render(lay, lay['condition'])
        jp = os.path.join(out, f'{seed}.jpg')
        im.save(jp, 'JPEG', quality=72, subsampling=0, optimize=False, progressive=False)
        t = truth(lay, seed, s, fi, ext, prov)
        tp = jp[:-4] + '.json'
        json.dump(t, open(tp, 'w'), ensure_ascii=False, indent=1)
        items.append(dict(seed=seed, image=os.path.relpath(jp, out), image_sha256=SG._sha(jp), truth_sha256=SG._sha(tp),
                          phrase_max_atom_count=t['phrase_stats']['max_atom_count'], borrowed_lines=t['phrase_stats']['borrowed'],
                          columns=lay['condition']['columns'], xh=lay['condition']['xh_px_at_800'],
                          n_blocks=len(t['blocks']), n_pairs=len(t['pairs']), levels=[p['level'] for p in t['pairs']],
                          vlm_subset=True))
    print(f'{len(items)}장 · 블록 {sum(i["n_blocks"] for i in items)} · 쌍 {sum(i["n_pairs"] for i in items)}')
    if a.manifest:
        json.dump(dict(what='깨끗한 세트 manifest', out=a.out, seeds=a.seeds, fonts={'helvetica': fi},
                       font_extents=ext, provenance=prov,
                       phrase_bank=dict(file='eval/clean_phrases.py', sha256=SG._sha(os.path.join(HERE, 'clean_phrases.py')),
                                        roles={n: len(r) for n, r in zip(CP.ROLE_NAMES, CP.ROLES)}, charset=''.join(CP.charset())),
                       items=items),
                  open(os.path.join(ROOT, a.manifest) if not os.path.isabs(a.manifest) else a.manifest, 'w'),
                  ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
