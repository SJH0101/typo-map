"""사람 확인용 표본 SoM 이미지 — 사전등록 docs/clean_preregister.json 수정 1 (4a763c8).

    python eval/clean_som_samples.py --check docs/clean_check.json --review-dir ~/.typo-mcp/clean/review

docs/clean_check.json 이 고른 **표본 판에만** Surya 검출을 돌리고, 단 단위 순서(order_columns)로 번호를 매겨
R2 딱지(eval/group_score.draw_som)로 그린다. 평가 세트 채점 · VLM 은 하지 않는다. 딱지 겹침 수를 적는다.
"""
import argparse
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import group_score as GS   # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', required=True); ap.add_argument('--review-dir', required=True)
    ap.add_argument('--only-new', action='store_true', help='«추가 생성 판» 표본에만 Surya 를 돌린다 (수정 2 사람 확인 2차)')
    a = ap.parse_args(argv)
    C = json.load(open(a.check))
    R = os.path.expanduser(a.review_dir); os.makedirs(R, exist_ok=True)
    from surya.detection import DetectionPredictor
    det = DetectionPredictor()
    samples = [x for x in C['표본'] if (not a.only_new) or x['고른_까닭'].startswith('추가 생성 판')]
    imgs = [Image.open(x['이미지']).convert('RGB') for x in samples]
    res = det(imgs)
    rows = []
    for x, r, im in zip(samples, res, imgs):
        ls = sorted(([float(v) for v in b.bbox] for b in r.bboxes), key=lambda b: (b[1], b[0]))
        ls, nb = GS.order_columns(ls)
        op = os.path.join(R, f"{x['seed']}_som.png")
        rects = GS.draw_som(im, ls, op)
        bad, cover = GS.label_overlaps(rects, ls)
        rows.append(dict(seed=x['seed'], 층=x['층'], Surya_줄=len(ls), 찾은_단=nb, 정답_단=int(x['층'][0]),
                         못_읽는_딱지=bad, 글자_가린_딱지=cover, 이미지=op))
        print(rows[-1])
    name = 'som_samples_new.json' if a.only_new else 'som_samples.json'
    json.dump(dict(무엇='사람 확인용 표본 SoM — 표본 판에만 Surya 검출, 채점 없음', 표본=rows),
              open(os.path.join(R, name), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
