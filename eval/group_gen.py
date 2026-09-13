"""묶기 비교용 합성 세트 — 무작위 배치, 쌍마다 간격 · 크기 비를 독립으로 뽑는다.

사전등록 docs/group_preregister.json (57f5dbe) 그대로. 렌더 · 정답 형식 · 좌표 약속은
eval/synth_gen.py 를 import 해서 쓴다.

    python eval/group_gen.py --out ~/.typo-mcp/group --manifest docs/group_manifest.json
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import synth_gen as SG   # noqa: E402

N = 240
COLS = (1, 2, 3)
XH = (5, 8, 12)
GAP_LEVELS = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0)
MULTS = (1.0, 1.5, 2.5)
MULT_P = (0.5, 0.25, 0.25)        # 본문 다음에 오는 배수의 확률. 큰 블록 다음은 반드시 본문
LINES = (1, 8)
MAX_BLOCKS = 8                    # 판당 블록 상한 (사전등록 «2~8»). 단마다 남은 몫을 고르게 나눈다
DESC_EM = 0.209                   # Helvetica p 디센더 (정답 파일의 font 지표와 같은 출처)
BOTTOM_PAD = SG.BOTTOM_PAD


def condition(seed):
    return dict(columns=COLS[seed % 3], xh_px_at_800=XH[(seed // 3) % 3],
                resolution=800, polarity='white_black', jpeg_q=72, rule='random_layout',
                font='helvetica')


def layout(seed, fi):
    rnd = np.random.RandomState(seed)
    cond = condition(seed)
    xh = cond['xh_px_at_800'] * SG.MASTER
    g_body = SG.LEAD_RATIO * xh
    Wm, Hm = SG.W800 * SG.MASTER, SG.H800 * SG.MASTER
    mL = SG.MARGIN * Wm; gut = SG.GUTTER * Wm
    c = cond['columns']
    colw = (Wm - 2 * mL - gut * (c - 1)) / c
    for _try in range(20):
        blocks, pairs = [], []
        for ci in range(c):
            x = mL + ci * (colw + gut)
            prev = None
            cap_here = int(np.ceil((MAX_BLOCKS - len(blocks)) / (c - ci)))
            n_here = 0
            while n_here < cap_here:
                if prev is None or prev['mult'] > 1.0:
                    mult = 1.0 if prev is not None else MULTS[rnd.choice(3, p=MULT_P)]
                else:
                    mult = MULTS[rnd.choice(3, p=MULT_P)]
                n = int(rnd.randint(LINES[0], LINES[1] + 1))
                xh_b = xh * mult
                size = xh_b / fi['xh_over_em']
                cap = size * fi['cap_over_em']
                lead = SG.LEAD_RATIO * xh_b
                font = ImageFont.truetype(fi['file'], size, index=fi['index'])
                level = bumped = None
                if prev is None:
                    base0 = 2 * g_body + cap
                else:
                    level = float(GAP_LEVELS[rnd.randint(len(GAP_LEVELS))])
                    g_up = SG.LEAD_RATIO * prev['xh']
                    base0 = prev['last'] + level * g_up
                    bumped = False
                    # 위 블록 디센더 바닥과 아래 블록 캡 윗끝이 부딪치면 1g 로 올린다
                    if base0 - cap < prev['last'] + DESC_EM * prev['size'] + SG.MASTER * 0.25:
                        level, bumped = 1.0, True
                        base0 = prev['last'] + level * g_up
                last = base0 + lead * (n - 1)
                if last + DESC_EM * size > Hm * (1 - BOTTOM_PAD):
                    break
                bases = [int(round(base0 + lead * i)) for i in range(n)]
                kind0 = rnd.randint(6)
                lines = []
                for i, b in enumerate(bases):
                    text = SG.fill_line(rnd, (kind0 + i) % 6, font, colw)
                    bb = font.getbbox(text, anchor='ls')
                    lines.append(dict(text=text, x=int(round(x)), baseline=b, fill=round(font.getlength(text) / colw, 3),
                                      ink=[int(round(x)) + bb[0], b + bb[1], int(round(x)) + bb[2], b + bb[3]],
                                      has_ascender=any(ch in 'bdfhklt0123456789ßÄÖÜ' or ch.isupper() for ch in text),
                                      has_descender=any(ch in 'gjpqy,;' for ch in text),
                                      has_mark=any(ch in 'ijäöü' for ch in text)))
                bid = f'{"ABC"[ci]}{len([b for b in blocks if b["column"] == ci]) + 1}'
                blk = dict(id=bid, role='body' if mult == 1.0 else 'big', column=ci, n=n, font_px=size,
                           xh_px=xh_b, cap_px=cap, lead_px=(lead if n > 1 else None),
                           gaps_px=[float(d) for d in np.diff(bases)], on_grid=False, xh_mult=mult,
                           font=font, lines=lines, mult=mult, xh=xh_b, size=size, last=bases[-1])
                if prev is not None:
                    pairs.append(dict(upper=prev['id'], lower=bid, column=ci, gap_level=level,
                                      gap_px=(bases[0] - prev['last']) / SG.MASTER,
                                      gap_over_g_upper=(bases[0] - prev['last']) / (SG.LEAD_RATIO * prev['xh']),
                                      size_ratio=round(max(mult, prev['mult']) / min(mult, prev['mult']), 2),
                                      upper_n=prev['n'], lower_n=n, bumped=bumped))
                blocks.append(blk)
                prev = blk
                n_here += 1
        if len(blocks) >= 2:
            break
    return dict(canvas=[Wm, Hm], g=g_body, grid=None, blocks=blocks, pairs=pairs, condition=cond)


def truth(lay, seed, s, fi, prov):
    t = SG.truth(lay, lay['condition'], 'group', seed, s, fi, prov)
    for tb, b in zip(t['blocks'], lay['blocks']):
        tb['xh_mult'] = b['xh_mult']
    t['pairs'] = lay['pairs']
    t['template'] = None
    t['grid_note'] = '무작위 배치 — 격자 없음'
    t['pairs_note'] = ('같은 단에서 세로로 이웃한 블록 둘. gap_px 는 위 마지막 베이스라인 → 아래 첫 베이스라인 (출력 px). '
                       'gap_level 은 뽑은 수준, bumped 는 0.5 가 부딪쳐 1 로 오른 것. g_upper = 2 × 위 블록 x높이')
    return t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--manifest')
    ap.add_argument('--seeds', nargs='*', type=int, default=list(range(1, N + 1)))
    ap.add_argument('--prereg', default='docs/group_preregister.json')
    ap.add_argument('--font-helvetica', default=SG.FONTS['helvetica']['file'])
    a = ap.parse_args(argv)
    SG.FONTS['helvetica']['file'] = a.font_helvetica
    out = os.path.expanduser(a.out); os.makedirs(out, exist_ok=True)
    fi = SG._font_info('helvetica')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT).decode().strip()
    except Exception:
        commit = None
    pp = os.path.join(ROOT, a.prereg)
    prov = dict(generator='eval/group_gen.py', commit=commit, prereg=a.prereg,
                prereg_sha256=(SG._sha(pp) if os.path.exists(pp) else None),
                pillow=Image.__version__, freetype=features.version('freetype2'),
                date=datetime.date.today().isoformat(), synthetic=True)
    items = []
    npairs = 0
    for seed in a.seeds:
        lay = layout(seed, fi)
        im, s = SG.render(lay, lay['condition'])
        jp = os.path.join(out, f'{seed:03d}.jpg')
        im.save(jp, 'JPEG', quality=72, subsampling=0, optimize=False, progressive=False)
        t = truth(lay, seed, s, fi, prov)
        tp = jp[:-4] + '.json'
        json.dump(t, open(tp, 'w'), ensure_ascii=False, indent=1)
        npairs += len(t['pairs'])
        items.append(dict(seed=seed, image=os.path.relpath(jp, out), image_sha256=SG._sha(jp),
                          truth_sha256=SG._sha(tp), columns=lay['condition']['columns'],
                          xh=lay['condition']['xh_px_at_800'], n_blocks=len(t['blocks']),
                          n_pairs=len(t['pairs']), vlm_subset=(seed % 2 == 0)))
    print(f'{len(items)}장 · 블록 {sum(i["n_blocks"] for i in items)} · 쌍 {npairs} · VLM 표본 {sum(i["vlm_subset"] for i in items)}')
    if a.manifest:
        json.dump(dict(what='묶기 비교 세트 manifest', out=a.out, seeds=a.seeds, fonts={'helvetica': fi},
                       provenance=prov, items=items),
                  open(os.path.join(ROOT, a.manifest), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
