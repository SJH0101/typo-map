"""IDML 가이드로 베이스라인·어센더선을 채점한다 — 방향 확인용 탐색.

사전등록 없이 빠르게 한다. **결과는 논문 수치로 쓰지 않는다** (2026-09-11).
가이드는 공동 연구자(공저자)가 InDesign 에서 오페라하우스 취리히 포스터에 그었다.

옛 채점(~/Documents/poster/out/gt.py · score.py)은 가이드 위치를 y/802×H 로
환산했다. 판(Page)·틀(Rectangle)·그림(Image)의 ItemTransform 을 보지 않았다.
여기서는 그 사슬을 거꾸로 따라가 가이드를 그림 픽셀로 옮긴다.

경로는 모두 인자로 받는다. 한 번에 다시 돌리는 명령은 eval/run_all.py 다.

    python idml_explore.py transforms --idml-dir IDML폴더 --map eval/idml_map.json --posters-dir 포스터폴더
    python idml_explore.py score      --idml-dir IDML폴더 --map eval/idml_map.json --posters-dir 포스터폴더 \\
                                      --out docs/idml_explore.json

--map 은 {IDML 이름: 포스터 파일 이름에 든 글자} (gt.py 의 MAP). 포스터는
--posters-dir/*/*.jpg 에서 찾는다.

가르기: 간격이 PAIR pt 안인 가이드 둘을 짝으로 보고 위를 베이스라인, 아래를
다음 줄 어센더선으로 둔다 (5a67500 과 같은 규칙). 짝이 없거나 셋 넘게 붙은
선은 뺀다. 가이드가 불완전하므로 정밀도·헛검출은 내지 않는다.
"""
import argparse
import glob
import json
import os
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

PAIR = 6.0          # pt
TOLS = (1, 2, 3)    # px


def load_map(path):
    m = json.load(open(os.path.expanduser(path)))
    return m.get('map', m)


def poster(posters_dir, key):
    c = [f for f in glob.glob(os.path.join(os.path.expanduser(posters_dir), '*', '*.jpg'))
         if key in os.path.basename(f)]
    return c[0] if c else None


def _m(s):
    """IDML ItemTransform «a b c d tx ty» → 3×3. x' = a x + c y + tx, y' = b x + d y + ty."""
    a, b, c, d, e, f = (float(v) for v in (s or '1 0 0 1 0 0').split())
    return np.array([[a, c, e], [b, d, f], [0.0, 0.0, 1.0]])


def layout(idml_dir, name):
    """IDML 한 파일 → 판 · 그림 사슬 · 가로 가이드(pt, 판 좌표)."""
    z = zipfile.ZipFile(os.path.join(os.path.expanduser(idml_dir), name + '.idml'))
    spreads = [n for n in z.namelist() if n.startswith('Spreads/')]
    assert len(spreads) == 1, (name, spreads)
    root = ET.fromstring(z.read(spreads[0]))
    parent = {c: p for p in root.iter() for c in p}
    pages = list(root.iter('Page'))
    assert len(pages) == 1, (name, len(pages))
    page = pages[0]
    guides = sorted(float(g.get('Location')) for g in page.iter('Guide')
                    if g.get('Orientation') == 'Horizontal')
    all_h = sum(1 for g in root.iter('Guide') if g.get('Orientation') == 'Horizontal')
    rects = [r for r in root.iter('Rectangle') if r.find('.//Image') is not None]
    assert len(rects) == 1, (name, len(rects))
    img = rects[0].find('.//Image')
    # 그림 안쪽 좌표 → 펼침면 좌표: 그림 ∘ 틀 ∘ (틀을 싼 그룹들)
    T = _m(img.get('ItemTransform'))
    node = img
    while node in parent:
        node = parent[node]
        if node.tag in ('Rectangle', 'Group'):
            T = _m(node.get('ItemTransform')) @ T
    gb = img.find('.//GraphicBounds')
    bounds = [float(gb.get(k)) for k in ('Left', 'Top', 'Right', 'Bottom')]
    ppi = [float(v) for v in (img.get('ActualPpi') or '72 72').split()]
    top, left, bottom, right = (float(v) for v in page.get('GeometricBounds').split())
    return dict(P=_m(page.get('ItemTransform')), T=T, bounds=bounds, ppi=ppi,
                page=(top, left, bottom, right), guides=guides, guides_all=all_h,
                skew=bool(abs(T[0, 1]) > 1e-9 or abs(T[1, 0]) > 1e-9))


