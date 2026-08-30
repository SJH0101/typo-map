"""선행연구 데이터베이스를 읽는 판으로 뽑는다.

    python docs/related.py            사람이 읽을 표
    python docs/related.py --gap      빈 자리만
    python docs/related.py --md       docs/RELATED.md 를 다시 쓴다

데이터는 docs/related.json 하나뿐이다. 새 논문을 찾으면 거기에 넣는다 —
표를 손으로 고치면 둘이 어긋난다.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = json.load(open(os.path.join(HERE, 'related.json')))


def lines():
    m, br = DB['meta'], DB['갈래']
    o = ['# 선행연구 — 세 갈래와 그 사이의 빈 자리', '',
         f"> **물음.** {m['물음']}", '',
         f"{m['찾은날']} · {m['찾은법']}", '', m['결론'], '',
         '---', '', '## 갈래', '']
    for k, v in br.items():
        n = sum(1 for r in DB['연구'] if r['갈래'] == k)
        o += [f"### {k}. {v['이름']}", '',
              f"- **재는 것** {v['재는것']}",
              f"- **작가 개념** {v['작가개념']}",
              f"- **우리와의 차이** {v['우리와의차이']}",
              f"- 모은 것 {n}건", '']
    o += ['---', '', '## 목록', '']
    for k, v in br.items():
        rs = [r for r in DB['연구'] if r['갈래'] == k]
        if not rs:
            continue
        o += [f"### {k} — {v['이름'].split(' — ')[0]}", '']
        for r in rs:
            head = f"**{r['제목']}**"
            meta = ' · '.join(x for x in [r.get('저자'), str(r.get('연도') or ''),
                                          r.get('학회')] if x)
            o.append(f"- {head}  \n  {meta}")
            if r.get('url'):
                o[-1] += f"  \n  {r['url']}"
            for tag, lab in (('요지', '요지'), ('가까움', '**가깝다**'),
                             ('차이', '**차이**'), ('공정하게', '공정하게'),
                             ('쓰임', '쓰임')):
                if r.get(tag):
                    o[-1] += f"  \n  {lab}: {r[tag]}"
            if r.get('확인'):
                o[-1] += f"  \n  *확인: {r['확인']}*"
        o.append('')
    o += ['---', '', '## 못 본 곳', '',
          '「없다」가 아니라 「이 범위에서 찾지 못했다」로 쓴다.', '']
    o += [f'- {x}' for x in m['못본곳']]
    o += ['', '## 쓴 질의', '', '```'] + m['질의'] + ['```', '',
          f"*{m['확인정도']}*", '']
    return o


def gap():
    print('가까운 것들 — 여기가 흔들리면 위치를 다시 잡아야 한다\n')
    for r in DB['연구']:
        if r.get('가까움'):
            print(f"  [{r['갈래']}] {r['제목'][:62]}")
            print(f"      가깝다: {r['가까움']}")
            if r.get('차이'):
                print(f"      차이  : {r['차이']}")
            print(f"      확인  : {r.get('확인','—')}\n")


if __name__ == '__main__':
    if '--gap' in sys.argv:
        gap()
    elif '--md' in sys.argv:
        p = os.path.join(HERE, 'RELATED.md')
        open(p, 'w').write('\n'.join(lines()))
        print(p, len(DB['연구']), '건')
    else:
        for k, v in DB['갈래'].items():
            n = sum(1 for r in DB['연구'] if r['갈래'] == k)
            print(f"  {k}  {v['이름']}  ({n}건)")
        print(f"\n  모두 {len(DB['연구'])}건 · 가까운 것 "
              f"{sum(1 for r in DB['연구'] if r.get('가까움'))}건")
