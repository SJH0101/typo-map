"""브로크만 실물 50장 묶기 1단계 — 정답 없는 탐색, 결과 봉인. 사전등록 docs/brockmann_group_preregister.json (ba6c620).

    python eval/brockmann_group_explore.py prepare --posters docs/labeling/posters_for_labelers.json \\
        --selection docs/labeling/selection.json --work ~/.typo-mcp/brockmann50
    python eval/brockmann_group_explore.py seal --files boxes/brockmann_vlm_pass1.json boxes/brockmann_vlm_pass2.json
    python eval/brockmann_group_explore.py explore --work ~/.typo-mcp/brockmann50 --vlm boxes/brockmann_vlm_pass1.json \\
        --vlm boxes/brockmann_vlm_pass2.json --prereg docs/brockmann_group_preregister.json --out docs/brockmann_group_explore.json

봉인 — 라벨링 제출 전 열지 않는다 (사용자 결정 2026-09-14). 이 스크립트는 수치를 화면에 찍지 않고 파일에만 쓴다.
prepare 는 eval/group_score.py detect · som 을 그대로 부르고 출력을 작업 폴더의 로그로 보낸다.
탐색용 · 논문 수치 아님. C · VLM 의 정의 · 문턱을 바꾸지 않는다.
"""
import argparse
import contextlib
import hashlib
import itertools
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import detector_score as DSc   # noqa: E402
import group_gap as GG         # noqa: E402
import group_score as GS       # noqa: E402

SEAL = '라벨링 제출 전 열지 않는다 — 사용자 결정 2026-09-14 (docs/brockmann_group_preregister.json)'
SEED_BASE = 100   # seed = 100 + 순서. group_score 파일 키 f'{seed:03d}' 와 clean_vlm_batches 의 str(seed) 가 같아진다

# 1단계 유형 표시 — 사전등록에 적은 값 그대로
SIZE_RATIO = 1.5
SMALL_H, SMALL_W = 0.6, 0.25
EDGE = 0.05
BG_BINS, BG_DIFF, BAND_INK = 32, 40, 0.10


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


# ── prepare ─────────────────────────────────────────────────────

def prepare(a):
    P = json.load(open(a.posters)); root = os.path.expanduser(P['image_root'])
    S = {x['order']: x for x in json.load(open(a.selection))['list']}
    items = []
    for it in P['main']:
        p = os.path.join(root, it['folder'], it['file'])
        if _sha(p) != it['sha256']:
            sys.exit(f"목록과 다른 이미지: 순서 {it['order']}")
        items.append(dict(seed=SEED_BASE + it['order'], order=it['order'], image=os.path.join(it['folder'], it['file']),
                          image_sha256=it['sha256'], vlm_subset=True,
                          template=S[it['order']]['template'] or f"판{it['order']:02d}"))
    W = os.path.expanduser(a.work); os.makedirs(W, exist_ok=True)
    man = os.path.join(W, 'manifest.json'); lines = os.path.join(W, 'lines.json'); som_dir = os.path.join(W, 'som')
    json.dump(dict(봉인=SEAL, 무엇='브로크만 1단계 판 목록 (seed = 100 + 순서)', image_root=P['image_root'], posters=a.posters,
                   posters_sha256=_sha(a.posters), selection=a.selection, selection_sha256=_sha(a.selection), items=items),
              open(man, 'w'), ensure_ascii=False, indent=1)
    with open(os.path.join(W, 'prepare.log'), 'w') as log, contextlib.redirect_stdout(log):
        GS.detect(argparse.Namespace(dir=root, manifest=man, lines=lines, order='columns'))
        GS.som(argparse.Namespace(dir=root, manifest=man, lines=lines, som_dir=som_dir))
    L = json.load(open(lines)); L['봉인'] = SEAL
    json.dump(L, open(lines, 'w'), ensure_ascii=False)
    with open(os.path.join(W, '봉인.txt'), 'w') as f:
        f.write(SEAL + '\n')
    n_png = sum(1 for f in os.listdir(som_dir) if f.endswith('_som.png'))
    print(f'준비 끝: 판 {len(items)} · Surya 줄 파일 1 · SoM 이미지 {n_png} → {W} (수치는 파일에만, 봉인)')


