"""검출기 상자 파일을 만든다 — 참조 · EasyOCR · Surya · Surya 줄 · VLM.

참조 데이터와 상자 파일 경로는 모두 인자로 받는다. 코드 안에 데이터 경로를
박지 않는다. 새 참조로 전부 다시 돌리는 명령은 eval/run_all.py 다.

    python detector_compare.py human       --csv 사람상자.csv --date 2026-08-21 --tool 도구.html --out boxes/human_v2.json
    python detector_compare.py easyocr     --ref boxes/human_v2.json --run 1 --out boxes/easyocr_run1.json
    python detector_compare.py surya       --ref boxes/human_v2.json --run 1 --out boxes/surya_run1.json
    python detector_compare.py surya_lines --ref boxes/human_v2.json --group boxes/surya_run1.json --out boxes/surya_lines.json
    python detector_compare.py vlm         --ref boxes/human_v2.json --raw vlm_pass1.raw.json --pass 1 \\
                                           --prompt docs/detector_vlm_prompt.md --model claude-opus-5 --out boxes/vlm_pass1.json
    python detector_compare.py posters     --ref boxes/human_v2.json

그림은 --image-root 로 준 폴더들에서 파일 이름으로 찾는다. 주지 않으면 코퍼스
폴더 설정(surface.ROOTS)을 쓴다. detect / ground / rules 의 파라미터는 건드리지
않는다. 여기서는 부르기만 한다.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import subprocess

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def _commit():
    return subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=HERE,
                          capture_output=True, text=True).stdout.strip() or None


def _sha(path):
    return hashlib.sha256(open(os.path.expanduser(path), 'rb').read()).hexdigest()


def _index(roots=None):
    """파일 이름 → 경로. roots 를 주지 않으면 코퍼스 폴더 설정."""
    if not roots:
        import surface
        roots = list(surface.ROOTS.values())
    idx = {}
    for root in roots:
        for d, _s, fs in os.walk(os.path.expanduser(root)):
            for f in fs:
                idx.setdefault(f, os.path.join(d, f))
    return idx


def ref_posters(ref, roots=None):
    """참조 상자 파일(typo-boxes/1) → [(코퍼스, 파일, 경로, W, H)]. 그림 크기가 파일과 같은지 확인한다."""
    idx = _index(roots)
    out = []
    for p in json.load(open(ref))['posters']:
        path = idx[p['file']]
        W, H = Image.open(path).size
        assert (W, H) == (p['img_w'], p['img_h']), p['file']
        out.append((p['corpus'], p['file'], path, W, H))
    return out


def _doc(source, items):
    return dict(schema='typo-boxes/1', source=source, coords='px',
                posters=[dict(corpus=c, file=f, img_w=W, img_h=H,
                              boxes=[dict(id=str(i + 1), box=[round(float(v), 1) for v in b])
                                     for i, b in enumerate(bs)])
                         for (c, f, W, H), bs in items])


def _save(path, doc):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(doc, open(path, 'w'), ensure_ascii=False, indent=1)
    print('→', path)


def human(csv_path, date, tool, out, roots=None):
    """사람 상자 CSV(typo-roles/1) → 상자 파일. img_w/img_h 가 실제 그림 크기와 같은지 확인한다."""
    rows = list(csv.DictReader(open(os.path.expanduser(csv_path), encoding='utf-8-sig')))
    idx = _index(roots)
    size, by = {}, {}
    for r in rows:
        f = r['poster']
        if f not in size:
            size[f] = Image.open(idx[f]).size
        W, H = size[f]
        assert (int(r['img_w']), int(r['img_h'])) == (W, H), f
        by.setdefault((r['corpus'], f, W, H), []).append(
            [float(r['x1']), float(r['y1']), float(r['x2']), float(r['y2'])])
    labelers = list(dict.fromkeys(r['labeler'] for r in rows))
    src = dict(kind='human', labeler=' · '.join(labelers), model=None,
               date=date, tool=tool,
               file=os.path.expanduser(csv_path), sha256=_sha(csv_path),
               note=('라벨러 한 명 — 정답이 아니라 참조' if len(labelers) == 1
                     else f'라벨러 {len(labelers)}명 — 정답이 아니라 참조'))
    _save(out, _doc(src, list(by.items())))


def easyocr_run(ref, run, out, roots=None):
    """옛 경로. baseline/scan.measure 가 내는 블록을 원본 좌표 축정렬 상자로."""
    import easyocr
    from baseline import scan
    reader = easyocr.Reader(['de'], gpu=scan.GPU, verbose=False)
    P = ref_posters(ref, roots)
    items, angles = [], {}
    for c, f, p, W, H in P:
        r = scan.measure(p, reader)
        bs = []
        if r.get('ok'):
            for b in r['blocks']:
                xs = [float(x) for x, _y in b['corners']]
                ys = [float(y) for _x, y in b['corners']]
                bs.append([min(xs), min(ys), max(xs), max(ys)])
            angles[f] = r['angle']
        items.append(((c, f, W, H), bs))
        print(f'  {len(items)}/{len(P)} {len(bs):3d}  {f[:40]}', flush=True)
    from importlib.metadata import version
    src = dict(kind='detector', name='easyocr+baseline/detect.run',
               version='easyocr ' + version('easyocr'), commit=_commit(),
               date=datetime.date.today().isoformat(), run=run,
               note='baseline/scan.measure 의 블록 corners 를 축정렬 상자로. 거르개(blockgate) 없음',
               angles=angles)
    _save(out, _doc(src, items))


def surya_run(ref, run, out, roots=None):
    """새 경로. Surya 줄 → detect_surya.group 블록. measure_corpus.measure_items 와 같은 부름."""
    from surya.detection import DetectionPredictor
    import detect_surya as DS
    det = DetectionPredictor()
    P = ref_posters(ref, roots)
    items = []
    for i in range(0, len(P), 8):
        chunk = P[i:i + 8]
        imgs = [Image.open(p).convert('RGB') for _c, _f, p, _W, _H in chunk]
        for (c, f, p, W, H), r in zip(chunk, det(imgs)):
            lines = [[float(v) for v in b.bbox] for b in r.bboxes]
            bs = [[x1 * W, y1 * H, x2 * W, y2 * H] for x1, y1, x2, y2 in DS.boxes_norm(lines, (W, H))]
            items.append(((c, f, W, H), bs))
            print(f'  {len(items)}/{len(P)} {len(bs):3d}  {f[:40]}', flush=True)
    from importlib.metadata import version
    src = dict(kind='detector', name='surya DetectionPredictor+detect_surya.group',
               version='surya-ocr ' + version('surya-ocr'), commit=_commit(),
               date=datetime.date.today().isoformat(), run=run)
    _save(out, _doc(src, items))


def surya_lines(ref, group, out, roots=None):
    """group() 이전의 Surya 줄. 같은 줄에 group() 을 걸어 group 상자 파일과 같은지 센다."""
    from surya.detection import DetectionPredictor
    import detect_surya as DS
    det = DetectionPredictor()
    g1 = {p['file']: [[round(float(v), 1) for v in b['box']] for b in p['boxes']]
          for p in json.load(open(group))['posters']}
    P = ref_posters(ref, roots)
    items, same = [], 0
    for i in range(0, len(P), 8):
        chunk = P[i:i + 8]
        imgs = [Image.open(p).convert('RGB') for _c, _f, p, _W, _H in chunk]
        for (c, f, p, W, H), r in zip(chunk, det(imgs)):
            lines = [[float(v) for v in b.bbox] for b in r.bboxes]
            items.append(((c, f, W, H), lines))
            g = [[round(float(v), 1) for v in (x1 * W, y1 * H, x2 * W, y2 * H)]
                 for x1, y1, x2, y2 in DS.boxes_norm(lines, (W, H))]
            same += (g == g1.get(f))
    from importlib.metadata import version
    src = dict(kind='detector', name='surya DetectionPredictor 줄 (group 이전, MIN_AREA 거르기 전)',
               version='surya-ocr ' + version('surya-ocr'), commit=_commit(),
               date=datetime.date.today().isoformat(),
               group_reproduces_run1=f'{same}/{len(P)}')
    print('group(줄) == group 상자 파일 :', f'{same}/{len(P)}')
    _save(out, _doc(src, items))


def vlm(ref, raw_path, k, prompt, model, out, roots=None):
    """서브에이전트가 쓴 JSON → 상자 파일. 모델명·날짜·지시문을 source 에 적는다."""
    raw = json.load(open(os.path.expanduser(raw_path)))
    P = ref_posters(ref, roots)
    got = {p['file']: p for p in raw['posters']}
    missing = sorted({f for _c, f, _p, _W, _H in P} - set(got))
    items = [((c, f, W, H), [b for b in (got.get(f) or {}).get('boxes', [])])
             for c, f, _p, W, H in P]
    wrapper = (f'먼저 이 지시문 파일 하나를 Read 도구로 읽고 그대로 따르라: {prompt} / '
               f'이 지시문 파일, 거기 적힌 이미지 {len(P)}장, 그리고 아래 출력 파일 말고는 어떤 파일도 열거나 '
               f'찾지 말라. 셸 명령도 쓰지 말라. / 출력 파일 경로: <scratchpad>/vlm_pass{k}.raw.json')
    src = dict(kind='vlm', model=model,
               how='Claude Code 서브에이전트 (대화 맥락 없이 새로 시작, 모델은 부모 세션 상속)',
               date=datetime.date.today().isoformat(), pass_=k,
               prompt=prompt, prompt_sha256=_sha(prompt),
               wrapper=wrapper,
               scale='원본 배율 (이미지 파일 그대로 Read)',
               files_opened=raw.get('files_opened'), notes=raw.get('notes'),
               missing_posters=missing, raw_sha256=_sha(raw_path))
    _save(out, _doc(src, items))


def main(argv=None):
    ap = argparse.ArgumentParser(description='검출기 상자 파일을 만든다. 경로는 모두 인자로 받는다.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--image-root', action='append',
                       help='그림을 찾을 폴더 (여러 번). 생략하면 surface.ROOTS')

    p = sub.add_parser('human', help='사람 상자 CSV → 상자 파일')
    p.add_argument('--csv', required=True)
    p.add_argument('--date', help='라벨한 날')
    p.add_argument('--tool', help='라벨 도구')
    p.add_argument('--out', required=True)
    common(p)
    for name in ('easyocr', 'surya'):
        p = sub.add_parser(name)
        p.add_argument('--ref', required=True)
        p.add_argument('--run', type=int, required=True)
        p.add_argument('--out', required=True)
        common(p)
    p = sub.add_parser('surya_lines')
    p.add_argument('--ref', required=True)
    p.add_argument('--group', required=True, help='같은 판의 Surya group 상자 파일 (재현 확인용)')
    p.add_argument('--out', required=True)
    common(p)
    p = sub.add_parser('vlm')
    p.add_argument('--ref', required=True)
    p.add_argument('--raw', required=True)
    p.add_argument('--pass', dest='k', type=int, required=True)
    p.add_argument('--prompt', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--out', required=True)
    common(p)
    p = sub.add_parser('posters', help='VLM 에 줄 판 목록 (좌표 없음)')
    p.add_argument('--ref', required=True)
    common(p)

    a = ap.parse_args(argv)
    if a.cmd == 'human':
        human(a.csv, a.date, a.tool, a.out, a.image_root)
    elif a.cmd == 'easyocr':
        easyocr_run(a.ref, a.run, a.out, a.image_root)
    elif a.cmd == 'surya':
        surya_run(a.ref, a.run, a.out, a.image_root)
    elif a.cmd == 'surya_lines':
        surya_lines(a.ref, a.group, a.out, a.image_root)
    elif a.cmd == 'vlm':
        vlm(a.ref, a.raw, a.k, a.prompt, a.model, a.out, a.image_root)
    elif a.cmd == 'posters':
        print(json.dumps([dict(corpus=c, file=f, path=p, img_w=W, img_h=H)
                          for c, f, p, W, H in ref_posters(a.ref, a.image_root)],
                         ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
