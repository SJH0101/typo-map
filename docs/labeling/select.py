"""브로크만 선 긋기 포스터 50장 고르기.

    .venv/bin/python docs/labeling/select.py ~/.typo-mcp/brockmann.json \
        docs/labeling/caps_claude_eye.json docs/labeling/rotation.json \
        "~/Documents/연구2/브로크만 정리/corpus/코어" docs/labeling

두 파일을 낸다.
    selection.json            분석 쪽 기록 — 칸(대문자 · 단 수) · 예상 줄 수 · 뺀 까닭. 라벨러에게 주지 않는다
    posters_for_labelers.json 도구가 읽는 목록 — 순서 · 폴더 · 파일 · sha256 만

뺀다: 기울어진 판 · 회전 블록이 있는 판 (rotation.json) · 파이프라인 추정 40줄 초과 · 같은 디자인의 변형 ·
연습 판 2장. 대문자 유무(Claude 눈 판정 — 사람 판정이 아니다)로 25장씩, 두 조건 각각에서 단 수(1단 / 2단 이상,
Surya 줄 상자로 센 파이프라인 값)를 가능한 한 반반으로 뽑는다. 칸 안 순서와 긋는 순서는 seed 로 섞는다.
줄 수는 파이프라인(Surya + ground) 추정이고 선정과 시간 어림에만 쓴다.
"""
import argparse
import collections
import hashlib
import json
import os
import random

SEED = 20260914
N = 50
MAX_LINES = 40
# 같은 판을 언어 · 장소만 바꾼 변형 (Claude 눈 확인). 한 무리에서 seed 순서로 먼저 나온 한 장만 쓴다
TWINS = [
    ['The Family of Man - -Wir Menschen- - Kunstgewerbemuseum', 'The Family of Man - -Wir Menschen- - Kunsthalle Bern'],
    ['1957_Werner Bischof', '1958_Werner Bischof'],
    ['Automobile-Club de Suisse', 'Schützt das Kind'],
    ['Cycliste - Attention', 'Radfahrer - Achtung'],
    ['Projet constitutionnel', 'Strassenbau-Vorlage'],
    ['Moins de bruit', 'Weniger Lärm'],
    ['Volg Traubensaft naturrein - Energieleistung', 'Volg Traubensaft naturrein - Festlichkeit',
     'Volg Traubensaft naturrein - Gesundheit', 'Volg Traubensaft naturrein - Konzentration',
     'Volg Traubensaft naturrein - Zuverlässigkeit'],
]
# 같은 틀 — 배치 틀(격자 · 색면 · 글 자리)이 같고 글과 색만 바꾼 판 무리 (Claude 눈 판정, 사람 판정 아님).
# 선정을 바꾸지 않는다. 표본마다 이 표시를 달아, 같은 틀 판이 독립 표본이 아니라는 것을 기록한다.
TEMPLATES = {
    'JF1956_축제음악회': ['Juni-Festwochen Zürich 1956 - '],
    'Opernhaus_머리판': ['Opernhaus__1964_Opernhaus Zürich - Die ', 'Opernhaus__1964_Opernhaus Zürich - Dornröschen',
                       'Opernhaus__1964_Opernhaus Zürich - Eröffnung der Spielzeit 1964-65',
                       'Opernhaus__1964_Opernhaus Zürich - Wiener Blut', 'Opernhaus__1965_Opernhaus Zürich - Andrea',
                       'Opernhaus__1965_Opernhaus Zürich - Der ', 'Opernhaus__1965_Opernhaus Zürich - Die Liebe',
                       'Opernhaus__1965_Opernhaus Zürich - Orpheus', 'Opernhaus__1965_Opernhaus Zürich - Schwanensee',
                       'Opernhaus__1965_Opernhaus Zürich - Undine', 'Opernhaus__1966_Opernhaus Zürich - Ballettabend',
                       'Opernhaus__1966_Opernhaus Zürich - Der fliegende', 'Opernhaus__1966_Opernhaus Zürich - Die lustige',
                       'Opernhaus__1966_Opernhaus Zürich - Don Carlos', 'Opernhaus__1966_Opernhaus Zürich - Wenn ich',
                       'Juni_Festwochen__1965_Opernhaus Zürich - Internationale Juni-Festwochen Zür',
                       'Juni_Festwochen__1966_Opernhaus Zürich - Internationale'],
    'JF1953_톤할레': ['1953_Juni-Festwochen Zürich 1953 - Tonhalle', '1953_Tonhalle Grosser Saal - Juni-Festwochen Zürich 1953'],
    'JF1957_1971_색막대': ['1957_Juni-Festwochen Zürich 1957 - Tonhalle Grosser Saal - 4. Jun', '1971_Junifestwochen Zürich 1971'],
    'JF1959_사선막대': ['1959_Juni-Festwochen Zürich 1959 - Abschiedskonzerte', '1959_Juni-Festwochen Zürich 1959 - Tonhalle Grosser Saal'],
    'JF1950_삽화': ['1950_Juni-Festwochen Zürich 1950 - Helmhaus', '1950_Kunstgewerbemuseum - Die gute Form',
                  '1950_Schauspielhaus - Juni-Festwochen', '1950_Stadttheater - Juni-Festwochen', '1950_Tonhalle - Juni-Festwochen'],
    'Tonhalle1955_사선조각': ['Ferenc Fricsay - Leitung', 'Carl Schuricht Leitung - Erica Morini', '1955_Erich Schmid - Leitung - Carl Seemann'],
    'MV1957_윗단': ['1957_Musica Viva - Grosser Saal Tonhalle', '1957_Musica Viva - Paul Hindemith'],
    'MV1962_1963': ['1962_Musica Viva - Ensemble de Musique Moderne', '1963_Musica Viva - Anton Webern'],
    'BEA_Viscount': ['Fly Viscount'],
}
# 연습 판 — 두 라벨러가 같이 보며 규칙을 맞추는 판. 본 목록에서 뺀다
PRACTICE = ['BEA__1958_Fly Viscount - the Rolls Royce of the skies - BEA - British .jpg',
            'Musica_Viva__1956_Musica Viva - V. Einem - Schönberg - Strawinsky - 11. Volksk.jpg']
