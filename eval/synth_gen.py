"""합성 포스터 생성기 — 정답을 알고 그린다.

사전등록 docs/synth_preregister.json (af0b145, 수정 1) 을 그대로 옮긴 것이다. 수준 · 템플릿 ·
좌표 약속은 거기 있고, 여기서 새로 정한 것은 없다. 결과를 보고 이 파일의 상수를
바꾸지 않는다.

    python eval/synth_gen.py --out ~/.typo-mcp/synth --manifest docs/synth_manifest.json
    python eval/synth_gen.py --out /tmp/x --cells base xh_18 --seeds 1 2     # 일부만

generate.py · render.py 와 다른 점 하나 — 장마다 정답 JSON 을 함께 쓴다. 낱말
주머니는 render.py 에서 import 한다 (옮기지 않는다).

좌표 약속. 마스터(800px 판의 4배)에 정수 좌표로 그리고 LANCZOS 로 줄인다. 정답은
출력 이미지의 연속 좌표다. 행 r 은 [r, r+1) 을 덮으므로 베이스라인 y=b 이면 평평한
글자 바닥이 행 b−1 에서 끝나고, measure/ink.py baseline() (마지막 잉크 행 + 1) 의
기대값은 b 자체다.
"""
import argparse
import colorsys
import datetime
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import render as R  # noqa: E402  낱말 주머니

W800, H800 = 566, 800          # F4. 실물 283장 폭 중앙 566 · 높이 800
MASTER = 4                     # 마스터 배율
XH_BASE = 8                    # 기준 x높이 (800px 판 px)
LEAD_RATIO = 2.0               # g = 행간 = 2.0 × x높이
TITLE_MULT = 2.0               # 표제 x높이 = 2 × 본문
MARGIN = 0.04                  # 좌우 여백 / W
GUTTER = 0.035                 # 단 사이 틈 / W
FILL = (0.60, 1.00)            # 줄이 단 폭을 채우는 비율
INDEP_RATIOS = (1.75, 2.0, 2.36)   # 블록별 독립: 행간 / x높이 (실물 25 · 50 · 75%)
RANDOM_JITTER = (0.70, 1.30)       # 무작위: 간격 × U
BOTTOM_PAD = 0.02              # 넘침 판정 — 마지막 디센더가 H·(1−0.02) 를 넘으면 다시 뽑는다

# (id, 역할, 열, 첫 베이스라인 g, 줄 수, x높이 배수, 행간 g)
TEMPLATE = [
    ('T', 'title', 'span', 3, 2, TITLE_MULT, 2),
    ('A', 'body', 0, 9, 5, 1.0, 1),
    ('C', 'body', 0, 16, 3, 1.0, 1),
    ('B', 'body', 1, 6, 8, 1.0, 1),
    ('E', 'single', 1, 14, 1, 1.0, 1),
    ('D', 'body', 1, 16, 4, 1.0, 1),
]

FONTS = {
    'helvetica': dict(file='/System/Library/Fonts/Helvetica.ttc', index=0),   # 서체 1종 (사전등록 수정 1)
}

def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

POLARITY = {
    'white_black': dict(ground=(255, 255, 255), ink=(0, 0, 0)),
    'colored_black': dict(ground=_hsv(40, 0.35, 0.72), ink=(0, 0, 0)),
    'dark_light': dict(ground=(25, 25, 28), ink=(245, 245, 242)),
}

BASE = dict(resolution=800, polarity='white_black', xh_px_at_800=XH_BASE, jpeg_q=72,
            rule='shared_grid', font='helvetica')

CELLS = {
    'base': {},
    'res_1600': dict(resolution=1600), 'res_400': dict(resolution=400),
    'pol_colored': dict(polarity='colored_black'), 'pol_dark': dict(polarity='dark_light'),
    'xh_3': dict(xh_px_at_800=3), 'xh_5': dict(xh_px_at_800=5),
    'xh_12': dict(xh_px_at_800=12), 'xh_18': dict(xh_px_at_800=18),
    'jpeg_95': dict(jpeg_q=95), 'jpeg_45': dict(jpeg_q=45),
    'rule_independent': dict(rule='independent'), 'rule_random': dict(rule='random'),
}

