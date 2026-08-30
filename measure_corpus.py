"""폴더 하나 → 잰 코퍼스. 찾기는 Surya, 재기는 measure/ground.py.

    python measure_corpus.py ~/…/로이핀/판 로이핀

옛 경로(baseline/scan.py + detect.py)는 한 함수가 찾기와 재기를 같이 했고,
영역 전체를 잉크 문턱으로 훑어 사진·도형 위에도 «줄» 을 만들었다. 사람이
라벨한 200개로 재보니 상자의 37% 가 글자가 아니었다.

여기서는 갈라 놓는다.

    찾기   Surya DetectionPredictor 가 «줄» 을 준다
    묶기   detect_surya.group() 이 크기계층·가로겹침·세로간격으로 «블록» 으로
    재기   measure/ground.py 가 그 상자 «안» 만 본다

기울기는 EasyOCR 상자의 각으로 따로 재서 적어 둔다. 14° 넘으면 skewed=True
로 표시만 하고 버리지 않는다 — 지표 쪽에서 쓸지 말지 정한다.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

import detect_surya as DS
from measure import ground as G

SKEW = 14.0
EXTS = ('.jpg', '.jpeg', '.png', '.JPG', '.PNG')


def _angle(reader, im):
    """EasyOCR 상자 윗변의 기울기 중앙값. 넓은 상자 12개만 본다."""
    try:
        res = reader.readtext(np.array(im), detail=1, paragraph=False)
    except Exception:
        return None
    A, W = [], []
    for q, _t, cf in res:
        if cf < 0.2:
            continue
        q = np.array(q, float)
        dx, dy = q[1] - q[0]
        w = float(np.hypot(dx, dy))
        if w < 12:
            continue
        A.append(float(np.degrees(np.arctan2(dy, dx)))); W.append(w)
    if not A:
        return None
    A = np.array(A); W = np.array(W)
    A = np.where(A > 90, A - 180, np.where(A < -90, A + 180, A))
    return round(float(np.median(A[np.argsort(-W)[:12]])), 2)


def run(folder, name, cache=None, skew=True, batch=8):
    from surya.detection import DetectionPredictor
    paths = sorted(os.path.join(r, f)
                   for r, _d, fs in os.walk(folder) for f in fs if f.endswith(EXTS))
    if not paths:
        return dict(ok=False, error=f'이미지가 없다: {folder}')
    det = DetectionPredictor()
    reader = None
    if skew:
        import easyocr
        reader = easyocr.Reader(['de', 'en'], gpu=False, verbose=False)

    raw, failed = {}, []
    for i in range(0, len(paths), batch):
        chunk = paths[i:i + batch]
        imgs = [Image.open(p).convert('RGB') for p in chunk]
        try:
            res = det(imgs)
        except Exception as e:
            failed += [(p, f'surya: {e}') for p in chunk]
            continue
        for p, r, im in zip(chunk, res, imgs):
            W, H = im.size
            lines = [[float(v) for v in b.bbox] for b in r.bboxes]
            bx = DS.boxes_norm(lines, (W, H))
            if not bx:
                failed.append((p, 'surya 가 상자를 못 냈다')); continue
            try:
                e, _ = G.entry(p, bx, coords='norm')
            except Exception as ex:
                failed.append((p, f'{type(ex).__name__}: {ex}')); continue
            e['n_columns'] = DS.columns(lines, W)
            e['n_surya_lines'] = len(lines)
            a = _angle(reader, im) if reader else None
            e['skew'] = a
            e['skewed'] = bool(a is not None and abs(a) >= SKEW)
            raw[os.path.basename(os.path.dirname(p)) + '__' + os.path.basename(p)] = e
        print(f'  {min(i+batch, len(paths))}/{len(paths)}', flush=True)

    cache = cache or os.path.expanduser(f'~/.typo-mcp/{name}.json')
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(dict(raw=raw, rules={}, source=folder, detector='surya'),
              open(cache, 'w'), ensure_ascii=False)
    n_skew = sum(1 for v in raw.values() if v.get('skewed'))
    print(f'\n{name} — 잰 판 {len(raw)}/{len(paths)} · 기울어짐 {n_skew} · 실패 {len(failed)}')
    for p, why in failed[:5]:
        print('  실패', os.path.basename(p)[:36], why)
    print(f'  → {cache}')
    return dict(ok=True, n=len(raw), cache=cache, failed=failed)


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'corpus')
