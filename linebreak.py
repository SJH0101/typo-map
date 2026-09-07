"""**줄 끊기** — 한 덩어리 안에서 줄이 어디서 끊기나.

그려 보고 나서 정한 물음이다. 잰 규칙만으로 브로크만 1965 를 다시 그렸더니
판의 34% 가 비었다. 폭이 먼저 걸려 활자를 못 키웠기 때문이다. 브로크만은
활자를 키우고 «줄을 다르게 끊어» 폭을 맞춘다. 그 규칙이 우리 어휘에 없었다.

무엇을 재나. 줄마다 «얼마나 찼나» 다.

    참함  그 줄의 잉크 폭 ÷ 그 덩어리에서 가장 긴 줄의 폭

기계가 끊으면(그리디: 들어가는 데까지 채우고 넘기면 다음 줄) 참함이 1.0
가까이 몰리고 마지막 줄만 짧다. 뜻으로 끊으면 골고루 흩어진다. 그래서
참함의 «분포» 가 끊는 방식을 드러낸다.

줄의 x 범위는 자료에 없다. 덩어리 상자와 베이스라인만 있다. 그래서 오늘
만든 획 마스크(measure/ink.strokes)로 직접 잰다 — 베이스라인 사이 띠에서
잉크의 좌우 끝을 본다. 상자를 통째로 쓰면 안 되는 이유는 오늘 배웠다.
"""
import numpy as np
from PIL import Image

from measure import ink

MIN_LINES = 3      # 두 줄로는 «분포» 를 말할 수 없다
MIN_INK = 3        # 이보다 적은 화소는 얼룩으로 본다


def line_widths(rgb, block):
    """덩어리 하나 → 줄마다 (왼끝, 오른끝). 못 재면 None."""
    bases = block.get('bases') or []
    if len(bases) < MIN_LINES:
        return None
    m, (x1, y1, x2, y2) = ink.strokes(rgb, (block['x1'], block['y1'],
                                            block['x2'], block['y2']))
    if m is None or not m.any():
        return None
    xh = block.get('xh') or (block['y2'] - block['y1']) / max(len(bases), 1) * 0.5
    out = []
    for b in bases:
        # 베이스라인 위로 x높이의 1.6배, 아래로 0.4배 — 어센더·디센더를 담는다
        top = int(round(b - xh * 1.6)) - y1
        bot = int(round(b + xh * 0.4)) - y1
        top = max(0, top); bot = min(m.shape[0], bot)
        if bot - top < 2:
            out.append(None); continue
        band = m[top:bot]
        cols = np.where(band.any(0))[0]
        out.append(None if len(cols) < MIN_INK
                   else (float(cols.min()), float(cols.max() + 1)))
    return out


def fills(path, blocks):
    """판 한 장 → 덩어리마다 줄 참함 목록."""
    rgb = np.asarray(Image.open(path).convert('RGB'))
    out = []
    for b in blocks:
        if b.get('n', 0) < MIN_LINES:
            continue
        w = line_widths(rgb, b)
        if not w:
            continue
        ws = [(r - l) for v in w if v for l, r in [v]]
        if len(ws) < MIN_LINES:
            continue
        M = max(ws)
        if M <= 0:
            continue
        out.append(dict(참함=[round(x / M, 4) for x in ws], 잰줄=len(ws),
                        전체줄=b.get('n'), 폭=round(M, 1)))
    return out


def greedy(words, measure, width):
    """그리디로 끊었을 때의 줄 폭. width(문자열)→폭 을 받는다."""
    out, cur = [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if width(t) <= measure or not cur:
            cur = t
        else:
            out.append(width(cur)); cur = w
    if cur:
        out.append(width(cur))
    return out
