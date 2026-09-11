"""검출기 셋(EasyOCR · Surya · VLM)을 사람 상자 v2 와 견준다.

사람 상자는 라벨러가 한 명이라 정답이 아니라 «참조» 다. 결과는 정확도가
아니라 «참조 상자와의 일치도» 로 적는다. 정의와 선택 기준은 돌리기 전에
docs/detector_preregister.json 에 박아 두었다.

    python detector_compare.py human               # CSV v2 → boxes/human_v2.json
    python detector_compare.py posters             # VLM 에 줄 판 목록 (좌표 없음)
    python detector_compare.py easyocr 1           # boxes/easyocr_run1.json
    python detector_compare.py surya 1             # boxes/surya_run1.json
    python detector_compare.py score               # docs/detector_compare.json

detect / ground / rules 의 파라미터는 건드리지 않는다. 여기서는 부르기만 한다.
"""
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BOXES = os.path.join(HERE, 'boxes')
HUMAN_CSV = os.path.expanduser('~/Downloads/boxes_송준혁-2.csv')
CORPUS = {'브로크만': 'brockmann', '호프만': 'corpus', '로제': 'rose', '루더': 'ruder'}


def _commit():
    return subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=HERE,
                          capture_output=True, text=True).stdout.strip() or None


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def _index():
    """파일 이름 → 경로. 네 코퍼스 폴더를 훑는다."""
    import surface
    idx = {}
    for root in surface.ROOTS.values():
        for d, _s, fs in os.walk(os.path.expanduser(root)):
            for f in fs:
                idx.setdefault(f, os.path.join(d, f))
    return idx


def _rows():
    return list(csv.DictReader(open(HUMAN_CSV, encoding='utf-8-sig')))


def posters():
    """참조가 덮는 26장. [(코퍼스, 파일, 경로, W, H)] — 좌표는 싣지 않는다."""
    idx, seen, out = _index(), set(), []
    for r in _rows():
        k = (r['corpus'], r['poster'])
        if k in seen:
            continue
        seen.add(k)
        p = idx[r['poster']]
        W, H = Image.open(p).size
        out.append((r['corpus'], r['poster'], p, W, H))
    return out


def _doc(source, items):
    return dict(schema='typo-boxes/1', source=source, coords='px',
                posters=[dict(corpus=c, file=f, img_w=W, img_h=H,
                              boxes=[dict(id=str(i + 1), box=[round(float(v), 1) for v in b])
                                     for i, b in enumerate(bs)])
                         for (c, f, W, H), bs in items])


def _save(name, doc):
    os.makedirs(BOXES, exist_ok=True)
    path = os.path.join(BOXES, name + '.json')
    json.dump(doc, open(path, 'w'), ensure_ascii=False, indent=1)
    print('→', path)


def human():
    """CSV v2 → 상자 파일. 좌표는 원본 픽셀이고 img_w/img_h 가 실제 크기와 같은지 확인한다."""
    size = {f: (W, H) for _c, f, _p, W, H in posters()}
    by = {}
    for r in _rows():
        W, H = size[r['poster']]
        assert (int(r['img_w']), int(r['img_h'])) == (W, H), r['poster']
        by.setdefault((r['corpus'], r['poster'], W, H), []).append(
            [float(r['x1']), float(r['y1']), float(r['x2']), float(r['y2'])])
    src = dict(kind='human', labeler='송준혁', model=None,
               date='2026-08-21', tool='~/Documents/poster/labeler/타이포덩어리-상자긋기.html',
               file=HUMAN_CSV, sha256=_sha(HUMAN_CSV),
               note='라벨러 한 명 — 정답이 아니라 참조')
    _save('human_v2', _doc(src, list(by.items())))


def easyocr_run(run):
    """옛 경로. baseline/scan.measure 가 내는 블록을 원본 좌표 축정렬 상자로."""
    import easyocr
    from baseline import scan
    reader = easyocr.Reader(['de'], gpu=scan.GPU, verbose=False)
    items, angles = [], {}
    for c, f, p, W, H in posters():
        r = scan.measure(p, reader)
        bs = []
        if r.get('ok'):
            for b in r['blocks']:
                xs = [float(x) for x, _y in b['corners']]
                ys = [float(y) for _x, y in b['corners']]
                bs.append([min(xs), min(ys), max(xs), max(ys)])
            angles[f] = r['angle']
        items.append(((c, f, W, H), bs))
        print(f'  {len(items)}/26 {len(bs):3d}  {f[:40]}', flush=True)
    from importlib.metadata import version
    src = dict(kind='detector', name='easyocr+baseline/detect.run',
               version='easyocr ' + version('easyocr'), commit=_commit(),
               date=datetime.date.today().isoformat(), run=run,
               note='baseline/scan.measure 의 블록 corners 를 축정렬 상자로. 거르개(blockgate) 없음',
               angles=angles)
    _save(f'easyocr_run{run}', _doc(src, items))


