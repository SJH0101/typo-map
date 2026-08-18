"""상자별 회전각을 구한다.

  1  뾰족함 탐색   상자 안을 돌려가며 가로 잉크 프로파일의 변동계수가 최대인 각
  2  글자 확인     그 각과 ±90, +180 으로 다시 읽어 신뢰도가 가장 높은 각을 채택

뾰족함만으로는 90° 어긋난 답(글자 사이 틈을 줄로 오인)을 못 가른다.
글자가 제대로 읽히는지는 방향을 직접 확인해 주므로 그 모호함이 사라진다.
"""
import numpy as np
from PIL import Image

STEP = 0.5
RANGE = 90          # 뾰족함 탐색 범위 (±)
MIN_W = 40          # 이보다 좁은 상자는 각도 추정을 신뢰하지 않음


def crop(gray, quad, pad=6):
    b = np.array(quad, dtype=float)
    x0, x1 = int(b[:, 0].min()), int(b[:, 0].max())
    y0, y1 = int(b[:, 1].min()), int(b[:, 1].max())
    return gray[max(0, y0-pad):y1+pad, max(0, x0-pad):x1+pad]


def rotate(sub, ang):
    return Image.fromarray(sub.astype(np.uint8)).rotate(
        ang, resample=Image.BICUBIC, expand=True, fillcolor=int(np.median(sub)))


def sharpness(sub, ang, th):
    a = np.asarray(rotate(sub, ang)).astype(float)
    r = (a < th).sum(axis=1).astype(float)
    return 0.0 if r.sum() == 0 else float(r.std() / (r.mean() + 1e-9))


def coarse_angle(sub):
    """뾰족함이 최대인 각. 90° 모호성이 남아 있다."""
    if sub.size == 0 or min(sub.shape) < 8:
        return None
    th = np.median(sub) * 0.72
    angs = np.arange(-RANGE, RANGE + STEP, STEP)
    return float(angs[int(np.argmax([sharpness(sub, a, th) for a in angs]))])


def verify(sub, cand, reader):
    """후보 각들로 읽어 신뢰도×글자수가 가장 큰 각을 고른다."""
    best = (None, -1.0, '')
    for a in cand:
        r = reader.readtext(np.array(rotate(sub, a).convert('RGB')),
                            detail=1, paragraph=False)
        if not r:
            continue
        conf, txt = max(((x[2], x[1]) for x in r), key=lambda t: t[0] * len(t[1]))
        score = conf * len(txt)
        if score > best[1]:
            best = (a, score, txt)
    return best


def box_angle(gray, quad, reader):
    b = np.array(quad, dtype=float)
    if np.hypot(*(b[1] - b[0])) < MIN_W:
        return None
    sub = crop(gray, quad)
    c = coarse_angle(sub)
    if c is None:
        return None
    cand = [c, c + 90, c - 90, c + 180]
    cand = [a - 360 * round(a / 360) for a in cand]
    a, score, txt = verify(sub, cand, reader)
    if a is None:
        return None
    return dict(angle=a, coarse=c, score=round(score, 2), text=txt)


def poster_angle(gray, quads, reader):
    """포스터 대표 각. 상자 폭으로 가중한 중앙값."""
    out = []
    for q in quads:
        r = box_angle(gray, q, reader)
        if r:
            b = np.array(q, dtype=float)
            r['w'] = float(np.hypot(*(b[1] - b[0])))
            out.append(r)
    if not out:
        return None, []
    A = np.array([r['angle'] for r in out])
    med = float(np.median(A))
    A = np.where(A - med > 90, A - 180, np.where(med - A > 90, A + 180, A))
    for r, a in zip(out, A):
        r['angle'] = float(a)
    return float(np.median(A)), out
