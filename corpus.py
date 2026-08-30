"""작가 하나를 «내려받은 것» 에서 «잰 것» 까지 한 번에.

    python corpus.py build --csv metadata.csv --images ./내려받음 --name 로이핀

여태 세 단계가 따로였다. 크롬 확장이 이미지와 CSV 를 뱉고, tkinter GUI
정리기가 폴더로 나누고, 그다음에야 우리가 쟀다. 작가 하나 붙일 때마다
GUI 를 띄워야 했다.

**판형을 빼지 않고 적어 둔다.** 옛 정리기는 Weltformat(≈128×90cm) 만
«코어» 로 남기고 나머지를 제외_판형으로 버렸다. 로제는 43장 중 14장이
그렇게 빠져 25장이 됐고, 그 25장으로는 뇌를 만들 수 없다 (63장 필요).

버릴 이유가 약하다. 우리 지표는 거의 다 «비율» 이다 — 마진은 폭 대비,
덮음은 면적 대비. 판형이 다르면 값이 달라지는지는 **재보면 되는 물음** 이지
미리 빼서 답을 없앨 일이 아니다. 판형을 열로 남기면 나중에 그것으로
설명되는 몫을 따로 뺄 수 있다.

버리는 것은 둘만 남긴다.
    비율불일치   스캔 가로세로비가 적힌 실물 치수와 3% 넘게 다르다.
                 측정 오류이지 디자인이 아니다.
    타인명의     designer 열이 이 작가로 시작하지 않는다.
"""
import argparse
import csv
import json
import os
import re
import shutil

WELT = 1.4142
RATIO_TOL = 3.0     # 스캔 비와 실물 비가 이보다 어긋나면 뺀다 (%)
EPS = 0.03          # 가로세로비가 √2 에서 이만큼 벗어나면 «기타판형»


def _f(v, d=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def fmt_family(r):
    """판형 이름. 버리지 않고 적어 두려고 낸다."""
    h, w = _f(r.get('h_cm')), _f(r.get('w_cm'))
    if not h or not w or h <= 0 or w <= 0:
        return '불명'
    if abs(h / w - WELT) > EPS:
        return '기타판형'
    return 'Weltformat' if h >= 120 else ('F4' if h >= 95 else '소형')


def safe(s, n=60):
    s = re.sub(r'[/\\:*?"<>|\n\r\t]', '-', str(s))
    return re.sub(r'\s+', ' ', s).strip(' .')[:n] or 'untitled'


def year_of(r):
    y = str(r.get('year', '')).strip()
    return y if re.fullmatch(r'(19|20)\d{2}', y) else '연도미상'


def plan(rows, designer_prefix=None):
    """CSV 행 → 어디로 갈지. 버리는 것은 이유와 함께."""
    out = []
    for r in rows:
        keep, why = True, None
        if designer_prefix and not str(r.get('designer', '')).strip().startswith(designer_prefix):
            keep, why = False, '타인명의'
        elif (_f(r.get('ratio_diff_pct'), 999) or 999) >= RATIO_TOL:
            keep, why = False, '비율불일치'
        out.append(dict(row=r, keep=keep, why=why, fmt=fmt_family(r),
                        year=year_of(r), title=safe(r.get('title', ''))))
    return out


def build(csv_path, images, name, out_root, designer_prefix=None, move=False):
    with open(csv_path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    P = plan(rows, designer_prefix)
    base = os.path.join(out_root, name)
    kept = os.path.join(base, '판')
    os.makedirs(kept, exist_ok=True)
    man, miss = [], []
    for p in P:
        r = p['row']
        src = _find(images, r)
        if not src:
            miss.append(r.get('title', '')[:40])
            continue
        if not p['keep']:
            d = os.path.join(base, '뺌_' + p['why'])
        else:
            d = kept
        os.makedirs(d, exist_ok=True)
        fn = f"{p['year']}_{p['title']}{os.path.splitext(src)[1]}"
        dst = os.path.join(d, fn)
        (shutil.move if move else shutil.copy2)(src, dst)
        man.append(dict(file=fn, path=dst, keep=p['keep'], why=p['why'],
                        판형=p['fmt'], year=p['year'],
                        title=r.get('title'), url=r.get('url'),
                        h_cm=_f(r.get('h_cm')), w_cm=_f(r.get('w_cm'))))
    json.dump(dict(name=name, n=len(man), manifest=man, not_found=miss),
              open(os.path.join(base, 'manifest.json'), 'w'), ensure_ascii=False, indent=1)
    return base, man, miss


def _find(images, r):
    """CSV 행에 맞는 이미지 파일을 찾는다. 확장이 붙인 이름이 제각각이라 여러 수를 쓴다."""
    for key in ('new_path', 'file', 'filename', 'image'):
        v = r.get(key)
        if v:
            for cand in (v, os.path.basename(v)):
                p = os.path.join(images, cand)
                if os.path.exists(p):
                    return p
    t = safe(r.get('title', ''), 40).lower()
    if not t:
        return None
    for f in os.listdir(images):
        if t[:24] and t[:24] in f.lower():
            return os.path.join(images, f)
    return None


def main():
    ap = argparse.ArgumentParser(description='작가 하나를 코퍼스로 만들고 잰다')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='CSV + 이미지 → 코퍼스 폴더')
    b.add_argument('--csv', required=True)
    b.add_argument('--images', required=True)
    b.add_argument('--name', required=True)
    b.add_argument('--out', default=os.path.expanduser('~/Documents/연구2/코퍼스'))
    b.add_argument('--designer-prefix', default=None,
                   help='designer 열이 이것으로 시작해야 한다. 비우면 전부')
    b.add_argument('--move', action='store_true')
    b.add_argument('--measure', action='store_true', help='만들고 바로 잰다')
    a = ap.parse_args()

    base, man, miss = build(a.csv, a.images, a.name, a.out, a.designer_prefix, a.move)
    from collections import Counter
    keep = [m for m in man if m['keep']]
    print(f"{a.name} — 전체 {len(man)} · 남김 {len(keep)} · 뺌 {len(man)-len(keep)}")
    print('  뺀 이유:', dict(Counter(m['why'] for m in man if not m['keep'])))
    print('  판형   :', dict(Counter(m['판형'] for m in keep)))
    if miss:
        print(f'  이미지 못 찾음 {len(miss)}장:', miss[:5])
    print(f'  → {base}')
    if a.measure:
        print('\n재는 중…')
        import measure_corpus
        measure_corpus.run(os.path.join(base, '판'), a.name)


if __name__ == '__main__':
    main()
