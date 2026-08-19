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
LAYER_GAP = 10.0   # 이웃 값의 간격이 간격 중앙값의 이 배를 넘으면 계층 경계로 본다.
                   # 행간/활자높이 51개로 스윕: 3~6배는 과분할(계층 6개),
                   # 8~15배가 평평(계층 4개), 25배부터 뭉갠다. 10 은 그 중간.

# TYPO_MCP_GPU=1 이면 GPU 를 쓴다. easyocr 은 cuda 가 없으면 mps 로 내려간다.
# 기본이 CPU 인 이유: M 계열에서 재보니 mps 가 빠르지 않다. 포스터 3장 기준
# cpu 1.7s/장, mps 1.9s/장, 측정값은 완전히 같았다. easyocr 의 인식 모델은
# CPU 에서 int8 양자화 경로를 타고, batch_size=1 이라 mps 는 이득이 없다.
GPU = os.environ.get('TYPO_MCP_GPU', '0') not in ('0', 'false', 'False')


def collect(paths, reader=None, progress=None, errors=None):
    """포스터들을 측정해 원자료를 모은다.

    errors 에 리스트를 주면 실패한 포스터와 이유를 담아 준다. 조용히 빠지게
    두면 안 된다 — fit_grid 의 음수 슬라이스 버그가 108장 중 2장을 떨어뜨리고
    있었는데, 예외가 삼켜져서 오래 드러나지 않았다.
    """
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
                if errors is not None:
                    errors.append(dict(file=n, reason=r.get('why', '측정 실패')))
                continue
            # 판면 마진을 재려면 종이 가장자리가 어딘지 알아야 한다. measure 는
            # orig_size 를 이미 계산해 돌려주는데 여기서 버리고 있었다.
            #
            # region 은 쓰면 안 된다. 그것은 회전·확장된 작업 이미지의 좌표계에
            # 있고 orig_size 는 원본 판면이다. 둘을 비교하면 회전된 포스터에서
            # 음수 마진이 나온다 (코어 4종 274장 중 30장, 전부 회전된 것).
            # 블록의 corners 는 measure 가 원본 좌표로 되돌려 둔 값이므로
            # 그것으로 글자 영역을 다시 잡는다.
            xs = [x for b in r['blocks'] for x, _ in b['corners']]
            ys = [y for b in r['blocks'] for _, y in b['corners']]
            raw[n] = dict(angle=r['angle'], size=list(r['orig_size']),
                          region=([min(xs), min(ys), max(xs), max(ys)] if xs else None),
                          n_columns=r.get('n_columns'),
                          blocks=[
                dict(x1=int(b['x1']), y1=int(b['y1']), x2=int(b['x2']), y2=int(b['y2']),
                     n=int(b['n']), xh=float(b['xh']),
                     lead=(None if b['lead'] is None else int(b['lead'])),
                     bases=[int(l['base']) for l in b['lines']],
                     caps=[None if l['cap'] is None else int(l['cap']) for l in b['lines']],
                     xtops=[int(l['x_top']) for l in b['lines']]) for b in r['blocks']])
        except Exception as e:
            if errors is not None:
                errors.append(dict(file=n, reason=f'{type(e).__name__}: {e}'))
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


def _margins(raw):
    """포스터마다 (좌, 우, 상, 하) 를 판면 대비 비율로.

    회전 보정을 받은 포스터는 뺀다. rotate(expand=True) 가 만든 채움 영역
    안에서 검출이 일어나면 원본 좌표로 되돌렸을 때 판면 밖으로 나간다.
    코어 4종 273장 중 26장이 그랬고 전부 회전된 것이었으며, 벗어난 정도가
    각도에 비례했다 (중앙 14px, 6.5°에서 58px). 음수 마진은 뜻이 없으므로
    값을 깎아 맞추지 않고 측정 대상에서 제외한다. 회전된 포스터의 마진은
    아직 잴 수 없다.
    """
    out = []
    for v in raw.values():
        sz, rg = v.get('size'), v.get('region')
        if not sz or not rg or abs(v.get('angle', 0)) >= 1:
            continue
        w, h = sz
        x1, y1, x2, y2 = rg
        if w <= 0 or h <= 0:
            continue
        out.append((x1 / w, (w - x2) / w, y1 / h, (h - y2) / h))
    return out


def m_margin_left(raw):
    return [m[0] for m in _margins(raw)]


def m_margin_right(raw):
    return [m[1] for m in _margins(raw)]


def m_margin_top(raw):
    return [m[2] for m in _margins(raw)]


def m_margin_bottom(raw):
    return [m[3] for m in _margins(raw)]


def m_columns(raw):
    return [v['n_columns'] for v in raw.values() if v.get('n_columns')]


