"""코퍼스에서 규칙을 뽑는다.

수치를 코드에 박지 않는다. 디렉토리의 포스터를 측정해 분포를 내고,
그 분포가 「몰려 있는가」를 판정해 몰린 것만 규칙으로 채택한다.

채택 기준
    변동계수 <= CV_MAX      값이 한 범위에 모임
    표본 수  >= N_MIN       우연이 아님
둘 중 하나라도 안 되면 규칙이 아니라 「자유」로 기록한다.
기준을 넘지 못한 항목도 분포는 남겨, 나중에 표본이 늘면 재판정할 수 있다.
"""
import json
import os
import numpy as np

CV_MAX = 0.30      # 이보다 흩어지면 제약으로 보지 않는다
N_MIN = 20         # 이보다 적으면 판정을 보류한다

# TYPO_MCP_GPU=1 이면 GPU 를 쓴다. easyocr 은 cuda 가 없으면 mps 로 내려간다.
# 기본이 CPU 인 이유: M 계열에서 재보니 mps 가 빠르지 않다. 포스터 3장 기준
# cpu 1.7s/장, mps 1.9s/장, 측정값은 완전히 같았다. easyocr 의 인식 모델은
# CPU 에서 int8 양자화 경로를 타고, batch_size=1 이라 mps 는 이득이 없다.
GPU = os.environ.get('TYPO_MCP_GPU', '0') not in ('0', 'false', 'False')


def collect(paths, reader=None, progress=None):
    """포스터들을 측정해 원자료를 모은다."""
    import easyocr
    import pipeline
    if reader is None:
        reader = easyocr.Reader(['de'], gpu=GPU, verbose=False)
    raw = {}
    for i, p in enumerate(paths, 1):
        n = os.path.basename(p)
        try:
            r = pipeline.measure(p, reader)
            if not r['ok']:
                continue
            raw[n] = dict(angle=r['angle'], blocks=[
                dict(x1=int(b['x1']), y1=int(b['y1']), x2=int(b['x2']), y2=int(b['y2']),
                     n=int(b['n']), xh=float(b['xh']),
                     lead=(None if b['lead'] is None else int(b['lead'])),
                     bases=[int(l['base']) for l in b['lines']],
                     caps=[None if l['cap'] is None else int(l['cap']) for l in b['lines']],
                     xtops=[int(l['x_top']) for l in b['lines']]) for b in r['blocks']])
        except Exception:
            pass
        if progress:
            progress(i, len(paths), n)
    return raw


# ── 지표: 원자료에서 값 목록을 뽑는 함수들 ──────────────────────────────

def _cap_h(b):
    return [base - c for c, base in zip(b['caps'], b['bases']) if c is not None]


def m_lead_over_cap(raw):
    out = []
    for v in raw.values():
        for b in v['blocks']:
            if b['lead'] and b['n'] >= 3:
                cs = _cap_h(b)
                if cs:
                    out.append(b['lead'] / float(np.median(cs)))
    return out


def m_gap(raw):
    out = []
    for v in raw.values():
        for b in v['blocks']:
            if b['lead'] and b['n'] >= 3:
                cs = _cap_h(b)
                if cs:
                    out.append(b['lead'] - float(np.median(cs)))
    return out


def m_asc_over_xh(raw):
    out = []
    for v in raw.values():
        for b in v['blocks']:
            for c, x, base in zip(b['caps'], b['xtops'], b['bases']):
                if c is None:
                    continue
                a, xh = base - c, base - x
                if xh > 0 and a >= xh:
                    out.append(a / xh)
    return out


def m_align_ratio(raw):
    out = []
    for v in raw.values():
        xs = sorted(b['x1'] for b in v['blocks'])
        if len(xs) < 3:
            continue
        g = []
        for x in xs:
            if g and x - g[-1][-1] <= 2:
                g[-1].append(x)
            else:
                g.append([x])
        out.append(len(g) / len(xs))
    return out


METRICS = {
    'lead_over_cap': (m_lead_over_cap, '행간 / 활자높이', '블록'),
    'gap_px':        (m_gap,           '여백 = 행간 − 활자높이 (px)', '블록'),
    'asc_over_xh':   (m_asc_over_xh,   '어센더 / x높이', '줄'),
    'align_ratio':   (m_align_ratio,   '정렬선 수 / 블록 수', '포스터'),
}


def derive(raw):
    """원자료에서 분포를 내고 규칙 채택 여부를 판정한다."""
    rules, free = {}, {}
    for key, (fn, label, unit) in METRICS.items():
        a = np.array(fn(raw), dtype=float)
        if len(a) == 0:
            continue
        cv = float(a.std() / a.mean()) if a.mean() else 9.9
        d = dict(label=label, unit=unit, n=int(len(a)),
                 median=round(float(np.median(a)), 3),
                 lo=round(float(np.percentile(a, 10)), 3),
                 hi=round(float(np.percentile(a, 90)), 3),
                 cv=round(cv, 3))
        if len(a) >= N_MIN and cv <= CV_MAX:
            d['verdict'] = '제약'
            rules[key] = d
        else:
            d['verdict'] = '자유' if len(a) >= N_MIN else '표본 부족'
            free[key] = d
    return dict(n_posters=len(raw), rules=rules, not_rules=free,
                criteria=dict(cv_max=CV_MAX, n_min=N_MIN))


def save(path, raw, rules):
    json.dump(dict(raw=raw, rules=rules), open(path, 'w'), ensure_ascii=False)


def load(path):
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d.get('rules')
