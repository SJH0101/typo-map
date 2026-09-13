"""브로크만 포스터 글자 인식 (EasyOCR) — 대문자 판정의 교차 확인용. 탐색용 · 논문 수치 아님.

    .venv/bin/python docs/labeling/ocr_run.py ~/.typo-mcp/brockmann.json \
        "~/Documents/연구2/브로크만 정리/corpus" docs/labeling/ocr_easyocr.json

캐시의 열쇠(«폴더__파일»)마다 코퍼스 폴더에서 이미지를 찾아 원본 해상도로 읽는다.
2026-09-14 실행분이 ocr_easyocr.json 이다 (easyocr 1.7.2, de+en, mag_ratio 2, CPU 약 9분).
"""
import argparse
import glob
import json
import os

import numpy as np
from PIL import Image


def paths_of(cache, root):
    raw = json.load(open(os.path.expanduser(cache)))['raw']
    found = {}
    for p in glob.glob(os.path.join(os.path.expanduser(root), '**', '*.jpg'), recursive=True):
        found.setdefault(os.path.basename(os.path.dirname(p)) + '__' + os.path.basename(p), p)
    miss = [k for k in raw if k not in found]
    if miss:
        raise SystemExit(f'이미지를 못 찾은 열쇠 {len(miss)}개: {miss[:3]}')
    return {k: found[k] for k in sorted(raw)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('root')
    ap.add_argument('out')
    a = ap.parse_args()
    import easyocr
    r = easyocr.Reader(['de', 'en'], gpu=False, verbose=False)
    out = {}
    for k, p in paths_of(a.cache, a.root).items():
        im = np.array(Image.open(p).convert('RGB'))
        res = r.readtext(im, detail=1, paragraph=False, mag_ratio=2.0)
        out[k] = [dict(t=tx, c=round(float(cf), 3), box=[[float(x), float(y)] for x, y in q])
                  for q, tx, cf in res]
    json.dump(dict(note='탐색용 · 논문 수치 아님. easyocr 1.7.2 de+en, mag_ratio 2, 원본 해상도', out=out),
              open(a.out, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
