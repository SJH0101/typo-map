"""간격 일정성으로 묶기 (방식 C) — 재기가 묶기보다 먼저다.

detect_surya.group (방식 A) 은 Surya 줄 상자의 높이 · 겹침 · 틈으로 묶고 그 뒤에 잰다.
C 는 줄 상자마다 먼저 베이스라인을 재고, 같은 단 안에서 베이스라인 간격이 일정하게
이어지는 구간을 한 블록으로 삼는다. 간격이 달라지는 자리에서 끊는다.

사전등록 docs/group_preregister.json 수정 1 (ef0cf65). A · VLM 결과를 본 뒤 구현했다.
A 의 상수(Y_GAP · X_OVER · H_RATIO · MIN_AREA)는 바꾸지 않는다 — X_OVER 는 읽어 쓰고,
패턴을 못 세운 줄은 detect_surya.group 에 그대로 넘긴다 (A 폴백).

    TAU = 1   간격 run 안 최대 − 최소 (px). 정수 베이스라인마다 ±0.5px 양자화 → 간격 ±1px.
              check_layout «블록 내 행간 일정» 과 같은 수. 합성에서 정한 값이라 실물 스캔으로
              옮겨가지 않을 수 있다 — 사전등록은 브로크만에서 과분할을 예측한다.
"""
import math
from collections import Counter, defaultdict

import detect_surya as DS
from measure import region

TAU = 1
PAD_RULES = ('fixed', 'neighbor_half')   # 줄 상자를 잴 때 세로 pad. 묶기 비교 240장 세트는 'fixed'


