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




# ── 지표: 원자료에서 값 목록을 뽑는 함수들 ──────────────────────────────

def _cap_h(b):
    return [base - c for c, base in zip(b['caps'], b['bases']) if c is not None]


def _lead(b):
    """행간은 «잰 값» 을 쓴다. 격자값은 「격자에 앉았나」라는 다른 질문이다.

    격자값(lead)은 자기상관 창(5~60px)을 벗어나거나 단 안에 블록이 여럿이면
    None 이 된다. 그것을 지표로 쓰니 브로크만 123장 중 64장이 행간을 한 값도
    내지 못했다. 실측값으로 바꾸면 그 대부분이 살아난다.
    """
    return b.get('lead_measured') or b.get('lead')


def m_lead_over_cap(raw):
    out = []
    for v in raw.values():
        for b in v['blocks']:
            if _lead(b) and b['n'] >= 3:
                cs = _cap_h(b)
                if cs:
                    out.append(_lead(b) / float(np.median(cs)))
    return out


def m_gap(raw):
    out = []
    for v in raw.values():
        for b in v['blocks']:
            if _lead(b) and b['n'] >= 3:
                cs = _cap_h(b)
                if cs:
                    out.append(_lead(b) - float(np.median(cs)))
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


def _color(raw, key):
    return [v['color'][key] for v in raw.values() if v.get('color')]


def m_ground_share(raw):  return _color(raw, 'ground_share')
def m_n_colors(raw):      return _color(raw, 'n_colors')
def m_saturation(raw):    return _color(raw, 'saturation')
def m_value(raw):         return _color(raw, 'value')
def m_gray_share(raw):    return _color(raw, 'gray_share')


def m_cap_range(raw):
    """한 포스터 안에서 가장 큰 활자와 가장 작은 활자의 비.

    호프만은 판을 덮는 표제활자와 8px 본문을 같이 쓴다. 브로크만은 그
    폭이 좁을 것으로 본다. 활자 크기 「비」 자체는 인접 비가 1.0~1.2 에
    몰려 측정 오차가 지배하지만, 한 포스터의 최대·최소 폭은 그 문제를
    받지 않는다 — 수십 배 차이를 재는 데 1px 오차는 무시할 만하다.
    """
    out = []
    for v in raw.values():
        xh = [b['xh'] for b in v['blocks'] if b['xh'] and b['xh'] > 0]
        if len(xh) >= 2:
            out.append(max(xh) / min(xh))
    return out


def m_text_area(raw):
    """블록이 덮은 면적의 합 / 판면 면적. 블록이 겹치면 겹친 만큼 더해진다."""
    out = []
    for v in raw.values():
        sz = v.get('size')
        if not sz or abs(v.get('angle', 0)) >= 1:
            continue
        w, h = sz
        if w <= 0 or h <= 0:
            continue
        area = sum(max(0, b['x2'] - b['x1']) * max(0, b['y2'] - b['y1']) for b in v['blocks'])
        out.append(area / float(w * h))
    return out


def m_n_blocks(raw):
    return [len(v['blocks']) for v in raw.values() if v['blocks']]


# 재려고 했으나 못 재는 것들. 주석이 아니라 데이터로 둔다 — 카드에 실어
# 보내야 소비자가 「안 쟀다」와 「재봤는데 못 믿겠다」를 구분한다.
BLOCKED = {
    'cap_ratio': dict(label='인접 활자 크기 비', unit='블록 쌍',
                      reason='인접 비가 1.0~1.2 에 몰려 측정 오차가 지배한다',
                      blocked_by='입력 해상도'),
    'descender': dict(label='디센더 깊이', unit='줄',
                      reason='검출 실패율이 높다',
                      blocked_by='입력 해상도'),
    'margin_const': dict(label='판면 마진 상수', unit='포스터',
                         reason='회전 보정된 포스터에서 글자 영역이 판면 밖으로 나간다',
                         blocked_by='회전 프레임의 채움 영역'),
}

