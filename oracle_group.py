"""오라클 묶기 — Surya 줄을 «사람 상자를 아는» 묶기로 묶었을 때의 상한.

하이브리드(Surya 줄 + VLM 묶기)를 짓기 전에, 묶기를 완벽하게 해도 줄
검출이 허락하는 한계가 어디인지를 잰다. 묶기는 사람 상자를 보고 한다 —
실제 시스템은 그것을 모른다. 그러니 이 값은 상한이고, **파라미터 튜닝에
쓰지 않는다**. 정의는 docs/oracle_preregister.json 에 있다.

경로는 모두 인자로 받는다. 한 번에 다시 돌리는 명령은 eval/run_all.py 다.

    python oracle_group.py --ref boxes/human_v2.json --lines boxes/surya_lines.json \\
        --group boxes/surya_run1.json --vlm boxes/vlm_pass1.json \\
        --prereg docs/oracle_preregister.json --out docs/oracle_upper.json
"""
import argparse
import json
from collections import Counter

import numpy as np
from PIL import Image

import detector_score as S

OUTSIDE = 0.5    # 줄 넓이 중 이 몫 이상이 사람 상자 밖이면 «상자를 넘는 줄»
COVER_X = 0.5    # 잉크 줄 폭 중 이 몫 이상 가로로 겹쳐야 «덮었다»


def assign(R, L):
    """줄마다 교집합 넓이가 가장 큰 사람 상자 번호. 안 겹치면 None. 같으면 앞 번호."""
    out = []
    for l in L:
        best, bi = 0.0, None
        for i, r in enumerate(R):
            v = S.inter(l, r)
            if v > best:
                best, bi = v, i
        out.append(bi)
    return out


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def ink_lines(gray, r):
    """사람 상자 안에서 재는 코드가 찾은 줄 — (x높이 가운데 y, 시작 x, 끝 x)."""
    from measure import region
    m = region.measure(gray, r)
    if m.get('n_lines', 0) == 0:
        return None
    return [((xt + b) / 2.0, float(xs), float(xe))
            for xt, b, xs, xe in zip(m['x_tops'], m['baselines'], m['x_starts'], m['x_ends'])]


def covered(line, s):
    y, xs, xe = line
    ox = min(xe, s[2]) - max(xs, s[0])
    return s[1] <= y <= s[3] and ox / max(1.0, xe - xs) >= COVER_X


def cause(gray, i, R, L, owner):
    r = R[i]
    mine = [j for j, o in enumerate(owner) if o == i]
    if mine and S.iou(union([L[j] for j in mine]), r) >= S.IOU_MIN:
        return '기타', '1:1 충돌'
    if not any(S.inter(l, r) > 0 for l in L):
        return '줄을 못 찾음', '전부'
    if not mine:
        return '줄 경계 틀림', '이웃 상자로 간 줄'
    ink = ink_lines(gray, r)
    if ink is not None and any(not any(covered(k, L[j]) for j in mine) for k in ink):
        return '줄을 못 찾음', '일부'
    if any(S.area(L[j]) and 1 - S.inter(L[j], r) / S.area(L[j]) >= OUTSIDE for j in mine):
        return '줄 경계 틀림', '상자를 넘는 줄'
    u = union([L[j] for j in mine])
    how = ('합집합이 작다' if S.inside(u, r) >= 0.8 else
           '합집합이 크다' if S.held(u, r) >= 0.8 else '어긋남')
    return '기타', how + ('' if ink is not None else ' · 잉크 줄 못 잼')