def to_px(L, y_pt, W, H):
    """판 좌표 y(pt) → 코퍼스 그림 픽셀 y."""
    top, left, bottom, right = L['page']
    s = L['P'] @ np.array([(left + right) / 2.0, y_pt, 1.0])
    inner = np.linalg.solve(L['T'], s)
    bl, bt, br, bb = L['bounds']
    link_h = (bb - bt) * L['ppi'][1] / 72.0
    return (inner[1] - bt) * L['ppi'][1] / 72.0 * (H / link_h)


def old_px(y_pt, H):
    return y_pt / 802.0 * H          # gt.py · score.py 의 환산


def transforms(idml_dir, posters_dir, mp):
    rows = {}
    for k, v in mp.items():
        L = layout(idml_dir, k)
        p = poster(posters_dir, v)
        W, H = Image.open(p).size
        bl, bt, br, bb = L['bounds']
        link = (round((br - bl) * L['ppi'][0] / 72.0, 1), round((bb - bt) * L['ppi'][1] / 72.0, 1))
        d = [to_px(L, y, W, H) - old_px(y, H) for y in L['guides']]
        rows[k] = dict(판높이_pt=round(L['page'][2] - L['page'][0], 3),
                       그림배율=[round(L['T'][0, 0], 5), round(L['T'][1, 1], 5)],
                       그림위치_pt=[round(L['T'][0, 2], 3), round(L['T'][1, 2] - L['P'][1, 2], 3)],
                       링크그림_px=link, 코퍼스그림_px=[W, H], 기울임=L['skew'],
                       가로가이드=len(L['guides']), 가로가이드_판밖=L['guides_all'] - len(L['guides']),
                       옛환산과_차_px=dict(최대=round(float(np.max(np.abs(d))), 3),
                                        중앙=round(float(np.median(np.abs(d))), 3)))
    return rows


def split(ys):
    ys = sorted(ys)
    groups = [[ys[0]]]
    for y in ys[1:]:
        (groups[-1].append(y) if y - groups[-1][-1] <= PAIR else groups.append([y]))
    B, A, cut = [], [], 0
    for c in groups:
        if len(c) == 2:
            B.append(c[0]); A.append(c[1])
        else:
            cut += len(c)
    return B, A, cut


def measure_old(paths):
    import easyocr
    from baseline import scan
    reader = easyocr.Reader(['de'], gpu=scan.GPU, verbose=False)
    out = {}
    for k, p in paths.items():
        r = scan.measure(p, reader)
        ls = [l for b in r.get('blocks', []) for l in b['lines']]
        out[k] = dict(base=[float((l['p_start'][1] + l['p_end'][1]) / 2) for l in ls],
                      cap=[float((l['p_cap'][0][1] + l['p_cap'][1][1]) / 2) for l in ls if l.get('p_cap')])
    return out


def measure_surya(paths):
    from surya.detection import DetectionPredictor
    import detect_surya as DS
    from measure import ground as G
    det = DetectionPredictor()
    keys = list(paths)
    out = {}
    for i in range(0, len(keys), 8):
        chunk = keys[i:i + 8]
        imgs = [Image.open(paths[k]).convert('RGB') for k in chunk]
        for k, r, im in zip(chunk, det(imgs), imgs):
            lines = [[float(v) for v in b.bbox] for b in r.bboxes]
            bx = DS.boxes_norm(lines, im.size)
            m = G.measure_boxes(paths[k], bx, coords='norm')['boxes']
            out[k] = dict(base=[float(v) for b in m if b.get('n_lines', 0) for v in b['baselines']],
                          cap=[float(v) for b in m if b.get('n_lines', 0) for v in b['caps'] if v is not None])
    return out


