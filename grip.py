"""«쥠» — 작가가 규칙을 얼마나 꽉 쥐는가.

여태 갈림 검사는 집단의 «중앙값» 을 견줬다. 그래서 이런 것이 안 보인다.

    브로크만  1.38 ± 0.01     늘 꽉 쥔다
    호프만    1.35 ± 0.20     느슨하다

중앙값은 같고 쥐는 힘이 다르다. 「엄격하다」는 누가 봐도 양식인데 위치만
견주는 검사는 구조적으로 못 본다.

어떻게 재나. 브라운-포사이드다 — 값을 «제 집단 중앙값에서의 거리» 로
바꾼 뒤, 그 위에서 여느 때와 같은 검사를 돌린다. 새 문턱을 짓지 않는다.

    ① 값 → |값 − 제 작가 중앙값|
    ② eta2 를 낸다
    ③ 딱지를 섞는다. 섞을 때마다 중앙값을 «다시» 낸다 — 안 그러면
       원래 묶음의 정보가 귀무에 새어 든다
    ④ 실제 / 귀무문턱 이 2.0 배를 넘으면 «갈림»

같은 값에 두 물음을 거는 것이므로 시험이 두 배가 된다. 본페로니로
나눈다 (distinct.explained 의 n_tests).
"""
import json, os, sys
import numpy as np
sys.path.insert(0,'/Users/junhyeoksong/Documents/poster/files')
import features, distinct, surface, docs_build

NAME={'brockmann':'브로크만','corpus':'호프만','rose':'로제','ruder':'루더'}
ORDER=['브로크만','호프만','로제','루더']
# 오늘 물린 것 — 마스크에서 나온 값은 안 건다
RETRACTED={'활자몫','바탕몫','색면몫','사진몫','면맞음x','면맞음y','면여유x','면여유y'}

vals={n:{k:[] for k in ORDER} for n in features.NAMES}
for c in surface.ROOTS:
    raw=json.load(open(os.path.join(docs_build.CACHE,c+'.json')))['raw']
    X,keys,names=features.matrix(raw)
    for j,n in enumerate(names):
        v=X[:,j]; v=v[np.isfinite(v)]
        vals[n][NAME[c]]=list(map(float,v))

def bf(groups, n_null=2000, seed=11, n_tests=2):
    """브라운-포사이드 + 딱지 섞기. (배수, eta2, 귀무문턱, n)"""
    g=[np.asarray(x,float) for x in groups if len(x)>=5]
    if len(g)<3: return None
    dev=[np.abs(x-np.median(x)) for x in g]
    e=distinct.eta2(dev)
    allv=np.concatenate(g); sizes=[len(x) for x in g]
    rnd=np.random.RandomState(seed); null=[]
    for _ in range(n_null):
        p=rnd.permutation(allv); i=0; gg=[]
        for s in sizes:
            gg.append(p[i:i+s]); i+=s
        null.append(distinct.eta2([np.abs(x-np.median(x)) for x in gg]))
    q=100*(1-distinct.ALPHA/n_tests)
    thr=float(np.percentile(null,q))
    return e/max(thr,1e-9), e, thr, sum(sizes)

print(f"{'지표':<8}{'브':>9}{'호':>9}{'로':>9}{'루':>9}{'':>3}{'쥠 배수':>8}  판정")
print('─'*66)
rows=[]
for n in features.NAMES:
    if n in RETRACTED: continue
    g=[vals[n][k] for k in ORDER]
    r=bf(g)
    if r is None:
        print(f"{n:<8}{'표본 모자람':>40}"); continue
    ratio,e,thr,N=r
    mads=[float(np.median(np.abs(np.asarray(x)-np.median(x)))) if len(x)>=5 else float('nan') for x in g]
    v='갈림' if ratio>=2.0 else ('경계' if ratio>=1.5 else '공통')
    print(f"{n:<8}"+''.join(f"{m:>9.3f}" for m in mads)+f"{'':>3}{ratio:>8.2f}  {v}")
    rows.append(dict(지표=n, MAD=dict(zip(ORDER,[round(m,4) for m in mads])),
                     배수=round(ratio,3), eta2=round(e,4), 귀무=round(thr,4), n=N, 판정=v))

print('\n판정 수:', {k:sum(1 for r in rows if r['판정']==k) for k in ('갈림','경계','공통')})
json.dump(rows, open(os.path.join(os.path.dirname(__file__),'grip.json'),'w'), ensure_ascii=False)