# 본문 블록 역할마다 문구를 짓는 법. 주머니는 render.py 의 것
def _phrase(rnd, kind):
    c = lambda pool: pool[rnd.randint(len(pool))]
    if kind == 0: return c(R.SUB)
    if kind == 1: return c(R.VENUE)
    if kind == 2: return c(R.WHEN) + '  ' + c(R.HOUR)
    if kind == 3: return c(R.COMPOSER) + '  ' + c(R.WORK)
    if kind == 4: return c(R.ROLE) + '  ' + c(R.PERSON)
    return c(R.SALE)


def _condition(cell):
    c = dict(BASE); c.update(CELLS[cell]); return c


def _font_info(name):
    f = FONTS[name]
    probe = ImageFont.truetype(f['file'], 1000, index=f['index'])
    cap = -probe.getbbox('H', anchor='ls')[1]
    xh = -probe.getbbox('x', anchor='ls')[1]
    return dict(file=f['file'], index=f['index'], name=' '.join(probe.getname()),
                sha256=hashlib.sha256(open(f['file'], 'rb').read()).hexdigest(),
                cap_over_em=cap / 1000.0, xh_over_em=xh / 1000.0)


def _lum(rgb):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _gray(rgb):
    return int(round(0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]))   # PIL 'L'


def contrast(ground, ink):
    lg, li = _lum(ground), _lum(ink)
    hi, lo = max(lg, li), min(lg, li)
    return dict(ground_rgb=list(ground), ink_rgb=list(ink),
                ground_luminance=round(lg, 4), ink_luminance=round(li, 4),
                wcag_ratio=round((hi + 0.05) / (lo + 0.05), 2),
                michelson=round((hi - lo) / (hi + lo), 4) if hi + lo else 0.0,
                gray_delta=abs(_gray(ground) - _gray(ink)))


def fill_line(rnd, kind, font, width):
    """문구를 이어 붙여 폭의 60~100% 를 채운다. 넘치면 마지막 문구를 뺀다. 활자는 안 줄인다.

    문구 하나도 안 들어가는 폭(x높이 18 의 단)에서는 그 역할 주머니에서 들어가는
    문구를 seed 순서로 찾고, 그래도 없으면 들어가는 가장 넓은 것을 쓴다. 한 글자로
    줄이지 않는다 — 한 글자 줄은 글줄이 아니다."""
    best = None
    for _ in range(40):
        parts = []
        while len(parts) < 6:
            cand = parts + [_phrase(rnd, kind)]
            if font.getlength('  '.join(cand)) <= width:
                parts = cand
            else:
                break
        if parts:
            t = '  '.join(parts)
            if font.getlength(t) >= FILL[0] * width:
                return t
            if best is None or font.getlength(t) > font.getlength(best):
                best = t
    if best is not None:
        return best
    pool = sorted({w for P in (R.HOUR, R.SUB, R.VENUE, R.COMPOSER, R.SALE) for w in P}, key=font.getlength)
    fit = [w for w in pool if font.getlength(w) <= width]
    return fit[rnd.randint(len(fit))] if fit else pool[0]


def title_line(rnd, font, width):
    order = rnd.permutation(len(R.TITLE))
    for i in order:
        if font.getlength(R.TITLE[i]) <= width:
            return R.TITLE[i]
    return R.TITLE[order[0]]