def seal(a):
    for f in a.files:
        d = json.load(open(f)); d['봉인'] = SEAL
        json.dump(d, open(f, 'w'), ensure_ascii=False, indent=1)
        print('봉인 표시 →', f)


# ── explore ─────────────────────────────────────────────────────

def boxes(lines, asg):
    return [b[1][:4] for b in GS.boxes_of(lines, asg)]


def pair_agree(lines, a1, a2):
    n = len(lines)
    if n < 2:
        return None
    return float(np.mean([(a1[i] == a1[j]) == (a2[i] == a2[j]) for i, j in itertools.combinations(range(n), 2)]))


def bands_of(lines):
    """order_columns 와 같은 식으로 줄마다 단 번호."""
    bands = []
    for x1, x2 in sorted((b[0], b[2]) for b in lines):
        if bands and x1 <= bands[-1][1]:
            bands[-1][1] = max(bands[-1][1], x2)
        else:
            bands.append([x1, x2])
    return [next((i for i, (u, v) in enumerate(bands) if u <= (b[0] + b[2]) / 2 <= v), len(bands)) for b in lines], len(bands)


def neighbours(lines):
    """세로로 이웃한 쌍 (가로 겹침 · 사이에 다른 줄 없음) 과 같은 행에 가로로 이웃한 쌍."""
    n = len(lines); out = set()
    cy = [(b[1] + b[3]) / 2 for b in lines]; h = [b[3] - b[1] for b in lines]
    xo = lambda a, b: min(a[2], b[2]) - max(a[0], b[0])
    yo = lambda a, b: min(a[3], b[3]) - max(a[1], b[1])
    for i in range(n):
        below = [j for j in range(n) if j != i and cy[j] > cy[i] and xo(lines[i], lines[j]) > 0
                 and yo(lines[i], lines[j]) < 0.5 * min(h[i], h[j])]
        if below:
            j = min(below, key=lambda j: cy[j])
            if not any(k not in (i, j) and cy[i] < cy[k] < cy[j] and xo(lines[k], lines[i]) > 0 and xo(lines[k], lines[j]) > 0
                       for k in range(n)):
                out.add(('세로', min(i, j), max(i, j)))
        right = [j for j in range(n) if j != i and lines[j][0] >= lines[i][2] - 1 and yo(lines[i], lines[j]) >= 0.5 * min(h[i], h[j])]
        if right:
            j = min(right, key=lambda j: lines[j][0])
            out.add(('가로', min(i, j), max(i, j)))
    return sorted(out)