# 지표마다 표본에서 무엇이 빠지는지. 표본 수만 주면 조건부인 줄 모른다.
EXCLUDES = {
    'margin_left':   '회전 보정된 포스터 — 판면 좌표를 신뢰할 수 없다',
    'margin_right':  '회전 보정된 포스터 — 판면 좌표를 신뢰할 수 없다',
    'margin_top':    '회전 보정된 포스터 — 판면 좌표를 신뢰할 수 없다',
    'margin_bottom': '회전 보정된 포스터 — 판면 좌표를 신뢰할 수 없다',
    'text_area':     '회전 보정된 포스터 — 판면 좌표를 신뢰할 수 없다',
}

UNITS = {
    'lead_over_cap': 'ratio', 'gap_px': 'px', 'asc_over_xh': 'ratio',
    'align_ratio': 'ratio', 'n_columns': 'count', 'cap_range': 'ratio',
    'text_area': 'fraction', 'n_blocks': 'count',
    'margin_left': 'fraction_of_width', 'margin_right': 'fraction_of_width',
    'margin_top': 'fraction_of_height', 'margin_bottom': 'fraction_of_height',
    'ground_share': 'fraction', 'n_colors': 'count',
    'saturation': 'fraction', 'value': 'fraction', 'gray_share': 'fraction',
}

