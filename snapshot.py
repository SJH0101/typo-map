"""측정 회귀 검사.

파이프라인을 고칠 때마다 「숫자가 늘었다」만 보면 안 된다. 늘면서 이미
맞던 것이 깨질 수 있다. 아래 포스터들은 지금까지 고친 문제마다 하나씩
골랐다. 측정값을 스냅샷으로 고정해두고 달라지면 알린다.

측정은 결정적이다 — 같은 입력에 같은 값이 나온다. 그래서 정확히 비교한다.
값이 달라졌다고 곧 틀린 것은 아니다. 의도한 개선일 수 있다. 그때는 눈으로
확인한 뒤 --bless 로 다시 굳힌다.

실행
    TYPO_MCP_CORPUS=~/코퍼스/코어 python snapshot.py           검사
    TYPO_MCP_CORPUS=~/코퍼스/코어 python snapshot.py --bless   현재값으로 갱신
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshot.json')
CORPUS = os.path.expanduser(os.environ.get('TYPO_MCP_CORPUS', ''))

# 무엇을 지키려고 이 포스터를 넣었는지 함께 적는다. 깨졌을 때 어디를
# 봐야 하는지 알려주는 것이 파일 이름보다 중요하다.
CASES = [
    ('Gewerbemuseum_Basel/1952_Die Gute Form 1952 - Gewerbemuseum Basel - 10.April - 10.Mai.jpg',
     '어두운 배경 + 오른쪽 정렬 5줄 블록 (극성, shares_axis)'),
    ('Kunsthalle_Basel/1966_Wilfredo Lam Malerei - Vic Gentils Bildhauerei - Kunsthalle .jpg',
     '어두운 배경, 6줄 블록 (극성)'),
    ('Sonstige/1954_Die gute Form - SWB-Sonderschau - Veranstaltet vom Schweizer.jpg',
     '대각선 표제활자를 130° 회전으로 오판했던 포스터 (MAX_SKEW)'),
    ('Gewerbemuseum_Basel/1969_Spitzen - Gewerbemuseum Basel.jpg',
     '-45° 로 오판했던 포스터 (MAX_SKEW)'),
    ('Konzert/1986_Basler Bach-Chor - Stadtcasino Basel - Stabat Mater.jpg',
     'x높이 464px 의 「B」가 8px 활자 6줄을 삼켰던 포스터 (scale_strata)'),
    ('Gewerbemuseum_etc/1951_Form & Farbe - Gewerbemuseum Winterthur - 22.6. - 15.7.jpg',
     '성긴 행간 계층. 눈으로 확인한 진짜 값이다 (layers)'),
    ('Gewerbemuseum_Basel/1938_Siedlungsbau in der Schweiz 1938-47 - Ausstellung im Gewerbe.jpg',
     '성긴 행간 계층, 행간/활자높이 4.00 (layers)'),
    ('Gewerbemuseum_Basel/1975_Gewerbemuseum Basel - Ausstellung Plan & Bau - 50 Jahre Arch.jpg',
     '원래부터 잘 잡히던 8줄 블록. 개선이 이것을 깨지 않았는지 본다'),
    ('Konzert/1986_J. Brahms - Ein deutsches Requiem.jpg',
     'fit_grid 의 음수 슬라이스로 측정이 죽던 포스터 (s0=-3)'),
    ('Stadttheater_Basel/1961_Stadttheater Basel - Beginn der Spielzeit 1961-62.jpg',
     'fit_grid 의 음수 슬라이스로 측정이 죽던 포스터 (s0=-7). 9줄·8줄 블록이 있다'),
]


def measure():
    """CASES 를 측정해 비교할 형태로 줄인다."""
    import easyocr
    import rules
    paths = [os.path.join(CORPUS, rel) for rel, _ in CASES]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.exit('포스터를 찾을 수 없다:\n  ' + '\n  '.join(missing))
    raw = rules.collect(paths, reader=easyocr.Reader(['de'], gpu=False, verbose=False))
    out = {}
    for rel, _ in CASES:
        name = os.path.basename(rel)
        v = raw.get(name)
        if v is None:
            out[rel] = None                      # 측정 실패도 스냅샷에 남긴다
            continue
        out[rel] = dict(
            angle=v['angle'],
            n_blocks=len(v['blocks']),
            # 블록은 위에서 아래 순서가 아니므로 정렬해 비교를 안정화한다
            blocks=sorted(
                [dict(n=b['n'], lead=b['lead'], xh=b['xh'],
                      box=[b['x1'], b['y1'], b['x2'], b['y2']])
                 for b in v['blocks']],
                key=lambda b: (b['box'][1], b['box'][0])))
    return out, raw


def flatten(d, prefix=''):
    """중첩 구조를 「필드 경로 → 값」 으로 편다. 어디가 달라졌는지 짚기 위해.

    포스터 파일명에 점이 들어 있으므로(10.April - 10.Mai.jpg) 최상위 키는
    여기서 다루지 않는다. 항목마다 따로 불러 쓴다.
    """
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, f'{prefix}.{k}' if prefix else str(k)))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(flatten(v, f'{prefix}[{i}]'))
    else:
        out[prefix or '(값)'] = d
    return out


def report(old, new):
    """달라진 지점만 보고한다. 반환값은 종료 코드."""
    why = dict(CASES)
    groups, total, n_fields = [], 0, 0
    for key in list(dict.fromkeys(list(old) + list(new))):
        a, b = flatten(old.get(key)), flatten(new.get(key))
        n_fields += len(b)
        ks = sorted(set(a) | set(b))
        diff = [(k, a.get(k, '없음'), b.get(k, '없음')) for k in ks if a.get(k) != b.get(k)]
        if diff:
            groups.append((key, diff))
            total += len(diff)

    if not groups:
        print(f'변화 없음. 포스터 {len(CASES)} 장, 비교 항목 {n_fields} 개.')
        return 0

    print(f'달라진 항목 {total} 개, 대상 {len(groups)} 개\n')
    for key, diff in groups:
        print(f'  {os.path.basename(key)}')
        if key in why:
            print(f'    지키려던 것: {why[key]}')
        for k, o, n in diff[:10]:
            print(f'      {k:26s} {o}  →  {n}')
        if len(diff) > 10:
            print(f'      … 그리고 {len(diff) - 10} 개')
        print()
    print('의도한 개선이면 눈으로 확인한 뒤 --bless 로 갱신하라.')
    return 1


def main():
    if not CORPUS:
        sys.exit('TYPO_MCP_CORPUS 에 포스터 디렉토리를 지정하라. 예:\n'
                 '  TYPO_MCP_CORPUS=~/코퍼스/코어 python snapshot.py')
    if not os.path.isdir(CORPUS):
        sys.exit(f'디렉토리가 아니다: {CORPUS}')

    bless = '--bless' in sys.argv
    if not bless and not os.path.exists(SNAP):
        sys.exit(f'스냅샷이 없다. 먼저 만들어라:\n  '
                 f'TYPO_MCP_CORPUS={CORPUS} python snapshot.py --bless')

    print(f'측정: 포스터 {len(CASES)} 장 · {CORPUS}', flush=True)
    new, raw = measure()

    # 계층 판정까지 함께 굳힌다. 측정이 같아도 derive 가 바뀌면 결과가 달라진다.
    import rules
    d = rules.derive(raw)
    new['_rules'] = {k: {kk: v[kk] for kk in ('n', 'median', 'lo', 'hi', 'min', 'max', 'cv', 'verdict')}
                     for k, v in list(d['rules'].items()) + list(d['not_rules'].items())}

    if bless:
        json.dump(new, open(SNAP, 'w'), ensure_ascii=False, indent=1, sort_keys=True)
        print(f'스냅샷 갱신: {SNAP}')
        return 0
    return report(json.load(open(SNAP)), new)


if __name__ == '__main__':
    sys.exit(main())