def layout(cond, seed, fonts):
    """한 장의 배치 (마스터 좌표, 정수 베이스라인). 같은 seed → 같은 배치."""
    rnd = np.random.RandomState(seed)
    xh = cond['xh_px_at_800'] * MASTER
    g = LEAD_RATIO * xh
    Wm, Hm = W800 * MASTER, H800 * MASTER
    mL = MARGIN * Wm; gut = GUTTER * Wm
    colw = (Wm - 2 * mL - gut) / 2
    fi = fonts[cond['font']]
    rule = cond['rule']
    blocks = []
    for bid, role, col, u0, n, mult, lead_u in TEMPLATE:
        xh_b = xh * mult
        size = xh_b / fi['xh_over_em']
        font = ImageFont.truetype(fi['file'], size, index=fi['index'])
        x = mL if col in ('span', 0) else mL + colw + gut
        width = (Wm - 2 * mL) if col == 'span' else colw
        lead = lead_u * g
        phase = 0.0
        if rule in ('independent', 'random'):
            phase = rnd.uniform(0, g)
            if n >= 3:
                lead = INDEP_RATIOS[rnd.randint(len(INDEP_RATIOS))] * xh
        for _try in range(50):
            gaps = [lead] * (n - 1)
            if rule == 'random':
                gaps = [lead * rnd.uniform(*RANDOM_JITTER) for _ in gaps]
            bases = [u0 * g + phase]
            for gp in gaps:
                bases.append(bases[-1] + gp)
            if bases[-1] + 0.25 * size <= Hm * (1 - BOTTOM_PAD):
                break
        bases = [int(round(b)) for b in bases]
        kind0 = rnd.randint(6)
        lines = []
        for i, b in enumerate(bases):
            if role == 'title':
                text = title_line(rnd, font, width)
            else:
                text = fill_line(rnd, (kind0 + i) % 6, font, width)
            bb = font.getbbox(text, anchor='ls')
            lines.append(dict(text=text, x=int(round(x)), baseline=b, fill=round(font.getlength(text) / width, 3),
                              ink=[int(round(x)) + bb[0], b + bb[1], int(round(x)) + bb[2], b + bb[3]],
                              has_ascender=any(ch in 'bdfhklt0123456789ßÄÖÜ' or ch.isupper() for ch in text),
                              has_descender=any(ch in 'gjpqy,;' for ch in text),
                              has_mark=any(ch in 'ijäöü' for ch in text)))
        blocks.append(dict(id=bid, role=role, column=(None if col == 'span' else col), n=n,
                           font_px=size, xh_px=xh_b, cap_px=size * fi['cap_over_em'],
                           lead_px=(float(np.median(np.diff(bases))) if n > 1 else None),
                           gaps_px=[float(d) for d in np.diff(bases)],
                           on_grid=(rule == 'shared_grid'), font=font, lines=lines))
    grid = dict(g_px=g, phi_px=0.0) if rule == 'shared_grid' else None
    return dict(canvas=[Wm, Hm], g=g, grid=grid, blocks=blocks)


def render(lay, cond):
    pol = POLARITY[cond['polarity']]
    im = Image.new('RGB', tuple(lay['canvas']), pol['ground'])
    d = ImageDraw.Draw(im)
    for b in lay['blocks']:
        for l in b['lines']:
            d.text((l['x'], l['baseline']), l['text'], font=b['font'], fill=pol['ink'], anchor='ls')
    s = cond['resolution'] / H800
    out = im.resize((int(round(W800 * s)), int(round(H800 * s))), Image.Resampling.LANCZOS)
    return out, s


