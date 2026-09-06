"""«선택» — 상황이 같을 때 작가가 다른 것을 고르나.

여태 잰 63개는 전부 «무조건부 스칼라» 다. 「이 판은 행간비가 1.38이더라」.
그런데 정책은 분포가 아니라 사상이다 — 「글자가 이만하면 행간을 이만큼」.

두 사람이 «주변분포가 똑같으면서» 사상이 다를 수 있다. 맡는 일이 다르면
그렇게 된다. 스칼라 검사는 이것을 구조적으로 못 본다.

어떻게 재나.

    ① 상황 S 와 선택 C 를 짝지어 놓는다
    ② 전부 한 줄로 맞춘다        →  RSS_공통
    ③ 작가마다 따로 맞춘다        →  RSS_따로
    ④ 얼마나 좋아졌나 = (공통−따로)/공통
    ⑤ 딱지를 섞어 같은 것을 잰다. 섞어도 좋아지는 만큼이 귀무다
       (칸을 늘리면 늘 좋아지므로, 귀무도 같은 칸 수로 재야 공정하다)

여느 검사와 같은 문턱을 쓴다 — 귀무 분위의 2.0 배.
"""
import json, os, sys
import numpy as np
sys.path.insert(0,'/Users/junhyeoksong/Documents/poster/files')
import surface, docs_build, distinct

NAME={'brockmann':'브로크만','corpus':'호프만','rose':'로제','ruder':'루더'}
ORDER=['브로크만','호프만','로제','루더']
RAW={}
for c in surface.ROOTS:
    RAW[NAME[c]]=json.load(open(os.path.join(docs_build.CACHE,c+'.json')))['raw']

def _rss(S,C):
    if len(S)<3: return float(((C-C.mean())**2).sum())
    A=np.vstack([S,np.ones_like(S)]).T
    b,*_=np.linalg.lstsq(A,C,rcond=None)
    return float(((C-A@b)**2).sum())

def policy(pairs, n_null=2000, seed=5, n_tests=1):
    """pairs = {작가: (S배열, C배열)}"""
    ks=[k for k in ORDER if len(pairs.get(k,([],[]))[0])>=8]
    if len(ks)<3: return None
    S=np.concatenate([pairs[k][0] for k in ks]); C=np.concatenate([pairs[k][1] for k in ks])
    lab=np.concatenate([[i]*len(pairs[k][0]) for i,k in enumerate(ks)])
    def gain(l):
        tot=_rss(S,C)
        sep=sum(_rss(S[l==i],C[l==i]) for i in range(len(ks)))
        return (tot-sep)/max(tot,1e-12)
    g=gain(lab)
    rnd=np.random.RandomState(seed)
    null=[gain(rnd.permutation(lab)) for _ in range(n_null)]
    thr=float(np.percentile(null,100*(1-distinct.ALPHA/n_tests)))
    return g/max(thr,1e-9), g, thr, len(S), ks

# ── 상황·선택 짝 ────────────────────────────────────────────
def poster_pairs(fS, fC):
    out={}
    for k,raw in RAW.items():
        S,C=[],[]
        for r in raw.values():
            try: s,c=fS(r),fC(r)
            except Exception: continue
            if s is None or c is None: continue
            if not (np.isfinite(s) and np.isfinite(c)): continue
            S.append(float(s)); C.append(float(c))
        out[k]=(np.array(S),np.array(C))
    return out

def blocks_ok(r):
    return (r.get('blocks') or []) if abs(r.get('angle',0))<1 else []
def nblocks(r): return len(blocks_ok(r)) or None
def area(r):
    sz=r.get('size'); bs=blocks_ok(r)
    if not sz or not bs or sz[0]<=0: return None
    return sum(max(0,b['x2']-b['x1'])*max(0,b['y2']-b['y1']) for b in bs)/float(sz[0]*sz[1])
def ncols(r): return r.get('n_columns')
def marginL(r):
    sz,rg=r.get('size'),r.get('region')
    return rg[0]/float(sz[0]) if sz and rg and sz[0]>0 and abs(r.get('angle',0))<1 else None
def levels(r):
    xh=sorted({round(b['xh'],1) for b in blocks_ok(r) if b.get('xh')})
    return len(xh) or None
def gy(r):
    sz=r.get('size'); bs=blocks_ok(r)
    if not sz or not bs or sz[1]<=0: return None
    a=np.array([max(0,b['x2']-b['x1'])*max(0,b['y2']-b['y1']) for b in bs],float)
    cy=np.array([(b['y1']+b['y2'])/2 for b in bs],float)
    return float((cy*a).sum()/a.sum()/sz[1]) if a.sum()>0 else None

# 블록 단위 — 행간은 활자 크기의 «함수» 다. 이게 조판의 대표적 정책이다.
def lead_pairs():
    out={}
    for k,raw in RAW.items():
        S,C=[],[]
        for r in raw.values():
            if abs(r.get('angle',0))>=1: continue
            for b in (r.get('blocks') or []):
                L=b.get('lead_measured') or b.get('lead')
                if L and b.get('xh') and b.get('n',0)>=3:
                    S.append(float(b['xh'])); C.append(float(L))
        out[k]=(np.array(S),np.array(C))
    return out

TESTS=[('단수 ~ 블록수',      lambda: poster_pairs(nblocks, ncols)),
       ('단수 ~ 활자넓이',     lambda: poster_pairs(area, ncols)),
       ('블록수 ~ 활자넓이',   lambda: poster_pairs(area, nblocks)),
       ('위계수 ~ 블록수',     lambda: poster_pairs(nblocks, levels)),
       ('마진좌 ~ 블록수',     lambda: poster_pairs(nblocks, marginL)),
       ('마진좌 ~ 활자넓이',   lambda: poster_pairs(area, marginL)),
       ('무게y ~ 블록수',      lambda: poster_pairs(nblocks, gy)),
       ('행간 ~ x높이 (블록)', lead_pairs)]
NT=len(TESTS)
print(f"조건부 검사 {NT}개 · 본페로니 {NT}로 나눔\n")
print(f"{'상황 → 선택':<20}{'좋아짐':>8}{'귀무':>8}{'배수':>8}  판정   n")
print('─'*62)
rows=[]
for nm,f in TESTS:
    r=policy(f(), n_tests=NT)
    if r is None: print(f"{nm:<20}{'표본 모자람':>26}"); continue
    ratio,g,thr,n,ks=r
    v='갈림' if ratio>=2.0 else ('경계' if ratio>=1.5 else '공통')
    print(f"{nm:<20}{g:>8.3f}{thr:>8.3f}{ratio:>8.2f}  {v}  {n}")
    rows.append(dict(짝=nm,좋아짐=round(g,4),귀무=round(thr,4),배수=round(ratio,3),판정=v,n=n,작가=ks))
json.dump(rows,open(os.path.join(os.path.dirname(__file__),'policy.json'),'w'),ensure_ascii=False)
