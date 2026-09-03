"""코퍼스에 «구조로» 물어본다.

    python ask.py                          한눈에
    python ask.py --where "축>=3 세로격자==없음"
    python ask.py --group corpus --col 축 피치 세로격자

여태 물어볼 수 없던 것들이다. 지표 벡터는 판마다 21개 수였고 구조가 없었다.
「축이 셋 이상이면서 세로 격자가 없는 판」 같은 물음에 답할 자료가 없었다.

문서가 생기니 한 줄이 된다. 이 파일은 그 한 줄을 쓰는 자리다.
"""
import argparse
import json
import os

import numpy as np

IDX = 'docs/corpus/index.json'
LAB = {'brockmann': '브로크만', 'corpus': '호프만', 'rose': '로제', 'ruder': '루더'}


def load(path=IDX):
    d = json.load(open(path))
    for r in d['판']:
        r['작가'] = LAB.get(r['corpus'], r['corpus'])
        r['계층수'] = len(r.get('계층') or [])
        c = r.get('계층') or []
        r['계층비'] = round(max(c) / min(c), 2) if len(c) >= 2 and min(c) > 0 else None
    return d


def where(rows, expr):
    """«축>=3 세로격자==없음» 같은 간단한 조건. 공백은 그리고."""
    import re
    out = rows
    for t in expr.split():
        m = re.match(r'^(\w+)(>=|<=|==|!=|>|<)(.+)$', t)
        if not m:
            continue
        k, op, v = m.groups()
        try:
            v = float(v)
        except ValueError:
            v = v.strip('"\'')
        def ok(r, k=k, op=op, v=v):
            x = r.get(k)
            if x is None:
                return False
            try:
                return {'>=': x >= v, '<=': x <= v, '==': x == v,
                        '!=': x != v, '>': x > v, '<': x < v}[op]
            except TypeError:
                return False
        out = [r for r in out if ok(r)]
    return out


def table(rows, cols, group=None):
    if group:
        gs = {}
        for r in rows:
            gs.setdefault(r.get(group), []).append(r)
    else:
        gs = {'전체': rows}
    w = max(len(str(k)) for k in gs) + 2
    head = f"{'':<{w}}{'n':>5}" + ''.join(f'{c:>11}' for c in cols)
    print(head); print('─' * len(head))
    for k, v in gs.items():
        line = f'{k:<{w}}{len(v):>5}'
        for c in cols:
            xs = [r.get(c) for r in v if r.get(c) is not None]
            if xs and isinstance(xs[0], (int, float)):
                line += f'{np.median(xs):>11.2f}'
            else:
                from collections import Counter
                line += f"{(Counter(xs).most_common(1)[0][0] if xs else '—'):>11}"
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--where', default=None)
    ap.add_argument('--group', default='작가')
    ap.add_argument('--col', nargs='*',
                    default=['마디', '글줄', '그림', '축', '피치', '세로격자', '계층수'])
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    d = load()
    rows = d['판']
    if a.where:
        rows = where(rows, a.where)
        print(f'조건: {a.where}  →  {len(rows)}장\n')
    if a.list:
        for r in rows[:40]:
            print(f"  {r['작가']:<6} 축 {r.get('축')} · 세로격자 {r.get('세로격자')} · "
                  f"계층 {r.get('계층')}  {r['file'][:44]}")
        return
    table(rows, a.col, a.group)
    print(f"\n형식 {d['형식']} · 만든날 {d['만든날']}")
    print('없는 칸:', ' · '.join(d['없는칸']))


if __name__ == '__main__':
    main()
