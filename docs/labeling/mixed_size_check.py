"""한 줄에 크기가 다른 글자가 섞일 때 파이프라인의 재기(measure/region.py)가 무엇을 내는가. 탐색용 · 논문 수치 아님.

    .venv/bin/python docs/labeling/mixed_size_check.py "~/Documents/연구2/브로크만 정리/corpus/코어" \
        docs/labeling/mixed_size_check.json

선 긋기 요청서 5절 «크기 섞임» 규칙을 정하려고 돌렸다. 두 가지를 본다.
    렌더    Helvetica 로 작은 딸림말 + 큰 이름을 한 줄에 그려, 정답 위치와 measure 결과를 견준다
    실물    선정 50장 중 네 판에서, 캐시의 큰 글 블록 상자(작은 글이 들어감)와 작은 글을 뺀 상자를 각각 잰다
실물 상자는 ~/.typo-mcp/brockmann.json (surya+ground, 9b252ed) 의 블록 상자이고, «뺀 상자» 의 왼 · 오른 끝은
Claude 가 3배 확대 이미지를 보고 정했다.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from measure import region  # noqa: E402 — 저장소 뿌리의 재기 코드를 그대로 부른다

FONT = '/System/Library/Fonts/Helvetica.ttc'

RENDER = {
    '작은 딸림말 + 큰 이름 (같은 베이스라인)': [('leitung', 11, 0), ('otto', 11, 0), ('klemperer', 34, 0)],
    '큰 이름 + 작은 딸림말': [('Ferenc Fricsay', 30, 0), ('leitung', 10, 0)],
    '작은 대문자 이름 + 큰 소문자': [('Carl', 12, 0), ('schuricht', 34, 0)],
    '작은 글이 큰 글 가운데 높이 (베이스라인 다름)': [('leitung', 11, -10), ('klemperer', 34, 0)],
    '큰 글만 (대조)': [('klemperer', 34, 0)],
}

REAL = [
    ('Tonhalle_Konzert', '1955_Ferenc Fricsay - Leitung - Arthur Rubinstein - Solist - Tonh.jpg',
     (53, 465, 288, 513), (53, 465, 248, 513), '큰 이름 오른쪽의 작은 «leitung» «solist»'),
    ('Tonhalle_Konzert', '1957_Extra-Konzert - Leitung Carl Schuricht - Violine Johanna Mar.jpg',
     (327, 492, 554, 597), (362, 492, 554, 597), '큰 이름 왼쪽의 작은 «leitung» «violine» (다른 색 면)'),
    ('Juni_Festwochen', '1957_Juni-Festwochen Zürich 1957 - Tonhalle Grosser Saal - 4. Jun.jpg',
     (55, 237, 288, 409), (116, 237, 288, 409), '큰 성 왼쪽의 작은 이름 «carl» «maria» …'),
    ('Juni_Festwochen', '1956_Juni-Festwochen Zürich 1956 - 1. Juni-Festkonzert - Leitung .jpg',
     (49, 479, 220, 618), (80, 479, 220, 618), '큰 성 왼쪽의 작은 이름 «otto» «nathan»'),
]


def render(parts, W=700, H=120, base=80):
    im = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(im)
    x, truth = 10, []
    for text, px, dy in parts:
        f = ImageFont.truetype(FONT, px)
        y = base + dy - f.getmetrics()[0]
        d.text((x, y), text, font=f, fill=0)
        bb = d.textbbox((x, y), text, font=f)
        truth.append(dict(text=text, px=px, cap_top=f.getbbox('H')[1] + y, x_top=f.getbbox('x')[1] + y,
                          baseline=f.getbbox('H')[3] + y))
        x = bb[2] + px * 0.5
    return np.asarray(im).astype(float), truth


def pick(m):
    return dict(n_lines=m['n_lines'], baselines=m['baselines'], caps=m['caps'], x_tops=m['x_tops'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image_root')
    ap.add_argument('out')
    a = ap.parse_args()
    rend = []
    for name, parts in RENDER.items():
        g, truth = render(parts)
        rend.append(dict(case=name, truth=truth, measure=pick(region.measure(g, (2, 2, 698, 118)))))
    real = []
    for folder, f, full, trim, what in REAL:
        p = os.path.join(os.path.expanduser(a.image_root), folder, f)
        A, B = pick(region.measure(p, full)), pick(region.measure(p, trim))
        diff = {k: [(i, x, y) for i, (x, y) in enumerate(zip(A[k], B[k])) if x != y] for k in ('baselines', 'caps', 'x_tops')}
        real.append(dict(folder=folder, file=f, what=what, box_with_small=full, box_without_small=trim,
                         with_small=A, without_small=B, differs={k: v for k, v in diff.items() if v}))
    res = dict(
        note='탐색용 · 논문 수치 아님',
        render=rend, real=real,
        conclusion=[
            '크기가 섞인 한 줄은 한 줄로 잡히고, 베이스라인 · 캡 · x높이 윗끝은 큰 글자의 값이다. 작은 글자는 재지 않는다 — 베이스라인이 달라도 그렇다 (렌더 다섯 경우).',
            '실물 네 판 중 셋은 작은 글이 상자에 들어가도 값이 같았다. 1957 Juni-Festwochen 4. 은 두 값이 1px 달라졌다 (작은 글 잉크가 행 합에 더해져 절반 문턱 행이 움직임).',
            '묶기 단계(detect_surya.group)는 작은 딸림말을 크기 계층(H_RATIO)으로 큰 글과 따로 두지만, Surya 줄 상자가 작은 글까지 덮으면 큰 글 블록 상자가 작은 글 자리까지 늘어난다. 작은 글이 따로 1줄 블록으로도 잡히거나(겹쳐 두 번 잼), 넓이 200px² 미만이라 버려진다.',
            '따라서 요청서 규칙: 가로로 틈을 둔 다른 크기 무리는 따로 블록, 가를 수 없으면 큰 글자에 선. 사람의 큰 글 블록 선이 파이프라인 큰 글 블록 값과 같은 대상을 가리키고, 파이프라인이 작은 글을 삼킨 것은 선 차이가 아니라 블록 차이로 드러난다.'])
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    for r in real:
        print(r['file'][:40], '같음' if not r['differs'] else r['differs'])


if __name__ == '__main__':
    main()
