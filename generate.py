"""v3 — 축을 «내용이» 정한다. 그리고 활자는 판을 채운다.

v2 에서 축 다섯을 판 폭에 균등 분할했다. 코퍼스가 「축 5개 · 피치 0.106W」
라고 했으니 그렇게 놓았다. 결과는 칸이 너무 넓어 활자가 최소 크기로
쪼그라들고 판의 40% 가 비었다.

**중앙값이 한 판을 다시 세우지 못한다.** 원본의 축은 균등하지 않다 —
칸마다 «그 칸에서 가장 긴 글» 만큼 넓다. 축의 자리는 상수가 아니라
내용에서 나오는 «유도» 다. 우리는 축이 몇 개고 간격이 얼마인지는 쟀지만
그것이 어떻게 «정해지는지» 는 못 쟀다.

여기서는 그 유도를 넣는다.

    ① 칸 너비 = 그 칸 최장 글 + 사이
    ② 활자 크기 = 그렇게 짠 것이 판 높이를 채우는 크기 (이분 탐색)

②도 규칙이다 — 브로크만은 판을 채운다. 「채운다」는 마진에서 이미 쟀다.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 566, 800
ML, MR, MT, MB = 0.037, 0.069, 0.128, 0.087
LEAD = 2.00          # 행간 ÷ x높이 (코퍼스 중앙)
XH_RATIO = 0.52      # 헬베티카 x높이 ÷ em
GUT = 0.30           # 칸 사이 = 활자 크기의 이 배. 잰 것이 아니다
FONT = '/System/Library/Fonts/Helvetica.ttc'
INK = [(26,26,26),(198,92,30),(180,44,48),(40,78,152),(28,112,74)]

def font(px): return ImageFont.truetype(FONT, max(8, int(round(px))), index=0)
def tw(d,t,f): return d.textlength(t,font=f) if t else 0.0

def layout(blocks, d, em):
    """활자 크기 em 에서 칸 자리와 전체 높이를 낸다."""
    ncol = max(len(l) for b in blocks for l in b['lines'])
    wid = [0.0]*ncol
    for b in blocks:
        f = font(em*(1.35 if b['level']==1 else 1))
        for l in b['lines']:
            if len(l) < 2: continue
            for i,fld in enumerate(l):
                wid[i] = max(wid[i], tw(d,fld,f))
    g = em*GUT
    xs=[0.0]
    for i in range(ncol-1): xs.append(xs[-1]+wid[i]+g)
    natural = xs[-1]+wid[-1]
    h = 0.0
    for b in blocks:
        e = em*(1.35 if b['level']==1 else 1)
        h += len(b['lines'])*e*XH_RATIO*LEAD
    return xs, natural, h

def draw(blocks, out, color=True):
    im=Image.new('RGB',(W,H),(232,229,221)); d=ImageDraw.Draw(im)
    x0,x1 = ML*W, W-MR*W
    y0,y1 = MT*H, H-MB*H
    colw, colh = x1-x0, y1-y0
    lo,hi = 8.0, 40.0
    for _ in range(40):
        m=(lo+hi)/2
        xs,nat,h = layout(blocks,d,m)
        # 폭과 높이 «둘 다» 들어가야 한다. 틈은 뒤에 나눠 넣으므로 0.86 까지만 찬다
        (lo,hi) = ((m,hi) if (nat<=colw and h<=colh*0.86) else (lo,m))
    em=lo
    xs,nat,h = layout(blocks,d,em)
    step = em*XH_RATIO*LEAD
    gap = max(step, ((colh-h)/max(len(blocks)-1,1))//step*step)
    y=y0
    for bi,b in enumerate(blocks):
        e=em*(1.35 if b['level']==1 else 1); f=font(e); lh=e*XH_RATIO*LEAD
        col = INK[bi%len(INK)] if color else INK[0]
        for l in b['lines']:
            if len(l)<2:
                if l[0]: d.text((x0,y), l[0], font=f, fill=col, anchor='ls')
            else:
                for i,fld in enumerate(l):
                    if fld: d.text((x0+xs[i], y), fld, font=f, fill=col, anchor='ls')
            y+=lh
        y+=gap
    im.save(out)
    return em, nat/colw, h/colh

# ── 그려 보고 안 것 ────────────────────────────────────────
#
# 브로크만 1965 (글자만 있는 판) 옆에 놓고 봤다. 구조는 선다 — 왼끝 정렬,
# 소문자, 칸에 붙는 낱말, 덩어리마다 다른 색, 여백. 그런데 판으로 안 읽힌다.
#
#   ① 판의 34% 가 빈다 (채움 0.656). 폭이 먼저 걸려서 (0.9985) 활자를
#      더 키울 수 없다. 브로크만은 활자를 키우고 «줄을 다르게 끊어» 폭을
#      맞춘다. 줄 끊기가 우리 어휘에 없다.
#   ② 남은 세로를 덩어리 사이에 골고루 나눠 넣었다. 브로크만은 그러지
#      않고 활자를 키운다. «남으면 고르게 편다» 가 기계의 버릇이다.
#   ③ 칸 나눔이 너무 규칙적이다. 원본은 「1. konzert - dienstag, den 1.
#      juni, 20.15 uhr」를 한 덩이로 두는데 나는 둘로 쪼갰다.
#   ④ 머리글 밑의 가로줄이 없다. 선은 우리가 한 번도 안 쟀다.
#
# 즉 **규칙은 재현되고 선택은 재현되지 않는다.** 결정도에서 나온 「교리는
# 격자를 정하고 칸 선택은 안 정한다」가 눈으로 그대로 나온다. 「AI 티」의
# 정체는 남은 자리를 고르게 펴고, 활자를 겁내고, 지나치게 규칙적으로
# 칸을 나누는 것이다 — 자유도를 쓸 정책이 없어서 전부 «가운데» 를 찍는다.
#
# 안 잰 채로 손으로 넣은 것 (논문에 이렇게 적을 것):
#   글자 내용   easyocr 로 읽고 눈으로 고쳤다
#   칸 나눔     내가 의미로 갈랐다
#   색 다섯 개  개수만 쟀다. 어느 색인지는 원본에서 집어 왔다
#   서체        헬베티카. 악치덴츠-그로테스크가 이 기계에 없다