def truth(lay, cond, cell, seed, s, fi, prov):
    k = MASTER / s               # 마스터 → 출력 px
    pol = POLARITY[cond['polarity']]
    blocks = []
    for b in lay['blocks']:
        ls = []
        for l in b['lines']:
            x1, y1, x2, y2 = l['ink']
            ls.append(dict(text=l['text'], fill=l['fill'], baseline_y=l['baseline'] / k,
                           cap_y=(l['baseline'] - b['cap_px']) / k,
                           xtop_y=(l['baseline'] - b['xh_px']) / k,
                           desc_y=y2 / k if l['has_descender'] else None,
                           x1=x1 / k, x2=x2 / k, ink_box=[x1 / k, y1 / k, x2 / k, y2 / k],
                           has_ascender=l['has_ascender'], has_descender=l['has_descender'],
                           has_mark=l['has_mark']))
        xs1 = min(l['ink'][0] for l in b['lines']); ys1 = min(l['ink'][1] for l in b['lines'])
        xs2 = max(l['ink'][2] for l in b['lines']); ys2 = max(l['ink'][3] for l in b['lines'])
        blocks.append(dict(id=b['id'], role=b['role'], column=b['column'], n=b['n'],
                           font_px=b['font_px'] / k, xh_px=b['xh_px'] / k, cap_px=b['cap_px'] / k,
                           lead_px=(None if b['lead_px'] is None else b['lead_px'] / k),
                           gaps_px=[x / k for x in b['gaps_px']], on_grid=b['on_grid'],
                           ink_box=[xs1 / k, ys1 / k, xs2 / k, ys2 / k], lines=ls))
    grid = None if lay['grid'] is None else dict(g_px=lay['grid']['g_px'] / k, phi_px=0.0)
    return dict(cell=cell, seed=seed, condition=cond,
                canvas=[int(round(W800 * s)), int(round(H800 * s))], scale_from_800=s,
                master_scale=MASTER,
                font={k_: v for k_, v in fi.items()},
                contrast=contrast(pol['ground'], pol['ink']),
                grid=grid, grid_note='격자 공유가 아니면 null. 위상 0 = 베이스라인이 g 의 정수배',
                template=[dict(id=t[0], role=t[1], column=t[2], first_unit=t[3], n=t[4],
                               xh_mult=t[5], lead_units=t[6]) for t in TEMPLATE],
                coord_note='연속 좌표. 행 r 은 [r, r+1). 베이스라인 b 이면 평평한 글자 바닥이 행 b−1 에서 끝난다',
                blocks=blocks, provenance=prov)


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description='합성 포스터와 정답을 만든다')
    ap.add_argument('--out', required=True, help='이미지 · 정답 폴더 (저장소 밖, 예 ~/.typo-mcp/synth)')
    ap.add_argument('--manifest', help='sha256 목록 JSON (예 docs/synth_manifest.json)')
    ap.add_argument('--cells', nargs='*', default=list(CELLS), choices=list(CELLS))
    ap.add_argument('--seeds', nargs='*', type=int, default=list(range(1, 31)))
    ap.add_argument('--prereg', default='docs/synth_preregister.json')
    ap.add_argument('--font-helvetica', default=FONTS['helvetica']['file'])
    a = ap.parse_args(argv)
    FONTS['helvetica']['file'] = a.font_helvetica
    out = os.path.expanduser(a.out)
    fonts = {k: _font_info(k) for k in FONTS}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT).decode().strip()
    except Exception:
        commit = None
    prov = dict(generator='eval/synth_gen.py', commit=commit, prereg=a.prereg,
                prereg_sha256=(_sha(os.path.join(ROOT, a.prereg)) if os.path.exists(os.path.join(ROOT, a.prereg)) else None),
                pillow=Image.__version__, freetype=features.version('freetype2'),
                date=datetime.date.today().isoformat(), synthetic=True)
    items = []
    for cell in a.cells:
        cond = _condition(cell)
        os.makedirs(os.path.join(out, cell), exist_ok=True)
        for seed in a.seeds:
            lay = layout(cond, seed, fonts)
            im, s = render(lay, cond)
            jp = os.path.join(out, cell, f'{seed:03d}.jpg')
            im.save(jp, 'JPEG', quality=cond['jpeg_q'], subsampling=0, optimize=False, progressive=False)
            t = truth(lay, cond, cell, seed, s, fonts[cond['font']], prov)
            tp = jp[:-4] + '.json'
            json.dump(t, open(tp, 'w'), ensure_ascii=False, indent=1)
            items.append(dict(cell=cell, seed=seed, image=os.path.relpath(jp, out),
                              image_sha256=_sha(jp), truth_sha256=_sha(tp),
                              n_lines=sum(b['n'] for b in t['blocks'])))
        print(f'{cell:18s} {len(a.seeds)}장  x높이 {cond["xh_px_at_800"]} · {cond["resolution"]}px · '
              f'{cond["polarity"]} · q{cond["jpeg_q"]} · {cond["rule"]} · {cond["font"]}', flush=True)
    if a.manifest:
        json.dump(dict(what='합성 포스터 manifest — 이미지 · 정답의 sha256. 생성기는 seed 에 결정론적이다',
                       out=a.out, cells={c: _condition(c) for c in a.cells}, seeds=a.seeds,
                       fonts=fonts, provenance=prov, items=items),
                  open(os.path.join(ROOT, a.manifest), 'w'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
