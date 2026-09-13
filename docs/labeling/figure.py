"""선 네 종류 참조 그림 — 요청서(docs/LABELING_REQUEST.md)와 선 긋기 도구가 같은 그림을 쓴다.

    .venv/bin/python docs/labeling/figure.py docs/labeling/lines.png

선 자리는 Helvetica 글리프의 실제 경계(PIL getbbox)다. 손으로 옮기지 않는다.
"""
import argparse

from PIL import Image, ImageDraw, ImageFont

FONT = '/System/Library/Fonts/Helvetica.ttc'
LABEL = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
PX = 110
COL = {'캡선': (200, 40, 30), '어센더선': (20, 110, 200), 'x높이선': (220, 130, 0), '베이스라인': (30, 140, 70)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    a = ap.parse_args()
    font = ImageFont.truetype(FONT, PX)
    lab = ImageFont.truetype(LABEL, 23)
    top = lambda ch: font.getbbox(ch)[1]
    bot = lambda ch: font.getbbox(ch)[3]
    rows = [
        ('Tonhalle', {'캡선': top('T'), '어센더선': top('h'), 'x높이선': top('x'), '베이스라인': bot('H')},
         ['네 선이 다 있는 줄. 이 글꼴은 캡선과 어센더선이 같은 높이다 — 그래도 둘 다 긋는다.',
          'o 의 둥근 윗·아랫끝이 조금 넘치는 것은 따르지 않는다 (평평한 글자 T · h · n 에 맞춘다).']),
        ('Leitung', {'캡선': top('L'), '어센더선': None, 'x높이선': top('x'), '베이스라인': bot('L')},
         ['t 는 어센더가 아니다 (b d h k l 만). g 의 꼬리는 베이스라인이 아니다.', 'i 의 점은 x높이선이 아니다.']),
        ('musica viva', {'캡선': None, '어센더선': None, 'x높이선': top('x'), '베이스라인': bot('x')},
         ['소문자만 — 대문자 · 어센더가 없으니 캡선 · 어센더선은 «없음». 다른 줄에서 옮겨 오지 않는다.']),
        ('ZÜRICH', {'캡선': top('H'), '어센더선': None, 'x높이선': None, '베이스라인': bot('H')},
         ['대문자만 — x높이선 · 어센더선 «없음». Ü 의 점은 캡선이 아니다.']),
    ]
    W, RH = 1560, 265
    im = Image.new('RGB', (W, RH * len(rows) + 30), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for i, (t, L, caps) in enumerate(rows):
        y0, x0 = 24 + i * RH + 40, 330
        tw = d.textlength(t, font=font)
        d.text((x0, y0), t, font=font, fill=(0, 0, 0))
        for k, v in L.items():
            if v is not None:
                d.line([(x0 - 24, y0 + v), (x0 + tw + 24, y0 + v)], fill=COL[k], width=2)
        last = -99
        for v, k in sorted((v, k) for k, v in L.items() if v is not None):
            ly = max(y0 + v - 14, last + 27)
            last = ly
            d.text((24, ly), k, font=lab, fill=COL[k])
            d.line([(160, ly + 14), (x0 - 28, y0 + v)], fill=COL[k], width=1)
        none = [k for k, v in L.items() if v is None]
        if none:
            d.text((x0 + tw + 50, y0 + 30), '없음: ' + ' · '.join(none), font=lab, fill=(105, 105, 105))
        for j, c in enumerate(caps):
            d.text((24, y0 + PX + 22 + j * 29), c, font=lab, fill=(60, 60, 60))
    im.save(a.out)


if __name__ == '__main__':
    main()