# 이미 사람 자료가 있는 판 — 해석할 때 적는다
IDML = ['Andrea Ch', 'Die Liebe', 'Don Carlo', 'Dornrösch', 'Die vier', 'Der flieg', 'Der Igel', 'Wenn ich',
        'Der Liebe', 'Orpheus', 'Die Schne', 'Schwanens', 'Undine', 'Der Vogel', 'Wiener Bl', 'Die lusti',
        'Ballettab', 'Der Opern']          # eval/idml_map.json 의 값 (Opernhaus 판 이름 앞부분)


def template_of(k):
    return next((name for name, subs in TEMPLATES.items() if any(s in k for s in subs)), None)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('caps')
    ap.add_argument('rotation')
    ap.add_argument('image_root')
    ap.add_argument('outdir')
    ap.add_argument('--boxed_csv', default=None, help='송준혁 상자 CSV — 이미 상자를 그은 판 표시용')
    a = ap.parse_args()
    raw = json.load(open(os.path.expanduser(a.cache)))['raw']
    caps = json.load(open(a.caps))['labels']
    rot = json.load(open(a.rotation))
    rotated = {x['key'] for x in rot['기울어진판']} | {x['key'] for x in rot['회전블록']}
    boxed = set()
    if a.boxed_csv:
        import csv
        import unicodedata
        boxed = {unicodedata.normalize('NFC', r['poster'])
                 for r in csv.DictReader(open(os.path.expanduser(a.boxed_csv), encoding='utf-8-sig'))}

    def twin(k):
        return next((i for i, g in enumerate(TWINS) if any(s in k for s in g)), None)

    excluded = collections.defaultdict(list)
    cells = collections.defaultdict(list)
    for k in sorted(raw):
        e = raw[k]
        nl = sum(b['n'] for b in e['blocks'])
        if k in rotated:
            excluded['회전 (기울어진 판 · 회전 블록)'].append(k)
        elif nl > MAX_LINES:
            excluded[f'줄 {MAX_LINES} 초과'].append(k)
        elif k in PRACTICE:
            excluded['연습 판'].append(k)
        else:
            cells[(caps[k]['cap'], '1단' if e.get('n_columns') == 1 else '2단+')].append(k)

    rng = random.Random(SEED)
    for c in sorted(cells):
        rng.shuffle(cells[c])
    used_twin, pool = set(), collections.defaultdict(list)
    # 변형 무리는 칸을 넘어 겹칠 수 있어, 칸을 고정 순서로 돌며 먼저 나온 한 장만 남긴다
    order = [('U', '1단'), ('L', '1단'), ('U', '2단+'), ('L', '2단+')]
    cursor = {c: 0 for c in order}
    while any(cursor[c] < len(cells[c]) for c in order):
        for c in order:
            if cursor[c] >= len(cells[c]):
                continue
            k = cells[c][cursor[c]]
            cursor[c] += 1
            t = twin(k)
            if t is not None and t in used_twin:
                excluded['같은 디자인 변형'].append(k)
                continue
            if t is not None:
                used_twin.add(t)
            pool[c].append(k)

    # 대문자 조건마다 25장, 그 안에서 2단+ 를 가능한 한 반(12 또는 13)으로
    half = N // 2
    take = {}
    for cap in ('U', 'L'):
        n2 = min(len(pool[(cap, '2단+')]), half // 2)
        n1 = half - n2
        if n1 > len(pool[(cap, '1단')]):
            n1 = len(pool[(cap, '1단')])
            n2 = min(len(pool[(cap, '2단+')]), half - n1)
        take[(cap, '1단')], take[(cap, '2단+')] = n1, n2
    chosen = [(c, k) for c in order for k in pool[c][:take[c]]]
    if len(chosen) != N:
        raise SystemExit(f'{N} 장을 채우지 못했다: {len(chosen)} · {take}')
    rng.shuffle(chosen)

    rows, lab = [], []
    for i, (c, k) in enumerate(chosen, 1):
        folder, f = k.split('__', 1)
        p = os.path.join(os.path.expanduser(a.image_root), folder, f)
        e = raw[k]
        h = sha(p)
        rows.append(dict(order=i, key=k, folder=folder, file=f, sha256=h,
                         cap=c[0], columns=c[1], n_columns_pipeline=e.get('n_columns'),
                         lines_pipeline=sum(b['n'] for b in e['blocks']), blocks_pipeline=len(e['blocks']),
                         allcaps_line=caps[k]['allcaps_line'], template=template_of(k),
                         idml_guides=(folder == 'Opernhaus' and any(s in f for s in IDML)),
                         boxed_by_songjunhyeok=(f in boxed)))
        lab.append(dict(order=i, folder=folder, file=f, sha256=h))
    practice = []
    for k in PRACTICE:
        folder, f = k.split('__', 1)
        practice.append(dict(order=len(practice) + 1, folder=folder, file=f,
                             sha256=sha(os.path.join(os.path.expanduser(a.image_root), folder, f))))

    cnt = collections.Counter((r['cap'], r['columns']) for r in rows)
    res = dict(
        note=('라벨러에게 주지 않는다. 대문자 유무는 Claude 눈 판정(사람 판정이 아니다), 단 수 · 줄 수는 파이프라인 값. '
              '탐색용 · 논문 수치 아님'),
        seed=SEED, n=N, max_lines=MAX_LINES,
        cells={f'{a_}·{b_}': cnt[(a_, b_)] for a_, b_ in order},
        pool={f'{a_}·{b_}': len(pool[(a_, b_)]) for a_, b_ in order},
        lines_total=sum(r['lines_pipeline'] for r in rows), blocks_total=sum(r['blocks_pipeline'] for r in rows),
        excluded={k: sorted(v) for k, v in excluded.items()},
        twins=TWINS, practice=PRACTICE, list=rows)
    json.dump(res, open(os.path.join(a.outdir, 'selection.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(dict(note='선 긋기 도구가 읽는 목록. 칸 표시 · 파이프라인 값은 넣지 않는다', seed=SEED,
                   image_root=a.image_root, main=lab, practice=practice),
              open(os.path.join(a.outdir, 'posters_for_labelers.json'), 'w'), ensure_ascii=False, indent=1)
    print(res['cells'], res['pool'], 'lines', res['lines_total'], 'blocks', res['blocks_total'],
          {k: len(v) for k, v in excluded.items()})


if __name__ == '__main__':
    main()
