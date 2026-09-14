"""깨끗한 세트 VLM 묶음 나누기 — 사전등록 docs/clean_preregister.json (수정 2 · 3: 묶음 수는 딱지 수를 보고 정한다).

    python eval/clean_vlm_batches.py --manifest docs/clean_manifest.json --som-dir ~/.typo-mcp/clean/som \\
        --raw ~/.typo-mcp/clean/vlm_raw --max-posters 10 --max-labels 700

manifest 순서대로 판을 채우다가, 판 수가 max-posters 에 이르거나 딱지를 더하면 max-labels 를 넘는 자리에서 끊는다
(한 판이 max-labels 보다 크면 그 판 혼자 한 묶음). 두 패스가 같은 묶음을 쓴다. 묶음마다 목록 파일
(file · path · 상자 수) 을 raw/lists/b{nn}.md 로, 전체를 raw/batches.json 으로 쓴다. 판정 · 모델 · 지시문과는 무관하다.
"""
import argparse
import json
import os


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True); ap.add_argument('--som-dir', required=True)
    ap.add_argument('--raw', required=True)
    ap.add_argument('--max-posters', type=int, default=10); ap.add_argument('--max-labels', type=int, default=700)
    a = ap.parse_args(argv)
    S = os.path.expanduser(a.som_dir); R = os.path.expanduser(a.raw)
    os.makedirs(os.path.join(R, 'lists'), exist_ok=True)
    som = {r['file'].split('_')[0]: r for r in json.load(open(os.path.join(S, 'list.json')))}
    M = json.load(open(a.manifest))
    batches, cur = [], []
    for it in M['items']:
        r = som[str(it['seed'])]
        if cur and (len(cur) >= a.max_posters or sum(x['n_lines'] for x in cur) + r['n_lines'] > a.max_labels):
            batches.append(cur); cur = []
        cur.append(r)
    if cur:
        batches.append(cur)
    out = []
    for i, b in enumerate(batches, 1):
        name = f'b{i:02d}'
        lp = os.path.join(R, 'lists', f'{name}.md')
        with open(lp, 'w') as f:
            f.write(f'## 이미지 {len(b)}장\n')
            for r in b:
                f.write(f'- file: {r["file"]}\n  path: {r["path"]}\n  상자 수: {r["n_lines"]}\n')
        out.append(dict(batch=name, list=lp, n=len(b), labels=sum(r['n_lines'] for r in b), files=[r['file'] for r in b]))
    json.dump(dict(max_posters=a.max_posters, max_labels=a.max_labels, manifest=a.manifest, batches=out),
              open(os.path.join(R, 'batches.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(out)}묶음 · 판 {sum(x["n"] for x in out)} · 딱지 {sum(x["labels"] for x in out)} · '
          f'묶음당 판 {min(x["n"] for x in out)}~{max(x["n"] for x in out)} · 딱지 {min(x["labels"] for x in out)}~{max(x["labels"] for x in out)}')


if __name__ == '__main__':
    main()