def main(argv=None):
    ap = argparse.ArgumentParser(description='오라클 묶기 상한. 경로는 모두 인자로 받는다.')
    ap.add_argument('--ref', required=True, help='참조 상자 파일')
    ap.add_argument('--lines', required=True, help='group() 이전 Surya 줄 상자 파일')
    ap.add_argument('--group', required=True, help='지금 Surya group 상자 파일')
    ap.add_argument('--vlm', required=True, help='VLM 상자 파일')
    ap.add_argument('--prereg', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--image-root', action='append')
    a = ap.parse_args(argv)

    _, ref = S.load(a.ref)
    lines_doc, lines = S.load(a.lines)
    paths = S._paths(a.ref, a.image_root)
    grays = {f: np.asarray(Image.open(paths[f]).convert('L')).astype(float) for f in ref}

    oracle, plus = {}, {}
    n_lines = 0
    orphan_n, orphan_area, orphan_by = 0, 0.0, Counter()
    causes, detail, per_box = Counter(), Counter(), []
    for f, rp in ref.items():
        W, H = rp['img_w'], rp['img_h']
        R, _ = S.clean([b['box'] for b in rp['boxes']], W, H)
        L, _ = S.clean([b['box'] for b in lines[f]['boxes']], W, H)
        n_lines += len(L)
        owner = assign(R, L)
        groups = {}
        for j, o in enumerate(owner):
            if o is None:
                orphan_n += 1
                orphan_area += S.area(L[j]) / float(W * H)
                orphan_by[rp['corpus']] += 1
            else:
                groups.setdefault(o, []).append(L[j])
        B = [union(groups[i]) for i in sorted(groups)]
        orphans = [L[j] for j, o in enumerate(owner) if o is None]
        oracle[f] = dict(rp, boxes=[dict(box=list(b)) for b in B])
        plus[f] = dict(rp, boxes=[dict(box=list(b)) for b in B + orphans])
        mr, _mp = S.match(R, B)
        for i in range(len(R)):
            if i in mr:
                continue
            c, d = cause(grays[f], i, R, L, owner)
            causes[c] += 1
            detail[f'{c} · {d}'] += 1
            per_box.append(dict(file=f, corpus=rp['corpus'], box=[round(v, 1) for v in R[i]],
                                원인=c, 자세히=d))

    rows = {}
    for name, got in (('Surya (지금 group)', S.load(a.group)[1]),
                      ('VLM 1차', S.load(a.vlm)[1]),
                      ('오라클 묶기', oracle),
                      ('오라클 묶기 + 안 겹치는 줄', plus)):
        rows[name], _ = S.score(ref, got, grays, 'A')

    out = dict(무엇='Surya 줄을 사람 상자를 아는 묶기로 묶었을 때 참조와의 일치도 — 상한',
               용도='상한 확인용. 파라미터 튜닝에 쓰지 않는다',
               사전등록=a.prereg)
    note = S._commit_note(a.prereg)
    if note:
        out['사전등록_커밋'] = note
    out.update(
        줄=dict(파일=a.lines, 수=n_lines, 장당=round(n_lines / len(ref), 2),
               group_재현=lines_doc['source'].get('group_reproduces_run1')),
        안겹치는줄=dict(수=orphan_n, 몫=round(orphan_n / n_lines, 3),
                   판면넓이_합_장평균=round(orphan_area / len(ref), 4),
                   코퍼스별=dict(orphan_by)),
        표=rows,
        오라클로도_못맞힌_사람상자=dict(수=sum(causes.values()), 원인=dict(causes),
                                자세히=dict(detail), 상자별=per_box))
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(f"줄 {n_lines} (장당 {n_lines / len(ref):.1f}) · group 재현 {out['줄']['group_재현']} · "
          f"안 겹치는 줄 {orphan_n} ({orphan_n / n_lines:.1%})")
    for k, v in rows.items():
        print(f"  {k:22s} R {v['재현율']:.3f}  P {v['정밀도']:.3f}  F1 {v['F1']:.3f}  "
              f"장당 {v['장당상자']:5.2f}  IoU {v['맞은짝_IoU_중앙값']}  참조쪽 {v['참조쪽']}")
    print('못 맞힌 사람 상자', sum(causes.values()), dict(causes))
    print('  자세히', dict(detail))
    print('→', a.out)


if __name__ == '__main__':
    main()
