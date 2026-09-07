"""마진은 상수인가 규칙인가.

머리로 견주면 안 된다 — 한 장을 빼고 나머지로 규칙을 세워 그 장을 맞힌다.
여느 검사와 같은 얼개다.

    ① 중앙값     나머지의 마진 중앙값을 그대로 쓴다 (지금 생성기가 하는 것)
    ② 활자 크기   마진 = k · x높이/판폭.  k 는 나머지에서 맞춘다
    ③ 행간       마진 = k · 행간/판폭
    ④ 글의 양     마진 = a + b · 활자넓이몫
    ⑤ 덩어리 수   마진 = a + b · 블록수

오차는 «판폭 대비 몫» 의 절대오차 중앙값이다. ①보다 크게 낮은 것이 있으면
마진은 상수가 아니라 그것의 함수다.
"""
import json, os, sys
import numpy as np
sys.path.insert(0,'/Users/junhyeoksong/Documents/poster/files')
import surface, docs_build

NAME={'brockmann':'브로크만','corpus':'호프만','rose':'로제','ruder':'루더'}
ORDER=['브로크만','호프만','로제','루더']

def rows_of(raw):
    out=[]
    for k,r in raw.items():
        sz=r.get('size'); rg=r.get('region'); bs=r.get('blocks') or []
        if not sz or not rg or abs(r.get('angle',0))>=1 or sz[0]<=0 or len(bs)<3: continue
        W,H=float(sz[0]),float(sz[1])
        xh=[b['xh'] for b in bs if b.get('xh')]
        ld=[(b.get('lead_measured') or b.get('lead')) for b in bs
            if (b.get('lead_measured') or b.get('lead')) and b.get('n',0)>=3]
        if not xh: continue
        area=sum(max(0,b['x2']-b['x1'])*max(0,b['y2']-b['y1']) for b in bs)/(W*H)
        out.append(dict(
            좌=rg[0]/W, 우=(W-rg[2])/W, 상=rg[1]/H, 하=(H-rg[3])/H,
            xh=float(np.median(xh))/W, xhH=float(np.median(xh))/H,
            행간=(float(np.median(ld))/W if ld else None),
            행간H=(float(np.median(ld))/H if ld else None),
            넓이=area, 블록=len(bs)))
    return out

def loo(rows, target, mode):
    """한 장 빼고 맞히기. 오차 목록을 낸다."""
    errs=[]
    vert = target in ('상','하')
    for i,r in enumerate(rows):
        rest=rows[:i]+rows[i+1:]
        y=np.array([x[target] for x in rest],float)
        if mode=='중앙값':
            p=float(np.median(y))
        else:
            key={'활자':('xhH' if vert else 'xh'),'행간':('행간H' if vert else '행간'),
                 '넓이':'넓이','블록':'블록'}[mode]
            xs=np.array([(x[key] if x[key] is not None else np.nan) for x in rest],float)
            m=np.isfinite(xs)
            if m.sum()<5: continue
            xs,yy=xs[m],y[m]
            if mode in ('활자','행간'):
                k=float(np.median(yy/np.where(xs==0,np.nan,xs)))   # 비례 상수
                v=r[key]
                if v is None or not np.isfinite(v): continue
                p=k*v
            else:
                A=np.vstack([xs,np.ones_like(xs)]).T
                b,*_=np.linalg.lstsq(A,yy,rcond=None)
                v=r[key]
                if v is None or not np.isfinite(v): continue
                p=b[0]*v+b[1]
        errs.append(abs(p-r[target]))
    return np.array(errs)

RAW={NAME[c]: json.load(open(os.path.join(docs_build.CACHE,c+'.json')))['raw'] for c in surface.ROOTS}
MODES=['중앙값','활자','행간','넓이','블록']
for who in ORDER:
    rows=rows_of(RAW[who])
    if len(rows)<12: 
        print(f"\n{who}  판 {len(rows)}장 — 적어서 건너뜀"); continue
    print(f"\n{who}  판 {len(rows)}장   (오차 = 판폭 대비 몫의 절대오차 중앙값)")
    print(f"  {'':<6}"+''.join(f"{m:>10}" for m in MODES))
    for t in ('좌','우','상','하'):
        line=f"  {t:<6}"
        base=None
        for m in MODES:
            e=loo(rows,t,m)
            v=float(np.median(e)) if len(e) else float('nan')
            if m=='중앙값': base=v
            line+=f"{v:>10.4f}"
        print(line)
    # 가장 좋은 것
    print("  "+"─"*52)
    for t in ('좌','우','상','하'):
        res={m: float(np.median(loo(rows,t,m))) for m in MODES}
        b=min(res,key=res.get)
        print(f"  {t}  가장 좋음 {b} {res[b]:.4f}  ·  중앙값 {res['중앙값']:.4f}  ·  {res['중앙값']/max(res[b],1e-9):.2f}배 나음")
