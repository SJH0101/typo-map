"""«스위스 포스터 만들어줘» — 코퍼스를 안 보고, 아는 대로.

이것이 모델이 가진 상식이다. 교과서와 웹에 적힌 스위스 양식 설명을 그대로
따른다. 어디서 왔는지 대라면 「그렇게들 말한다」밖에 없다.

    여백    넉넉하게. 사방 10% 쯤. 「여백이 곧 디자인」
    행간    활자 크기의 1.4 배. 읽기 좋은 표준
    격자    3~4단. 「모듈 격자」
    색      바탕 흰색 · 검정 본문 · 강조 빨강 하나
    정렬    왼끝 맞춤 · 소문자 · 산세리프
    위계    제목 크게, 본문 작게 (2~3배 차이)
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 566, 800
MARGIN = 0.10          # 사방 넉넉하게
LEAD_EM = 1.40         # 활자 크기의 1.4배
HEAD_MULT = 2.2        # 제목은 본문의 2배쯤
BODY_PT = 13           # 「읽기 좋은」 본문 크기
ACCENT = (200, 30, 30) # 스위스 하면 빨강
FONT = '/System/Library/Fonts/Helvetica.ttc'

def font(px): return ImageFont.truetype(FONT, max(8,int(round(px))), index=0)
def tw(d,t,f): return d.textlength(t,font=f) if t else 0.0

def draw(blocks, out):
    im=Image.new('RGB',(W,H),(255,255,255)); d=ImageDraw.Draw(im)
    x0=MARGIN*W; x1=W-MARGIN*W; y0=MARGIN*H
    colw=x1-x0
    y=y0
    stats=[]
    for i,b in enumerate(blocks):
        em = BODY_PT*HEAD_MULT if b['level']==1 else BODY_PT
        f=font(em); lh=em*LEAD_EM
        col = ACCENT if b['level']==1 else (0,0,0)
        for l in b['lines']:
            t=' '.join(x for x in l if x)
            # 넘치면 그리디로 접는다
            cur=''
            for wd_ in t.split():
                s=(cur+' '+wd_).strip()
                if tw(d,s,f)<=colw or not cur: cur=s
                else:
                    d.text((x0,y),cur,font=f,fill=col,anchor='ls'); stats.append(tw(d,cur,f)/colw); y+=lh; cur=wd_
            if cur:
                d.text((x0,y),cur,font=f,fill=col,anchor='ls'); stats.append(tw(d,cur,f)/colw); y+=lh
        y += lh*0.9      # 문단 사이 한 줄쯤
    im.save(out)
    return dict(마진좌=MARGIN, 마진우=MARGIN, 마진상=MARGIN, 마진하=MARGIN,
                활자=BODY_PT, 행간나눔xh=LEAD_EM/0.52,
                채움=(y-lh*0.9-y0)/(H-2*MARGIN*H), 참함=sum(stats)/len(stats), 색수=3)

if __name__ == '__main__':
    from content_1965 import C
    out = sys.argv[1] if len(sys.argv) > 1 else 'gen_naive.png'
    print(out, draw(C, out))
