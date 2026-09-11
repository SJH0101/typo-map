"""시리즈 판별 시험 진단 — 사전등록 밖. 변형 (a) 의 부동소수 오차를 가른다.

변형 (a) b_i' = b_0 + i·g·f + r_i 는 실수 셈으로는 간격끼리의 편차를 바꾸지
않는다. 원래 통과한 블록(편차 1px 이하)이 (a) 뒤에 «블록 내 행간 일정(편차
1px 초과)» 으로 잡혔다면 부동소수 오차다 — 편차가 정확히 1 이던 블록이
1.0000000000000018 이 된다. 여기서는 변형마다 잡힌 규칙과 부동소수 편차를
적어, 비율 규칙(계층 밖 · 줄 겹침 · 보류)으로 잡힌 몫을 따로 낸다.
check_layout 과 문턱은 고치지 않는다.

    python eval/series_check_diag.py --cache ~/.typo-mcp/brockmann.json --series Musica_Viva \\
        --out docs/series_check_diag.json
"""
import argparse
import json
import os
import sys
import tempfile
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'eval'))

import rules                        # noqa: E402
import series_check as SC           # noqa: E402

EPS = 1e-9


def main(argv=None):
    ap = argparse.ArgumentParser(description='변형 (a) 부동소수 오차 진단 (사전등록 밖)')
    ap.add_argument('--cache', required=True)
    ap.add_argument('--series', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    raw = json.load(open(os.path.expanduser(a.cache)))['raw']
    held = {k: v for k, v in raw.items() if k.startswith(a.series + '__')}
    rest = {k: v for k, v in raw.items() if not k.startswith(a.series + '__')}
    R_out = rules.derive(rest)
    out = dict(무엇='변형 (a) 전체 배율에서 «블록 내 행간 일정» 으로 잡힌 것이 부동소수 오차인지 가른다',
               용도='사전등록 밖 진단. check_layout 과 문턱은 고치지 않았다. 논문 수치로 쓰지 않는다',
               결과={})
    with tempfile.TemporaryDirectory() as tmp:
        c_out = os.path.join(tmp, 'out.json')
        rules.save(c_out, {}, R_out)
        blocks = SC.test_blocks(held)
        for mode, layer in SC.MODES:
            passed = [b for b in blocks if SC.judge(c_out, b['cap'], b['bases'], layer)[0] == '통과']
            orig_spread = Counter()
            for b in passed:
                g = np.diff(b['bases'])
                orig_spread[float(g.max() - g.min())] += 1
            by_f = {}
            for f in SC.FACTORS:
                t = dict(변형=0, 거부=0, 비율규칙으로_거부=0, 행간일정만=0, 행간일정만_중_부동소수=0)
                for b in passed:
                    v = SC.scale(b['bases'], f)
                    j, ks = SC.judge(c_out, b['cap'], v, layer)
                    g = np.diff(sorted(v))
                    spread = float(g.max() - g.min())
                    t['변형'] += 1
                    if j == '통과':
                        continue
                    t['거부'] += 1
                    if set(ks) - {'블록 내 행간 일정'}:
                        t['비율규칙으로_거부'] += 1
                    else:
                        t['행간일정만'] += 1
                        if 1.0 < spread <= 1.0 + EPS:
                            t['행간일정만_중_부동소수'] += 1
                t['비율규칙_거부율'] = round(t['비율규칙으로_거부'] / t['변형'], 3) if t['변형'] else None
                by_f[f'×{f}'] = t
            out['결과'][mode] = dict(대상_블록=len(passed),
                                   원래_간격편차_분포={str(k): v for k, v in sorted(orig_spread.items())},
                                   배율별=by_f)
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out['결과'], ensure_ascii=False, indent=1))
    print('→', a.out)


if __name__ == '__main__':
    main()
