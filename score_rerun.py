"""docs/rerun_sept.json 을 docs/rerun_preregister.json 의 기준으로 채점한다.

판정을 손으로 쓰지 않는다 (docs/method.json P4). 기준 수치는 못 박은 문서와
같게 여기 적고, 캐시마다 같은 함수로 잰다.
"""
import json

import features

LEAD_MAX = 0.8          # 작가 남기기 두 방향 모두 C÷A 이하
LEAD_K = (1.8, 2.2)     # 예측 — k 범위
NARROW_MIN = 0.70       # 가로 좁힘결정도
GAIN_MAX = 2.0          # 고르는 규칙 다섯이 모두 이보다 작아야


def score(o):
    L = o['행간규칙']
    a, b = L['브+호→로+루'], L['로+루→브+호']
    D = o['결정도']
    rules = {k: v['이득'] for k, v in D['고르는 규칙'].items() if isinstance(v, dict)}
    V = o['지표']
    typeset_split = [n for n, v in V.items() if n not in features.COLOR and v['판정'] == '갈림']
    return {
        '행간 규칙이 선다': dict(
            통과=a['비'] <= LEAD_MAX and b['비'] <= LEAD_MAX,
            값=f"브+호→로+루 {a['비']} · 로+루→브+호 {b['비']} (기준 ≤ {LEAD_MAX})",
            예측_k=dict(통과=all(LEAD_K[0] <= x['k'] <= LEAD_K[1] for x in (a, b)),
                       값=f"k {a['k']} · {b['k']} (예측 {LEAD_K[0]}~{LEAD_K[1]})")),
        '격자가 가로 자리를 좁힌다': dict(
            통과=D['전체']['가로']['좁힘결정도'] >= NARROW_MIN,
            값=f"좁힘결정도 {D['전체']['가로']['좁힘결정도']} (기준 ≥ {NARROW_MIN})"),
        '칸은 정하지 않는다': dict(
            통과=all(g < GAIN_MAX for g in rules.values()),
            값=' · '.join(f'{k} {g}' for k, g in rules.items()) + f' (기준 모두 < {GAIN_MAX})'),
        '작가를 가르는 것은 색뿐': dict(
            통과=(V.get('색수', {}).get('판정') == '갈림' and V.get('밝기', {}).get('판정') == '갈림'
                  and not typeset_split),
            값=(f"색수 {V.get('색수', {}).get('배수')} {V.get('색수', {}).get('판정')} · "
                f"밝기 {V.get('밝기', {}).get('배수')} {V.get('밝기', {}).get('판정')} · "
                f"조판에서 갈림 {typeset_split or '없음'}")),
    }


if __name__ == '__main__':
    R = json.load(open('docs/rerun_sept.json'))
    out = {c: score(o) for c, o in R.items()}
    for c, s in out.items():
        print(f'\n■ {c}')
        for name, r in s.items():
            print(f"  {'○' if r['통과'] else '✗'} {name:<16} {r['값']}")
            if '예측_k' in r:
                print(f"    {'○' if r['예측_k']['통과'] else '✗'} 예측 {r['예측_k']['값']}")
    json.dump(out, open('docs/rerun_score.json', 'w'), ensure_ascii=False, indent=1)
