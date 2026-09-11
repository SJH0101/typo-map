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


PIPELINE = 'surya+ground'


def provenance(source=None, n=None):
    """캐시가 «어느 경로로 · 언제 · 어느 코드로» 쟀는지.

    옛 경로(baseline/scan + detect)와 이 경로가 같은 ~/.typo-mcp/{이름}.json 에
    썼는데 옛 파일에는 표시가 없어서, 파일만 봐서는 어느 쪽 결과인지 몰랐다.
    9월 검증 분석이 전부 옛 경로 값 위에서 돌았다는 것을 순서도를 그리고서야
    알았다 (docs/y2_bug.json). 읽는 쪽은 docs_build.load_raw 로 이것을 확인한다.
    """
    import datetime
    import subprocess
    try:
        from importlib.metadata import version
        sv = version('surya-ocr')
    except Exception:
        sv = None
    try:
        commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                cwd=os.path.dirname(os.path.abspath(__file__)),
                                capture_output=True, text=True).stdout.strip() or None
    except Exception:
        commit = None
    return dict(pipeline=PIPELINE,
                detector=('surya-ocr ' + sv) if sv else 'surya-ocr',
                grouping='detect_surya.boxes_norm', measurer='measure/ground.py',
                skew='EasyOCR 상자 기울기 중앙값 · skewed = |각| >= %.0f°' % SKEW,
                commit=commit, date=datetime.date.today().isoformat(),
                source=source, n=n)


def items_of(paths):
    """경로 → [(열쇠, 경로)]. 열쇠는 «폴더__파일» 이다."""
    return [(os.path.basename(os.path.dirname(p)) + '__' + os.path.basename(p), p)
            for p in paths]


def measure_items(items, skew=True, batch=8, log=print):
    """[(열쇠, 경로)] → (raw, failed). 찾기는 Surya, 재기는 measure/ground.py.

    열쇠를 받는 까닭 — 다시 잴 때 옛 캐시의 열쇠를 그대로 써야 결과를 견줄 수
    있다. 로제 9장은 열쇠가 «..__폴더__파일» 모양이라 경로에서 다시 만들면
    달라진다.

    기울어진 판. 이 경로는 원본 좌표에서 재므로 angle 을 0 으로 두었는데, 읽는
    쪽 지표들은 |angle| >= 1 로 기울어진 판을 거른다. 그래서 skewed(14° 이상,
    labels/skewflag283 에서 정밀 100% · 재현 67%)인 판에만 그 각을 angle 에
    적는다. 옛 경로는 4° 스캔 기울기도 걸렀으므로 걸리는 판이 다를 수 있다.
    """
    from surya.detection import DetectionPredictor
    det = DetectionPredictor()
    reader = None
    if skew:
        import easyocr
        reader = easyocr.Reader(['de', 'en'], gpu=False, verbose=False)
    raw, failed = {}, []
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        imgs = [Image.open(p).convert('RGB') for _k, p in chunk]
        try:
            res = det(imgs)
        except Exception as e:
            failed += [(p, f'surya: {e}') for _k, p in chunk]
            continue
        for (k, p), r, im in zip(chunk, res, imgs):
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
            if e['skewed']:
                e['angle'] = float(a)
            raw[k] = e
        if log:
            log(f'  {min(i + batch, len(items))}/{len(items)}', flush=True)
    return raw, failed


def write(cache, raw, rules=None, source=None):
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(dict(raw=raw, rules=rules or {}, source=source, detector='surya',
                   provenance=provenance(source, len(raw))),
              open(cache, 'w'), ensure_ascii=False)


def run(folder, name, cache=None, skew=True, batch=8):
    paths = sorted(os.path.join(r, f)
                   for r, _d, fs in os.walk(folder) for f in fs if f.endswith(EXTS))
    if not paths:
        return dict(ok=False, error=f'이미지가 없다: {folder}')
    raw, failed = measure_items(items_of(paths), skew=skew, batch=batch)
    cache = cache or os.path.expanduser(f'~/.typo-mcp/{name}.json')
    write(cache, raw, source=folder)
    n_skew = sum(1 for v in raw.values() if v.get('skewed'))
    print(f'\n{name} — 잰 판 {len(raw)}/{len(paths)} · 기울어짐 {n_skew} · 실패 {len(failed)}')
    for p, why in failed[:5]:
        print('  실패', os.path.basename(p)[:36], why)
    print(f'  → {cache}')
    return dict(ok=True, n=len(raw), cache=cache, failed=failed)


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'corpus')