def _overlap(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def neighbor_pad(lines, i):
    """P1 — 위 · 아래 pad = min(PAD, ⌊이웃 줄 상자까지 틈 / 2⌋), 틈 < 0 이면 0, 이웃 없으면 PAD.

    이웃 = 가로 범위가 (좌우 PAD 로 넓힌) 이 상자와 겹치고 세로 중심이 위(아래)인 다른 줄 상자.
    PAD 3 창에 이웃 줄 잉크가 들어와 줄이 늘던 것을 막는다. 사전등록 docs/measure_pad_preregister.json.
    """
    P = region.PAD
    x1, y1, x2, y2 = lines[i]
    cy = (y1 + y2) / 2
    near = [b for j, b in enumerate(lines) if j != i and min(x2 + P, b[2]) - max(x1 - P, b[0]) > 0]
    up = [b[3] for b in near if (b[1] + b[3]) / 2 < cy]
    dn = [b[1] for b in near if (b[1] + b[3]) / 2 > cy]
    pt = P if not up else max(0, min(P, math.floor((y1 - max(up)) / 2)))
    pb = P if not dn else max(0, min(P, math.floor((min(dn) - y2) / 2)))
    return pt, pb


def elements(gray, lines, pad_rule='fixed'):
    """줄 상자마다 region.measure. 잰 줄 하나가 요소 하나다."""
    if pad_rule not in PAD_RULES:
        raise ValueError(f'pad_rule 은 {PAD_RULES} 가운데 하나다: {pad_rule!r}')
    els, per_line = [], []
    for i, box in enumerate(lines):
        m = region.measure(gray, box, pad=(None if pad_rule == 'fixed' else neighbor_pad(lines, i)))
        n = int(m.get('n_lines', 0))
        per_line.append(n)
        for j in range(n):
            els.append(dict(line=i, b=int(m['baselines'][j]), xh=float(m['x_heights'][j]),
                            xs=int(m['x_starts'][j]), xe=int(m['x_ends'][j])))
    return els, per_line


def _xover(a, b):
    """가로 겹침 — detect_surya.group 과 같은 식. 좁은 쪽 폭의 X_OVER 를 넘어야 한다."""
    ov = min(a['xe'], b['xe']) - max(a['xs'], b['xs'])
    return ov if ov > DS.X_OVER * min(a['xe'] - a['xs'], b['xe'] - b['xs']) else None


def chains(els, tau=TAU):
    """세로 사슬. 앞 요소 = τ 넘게 위에 있고 가로로 겹치는 가장 가까운 요소."""
    order = sorted(range(len(els)), key=lambda k: (els[k]['b'], els[k]['xs']))
    pred = {}
    for k in order:
        e = els[k]; best = None
        for q in order:
            p = els[q]
            if e['b'] - p['b'] <= tau:
                break                     # 여기부터는 같은 행이거나 아래다
            ov = _xover(e, p)
            if ov is None:
                continue
            key = (p['b'], ov)
            if best is None or key > best[0]:
                best = (key, q, ov)
        if best is not None:
            pred[k] = (best[1], best[2])
    claim = {}
    for k, (q, ov) in pred.items():
        cand = (ov, -els[k]['b'], -els[k]['xs'])
        if q not in claim or cand > claim[q][0]:
            claim[q] = (cand, k)
    succ = {q: k for q, (_c, k) in claim.items()}
    linked = set(succ.values())
    out = []
    for k in order:
        if k in linked:
            continue
        ch = [k]
        while ch[-1] in succ:
            ch.append(succ[ch[-1]])
        out.append(ch)
    return out


def runs(gaps, tau=TAU):
    """간격을 앞에서부터 run 으로. run (i, j) 는 간격 i..j, 요소 i..j+1 을 덮는다."""
    out, i = [], 0
    while i < len(gaps):
        j = i + 1
        while j < len(gaps) and max(gaps[i:j + 1]) - min(gaps[i:j + 1]) <= tau:
            j += 1
        out.append((i, j - 1))
        i = j
    return out


def _owners(ch, els, tau, stats):
    """사슬의 자리마다 패턴 run 번호 (없으면 None)."""
    b = [els[k]['b'] for k in ch]
    rs = runs([b[i + 1] - b[i] for i in range(len(b) - 1)], tau)
    pat = [r for r, (s, e) in enumerate(rs) if e - s + 1 >= 2]
    own = []
    for pos in range(len(ch)):
        cov = [r for r in pat if rs[r][0] <= pos <= rs[r][1] + 1]
        if not cov:
            own.append(None)
        elif len(cov) == 1:
            own.append(cov[0])
        else:
            x = els[ch[pos]]['xh']
            same1 = abs(x - els[ch[pos - 1]]['xh']) <= tau
            same2 = abs(x - els[ch[pos + 1]]['xh']) <= tau
            if same1 and not same2:
                own.append(cov[0]); stats['공유 요소 · x높이로 앞 블록'] += 1
            elif same2 and not same1:
                own.append(cov[1]); stats['공유 요소 · x높이로 뒤 블록'] += 1
            else:
                own.append(None); stats['공유 요소 · 가르지 못함'] += 1
    return own


def group_gap(gray, lines, tau=TAU, pad_rule='fixed'):
    """Surya 줄 상자 → (줄마다 묶음 번호 또는 None, 진단). 번호는 패턴 블록이 먼저, 폴백 묶음이 뒤."""
    els, per_line = elements(gray, lines, pad_rule)
    stats = Counter()
    blk = {}
    for ci, ch in enumerate(chains(els, tau)):
        for k, r in zip(ch, _owners(ch, els, tau, stats)):
            blk[k] = None if r is None else (ci, r)
    by_line = defaultdict(Counter)
    for k, e in enumerate(els):
        by_line[e['line']][blk.get(k)] += 1
    asg, src, ids, leftover = [None] * len(lines), [None] * len(lines), {}, []
    for i in range(len(lines)):
        c = by_line.get(i)
        pats = [(n, key) for key, n in (c or {}).items() if key is not None]
        if pats:
            n, key = max(pats, key=lambda t: (t[0], -t[1][0], -t[1][1]))
            if n >= c.get(None, 0):
                asg[i] = ids.setdefault(key, len(ids)); src[i] = 'C'
                continue
        leftover.append(i)
    n_fb = 0
    if leftover:
        sub = [lines[i] for i in leftover]
        boxes = [b[:4] for b in DS.group(sub)]
        n_fb = len(boxes)
        for i, box in zip(leftover, sub):
            best, bv = None, 0.0
            for j, bb in enumerate(boxes):
                v = _overlap(box, bb)
                if v > bv:
                    best, bv = j, v
            if best is not None:
                asg[i] = len(ids) + best; src[i] = 'A'
    return asg, dict(per_line_measured=per_line, source=src, n_elements=len(els), pad_rule=pad_rule,
                     n_pattern_blocks=len(ids), n_fallback_blocks=n_fb, n_leftover_lines=len(leftover),
                     ties=dict(stats))
