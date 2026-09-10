"""가로줄 — 원본 머리글 밑에 있었고 우리 어휘에 없던 것.

**검증 안 됨. 결과에 쓰지 말 것.** 다섯 판을 거쳤다 (docs/rules_line_test.json).
1965 머리글 줄과 1959 행 사이 줄은 잡지만, 도형 가장자리와 큰 표제 글자
가장자리를 함께 잡는다. 판마다 기준을 하나씩 지어냈다 — 손라벨 없이 더
고치면 같은 짓을 되풀이한다. 아래는 넷째 판(위아래 대비)이다.

«행» 단위로 찾는다. 첫 판은 이어진 잉크 덩어리(연결 성분)로 찾았다가 둘
다 틀렸다.

    1965 머리글 밑 줄   잉크로는 잡혔다(535px). 가장자리가 들쭉날쭉해 외접상자
                        채움이 0.578 — 내가 지어낸 «채움 0.6» 에 걸려 버려졌다.
    스캔 테두리          판 아래 끝의 긴 띠를 줄로 잡았다. 넷 중 넷이 그것이었다.

그래서 문턱을 판 스스로에게 대어 정한다. 지어낸 수는 없다.

    글자최장   글줄 띠 안에서 끊김 없이 이어진 잉크의 가장 긴 가로 길이.
               글자 사이엔 틈이 있으므로 이것이 글자가 만들 수 있는 최장이다.
    줄 행      그보다 길게 끊김 없이 이어진 잉크가 있는 행.
    줄         줄 행이 세로로 붙어 있고 가로 구간이 겹치면 한 줄. 두께(행 수)가
               그 판 x높이 중앙값보다 얇아야 한다 — 글자보다 얇은 것이 선이다.
    모서리     판의 네 끝 어디에든 닿는 줄은 뺀다. 스캔 테두리와 판 밖 번짐이다.
               (처음엔 왼·오른끝만 뺐다가 맨 아래 행 y797 을 줄로 잡았다.
               끝에서 끝까지 찍힌 «의도된» 줄도 함께 빠진다. 구별할 방법이 없다.)
    길이       그 판 글 덩어리 폭의 중앙값보다 짧으면 뺀다. 조판의 줄은 글을
               나누므로 글 덩어리만큼은 뻗는다. 새 그림 붓질(0.04~0.12w)과 산
               곡선(0.05~0.18w)이 이것으로 빠진다.
"""
import numpy as np
from PIL import Image


def _otsu(v):
    h, ed = np.histogram(v, bins=64)
    p = h / max(h.sum(), 1); mids = (ed[:-1] + ed[1:]) / 2
    w0 = np.cumsum(p); m0 = np.cumsum(p * mids); mt = m0[-1]
    ok = (w0 > 1e-6) & (w0 < 1 - 1e-6)
    if not ok.any():
        return float(v.max()) + 1
    bt = np.where(ok, (mt * w0 - m0) ** 2 / np.where(ok, w0 * (1 - w0), 1), 0)
    return float(mids[int(np.argmax(bt))])


def _runs(row):
    """한 행의 끊김 없는 잉크 구간들 [(시작, 끝)]."""
    out, i, n = [], 0, len(row)
    while i < n:
        if row[i]:
            j = i
            while j < n and row[j]:
                j += 1
            out.append((i, j)); i = j
        else:
            i += 1
    return out


def find(path, blocks):
    """판 한 장 → 가로줄들.

    잉크를 «바탕색에서 먼 화소 + 판 전체 오츠 한 번» 으로 잡으면 안 된다.
    1959 Stadttheater 는 짙은 빨강 바탕 [135,43,17] 에 흰 글자와 검은 줄이
    함께 있다. 오츠 문턱이 흰 글자(거리 ~300)에 맞춰 151 로 올라가 검은
    줄(거리 ~117)이 잉크에서 빠졌다. 문턱 하나가 잉크 한 종류만 가정했다.

    그래서 «위아래 대비» 로 본다. 줄은 제 위아래보다 다른 색이다. 화소마다
    k 행 위와 k 행 아래 색까지의 거리 중 «작은 쪽» 을 잰다 — 양쪽 모두와
    달라야 가는 띠다. k 는 그 판 x높이 중앙값(줄은 글자보다 얇다). 대비의
    로그 분포를 오츠로 가른다 — 바탕 잡음은 한 무리, 줄과 글자 획은 다른 무리.
    """
    rgb = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    H, W = rgb.shape[:2]
    xh = [base - top for b in blocks
          for base, top in zip(b.get('bases') or [], b.get('xtops') or [])
          if base is not None and top is not None]
    if not xh:
        return None
    thin = float(np.median(xh))
    k = max(2, int(round(thin)))

    c = np.zeros((H, W), np.float32)
    up = np.sqrt(((rgb[k:H - k] - rgb[0:H - 2 * k]) ** 2).sum(-1))
    dn = np.sqrt(((rgb[k:H - k] - rgb[2 * k:H]) ** 2).sum(-1))
    c[k:H - k] = np.minimum(up, dn)
    lc = np.log1p(c)
    ink = lc > _otsu(lc[k:H - k].ravel())

    text_run = 0
    for b in blocks:
        x1, x2 = max(0, int(b['x1'])), min(W, int(b['x2']))
        for base, top in zip(b.get('bases') or [], b.get('xtops') or []):
            if base is None or top is None:
                continue
            for y in range(max(0, int(top)), min(H, int(base) + 1)):
                for a, z in _runs(ink[y, x1:x2]):
                    text_run = max(text_run, z - a)

    segs = []
    for y in range(k, H - k):
        for a, z in _runs(ink[y]):
            if z - a > text_run and a > 0 and z < W:
                segs.append((y, a, z))
    lines = []
    for y, a, z in segs:
        for L in lines:
            if y - L['y2'] <= 1 and min(z, L['x2']) - max(a, L['x1']) > 0:
                L['y2'] = y; L['x1'] = min(L['x1'], a); L['x2'] = max(L['x2'], z)
                break
        else:
            lines.append(dict(y1=y, y2=y, x1=a, x2=z))
    bw = float(np.median([(min(W, b['x2']) - max(0, b['x1'])) for b in blocks]))
    out = [dict(L, 두께=L['y2'] - L['y1'] + 1, 폭몫=round((L['x2'] - L['x1']) / W, 3))
           for L in lines
           if (L['y2'] - L['y1'] + 1) < thin
           and L['y1'] > k and L['y2'] < H - k - 1
           and (L['x2'] - L['x1']) >= bw]
    return dict(선=out, 글자최장=text_run, xh=thin, 덩어리폭=bw)
