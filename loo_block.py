"""사후 후속 — 규칙을 «블록» 층에서 시험한다. 못 박은 것 밖이므로 그렇게 적는다.

판 층에서 C가 졌다. 그런데 「행간은 활자 크기를 따라간다」는 원래 «한 덩어리
안» 의 관계다. 판의 «중앙값 xh» 는 표제 40px 와 본문 9px 를 섞은 값이라,
그것을 곱하면 없애는 잡음보다 넣는 잡음이 클 수 있다.

그래서 같은 물음을 블록 하나 단위로 다시 던진다. 딱지는 «판» 단위로 뺀다 —
같은 판의 다른 블록으로 그 블록을 맞히면 새는 것이다.
"""
import json, os, sys
import numpy as np
sys.path.insert(0,'/Users/junhyeoksong/Documents/poster/files')
import surface, docs_build

rows=[]
for c in surface.ROOTS:
    raw=docs_build.load_raw(c)
    for k,r in raw.items():
        sz=r.get('size')
        if not sz or abs(r.get('angle',0))>=1 or sz[1]<=0: continue
        H=float(sz[1])
        for b in (r.get('blocks') or []):
            L=b.get('lead_measured') or b.get('lead')
            if L and b.get('xh') and b.get('n',0)>=3:
                rows.append(dict(판=k, xh=b['xh']/H, lead=L/H))
print(f"블록 {len(rows)}개 · 판 {len(set(r['판'] for r in rows))}장\n")

keys=sorted(set(r['판'] for r in rows))
errA=[];errC=[];errB=[]
for k in keys:
    rest=[r for r in rows if r['판']!=k]
    mine=[r for r in rows if r['판']==k]
    a=float(np.median([r['lead'] for r in rest]))
    c=float(np.median([r['lead']/r['xh'] for r in rest]))
    for r in mine:
        errA.append(abs(a-r['lead']))
        errC.append(abs(c*r['xh']-r['lead']))
        errB.append(abs(1.40/0.52*r['xh']-r['lead']))
A=np.array(errA);C=np.array(errC);B=np.array(errB)
w=int((C<A).sum()); l=int((C>A).sum()); t=int((C==A).sum()); n=w+l
z=(w-n/2)/np.sqrt(n/4) if n else float('nan')
print(f"{'':<10}{'중앙 오차':>11}{'사분위':>22}")
for nm,v in (('A 중앙값',A),('B 통념',B),('C 규칙',C)):
    print(f"{nm:<10}{np.median(v):>11.5f}   [{np.percentile(v,25):.5f}, {np.percentile(v,75):.5f}]")
print(f"\nC÷A  {np.median(C)/np.median(A):.3f}")
print(f"C가 더 가까운 블록  {w}/{n}  (동점 {t})   부호검정 z = {z:.2f}")
json.dump(dict(블록=len(rows), A=float(np.median(A)), B=float(np.median(B)), C=float(np.median(C)),
               비=float(np.median(C)/np.median(A)), 이긴블록=w, 전체=n, z=float(z)),
          open('/private/tmp/claude-501/-Users-junhyeoksong-Documents-poster-files/1001d578-0384-4369-8e61-ae37a78e5516/scratchpad/loo2.json','w'), ensure_ascii=False)