METRICS = {
    'lead_over_cap': (m_lead_over_cap, '행간 / 활자높이', '블록'),
    'margin_left':   (m_margin_left,   '좌 마진 / 판면 폭', '포스터'),
    'margin_right':  (m_margin_right,  '우 마진 / 판면 폭', '포스터'),
    'margin_top':    (m_margin_top,    '상 마진 / 판면 높이', '포스터'),
    'margin_bottom': (m_margin_bottom, '하 마진 / 판면 높이', '포스터'),
    'n_columns':     (m_columns,       '단 개수', '포스터'),
    'cap_range':     (m_cap_range,     '활자 크기 폭 (최대/최소)', '포스터'),
    'text_area':     (m_text_area,     '글자 면적 / 판면 면적', '포스터'),
    'n_blocks':      (m_n_blocks,      '블록 개수', '포스터'),
    'ground_share':  (m_ground_share,  '최빈색 점유율', '포스터'),
    'n_colors':      (m_n_colors,      '색 수 (2% 이상 쓰인)', '포스터'),
    'saturation':    (m_saturation,    '채도 중앙값', '포스터'),
    'value':         (m_value,         '밝기 중앙값', '포스터'),
    'gray_share':    (m_gray_share,    '무채색 화소 비율', '포스터'),
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


# 지표 이름 → discrim 의 자리 지표. 여기 없는 지표는 자리를 섞어도 값이
# 변하지 않으므로(행간비·어센더비 등) 판별력을 잴 수 없고 CV 판정을 쓴다.
DISCRIM_MAP = {
    'margin_left': '마진왼쪽', 'margin_right': '마진오른쪽',
    'margin_top': '마진위',    'margin_bottom': '마진아래',
    'text_area': '덮음',       'align_ratio': '축_왼쪽수',
}


def _posters_for_discrim(raw):
    """원자료에서 (상자들, 폭, 높이) 를 뽑는다."""
    out = []
    for r in raw.values():
        bs = r.get('blocks') or []
        sz = r.get('orig_size') or r.get('size')
        if not bs or not sz:
            continue
        out.append(([(b['x1'], b['y1'], b['x2'], b['y2']) for b in bs],
                    float(sz[0]), float(sz[1])))
    return out


def derive(raw, references=None):
    """원자료에서 분포를 내고 규칙 채택 여부를 판정한다.

    판정이 셋이다.

        변동계수   이 코퍼스 안에서 값이 모이는가       (이 사람이 붙들었나)
        판별력     자리를 섞은 배치와 구분되는가         (우연이 아닌가)
        설명력     다른 작가와 다른가                  (이 사람 것인가)

    앞의 둘은 자주 엇갈린다 — discrim.py 첫머리와 docs/PART3.md 를 보라.
    셋째는 references 를 줄 때만 나온다. {이름: 원자료} 를 받는다.

    셋째는 버리는 기준이 아니다. 「브로크만은 행간을 활자높이의 1.5배로
    쓴다」는 호프만도 그래도 여전히 브로크만의 규칙이다. 채택은 앞의 둘로
    하고, 셋째는 scope 로 «갈림/공통» 를 표시만 한다. 그것이 없으면 폰트
    상수가 가장 먼저 규칙으로 채택된다 (distinct.py 첫머리).
    """
    import discrim
    import distinct
    rules, free = {}, {}
    exp = {}
    if references:
        per = {}
        for key, (fn, _l, _u) in METRICS.items():
            g = {'(이 코퍼스)': fn(raw)}
            for nm, rr in references.items():
                g[nm] = fn(rr)
            per[key] = g
        exp = distinct.by_metric(per)
    sep = discrim.separability(_posters_for_discrim(raw))
    n_all_posters = len(raw)
    for key, (fn, label, unit) in METRICS.items():
        a = np.array(fn(raw), dtype=float)
        if len(a) == 0:
            continue
        # 측정값 개수(n) 와 그 값을 낸 포스터 수는 다르다. 행간처럼 한 장에서
        # 여러 블록이 값을 내는 지표는 n 이 커도 소수의 포스터에서만 나올 수
        # 있다 — 빽빽한 활자 포스터나 사진 포스터는 블록이 안 묶여 한 값도
        # 내지 못한다. 규칙을 몇 장이 떠받치는지는 판단에 필요한 사실이다.
        n_from = sum(1 for name, r in raw.items() if len(fn({name: r})) > 0)
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
                # 잔여물은 규칙이 될 수 없다. 여러 작은 계층을 모은 것이라
                # 하나의 무리가 아니고, CV 가 낮게 나오는 것은 우연이다.
                # 표시하지 않으면 대표 계층 자리를 차지해 검사기가 잔여물의
                # 범위를 규칙으로 들이댄다 (브로크만 상 마진에서 실제로 그랬다).
                r['verdict'] = '혼합'
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
        # n 은 대표 계층의 측정값 수다. 아래 둘은 지표 전체 기준이므로
        # 계층이 갈린 지표에서는 n 보다 클 수 있다.
        d.setdefault('n_all', int(len(a)))
        d['n_posters'] = n_from
        d['n_posters_all'] = n_all_posters
        if n_from < n_all_posters:
            d['coverage'] = (f'이 지표는 {n_all_posters} 장 중 {n_from} 장에서 나왔다 '
                             f'({n_from / n_all_posters * 100:.0f}%). 나머지 '
                             f'{n_all_posters - n_from} 장은 한 값도 내지 못했다 — '
                             f'무작위 표본이 아니므로 규칙을 그 장들까지 확장해 읽으면 안 된다.')
        # 자리에서 나오는 지표는 판별력도 함께 묻는다. 값이 모여도 자리를
        # 섞은 것과 구분되지 않으면 작가의 선택이라 할 수 없다.
        dk = DISCRIM_MAP.get(key)
        if dk and dk in sep:
            v = sep[dk]
            d['auc'] = v['auc']
            d['auc_real'] = v['real']
            d['auc_null'] = v['null']
            if v['auc'] < discrim.AUC_MIN:
                if d['verdict'] == '제약':
                    d['verdict'] = '정보 없음'
                    d['note_discrim'] = (
                        f'변동계수 {d["cv"]} 로는 모이지만 자리를 섞은 배치와 '
                        f'구분되지 않는다 (AUC {v["auc"]}, 진짜 {v["real"]} 대 '
                        f'무작위 {v["null"]}). 규칙으로 쓰면 안 된다.')
                else:
                    d['note_discrim'] = f'판별력도 없다 (AUC {v["auc"]}).'
            elif d['verdict'] != '제약':
                d['note_discrim'] = (
                    f'변동계수 {d["cv"]} 로는 흩어지지만 자리를 섞은 배치와는 '
                    f'구분된다 (AUC {v["auc"]}, 진짜 {v["real"]} 대 무작위 '
                    f'{v["null"]}). 값 하나로 못 박을 수는 없어도 방향은 있다.')
        # 셋째 축. 채택을 바꾸지 않고 표시만 한다.
        if key in exp:
            e = exp[key]
            d['scope'] = e['scope']
            d['eta2'] = e['eta2']
            d['eta2_null'] = e['eta2_null']
            d['eta2_ratio'] = e['ratio']
            d['scope_pct'] = e['pct']
            d['scope_of'] = e['corpora']
            if e['scope'] == '경계':
                d['note_scope'] = (
                    f'문턱에 걸쳐 있다 (설명력 {e["eta2"]*100:.1f}%, 무작위 딱지 '
                    f'{e["eta2_null"]*100:.1f}% — {e["ratio"]}배). 참조를 조금만 바꿔도 '
                    f'판정이 뒤집힌다. 갈린다고도 안 갈린다고도 적을 수 없다.')
            elif e['scope'] == '공통':
                d['note_scope'] = (
                    f'이 지표는 참조 {e["n_corpora"]} 종을 가르지 못한다 '
                    f'(설명력 {e["eta2"]*100:.1f}%, 딱지를 섞어도 '
                    f'{e["eta2_null"]*100:.1f}% 는 나온다 — {e["ratio"]}배). 값이 몰리더라도 '
                    f'작가의 선택이 아니라 폰트·판형·인쇄에서 오는 것일 수 있다.')
            else:
                d['note_scope'] = (
                    f'이 지표는 참조 {e["n_corpora"]} 종을 가른다 '
                    f'(설명력 {e["eta2"]*100:.1f}%, 무작위 딱지 '
                    f'{e["eta2_null"]*100:.1f}% — {e["ratio"]}배). 다만 이 코퍼스가 남들 밖에 있는지는 '
                    f'따로 물어야 한다 — style_card 의 reference 를 보라.')
        (rules if d['verdict'] == '제약' else free)[key] = d
    return dict(n_posters=len(raw), rules=rules, not_rules=free,
                separability=sep, scope=exp or None,
                criteria=dict(cv_max=CV_MAX, n_min=N_MIN, layer_gap=LAYER_GAP,
                              auc_min=discrim.AUC_MIN,
                              scope_alpha=distinct.ALPHA if references else None,
                              scope_min_ratio=distinct.MIN_RATIO if references else None))


def median_ci(a, boot=4000, seed=0):
    """중앙값의 95% 신뢰구간. 표본이 적으면 넓게 나온다 — 그게 정보다."""
    a = np.asarray(a, dtype=float)
    if len(a) < 3:
        return None
    rng = np.random.default_rng(seed)
    bs = np.median(rng.choice(a, (boot, len(a)), replace=True), axis=1)
    return [round(float(x), 4) for x in np.percentile(bs, [2.5, 97.5])]


def compare(key, raws):
    """참조 코퍼스들과 대조한다. 사실만 낸다 — 결론은 읽는 쪽이 낸다.

    separating_pairs 가 0 이면 「지금 라이브러리로는 이 지표가 아무도 구분하지
    못한다」는 뜻이다. 그것이 지표의 성질인지 라이브러리가 한쪽으로 치우쳐서인지는
    도구가 알 수 없다. 라이브러리에 없는 것이 무엇인지는 라이브러리가 모른다.
    """
    fn = METRICS[key][0]
    med, cis, names = [], [], []
    for name, raw in raws.items():
        a = np.array(fn(raw), dtype=float)
        if key in ('lead_over_cap', 'gap_px', 'asc_over_xh') and len(a):
            # 표본이 가장 많은 계층을 대표로 쓴다. derive() 와 같은 규칙이다.
            # 가장 낮은 계층을 쓰면 값 하나짜리 이상치가 코퍼스 값을 가로챈다 —
            # 브로크만 행간비가 실제 본문 계층(n=184, 1.437) 대신 n=1 인
            # 0.72 로 보고됐다.
            a = np.array(max(layers(a), key=len), dtype=float)
        if not len(a):
            continue
        names.append(name)
        med.append(float(np.median(a)))
        cis.append(median_ci(a))
    if len(names) < 2:
        return None
    sep, pairs = 0, []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            x, y = cis[i], cis[j]
            if not x or not y:
                continue
            if x[1] < y[0] or y[1] < x[0]:
                sep += 1
                pairs.append([names[i], names[j]])
    m = np.array(med)
    return dict(n_corpora=len(names), corpora=names,
                medians={n: round(v, 4) for n, v in zip(names, med)},
                spread=(round(float(m.max() / m.min()), 3) if m.min() > 0 else None),
                separating_pairs=sep, of_pairs=len(names) * (len(names) - 1) // 2,
                separated=pairs)


def save(path, raw, rules):
    json.dump(dict(raw=raw, rules=rules), open(path, 'w'), ensure_ascii=False)


def load(path):
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d.get('rules')