def surya_run(run):
    """새 경로. Surya 줄 → detect_surya.group 블록. measure_corpus.measure_items 와 같은 부름."""
    from surya.detection import DetectionPredictor
    import detect_surya as DS
    det = DetectionPredictor()
    P = posters()
    items = []
    for i in range(0, len(P), 8):
        chunk = P[i:i + 8]
        imgs = [Image.open(p).convert('RGB') for _c, _f, p, _W, _H in chunk]
        for (c, f, p, W, H), r in zip(chunk, det(imgs)):
            lines = [[float(v) for v in b.bbox] for b in r.bboxes]
            bs = [[x1 * W, y1 * H, x2 * W, y2 * H] for x1, y1, x2, y2 in DS.boxes_norm(lines, (W, H))]
            items.append(((c, f, W, H), bs))
            print(f'  {len(items)}/26 {len(bs):3d}  {f[:40]}', flush=True)
    from importlib.metadata import version
    src = dict(kind='detector', name='surya DetectionPredictor+detect_surya.group',
               version='surya-ocr ' + version('surya-ocr'), commit=_commit(),
               date=datetime.date.today().isoformat(), run=run)
    _save(f'surya_run{run}', _doc(src, items))


def surya_lines():
    """group() 이전의 Surya 줄. 같은 줄에 group() 을 걸어 surya_run1 과 같은지 센다."""
    from surya.detection import DetectionPredictor
    import detect_surya as DS
    det = DetectionPredictor()
    run1 = json.load(open(os.path.join(BOXES, 'surya_run1.json')))
    r1 = {p['file']: [[round(float(v), 1) for v in b['box']] for b in p['boxes']]
          for p in run1['posters']}
    P = posters()
    items, same = [], 0
    for i in range(0, len(P), 8):
        chunk = P[i:i + 8]
        imgs = [Image.open(p).convert('RGB') for _c, _f, p, _W, _H in chunk]
        for (c, f, p, W, H), r in zip(chunk, det(imgs)):
            lines = [[float(v) for v in b.bbox] for b in r.bboxes]
            items.append(((c, f, W, H), lines))
            g = [[round(float(v), 1) for v in (x1 * W, y1 * H, x2 * W, y2 * H)]
                 for x1, y1, x2, y2 in DS.boxes_norm(lines, (W, H))]
            same += (g == r1[f])
    from importlib.metadata import version
    src = dict(kind='detector', name='surya DetectionPredictor 줄 (group 이전, MIN_AREA 거르기 전)',
               version='surya-ocr ' + version('surya-ocr'), commit=_commit(),
               date=datetime.date.today().isoformat(),
               group_reproduces_run1=f'{same}/{len(P)}')
    print('group(줄) == surya_run1 :', f'{same}/{len(P)}')
    _save('surya_lines', _doc(src, items))


SCRATCH_WRAPPER = ('먼저 이 지시문 파일 하나를 Read 도구로 읽고 그대로 따르라: docs/detector_vlm_prompt.md / '
                   '이 지시문 파일, 거기 적힌 이미지 26장, 그리고 아래 출력 파일 말고는 어떤 파일도 열거나 '
                   '찾지 말라. 셸 명령도 쓰지 말라. / 출력 파일 경로: <scratchpad>/vlm_pass{K}.raw.json')


def vlm(k, raw_path, files_opened_ok=None):
    """서브에이전트가 쓴 JSON → 상자 파일. 모델명·날짜·지시문을 source 에 적는다."""
    raw = json.load(open(raw_path))
    want = {f: (W, H) for _c, f, _p, W, H in posters()}
    corpus = {f: c for c, f, _p, _W, _H in posters()}
    got = {p['file']: p for p in raw['posters']}
    missing = sorted(set(want) - set(got))
    items = [((corpus[f], f, W, H), [b for b in (got.get(f) or {}).get('boxes', [])])
             for f, (W, H) in want.items()]
    prompt = os.path.join(HERE, 'docs', 'detector_vlm_prompt.md')
    src = dict(kind='vlm', model='claude-opus-5',
               how='Claude Code 서브에이전트 (대화 맥락 없이 새로 시작, 모델은 부모 세션 상속)',
               date=datetime.date.today().isoformat(), pass_=k,
               prompt='docs/detector_vlm_prompt.md', prompt_sha256=_sha(prompt),
               wrapper=SCRATCH_WRAPPER.replace('{K}', str(k)),
               scale='원본 배율 (이미지 파일 그대로 Read)',
               files_opened=raw.get('files_opened'), notes=raw.get('notes'),
               missing_posters=missing, raw_sha256=_sha(raw_path))
    _save(f'vlm_pass{k}', _doc(src, items))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'vlm':
        vlm(int(sys.argv[2]), sys.argv[3])
    if cmd == 'human':
        human()
    elif cmd == 'posters':
        print(json.dumps([dict(corpus=c, file=f, path=p, img_w=W, img_h=H)
                          for c, f, p, W, H in posters()], ensure_ascii=False, indent=1))
    elif cmd == 'easyocr':
        easyocr_run(int(sys.argv[2]))
    elif cmd == 'surya':
        surya_run(int(sys.argv[2]))
    elif cmd == 'surya_lines':
        surya_lines()
    elif cmd == 'score':
        import detector_score
        detector_score.main()