METRICS = {
    'lead_over_cap': (m_lead_over_cap, '행간 / 활자높이', '블록'),
    'margin_left':   (m_margin_left,   '좌 마진 / 판면 폭', '포스터'),
    'margin_right':  (m_margin_right,  '우 마진 / 판면 폭', '포스터'),
    'margin_top':    (m_margin_top,    '상 마진 / 판면 높이', '포스터'),
    'margin_bottom': (m_margin_bottom, '하 마진 / 판면 높이', '포스터'),
    'n_columns':     (m_columns,       '단 개수', '포스터'),
    'gap_px':        (m_gap,           '여백 = 행간 − 활자높이 (px)', '블록'),
    'asc_over_xh':   (m_asc_over_xh,   '어센더 / x높이', '줄'),
    'align_ratio':   (m_align_ratio,   '정렬선 수 / 블록 수', '포스터'),
}


def layers(vals, factor=None):
    """값을 계층으로 가른다. 규칙이 몇 개인지도 코퍼스가 정한다.

    「몰렸나 흩어졌나」만 물으면 세 번째 경우를 놓친다 — 여러 곳에 몰림.
    호프만의 행간이 그렇다. 본문은 1.33 에 몰리고 실무 정보(개관 시간,
    입장료)는 2.0~4.0 에 몰린다. 그 둘을 한 덩어리로 재면 CV 가 커져서
    「자유」로 판정되지만, 실제로는 자유가 아니라 규칙이 둘이다.

    경계는 절대값으로 정하지 않는다. 이웃 간격이 그 지표 자신의 간격
    중앙값보다 LAYER_GAP 배 크면 거기서 가른다. 지표마다 단위가 달라도
    (배수, px, 비율) 같은 규칙이 적용된다.
    """
    factor = LAYER_GAP if factor is None else factor
    v = sorted(float(x) for x in vals)
    if len(v) < 4:
        return [v]
    gaps = np.diff(v)
    pos = gaps[gaps > 0]
    if pos.size == 0:
        return [v]
    thr = factor * float(np.median(pos))
    out, cur = [], [v[0]]
    for g, x in zip(gaps, v[1:]):
        if g > thr:
            out.append(cur)
            cur = [x]
        else:
            cur.append(x)
    out.append(cur)
    return out


def _judge(a, label, unit):
    """한 계층의 분포와 판정."""
    a = np.asarray(a, dtype=float)
    cv = float(a.std() / a.mean()) if a.mean() else 9.9
    d = dict(label=label, unit=unit, n=int(len(a)),
             median=round(float(np.median(a)), 3),
             lo=round(float(np.percentile(a, 10)), 3),
             hi=round(float(np.percentile(a, 90)), 3),
             # 실측 전폭. lo~hi 는 권장 범위이고 이쪽은 「코퍼스에 그런 값이
             # 있었는가」를 묻는 데 쓴다. 표본이 적으면 10~90% 밴드가 자기
             # 계층의 최대값조차 밀어내므로 둘을 구분해 둔다.
             min=round(float(a.min()), 3),
             max=round(float(a.max()), 3),
             cv=round(cv, 3))
    d['verdict'] = ('제약' if len(a) >= N_MIN and cv <= CV_MAX
                    else ('자유' if len(a) >= N_MIN else '표본 부족'))
    return d


def derive(raw):
    """원자료에서 분포를 내고 규칙 채택 여부를 판정한다."""
    rules, free = {}, {}
    for key, (fn, label, unit) in METRICS.items():
        a = np.array(fn(raw), dtype=float)
        if len(a) == 0:
            continue
        ls = layers(a)
        # 판정할 만큼 큰 계층만 따로 보고하고, 나머지는 한 덩어리로 모은다.
        # 표본이 조밀할수록 간격 중앙값이 작아져 희소한 꼬리가 잘게 부서지는데,
        # 그 조각 하나하나는 계층이 아니라 「아직 모르는 값」이다.
        big = [x for x in ls if len(x) >= N_MIN]
        rest = [v for x in ls if len(x) < N_MIN for v in x]
        if len(big) <= 1 and not rest:
            d = _judge(a, label, unit)
        else:
            parts = [_judge(x, label, unit) for x in big]
            if rest:
                r = _judge(rest, label, unit)
                r['label'] = label + ' (나머지)'
                parts.append(r)
            parts.sort(key=lambda p: p['median'])
            # 채택된 계층 중 표본이 가장 많은 것을 대표로 둔다. 대표가 없으면
            # 전체를 대표로 두어, 계층을 모르는 소비자도 예전처럼 동작한다.
            ok = [p for p in parts if p['verdict'] == '제약']
            d = dict(max(ok, key=lambda p: p['n'])) if ok else _judge(a, label, unit)
            d['n_all'] = int(len(a))
            d['layers'] = parts
            d['note'] = (f'값이 계층 {len(parts)} 개로 갈렸다. 위 수치는 대표 계층의 것이고 '
                         f'전체 {len(a)} 개 중 {d["n"]} 개를 덮는다. 계층별 분포는 layers 에 있다.')
        (rules if d['verdict'] == '제약' else free)[key] = d
    return dict(n_posters=len(raw), rules=rules, not_rules=free,
                criteria=dict(cv_max=CV_MAX, n_min=N_MIN, layer_gap=LAYER_GAP))


def save(path, raw, rules):
    json.dump(dict(raw=raw, rules=rules), open(path, 'w'), ensure_ascii=False)


def load(path):
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d.get('rules')
