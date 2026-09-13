"""줄 단위 재기 pad 규칙 검증 — 사전등록 docs/measure_pad_preregister.json (2eac80c) 그대로.

    python eval/measure_pad_check.py --dir ~/.typo-mcp/measure_pad --manifest docs/measure_pad_manifest.json \\
        --lines ~/.typo-mcp/measure_pad-lines.json --prereg docs/measure_pad_preregister.json \\
        --out docs/measure_pad_result.json

줄 상자마다 region.measure 로 잰 줄 수를 정답 줄 수(잉크 세로 중심이 상자 세로 범위 안 · 가로로 겹침)와
견준다. 현재(fixed, PAD 3)와 P1(group_gap.neighbor_pad)을 같은 상자에서 짝지어 잰다. 묶기는 돌리지 않는다.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import group_gap as GG        # noqa: E402
from measure import region    # noqa: E402


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def _cat(n, t):
    return '같음' if n == t else ('늘어남' if n > t else '빠짐')


def main(argv=None):
    ap = argparse.ArgumentParser(description='줄 단위 재기 pad 규칙 검증 — 경로는 모두 인자')
    ap.add_argument('--dir', required=True); ap.add_argument('--manifest', required=True)
    ap.add_argument('--lines', required=True); ap.add_argument('--prereg', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    D = os.path.expanduser(a.dir); M = json.load(open(a.manifest))
    Ld = json.load(open(os.path.expanduser(a.lines))); L = Ld['lines']
    tot = {'현재': Counter(), 'P1': Counter()}
    pair = Counter(); strata = defaultdict(lambda: {'현재': Counter(), 'P1': Counter()})
    n_box = 0
    for it in M['items']:
        k = f"{it['seed']:03d}"
        p = os.path.join(D, it['image'])
        if _sha(p) != it['image_sha256'] or L[k]['sha256'] != it['image_sha256']:
            sys.exit(f'manifest 와 다른 이미지 또는 줄 캐시: {p}')
        t = json.load(open(p[:-4] + '.json'))
        g = np.asarray(Image.open(p).convert('L')).astype(float)
        tl = [ln['ink_box'] for b in t['blocks'] for ln in b['lines']]
        boxes = L[k]['lines']
        for i, box in enumerate(boxes):
            n_box += 1
            tru = sum(1 for ib in tl if box[1] <= (ib[1] + ib[3]) / 2 <= box[3] and min(box[2], ib[2]) - max(box[0], ib[0]) > 0)
            n0 = int(region.measure(g, box).get('n_lines', 0))
            n1 = int(region.measure(g, box, pad=GG.neighbor_pad(boxes, i)).get('n_lines', 0))
            c0, c1 = _cat(n0, tru), _cat(n1, tru)
            tot['현재'][c0] += 1; tot['P1'][c1] += 1
            strata[it['xh']]['현재'][c0] += 1; strata[it['xh']]['P1'][c1] += 1
            pair[('맞음' if c0 == '같음' else '틀림', '맞음' if c1 == '같음' else '틀림')] += 1
    acc = {r: tot[r]['같음'] / n_box for r in tot}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT).decode().strip()
    except Exception:
        commit = None
    res = dict(
        무엇='줄 단위 재기 pad 규칙 검증 — 줄 상자당 잰 줄 수가 정답과 같은 몫, 현재(PAD 3) 대 P1(이웃 틈 절반)',
        사전등록=a.prereg, 사전등록_sha256=_sha(a.prereg), manifest=a.manifest, manifest_sha256=_sha(a.manifest),
        줄_provenance=Ld.get('provenance'), commit=commit,
        장=len(M['items']), 줄상자=n_box,
        현재=dict(일치율=round(acc['현재'], 4), **dict(tot['현재'])),
        P1=dict(일치율=round(acc['P1'], 4), **dict(tot['P1'])),
        짝지은_네칸={'둘 다 맞음': pair[('맞음', '맞음')], '현재만 맞음': pair[('맞음', '틀림')],
                  'P1 만 맞음': pair[('틀림', '맞음')], '둘 다 틀림': pair[('틀림', '틀림')]},
        x높이층={str(x): {r: dict(상자=sum(c.values()), 일치율=round(c['같음'] / sum(c.values()), 4), **dict(c))
                        for r, c in d.items()} for x, d in sorted(strata.items())},
        판정=('채택' if acc['P1'] > acc['현재'] else '불채택'),
        판정_규칙='P1 일치율 > 현재 일치율 이면 채택. 낮거나 같으면 불채택 · 깨끗한 세트도 fixed · 재탐색 없음')
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ('줄_provenance',)}, ensure_ascii=False, indent=1))
    print('→', a.out)


if __name__ == '__main__':
    main()
