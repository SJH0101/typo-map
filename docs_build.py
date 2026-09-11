"""코퍼스를 «잰 문서» 묶음으로 만든다.

    python docs_build.py                 283장 전부
    python docs_build.py --n 20          20장만
    python docs_build.py --out ~/docs    다른 곳에

한 판마다 XML 한 벌과, 질의하기 좋은 JSON 요약 한 줄을 낸다. XML 은 사람이
읽고 고치는 얼굴이고, JSON 은 코퍼스에 물어보는 얼굴이다. 같은 자료다.

문서에 «없는» 것을 적어 둔다 — 지금 이 형식은 자리·크기·위계·격자만 담는다.
글자 내용도, 색도, 서체도 없다. 그래서 이 문서로는 골격은 세워도 포스터를
다시 그리지 못한다. 없는 칸을 아는 것이 있는 칸을 아는 것만큼 중요하다.
"""
import argparse
import datetime
import json
import os

import numpy as np
from PIL import Image

import decon
import recurse
import schema
import surface
from measure import ground as G

ROOTS = surface.ROOTS
CACHE = os.path.expanduser('~/.typo-mcp')
MISSING = ['글자 내용', '색', '서체', '자획 굵기']
_WARNED = set()


def load_raw(corpus, cache=None):
    """캐시 한 코퍼스의 원자료. 어느 경로로 쟀는지 보고, 모르면 크게 알린다.

    옛 경로 캐시에는 provenance 가 없다. 조용히 읽으면 옛 값 위에서 돈 결과가
    새 값인 것처럼 섞인다 — 9월 검증 분석이 그랬다.
    """
    import sys
    path = os.path.join(os.path.expanduser(cache or CACHE), corpus + '.json')
    d = json.load(open(path))
    pv = d.get('provenance') or {}
    if pv.get('pipeline') != 'surya+ground' and path not in _WARNED:
        _WARNED.add(path)
        print(f'[주의] {path} — 측정 경로 표시가 없다. 옛 경로(baseline/detect) '
              f'산출물일 수 있다 (docs/y2_bug.json).', file=sys.stderr)
    return d['raw']


def one(path, det, source=None):
    root, _lines = recurse.read(path, det)
    W, H = Image.open(path).size
    leaf = [n for n in root.walk() if n.kind == '글줄']
    bs = []
    if leaf:
        r = G.measure_boxes(path, [n.box for n in leaf], coords='norm')
        bs = [dict(x1=b['box_ink'][0], y1=b['box_ink'][1],
                   x2=b['box_ink'][2], y2=b['box_ink'][3],
                   n=b['n_lines'], xh=b['xh_median'], bases=b['baselines'])
              for b in r['boxes'] if b.get('box_ink') and b.get('n_lines')]
    rules = decon.analyse(dict(size=[W, H], blocks=bs))
    doc, _ = schema.build(root, rules,
                          source=dict(file=os.path.basename(path), w=W, h=H,
                                      **(source or {})),
                          made=dict(grounding='auto', detector='surya-ocr 0.22.1',
                                    date=datetime.date.today().isoformat()))
    c, un = schema.add_content(doc, root, levels=(rules or {}).get('계층'))
    un += getattr(root, 'unmeasured', [])
    schema.add_unmeasured(doc, un)
    ns = list(root.walk())
    ax = (rules or {}).get('단') or {}
    gt = (rules or {}).get('격자검사') or {}
    hit = (rules or {}).get('맞힘') or {}
    row = dict(
        file=os.path.basename(path), w=W, h=H,
        마디=len(ns), 글줄=sum(1 for x in ns if x.kind == '글줄'),
        그림=sum(1 for x in ns if x.kind == '그림'),
        깊이=max(x.id.count('.') for x in ns),
        축=len(ax.get('축') or []), 피치=ax.get('피치'), 흔들림=ax.get('피치흔들림'),
        축맞힘=hit.get('어긋남중앙'), 축배수=hit.get('배수'),
        세로격자=(None if not gt else ('있음' if gt.get('분위', 1) < 0.05 else '없음')),
        격자단위=((rules or {}).get('격자') or {}).get('단위'),
        계층=[l['xh'] for l in ((rules or {}).get('계층') or [])],
        못잼=len(un))
    return schema.to_xml(doc), row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=None)
    ap.add_argument('--out', default='docs/corpus')
    a = ap.parse_args()
    from surya.detection import DetectionPredictor
    det = DetectionPredictor()
    os.makedirs(a.out, exist_ok=True)
    rows = []
    for c, root_dir in ROOTS.items():
        raw = load_raw(c)
        P = surface.resolve(raw, root_dir)
        ks = sorted(P)
        if a.n:
            ks = ks[:a.n]
        d = os.path.join(a.out, c)
        os.makedirs(d, exist_ok=True)
        for i, k in enumerate(ks):
            try:
                x, row = one(P[k], det)
            except Exception as e:
                print('  실패', c, k[:26], type(e).__name__, e, flush=True)
                continue
            row['corpus'] = c
            row['key'] = k
            open(os.path.join(d, k.replace('/', '_') + '.xml'), 'w').write(x)
            rows.append(row)
            if i % 25 == 0:
                print(f'  {c} {i + 1}/{len(ks)}', flush=True)
        print(f'{c} 끝 {len(ks)}', flush=True)
    json.dump(dict(만든날=datetime.date.today().isoformat(),
                   형식=schema.VERSION, 없는칸=MISSING, 판=rows),
              open(os.path.join(a.out, 'index.json'), 'w'), ensure_ascii=False)
    print(f'\n{len(rows)}장 · {a.out}')


if __name__ == '__main__':
    main()
