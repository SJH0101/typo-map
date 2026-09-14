"""283장을 새 경로(Surya + measure/ground)로 다시 잰다 — 옛 캐시의 열쇠 그대로.

왜. 9월 검증 분석이 전부 8/24 옛 경로(baseline/scan + detect) 캐시 위에서
돌았다. 순서도를 그리고서야 알았다 (docs/y2_bug.json). 새 경로로 다시 재서
캐시를 바꾸고, 분석을 그 위에서 다시 낸다.

    python remeasure.py            네 코퍼스 전부
    python remeasure.py rose       하나만

열쇠는 보관본(~/.typo-mcp/old-20260824)에서 가져온다. 폴더를 통째로 다시
재면 코퍼스가 달라진다 — 폴더에는 283장보다 많은 이미지가 있다
(브로크만 203 · 호프만 117 · 로제 44 · 루더 35).

규칙은 네 코퍼스를 다 잰 뒤, 나머지 셋을 참조로 넣어 뽑는다 (rules.derive).
결과 요약은 docs/remeasure_log.json 에 남긴다.
"""
import json
import os
import sys

import measure_corpus as MC
import rules
import surface

OLD = os.path.expanduser('~/.typo-mcp/old-20260824')
NEW = os.path.expanduser('~/.typo-mcp')


def keys_of(c):
    raw = json.load(open(os.path.join(OLD, c + '.json')))['raw']
    P = surface.resolve(raw, surface.ROOTS[c])
    return [(k, P[k]) for k in sorted(P)], [k for k in raw if k not in P]


def main(which):
    got, report = {}, {}
    for c in which:
        items, miss = keys_of(c)
        print(f'{c}: {len(items)}장 (경로 못 찾음 {len(miss)})', flush=True)
        raw, failed = MC.measure_items(items)
        got[c] = raw
        bs = [b for e in raw.values() for b in (e.get('blocks') or [])]
        report[c] = dict(판=len(items), 잰판=len(raw),
                         실패=[[os.path.basename(p), w] for p, w in failed], 경로못찾음=miss,
                         덩어리=len(bs), 뒤집힌아래끝=sum(1 for b in bs if b['y2'] < b['y1']),
                         기울어짐=sum(1 for e in raw.values() if e.get('skewed')))
        print(f"  잰 판 {len(raw)} · 실패 {len(failed)} · 덩어리 {len(bs)} · "
              f"뒤집힌 아래끝 {report[c]['뒤집힌아래끝']} · 기울어짐 {report[c]['기울어짐']}", flush=True)
    for c, raw in got.items():
        refs = {o: (got[o] if o in got else json.load(open(os.path.join(NEW, o + '.json')))['raw'])
                for o in surface.ROOTS if o != c}
        r = rules.derive(raw, references=refs)
        MC.write(os.path.join(NEW, c + '.json'), raw, rules=r,
                 source=f'remeasure.py — {OLD}/{c}.json 의 열쇠 {len(raw)}장')
        print(f'  → {NEW}/{c}.json', flush=True)
    # 일부 코퍼스만 다시 재면 그 코퍼스 항목만 바꾸고 나머지 기록은 남긴다 (2026-09-15, 브로크만만 G1 로 다시 잴 때)
    log = 'docs/remeasure_log.json'
    prev = json.load(open(log)) if os.path.exists(log) else {}
    prev.update(report)
    json.dump(prev, open(log, 'w'), ensure_ascii=False, indent=1)
    print('끝', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:] or list(surface.ROOTS))
