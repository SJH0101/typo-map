"""블록 단위 «선택» 검사 — 판을 중앙값으로 뭉개지 않는다.

283장을 판마다 한 수로 줄이면 자료가 283개다. 그런데 그 안에 블록이
3,268개 있다. 로제는 판이 25장뿐이지만 블록은 177개다. 표본을 못 늘려도
이것은 이미 있다.

한 가지를 지켜야 한다. **한 판 안의 블록은 서로 독립이 아니다.** 딱지를
블록 단위로 섞으면 귀무가 실제보다 «흩어져» 배수가 부풀려진다. 판 단위로
섞는다 — 판 하나가 통째로 다른 작가에게 간다. 그러면 판 안의 뭉침이
실제와 귀무에 똑같이 들어간다.

(앞선 policy.py 의 「행간~x높이」는 블록 단위로 섞었다. 틀렸다. 값이
1.10 이라 결론은 안 바뀌지만 여기서 다시 낸다.)
"""
import json, os, sys
import numpy as np
sys.path.insert(0,'/Users/junhyeoksong/Documents/poster/files')
import surface, docs_build, distinct

NAME={'brockmann':'브로크만','corpus':'호프만','rose':'로제','ruder':'루더'}
ORDER=['브로크만','호프만','로제','루더']
RAW={NAME[c]: json.load(open(os.path.join(docs_build.CACHE,c+'.json')))['raw']
     for c in surface.ROOTS}

def collect(fn):
    """fn(r, b, W, H) → (S, C) 또는 None. 판 번호를 함께 낸다."""
    S=[];C=[];pid=[];lab=[]
    pi=0
    for gi,k in enumerate(ORDER):
        for r in RAW[k].values():
            sz=r.get('size')
            if not sz or sz[0]<=0 or sz[1]<=0 or abs(r.get('angle',0))>=1: continue
            bs=r.get('blocks') or []
            got=False
            for b in bs:
                v=fn(r,b,float(sz[0]),float(sz[1]))
                if v is None: continue
                s,c=v
                if not (np.isfinite(s) and np.isfinite(c)): continue
                S.append(s);C.append(c);pid.append(pi);lab.append(gi);got=True
            if got: pi+=1
    return (np.array(S,float),np.array(C,float),np.array(pid),np.array(lab))

def _rss(s,c):
    if len(s)<3: return float(((c-c.mean())**2).sum()) if len(c) else 0.0
    A=np.vstack([s,np.ones_like(s)]).T
    b,*_=np.linalg.lstsq(A,c,rcond=None)
    return float(((c-A@b)**2).sum())

def test(S,C,pid,lab,n_null=2000,seed=3,n_tests=1):
    ks=sorted(set(lab))
    if len(ks)<3: return None
    def gain(l):
        t=_rss(S,C); sep=sum(_rss(S[l==i],C[l==i]) for i in ks)
        return (t-sep)/max(t,1e-12)
    g=gain(lab)
    # 판 단위로 섞는다 — 판의 딱지를 바꾸고 그 판의 모든 블록이 따라간다
    P=np.unique(pid); plab=np.array([lab[pid==p][0] for p in P])
    rnd=np.random.RandomState(seed); null=[]
    for _ in range(n_null):
        q=rnd.permutation(plab)
        m=dict(zip(P,q)); null.append(gain(np.array([m[p] for p in pid])))
    thr=float(np.percentile(null,100*(1-distinct.ALPHA/n_tests)))
    r=g/max(thr,1e-9)
    v='경계' if abs(r-2.0)<=0.5 else ('갈림' if r>=2.0 else '공통')
    return r,g,thr,len(S),len(P),v

def lead(r,b,W,H):
    L=b.get('lead_measured') or b.get('lead')
    return (float(b['xh']),float(L)) if L and b.get('xh') and b.get('n',0)>=3 else None
def leftxh(r,b,W,H):
    return (float(b['xh']),float(b['x1'])/W) if b.get('xh') else None
def lefty(r,b,W,H):
    return (float((b['y1']+b['y2'])/2)/H, float(b['x1'])/W)
def widthxh(r,b,W,H):
    return (float(b['xh']), float(b['x2']-b['x1'])/W) if b.get('xh') else None
def rightxh(r,b,W,H):
    return (float(b['xh']), float(W-b['x2'])/W) if b.get('xh') else None

TESTS=[('행간 ~ x높이',lead),('왼끝 ~ x높이',leftxh),('왼끝 ~ 세로위치',lefty),
       ('블록너비 ~ x높이',widthxh),('오른끝 ~ x높이',rightxh)]
NT=len(TESTS)
print(f"블록 단위 · 판 단위로 딱지 섞음 · 본페로니 {NT}\n")
print(f"{'상황 → 선택':<18}{'좋아짐':>8}{'귀무':>8}{'배수':>7}  판정   블록    판")
print('─'*62)
rows=[]
for nm,f in TESTS:
    S,C,pid,lab=collect(f)
    r=test(S,C,pid,lab,n_tests=NT)
    if r is None: continue
    ratio,g,thr,n,np_,v=r
    print(f"{nm:<18}{g:>8.3f}{thr:>8.3f}{ratio:>7.2f}  {v}  {n:>5}{np_:>6}")
    rows.append(dict(짝=nm,좋아짐=round(g,4),귀무=round(thr,4),배수=round(ratio,3),판정=v,블록=n,판=np_))
json.dump(rows,open(os.path.join(os.path.dirname(__file__),'block.json'),'w'),ensure_ascii=False)
