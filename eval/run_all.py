"""참조 데이터가 바뀌면 한 명령으로 채점·분석을 전부 다시 돌린다.

    python eval/run_all.py eval/refs.json               # 있는 검출기 상자로 채점·분석
    python eval/run_all.py eval/refs.json --redetect    # EasyOCR · Surya · Surya 줄을 새 참조 판에 다시 짚는다
    python eval/run_all.py eval/refs.json --skip-idml   # IDML 탐색(검출기를 새로 돌려 몇 분 걸린다)을 뺀다

참조 데이터 경로는 refs.json 에만 있다 — 스크립트에는 박지 않는다. 순서:

    1. 사람 상자 CSV → 참조 상자 파일           detector_compare.py human
    2. 검출기 상자가 참조 판을 다 덮는지 확인
       EasyOCR · Surya 가 모자라면 --redetect 로 다시 짚는다
       VLM 이 모자라면 멈춘다 — VLM 상자는 사람 상자를 본 적 없는 새 세션에서
       만들어야 하므로 이 스크립트가 만들지 않는다
    3. 검출기 비교                               detector_score.py
    4. 오라클 묶기 상한                          oracle_group.py
    5. place_text leave-one-out (탐색)          eval/loo_place_text.py
    6. 시리즈 판별 시험 (탐색)                   eval/series_check.py
    7. IDML 가이드 탐색                          idml_explore.py score
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args):
    print('\n$ python', ' '.join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def posters_of(path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return None
    return {x['file'] for x in json.load(open(p))['posters']}


def main(argv=None):
    ap = argparse.ArgumentParser(description='새 참조로 채점·분석을 전부 다시 돌린다')
    ap.add_argument('refs', help='참조 경로 목록 JSON (eval/refs.json)')
    ap.add_argument('--redetect', action='store_true', help='EasyOCR · Surya · Surya 줄을 다시 짚는다')
    ap.add_argument('--skip-idml', action='store_true')
    a = ap.parse_args(argv)
    R = json.load(open(a.refs))

    roots = []
    for r in (R.get('image_roots') or []):
        roots += ['--image-root', r]

    hb = R['human_boxes']
    run('detector_compare.py', 'human', '--csv', hb['csv'], '--date', hb['date'],
        '--tool', hb['tool'], '--out', hb['out'], *roots)
    ref = hb['out']
    want = posters_of(ref)

    det = R['detectors']
    if a.redetect:
        for name, cmd in (('EasyOCR', 'easyocr'), ('Surya', 'surya')):
            for i, f in enumerate(det[name], 1):
                run('detector_compare.py', cmd, '--ref', ref, '--run', str(i), '--out', f, *roots)
        run('detector_compare.py', 'surya_lines', '--ref', ref, '--group', det['Surya'][0],
            '--out', R['surya_lines'], *roots)

    short = {}
    for name, fs in det.items():
        for f in fs + ([R['surya_lines']] if name == 'Surya' else []):
            gap = want - (posters_of(f) or set())
            if gap:
                short[f] = (name, sorted(gap))
    if short:
        print('\n참조 판을 다 덮지 못한 상자 파일:')
        for f, (name, gap) in short.items():
            print(f'  {name:8s} {f} — {len(gap)}장 모자람 (예: {gap[0][:50]})')
        if any(name == 'VLM' for name, _ in short.values()):
            print('VLM 상자는 이 스크립트가 만들지 않는다. docs/detector_vlm_prompt.md 방식으로 '
                  '사람 상자를 본 적 없는 새 세션에서 만든 뒤 detector_compare.py vlm 으로 옮겨라.')
        if any(name != 'VLM' for name, _ in short.values()) and not a.redetect:
            print('EasyOCR · Surya 는 --redetect 로 다시 짚는다.')
        sys.exit(2)

    srcs = []
    for name, fs in det.items():
        srcs += ['--source', f'{name}=' + ','.join(fs)]
    notes = []
    for k, v in (R.get('detector_notes') or {}).items():
        notes += ['--note', f'{k}={v}']
    run('detector_score.py', '--ref', ref, *srcs, '--prereg', R['detector_prereg'],
        '--out', R['detector_out'], *notes, *roots)

    run('oracle_group.py', '--ref', ref, '--lines', R['surya_lines'], '--group', det['Surya'][0],
        '--vlm', det['VLM'][0], '--prereg', R['oracle_prereg'], '--out', R['oracle_out'], *roots)

    if R.get('loo_place_text') and R.get('hand_lines'):
        P, H = R['loo_place_text'], R['hand_lines']
        ps = []
        for x in P['posters']:
            ps += ['--poster', x]
        run('eval/loo_place_text.py', '--lines', H['lines'], '--blocks', H['blocks'],
            '--cache', P['cache'], *ps, '--out', P['out'])

    if R.get('series_check'):
        C, H = R['series_check'], R.get('hand_lines') or {}
        extra = []
        for n, p in C['others'].items():
            extra += ['--other', f'{n}={p}']
        if H:
            extra += ['--hand-lines', H['lines'], '--hand-blocks', H['blocks']]
            for x in C.get('hand_posters', []):
                extra += ['--hand-poster', x]
        run('eval/series_check.py', '--cache', C['cache'], '--series', C['series'], *extra,
            '--prereg', C['prereg'], '--out', C['out'])
        if C.get('diag_out'):
            run('eval/series_check_diag.py', '--cache', C['cache'], '--series', C['series'],
                '--out', C['diag_out'])

    if R.get('synth'):
        S = R['synth']
        run('eval/synth_score.py', '--dir', S['dir'], '--manifest', S['manifest'],
            '--prereg', S['prereg'], '--cache-dir', S['cache_dir'], '--out', S['out'])

    if R.get('group') and R['group'].get('폐기'):
        print(f"\n묶기 비교 240장 세트는 폐기됐다 ({R['group']['폐기']['날짜']}, {R['group']['폐기']['경위']}) — 다시 채점하지 않는다")
    elif R.get('group'):
        Gp = R['group']
        vl = [os.path.expanduser(v) for v in Gp['vlm']]
        if not all(os.path.exists(v) for v in vl):
            print('VLM 묶음 파일이 없다 — docs/group_vlm_prompt.md 방식으로 새 서브에이전트가 만든다. 묶기 채점을 건너뛴다')
        else:
            vv = []
            for v in Gp['vlm']:
                vv += ['--vlm', v]
            nn = []
            for n in Gp.get('notes', []):
                nn += ['--note', n]
            run('eval/group_score.py', 'score', '--dir', Gp['dir'], '--manifest', Gp['manifest'],
                '--lines', Gp['lines'], *vv, '--prereg', Gp['prereg'], '--out', Gp['out'], *nn,
                '--c-pad-rule', Gp.get('c_pad_rule', 'fixed'))
            if Gp.get('diag_out'):
                run('eval/group_diag.py', '--dir', Gp['dir'], '--manifest', Gp['manifest'],
                    '--lines', Gp['lines'], *vv, '--out', Gp['diag_out'])

    if R.get('clean') and os.path.exists(os.path.join(ROOT, R['clean']['manifest'])):
        Cl = R['clean']
        hh = ['--human-check', json.dumps(Cl.get('human_check') or [], ensure_ascii=False)]
        if Cl.get('human_check_pending'):
            hh += ['--human-check-pending', Cl['human_check_pending']]
        if Cl.get('new_from_seed') is not None:
            hh += ['--new-from-seed', str(Cl['new_from_seed']), '--new-samples', str(Cl.get('new_samples', 0))]
            if Cl.get('new_strata'):
                hh += ['--new-strata', Cl['new_strata']]
        run('eval/clean_check.py', '--dir', Cl['dir'], '--manifest', Cl['manifest'], '--prereg', Cl['prereg'],
            '--out', Cl['check_out'], '--review-dir', Cl['review_dir'], *hh)
        run('eval/clean_som_samples.py', '--check', Cl['check_out'], '--review-dir', Cl['review_dir'])

    if R.get('measure_pad'):
        Mp = R['measure_pad']
        if os.path.exists(os.path.expanduser(Mp['lines'])):
            run('eval/measure_pad_check.py', '--dir', Mp['dir'], '--manifest', Mp['manifest'],
                '--lines', Mp['lines'], '--prereg', Mp['prereg'], '--out', Mp['out'])
        else:
            print('pad 검증 줄 파일이 없다 — eval/group_score.py detect 로 먼저 짚는다. 건너뛴다')

    if R.get('idml') and not a.skip_idml:
        I = R['idml']
        run('idml_explore.py', 'score', '--idml-dir', I['dir'], '--map', I['map'],
            '--posters-dir', I['posters_dir'], '--out', I['out'])

    print('\n끝. 결과 파일이 커밋본과 달라졌는지:')
    outs = ([hb['out'], R['detector_out'], R['oracle_out']]
            + ([R['loo_place_text']['out']] if R.get('loo_place_text') else [])
            + ([R['series_check']['out']] if R.get('series_check') else [])
            + ([R['synth']['out']] if R.get('synth') else [])
            + ([R['group']['out'], R['group'].get('diag_out')] if R.get('group') and not R['group'].get('폐기') else [])
            + ([R['clean']['check_out']] if R.get('clean') else [])
            + ([R['measure_pad']['out']] if R.get('measure_pad') else [])
            + ([R['idml']['out']] if R.get('idml') else []))
    subprocess.run(['git', 'status', '--short', '--', *outs], cwd=ROOT)


if __name__ == '__main__':
    main()