def recall(guides_by, meas_by, which):
    """가이드마다 가장 가까운 측정선까지 거리 → 허용 px 별 재현율과 맞은 것의 오차 중앙값."""
    d = []
    for k, gs in guides_by.items():
        ms = np.array(meas_by[k][which], float)
        for g in gs:
            d.append(float(np.min(np.abs(ms - g))) if ms.size else float('inf'))
    d = np.array(d)
    out = {}
    for t in TOLS:
        hit = d[d <= t]
        out[f'±{t}px'] = dict(재현율=round(float(hit.size / d.size), 3), 맞음=int(hit.size), 전체=int(d.size),
                              오차중앙_px=(round(float(np.median(hit)), 2) if hit.size else None))
    return out


def score(idml_dir, posters_dir, mp, out_path):
    paths, Bn, An, Bo, Ao, cut = {}, {}, {}, {}, {}, 0
    for k, v in mp.items():
        L = layout(idml_dir, k)
        p = poster(posters_dir, v)
        W, H = Image.open(p).size
        paths[k] = p
        B, A, c = split(L['guides'])
        cut += c
        Bn[k] = [to_px(L, y, W, H) for y in B]; An[k] = [to_px(L, y, W, H) for y in A]
        Bo[k] = [old_px(y, H) for y in B];      Ao[k] = [old_px(y, H) for y in A]
    meas = {'옛 경로 (EasyOCR+detect.run)': measure_old(paths),
            'Surya 경로 (Surya→group→ground)': measure_surya(paths)}
    res = dict(
        무엇='IDML 가로 가이드(공동 연구자가 그음)로 베이스라인·어센더선 재현율과 오차',
        용도='방향 확인용 탐색. 사전등록 없음. 논문 수치로 쓰지 않는다',
        가르기=dict(규칙=f'간격 {PAIR}pt 안의 가이드 둘 = 위 베이스라인 · 아래 어센더선. 짝 없는 선·셋 이상 붙은 선은 뺐다',
                  베이스라인=sum(map(len, Bn.values())), 어센더선=sum(map(len, An.values())), 뺀선=cut),
        환산=transforms(idml_dir, posters_dir, mp),
        결과={})
    for name, m in meas.items():
        res['결과'][name] = dict(베이스라인=recall(Bn, m, 'base'), 어센더선=recall(An, m, 'cap'),
                               옛환산으로_베이스라인=recall(Bo, m, 'base'),
                               측정줄=sum(len(x['base']) for x in m.values()))
    json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res['가르기'], ensure_ascii=False))
    for name, v in res['결과'].items():
        print(name, '측정줄', v['측정줄'])
        for part in ('베이스라인', '어센더선', '옛환산으로_베이스라인'):
            print('  ', part, {t: (x['재현율'], x['오차중앙_px']) for t, x in v[part].items()})
    print('→', out_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description='IDML 가이드 탐색 채점. 경로는 모두 인자로 받는다.')
    ap.add_argument('cmd', choices=['transforms', 'score'])
    ap.add_argument('--idml-dir', required=True, help='IDML 파일 폴더')
    ap.add_argument('--map', required=True, help='{IDML 이름: 포스터 파일 이름 글자} JSON')
    ap.add_argument('--posters-dir', required=True, help='포스터 폴더 (그 아래 */*.jpg)')
    ap.add_argument('--out', help='score 결과 JSON')
    a = ap.parse_args(argv)
    mp = load_map(a.map)
    if a.cmd == 'transforms':
        for k, v in transforms(a.idml_dir, a.posters_dir, mp).items():
            print(k, json.dumps(v, ensure_ascii=False))
    else:
        if not a.out:
            ap.error('score 는 --out 이 필요하다')
        score(a.idml_dir, a.posters_dir, mp, a.out)


if __name__ == '__main__':
    main()
