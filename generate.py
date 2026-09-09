"""v4 — 폭을 글에 맞춘다. 그리고 남으면 «활자를 키운다».

v3 는 판의 34% 가 비었다. 글을 정해진 폭에 맞추려다 폭이 먼저 걸려 활자를
못 키웠기 때문이다. 재보니 브로크만은 반대로 한다.

    그리디      참함 0.957 · 마지막 줄 0.669   꽉 채우고 마지막만 짧다
    고르게      참함 0.957 · 마지막 줄 0.967
    실측 브    참함 0.865 · 마지막 줄 0.887

둘 다 아니다. 마지막 줄이 안 짧으니 그리디가 아니고, 0.86 이라 폭을 꽉
채우지도 않는다. **뜻 단위로 끊고 폭이 그것을 따라간다.**

그래서 v4 는 순서를 뒤집는다.

    ① 뜻 단위(칸)로 끊는다 — 끊을 자리는 내용이 준다
    ② 그 상태에서 «판 높이를 채우는» 크기를 찾는다
    ③ 폭이 넘치면 그 줄만 한 번 더 접는다 (그래도 활자를 안 줄인다)

②가 핵심이다. v3 는 폭을 지키려고 활자를 줄였고 v4 는 높이를 채우려고
활자를 키운다. 「남으면 고르게 편다」가 기계의 버릇이고 「남으면 키운다」
가 사람의 버릇이다.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 566, 800
ML, MR, MT, MB = 0.037, 0.069, 0.128, 0.087
LEAD, XH = 2.00, 0.52
FONT = '/System/Library/Fonts/Helvetica.ttc'
INK = [(26,26,26),(198,92,30),(180,44,48),(40,78,152),(28,112,74)]

def font(px): return ImageFont.truetype(FONT, max(8,int(round(px))), index=0)
def tw(d,t,f): return d.textlength(t,font=f) if t else 0.0

def flow(blocks, d, em, colw):
    """칸을 이어 붙이고, 넘치면 뜻 경계에서 접는다. → 줄 목록."""
    out=[]
    for b in blocks:
        e = em*(1.35 if b['level']==1 else 1); f=font(e)
        lines=[]
        for l in b['lines']:
            fields=[x for x in l if x]
            cur=[]
            for fld in fields:
                t=' '.join(cur+[fld])
                if tw(d,t,f) <= colw or not cur:
                    cur.append(fld)
                else:
                    lines.append(' '.join(cur)); cur=[fld]
            if cur: lines.append(' '.join(cur))
        out.append((b, e, lines))
    return out

def height(flowed, gapn):
    h=sum(len(ls)*e*XH*LEAD for _b,e,ls in flowed)
    return h + gapn*max(len(flowed)-1,1)

def draw(blocks, out, color=True):
    im=Image.new('RGB',(W,H),(232,229,221)); d=ImageDraw.Draw(im)
    x0,x1 = ML*W, W-MR*W; y0,y1 = MT*H, H-MB*H
    colw, colh = x1-x0, y1-y0
    # 높이를 채우는 크기를 찾는다. 틈은 한 줄 높이로 고정 — 남는다고 벌리지 않는다
    lo,hi=8.0,44.0
    for _ in range(44):
        m=(lo+hi)/2
        fl=flow(blocks,d,m,colw)
        (lo,hi)=((m,hi) if height(fl, m*XH*LEAD) <= colh else (lo,m))
    em=lo; fl=flow(blocks,d,em,colw); gap=em*XH*LEAD
    y=y0
    for i,(b,e,ls) in enumerate(fl):
        f=font(e); lh=e*XH*LEAD
        col=INK[i%len(INK)] if color else INK[0]
        for t in ls:
            d.text((x0,y), t, font=f, fill=col, anchor='ls'); y+=lh
        y+=gap
    im.save(out)
    fills=[tw(d,t,font(e))/colw for _b,e,ls in fl for t in ls]
    return em, sum(fills)/len(fills), (y-gap-y0)/colh

if __name__ == '__main__':
    # 불러오기만으로 그림이 그려지면 안 된다. 부를 때만 그린다.
    from content_1965 import C
    out = sys.argv[1] if len(sys.argv) > 1 else 'gen_v4.png'
    em, fill, page = draw(C, out)
    print(f'{out}  활자 {em:.1f}px · 줄참함 {fill:.3f} · 판채움 {page:.3f}')