def background(g):
    q = (g // (256 // BG_BINS)).astype(int)
    m = Counter(q.ravel().tolist()).most_common(1)[0][0]
    return (m + 0.5) * (256 // BG_BINS)


def band_ink(g, bg, lines, i, j):
    H, W = g.shape
    a, b = lines[i], lines[j]
    m = max(a[3] - a[1], b[3] - b[1])
    x1 = int(max(0, min(a[0], b[0]) - m)); y1 = int(max(0, min(a[1], b[1]) - m))
    x2 = int(min(W, max(a[2], b[2]) + m)); y2 = int(min(H, max(a[3], b[3]) + m))
    if x2 <= x1 or y2 <= y1:
        return None
    keep = np.ones((y2 - y1, x2 - x1), bool)
    for bx in lines:
        u1 = int(max(x1, bx[0] - 2)); v1 = int(max(y1, bx[1] - 2)); u2 = int(min(x2, bx[2] + 2)); v2 = int(min(y2, bx[3] + 2))
        if u2 > u1 and v2 > v1:
            keep[v1 - y1:v2 - y1, u1 - x1:u2 - x1] = False
    if not keep.any():
        return None
    sub = g[y1:y2, x1:x2]
    return float((np.abs(sub - bg) > BG_DIFF)[keep].mean())


def explore(a):
    W = os.path.expanduser(a.work)
    M = json.load(open(os.path.join(W, 'manifest.json'))); root = os.path.expanduser(M['image_root'])
    LL = json.load(open(os.path.join(W, 'lines.json'))); L = LL['lines']
    items = GS._items(root, M)
    vlms = [GS.load_vlm(v) for v in a.vlm]
    names = [f'VLM{i}' for i in range(1, len(vlms) + 1)]
    tmpl = {GS._key(it['seed']): it['template'] for it in M['items']}
    agg = defaultdict(Counter); per_t = defaultdict(lambda: defaultdict(Counter)); agree = defaultdict(list)
    fb = Counter(); vparse = {nm: Counter() for nm in names}; sites = []; posters = []
    for k, p, it in items:
        if _sha(p) != it['image_sha256'] or L[k]['sha256'] != it['image_sha256']:
            sys.exit(f'목록과 다른 이미지 또는 줄 캐시: {p}')
        lines = L[k]['lines']
        g = np.asarray(Image.open(p).convert('L')).astype(float); H, Wd = g.shape
        c_asg, cd = GG.group_gap(g, lines, pad_rule=a.c_pad_rule)
        asg = {'C': c_asg}
        for nm, (vm, _info) in zip(names, vlms):
            asg[nm], info = GS.groups_vlm(lines, vm.get(k))
            vparse[nm].update(info); vparse[nm]['없는 장'] += (k not in vm)
        src = cd['source']
        fb['줄'] += len(lines); fb['줄_A'] += sum(1 for s in src if s == 'A'); fb['줄_소속없음'] += sum(1 for s in src if s is None)
        gsrc = {}
        for i, j in enumerate(c_asg):
            if j is not None:
                gsrc.setdefault(j, src[i])
        fb['C묶음'] += len(gsrc); fb['C묶음_A'] += sum(1 for s in gsrc.values() if s == 'A')
        P = {m: boxes(lines, v) for m, v in asg.items()}
        prow = dict(key=k, 순서=it['order'], 틀=tmpl[k], 줄=len(lines), 묶음={m: len(v) for m, v in P.items()})
        for x, y in [('C', nm) for nm in names] + ([(names[0], names[1])] if len(names) >= 2 else []):
            mr, _mp = DSc.match(P[x], P[y])
            key = f'{x}·{y}'
            for cnt in (agg[key], per_t[tmpl[k]][key]):
                cnt['짝'] += len(mr); cnt[x] += len(P[x]); cnt[y] += len(P[y])
            pa = pair_agree(lines, asg[x], asg[y])
            if pa is not None:
                agree[key].append(pa)
            prow[f'짝_{key}'] = len(mr)
        posters.append(prow)
        # 갈린 자리
        hs = [b[3] - b[1] for b in lines]; hmed = float(np.median(hs)) if hs else 0.0
        band, nb = bands_of(lines) if lines else ([], 0)
        bg = background(g)
        for kind, i, j in neighbours(lines):
            same = {m: (v[i] is not None and v[i] == v[j]) for m, v in asg.items()}
            for x, y in [('C', nm) for nm in names]:
                if same[x] == same[y]:
                    continue
                bi, bj = lines[i], lines[j]
                small = lambda b: (b[3] - b[1]) <= SMALL_H * hmed and (b[2] - b[0]) <= SMALL_W * Wd
                edge = lambda b: b[0] <= EDGE * Wd or b[2] >= (1 - EDGE) * Wd or b[1] <= EDGE * H or b[3] >= (1 - EDGE) * H
                ink = band_ink(g, bg, lines, i, j)
                cyu = ((min(bi[1], bj[1]) + max(bi[3], bj[3])) / 2) / H
                tags = dict(크기_섞임=max(hs[i], hs[j]) / max(1e-6, min(hs[i], hs[j])) >= SIZE_RATIO,
                            작은_딸림말=small(bi) or small(bj), 판_가장자리=edge(bi) or edge(bj),
                            도형_사진_옆=(ink is not None and ink >= BAND_INK), C_기전_밖=(src[i] == 'A' or src[j] == 'A'))
                sites.append(dict(key=k, 순서=it['order'], 틀=tmpl[k], 견줌=f'{x}·{y}', 이웃=kind, 줄=[i, j], 상자=[bi, bj],
                                  붙인_쪽=(x if same[x] else y), 유형=tags, 띠_잉크=None if ink is None else round(ink, 3),
                                  세로_자리=('위' if cyu < 1 / 3 else '가운데' if cyu < 2 / 3 else '아래'),
                                  단=[band[i], band[j]], 단_수=nb))
    def f1(c, x, y):
        return round(2 * c['짝'] / (c[x] + c[y]), 4) if (c[x] + c[y]) else None
    pairs = [('C', nm) for nm in names] + ([(names[0], names[1])] if len(names) >= 2 else [])
    res = dict(
        봉인=SEAL, 무엇='브로크만 실물 50장 묶기 1단계 — C 와 VLM, 정답 없음', 성격='탐색용 · 논문 수치 아님. C · VLM 의 정의 · 문턱을 바꾸지 않았다',
        사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg), manifest=os.path.join(a.work, 'manifest.json'),
        manifest_sha256=_sha(os.path.join(W, 'manifest.json')), 줄_provenance=LL.get('provenance'), 줄_순서=LL.get('order'),
        VLM=[v[1] for v in vlms], VLM_파싱={nm: dict(c) for nm, c in vparse.items()}, pad_rule=a.c_pad_rule,
        유형_표시_값=dict(크기_섞임=SIZE_RATIO, 작은_딸림말=[SMALL_H, SMALL_W], 판_가장자리=EDGE, 도형_사진_옆=[BG_BINS, BG_DIFF, BAND_INK]),
        같은_블록={f'{x}·{y}': dict(**dict(agg[f'{x}·{y}']), 대칭_F1=f1(agg[f'{x}·{y}'], x, y),
                                  줄쌍_일치율_평균=(round(float(np.mean(agree[f'{x}·{y}'])), 4) if agree[f'{x}·{y}'] else None))
                   for x, y in pairs},
        틀별_같은_블록={t: {f'{x}·{y}': dict(**dict(v[f'{x}·{y}']), 대칭_F1=f1(v[f'{x}·{y}'], x, y)) for x, y in pairs}
                     for t, v in sorted(per_t.items())},
        VLM_패스간_일치=(GS.pass_agreement(items, L, vlms[0][0], vlms[1][0]) if len(vlms) >= 2 else None),
        C_폴백_몫=dict(**dict(fb), 줄_A폴백=(round(fb['줄_A'] / fb['줄'], 4) if fb['줄'] else None),
                    C묶음_A폴백=(round(fb['C묶음_A'] / fb['C묶음'], 4) if fb['C묶음'] else None)),
        갈린_자리_요약={f'C·{nm}': dict(
            자리=sum(1 for s in sites if s['견줌'] == f'C·{nm}'),
            이웃=dict(Counter(s['이웃'] for s in sites if s['견줌'] == f'C·{nm}')),
            붙인_쪽=dict(Counter(s['붙인_쪽'] for s in sites if s['견줌'] == f'C·{nm}')),
            유형={t: sum(1 for s in sites if s['견줌'] == f'C·{nm}' and s['유형'][t]) for t in
                  ('크기_섞임', '작은_딸림말', '판_가장자리', '도형_사진_옆', 'C_기전_밖')},
            유형_없음=sum(1 for s in sites if s['견줌'] == f'C·{nm}' and not any(s['유형'].values())),
            세로_자리=dict(Counter(s['세로_자리'] for s in sites if s['견줌'] == f'C·{nm}')),
            틀별=dict(Counter(s['틀'] for s in sites if s['견줌'] == f'C·{nm}'))) for nm in names},
        판=posters, 갈린_자리=sites)
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('1단계 탐색 끝 →', a.out, '(봉인 — 수치는 파일에만)')


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('prepare')
    s.add_argument('--posters', required=True); s.add_argument('--selection', required=True); s.add_argument('--work', required=True)
    s = sp.add_parser('seal')
    s.add_argument('--files', nargs='+', required=True)
    s = sp.add_parser('explore')
    s.add_argument('--work', required=True); s.add_argument('--vlm', action='append', required=True)
    s.add_argument('--prereg', required=True); s.add_argument('--out', required=True)
    s.add_argument('--c-pad-rule', default='neighbor_half', choices=GG.PAD_RULES)
    a = ap.parse_args(argv)
    {'prepare': prepare, 'seal': seal, 'explore': explore}[a.cmd](a)


if __name__ == '__main__':
    main()
