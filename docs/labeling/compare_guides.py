"""두 라벨러의 선 긋기 파일을 견준다 — 연습 판에서 «같은 행을 고르는가» 를 확인하는 데 먼저 쓴다.

    .venv/bin/python docs/labeling/compare_guides.py guides_송준혁_….json guides_공동연구자_….json \
        --set practice --out 비교.json

두 파일 모두 선 긋기 도구(docs/labeling/tool)가 저장한 것이어야 한다 (schema typo-guides/1).
한쪽을 정답이라 부르지 않는다. 차이는 «B − A» (행)로 적는다.

    블록 짝     같은 포스터에서 IoU 가 가장 큰 쌍부터 1:1, IoU ≥ BLOCK_IOU
    줄 짝       짝지은 블록 안에서 베이스라인 차가 가장 작은 쌍부터 1:1, |차| ≤ LINE_TOL 행
    칸 비교     줄마다 네 선: 둘 다 그음 → 행 차 / 한쪽만 그음 → «선 대 표시» / 둘 다 표시 → 같은 표시인가

연습 판 결과는 규칙 맞추기용이다 — 논문 수치가 아니다. 본 목록의 2인 일치도를 논문에 쓰려면 사전등록부터 쓴다.
"""
import argparse
import collections
import json

BLOCK_IOU = 0.5
LINE_TOL = 3
TYPES = ['base', 'cap', 'asc', 'xh']


def iou(a, b):
    ix = max(0, min(a['x2'], b['x2']) - max(a['x1'], b['x1']))
    iy = max(0, min(a['y2'], b['y2']) - max(a['y1'], b['y1']))
    inter = ix * iy
    ua = (a['x2'] - a['x1']) * (a['y2'] - a['y1']) + (b['x2'] - b['x1']) * (b['y2'] - b['y1']) - inter
    return inter / ua if ua > 0 else 0.0


def greedy(pairs):
    """(점수, i, j) 를 좋은 순서로 받아 1:1 짝."""
    used_i, used_j, out = set(), set(), []
    for s, i, j in pairs:
        if i in used_i or j in used_j:
            continue
        used_i.add(i); used_j.add(j); out.append((i, j, s))
    return out


def load(path, set_name):
    o = json.load(open(path))
    if o.get('schema') != 'typo-guides/1':
        raise SystemExit(f'선 긋기 도구 파일이 아니다: {path}')
    ps = {(p['set'], p['order']): p for p in o['posters'] if p['set'] == set_name}
    return o, ps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--set', default='practice', choices=['practice', 'main'])
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    oa, pa = load(a.a, a.set)
    ob, pb = load(a.b, a.set)
    if oa['data_fp'] != ob['data_fp']:
        raise SystemExit('두 파일의 포스터 목록 지문이 다르다')

    diffs = {t: collections.Counter() for t in TYPES}
    kinds = {t: collections.Counter() for t in TYPES}
    posters = []
    tot = collections.Counter()
    for key in sorted(set(pa) & set(pb)):
        A, B = pa[key], pb[key]
        if A['sha256'] != B['sha256']:
            raise SystemExit(f'같은 순서의 포스터가 다르다: {key}')
        bm = greedy(sorted(((iou(x, y), i, j) for i, x in enumerate(A['blocks'])
                            for j, y in enumerate(B['blocks']) if iou(x, y) >= BLOCK_IOU), reverse=True))
        tot['blocks_a'] += len(A['blocks']); tot['blocks_b'] += len(B['blocks']); tot['blocks_matched'] += len(bm)
        prow = dict(set=key[0], order=key[1], file=A['file'], done_a=A['done'], done_b=B['done'],
                    blocks_a=len(A['blocks']), blocks_b=len(B['blocks']), blocks_matched=len(bm), rows=[])
        for i, j, s in bm:
            X, Y = A['blocks'][i], B['blocks'][j]
            if X['flag'] != Y['flag']:
                tot['flag_differs'] += 1
            lx = [l for l in X['lines'] if l['base'] and l['base'].get('y') is not None]
            ly = [l for l in Y['lines'] if l['base'] and l['base'].get('y') is not None]
            lm = greedy(sorted(((-abs(p['base']['y'] - q['base']['y']), u, v) for u, p in enumerate(lx)
                                for v, q in enumerate(ly) if abs(p['base']['y'] - q['base']['y']) <= LINE_TOL),
                               reverse=True))
            tot['lines_a'] += len(lx); tot['lines_b'] += len(ly); tot['lines_matched'] += len(lm)
            for u, v, _ in lm:
                p, q = lx[u], ly[v]
                row = dict(block_a=X['no'], block_b=Y['no'], line_a=p['no'], line_b=q['no'])
                for t in TYPES:
                    g, h = p.get(t), q.get(t)
                    if g is None or h is None:
                        k = '빈칸 있음'
                    elif g.get('y') is not None and h.get('y') is not None:
                        d = h['y'] - g['y']
                        diffs[t][d] += 1
                        k = '둘 다 그음'
                        row[t] = d
                    elif g.get('y') is not None or h.get('y') is not None:
                        k = '선 대 표시'
                        row[t] = f"{g.get('y', g.get('mark'))} / {h.get('y', h.get('mark'))}"
                    else:
                        k = '같은 표시' if g.get('mark') == h.get('mark') else '다른 표시'
                        if k == '다른 표시':
                            row[t] = f"{g.get('mark')} / {h.get('mark')}"
                    kinds[t][k] += 1
                prow['rows'].append(row)
        prow['rows'].sort(key=lambda r: (r['block_a'], r['line_a']))
        posters.append(prow)

    summary = {}
    for t in TYPES:
        c = diffs[t]
        n = sum(c.values())
        summary[t] = dict(both_drawn=n,
                          same_row=c.get(0, 0),
                          within_1=sum(v for d, v in c.items() if abs(d) <= 1),
                          over_1=sum(v for d, v in c.items() if abs(d) > 1),
                          mean_signed=(round(sum(d * v for d, v in c.items()) / n, 3) if n else None),
                          histogram={str(d): v for d, v in sorted(c.items())},
                          kinds=dict(kinds[t]))
    res = dict(note='연습 판 · 규칙 맞추기용 — 논문 수치 아님. 차이는 B − A (행). 한쪽을 정답이라 부르지 않는다',
               a=dict(file=a.a, labeler=oa['labeler']), b=dict(file=a.b, labeler=ob['labeler']),
               set=a.set, block_iou=BLOCK_IOU, line_tol=LINE_TOL, totals=dict(tot), summary=summary, posters=posters)
    if a.out:
        json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(f"블록 짝 {tot['blocks_matched']} (A {tot['blocks_a']} · B {tot['blocks_b']}) · "
          f"줄 짝 {tot['lines_matched']} (A {tot['lines_a']} · B {tot['lines_b']}) · 표시 다른 블록 {tot['flag_differs']}")
    names = dict(base='베이스라인', cap='캡선', asc='어센더선', xh='x높이선')
    for t in TYPES:
        s = summary[t]
        print(f"{names[t]:6s} 둘 다 그음 {s['both_drawn']:3d} · 같은 행 {s['same_row']:3d} · ±1 이내 {s['within_1']:3d} · "
              f"±1 넘음 {s['over_1']:3d} · 평균 {s['mean_signed']} · {s['kinds']}")


if __name__ == '__main__':
    main()
