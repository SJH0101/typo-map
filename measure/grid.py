"""베이스라인을 격자에 맞춰 본다.

측정값은 건드리지 않는다. 격자는 별도 열로만 남긴다 — 맞춰 놓고 그것을
측정값이라 부르면 «격자를 쓴다» 는 결론이 측정이 아니라 가정이 된다.
"""
import numpy as np


def fit_grid(bases, ink, s0, s1):
    """블록의 베이스라인들을 등간격 격자에 맞춘다.
       행간은 자기상관으로 구하고, 위상은 잔차 제곱합 최소로 정한다.
       줄 하나가 글자 모양 때문에 1px 흔들려도 나머지가 위치를 잡아준다."""
    if len(bases) < 3:
        return bases, None, 0.0
    # 창을 잉크 배열 안으로 가둔다. apply_grid 는 첫 베이스라인에서 20px 위를
    # 창의 시작으로 잡는데, 블록이 단 상단에 가까우면 음수가 된다. numpy 는
    # 음수 시작을 뒤에서부터로 해석하므로 ink[-3:59] 가 빈 배열이 되어
    # np.correlate 가 죽었다. 코어 108장 중 2장이 이 때문에 빠져 있었다.
    s0 = max(0, int(s0))
    s1 = min(len(ink), int(s1))
    if s1 - s0 < 3:
        return bases, None, 0.0
    r = ink[s0:s1] - ink[s0:s1].mean()
    ac = np.correlate(r, r, 'full')[len(r)-1:]
    if ac[0] <= 0: return bases, None, 0.0
    ac = ac / ac[0]
    lo, hi = 5, min(len(ac) - 1, 60)
    if hi <= lo: return bases, None, 0.0
    seg = ac[lo:hi]
    peaks = [lo + i for i in range(1, len(seg) - 1)
             if seg[i] > seg[i-1] and seg[i] >= seg[i+1] and seg[i] > 0.25]
    if not peaks: return bases, None, 0.0
    lead = min(peaks)                  # 배수 봉우리를 피해 기본 주기를 고른다
    med = np.median(np.diff(bases)) if len(bases) > 1 else lead
    if abs(lead - med) > 2:            # 실측과 크게 다르면 신뢰하지 않음
        return bases, None, 0.0
    k = np.round((np.array(bases) - bases[0]) / lead)
    phase = float(np.mean(np.array(bases) - k * lead))
    fitted = [int(round(phase + i * lead)) for i in k]
    resid = float(np.mean(np.abs(np.array(fitted) - np.array(bases))))
    return fitted, lead, resid

def apply_grid(ls, ink):
    if len(ls) < 3: return ls, None, 0.0
    bases = [l['base'] for l in ls]
    fitted, lead, resid = fit_grid(bases, ink, ls[0]['base'] - 20, ls[-1]['base'] + 8)
    # 측정값은 그대로 둔다. 격자는 별도 열로만 남긴다.
    for l, b0, b1 in zip(ls, bases, fitted):
        l['base_grid'] = b1
        l['shift'] = b1 - b0
    return ls, lead, resid
