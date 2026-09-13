"""선 긋기 도구 만들기 — 포스터 원본 바이트와 참조 그림을 template.html 에 박아 HTML 파일 하나로 낸다.

    .venv/bin/python docs/labeling/tool/build.py docs/labeling/posters_for_labelers.json \
        "~/Documents/연구2/브로크만 정리/corpus/코어" docs/labeling/lines.png \
        ~/Documents/poster/labeler/선긋기.html

넣는 것: 포스터 이미지 바이트(줄이거나 다시 압축하지 않는다) · 폴더 · 파일 · sha256 · 크기, 참조 그림.
넣지 않는 것: 검출 상자 · 파이프라인 측정값 · 칸 표시(대문자 · 단 수). 목록 파일에 그런 필드가 있으면 멈춘다.
포스터 이미지가 들어 있으므로 결과 HTML 은 저장소에 두지 않는다.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = 'guides-tool 1.0'
ALLOWED = {'order', 'folder', 'file', 'sha256'}
MIME = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('posters', help='posters_for_labelers.json 모양: {main:[...], practice:[...]}')
    ap.add_argument('image_root')
    ap.add_argument('figure')
    ap.add_argument('out')
    ap.add_argument('--label', default='브로크만 포스터', help='도구 제목에 붙는 이름')
    a = ap.parse_args()

    L = json.load(open(a.posters))
    root = os.path.expanduser(a.image_root)
    items = []
    for set_name in ('practice', 'main'):
        for r in L.get(set_name, []):
            extra = set(r) - ALLOWED
            if extra:
                raise SystemExit(f'목록에 라벨러에게 보이면 안 되는 필드가 있다: {sorted(extra)}')
            p = os.path.join(root, r['folder'], r['file'])
            raw = open(p, 'rb').read()
            h = hashlib.sha256(raw).hexdigest()
            if r.get('sha256') and r['sha256'] != h:
                raise SystemExit(f'sha256 이 목록과 다르다: {p}')
            w, hh = Image.open(p).size
            items.append(dict(set=set_name, order=int(r['order']), folder=r['folder'], file=r['file'],
                              sha256=h, w=w, h=hh, mime=MIME[os.path.splitext(p)[1].lower()],
                              b64=base64.b64encode(raw).decode()))
    fp = hashlib.sha256('\n'.join(f"{i['set']}/{i['order']}/{i['sha256']}" for i in items).encode()).hexdigest()
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    tool = dict(version=VERSION, template_sha256=hashlib.sha256(tpl.encode()).hexdigest()[:16])
    data = dict(schema='typo-guides-data/1', fp=fp, label=a.label,
                built=datetime.datetime.now().isoformat(timespec='seconds'),
                list_file=os.path.basename(a.posters), tool=tool, posters=items)
    fig = base64.b64encode(open(a.figure, 'rb').read()).decode()
    js = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    for key in ('__DATA__', '__FIGURE__'):
        if tpl.count(key) != 1:
            raise SystemExit(f'template 의 {key} 자리가 하나가 아니다')
    html = tpl.replace('__FIGURE__', fig).replace('__DATA__', js)
    os.makedirs(os.path.dirname(os.path.abspath(os.path.expanduser(a.out))), exist_ok=True)
    open(os.path.expanduser(a.out), 'w', encoding='utf-8').write(html)
    n = {s: sum(1 for i in items if i['set'] == s) for s in ('practice', 'main')}
    print(f'{a.out} — 연습 {n["practice"]} · 본 목록 {n["main"]} · {len(html) / 1e6:.1f}MB · fp {fp[:12]} · '
          f'template {tool["template_sha256"]}')


if __name__ == '__main__':
    main()
