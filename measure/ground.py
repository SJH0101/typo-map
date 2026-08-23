"""VLM 이 짚은 상자를 받아 재고, 코퍼스 원자료로 쌓는다.

이 파일이 파이프라인의 빠진 고리다. region 은 상자 하나를 재고,
rules 는 원자료 더미에서 규칙을 뽑는데, 그 사이에 「누가 상자를 짚나」가
비어 있었다. baseline 의 detect.run() 이 그 자리를 맡고 있었고 그것이 헛것 92개·
놓침 52개를 냈다. 여기서는 짚는 쪽을 부르는 쪽에게 넘긴다.

부르는 쪽이 곧 VLM 이다 — API 키가 필요하지 않다. 이 저장소는 MCP 서버라
클로드가 클라이언트로 붙는다. 클로드가 포스터를 눈으로 보고 상자를 불러주면
서버가 그 안을 잰다. 판단은 모델이, 계측은 코드가 (judgment–measurement
separation, region.py 참조).

좌표는 기본이 정규화(0~1)다. 모델은 픽셀 수를 세지 않고 화면의 비율로
본다 — 원본 해상도를 알려주지 않아도 상자를 부를 수 있어야 한다.

    from ground import ground
    ground('poster.jpg', [{'id':'제목', 'box':[0.08,0.10,0.62,0.19]}])
"""
import json
import os

import numpy as np
from PIL import Image

import rules
from color import fields
from measure import region


MIN_LINES = 1     # 줄을 하나도 못 찾은 상자는 원자료에 넣지 않는다


def _px(box, W, H, coords):
    """정규화 좌표를 원본 픽셀로. 이미 픽셀이면 그대로."""
    x1, y1, x2, y2 = [float(v) for v in box]
    if coords == 'norm':
        x1, x2 = x1 * W, x2 * W
        y1, y2 = y1 * H, y2 * H
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def measure_boxes(path, boxes, coords='norm'):
    """짚어준 상자마다 그 안의 조판을 잰다. 상자 밖은 보지 않는다."""
    img = Image.open(path)
    W, H = img.size
    g = np.asarray(img.convert('L')).astype(float)
    out = []
    for i, b in enumerate(boxes):
        raw = b['box'] if isinstance(b, dict) else b
        bid = b.get('id') or f'b{i + 1}' if isinstance(b, dict) else f'b{i + 1}'
        px = _px(raw, W, H, coords)
        m = region.measure(g, px)
        out.append(dict(id=bid, box_px=[round(v, 1) for v in px],
                        role=(b.get('role') if isinstance(b, dict) else None), **m))
    return dict(size=[W, H], boxes=out)


def _block(m):
    """측정 결과를 rules 가 아는 블록 모양으로. 상자는 잉크 실측으로 잡는다.

    짚어준 상자가 아니라 box_ink 를 쓴다. 짚기는 넉넉하게 들어오지만
    마진과 덮음 비율은 글자가 실제로 닿은 자리를 물어보는 지표다.
    """
    x1, y1, x2, y2 = m['box_ink']
    return dict(x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2),
                n=int(m['n_lines']), xh=float(m['xh_median']),
                lead=(None if m['lead_measured'] is None else int(round(m['lead_measured']))),
                bases=[int(v) for v in m['baselines']],
                caps=[None if c is None else int(c) for c in m['caps']],
                xtops=[int(v) for v in m['x_tops']])


def entry(path, boxes, coords='norm', photo=True):
    """포스터 한 장의 원자료. rules.collect 가 내는 것과 같은 모양이다."""
    r = measure_boxes(path, boxes, coords)
    bs = [_block(m) for m in r['boxes'] if m.get('n_lines', 0) >= MIN_LINES]
    xs = [v for b in bs for v in (b['x1'], b['x2'])]
    ys = [v for b in bs for v in (b['y1'], b['y2'])]
    e = dict(angle=0.0,                       # 원본 좌표계에서 잰다. 회전 보정을 하지 않는다
             size=list(r['size']),
             color=fields.features(path),
             region=([min(xs), min(ys), max(xs), max(ys)] if xs else None),
             n_columns=None,                  # 열은 짚어주지 않았으므로 재지 않는다
             blocks=bs,
             grounded=True)                   # 자동 검출이 아니라 짚어준 상자라는 표시
    if photo:
        try:
            from color import photo as _p
            ph = _p.look(path)
            if ph:
                e['photo'] = ph
        except Exception:
            pass
    return e, r


def load_raw(cache):
    if not os.path.exists(cache):
        return {}
    return json.load(open(cache)).get('raw', {})


def ground(path, boxes, cache=None, coords='norm', store=True):
    """한 장을 짚어 재고, 원하면 캐시에 쌓고 규칙을 다시 뽑는다."""
    e, r = entry(path, boxes, coords)
    res = dict(ok=True, file=os.path.basename(path), size=r['size'],
               n_boxes=len(boxes), n_measured=len(e['blocks']), boxes=r['boxes'])
    if not store or not cache:
        return res
    raw = load_raw(cache)
    mixed = [k for k, v in raw.items() if not v.get('grounded')]
    raw[os.path.basename(path)] = e
    R = rules.derive(raw)
    rules.save(cache, raw, R)
    res.update(cache=cache, n_posters=len(raw), rules_n=len(R.get('rules', {})))
    if mixed:
        # 자동 검출한 것과 짚어준 것을 한 캐시에 섞으면 분포가 두 방법의
        # 혼합이 된다. 규칙이 어느 쪽에서 나왔는지 말할 수 없게 된다.
        res['warning'] = (f'이 캐시에 자동 검출로 재둔 포스터가 {len(mixed)}장 있다. '
                          f'짚어준 것과 섞이면 분포를 해석할 수 없다. 캐시를 나눠라')
    return res
