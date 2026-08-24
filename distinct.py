"""이 지표가 «이 사람 것» 인가 «다들 그러나» 인가.

CV 는 «이 코퍼스 안에서 몰렸나» 를 묻고 discrim 은 «무작위 배치와 다른가» 를
묻는다. 둘 다 통과해도 그 값이 모든 작가에게 같으면 그것은 작가의 규칙이
아니다.

    어센더/x높이   브로크만 1.38 · 호프만 1.35 · 로제 1.40 · 루더 1.38

네 코퍼스가 똑같다. 작가가 아니라 악치덴츠의 성질이다. 그런데 가장 안
흔들리므로 CV 기준에서 가장 먼저 「제약」으로 채택된다. 코퍼스 4종 274장으로
재보니 채택된 지표들의 설명력이 0.3~1.8% 로 바닥이었고, 정작 코퍼스를
가르는 지표(색 수 15%, 좌 마진 12.6%)는 CV 가 커서 전부 탈락해 있었다.
기준이 뒤집혀 있었다.

이것은 **지표의 성질**이지 «이 작가가 남다르다» 가 아니다. 같은 참조 묶음을
쓰면 네 코퍼스 모두 같은 지표가 «갈림» 으로 나온다 — 그 지표가 작가를 가를
힘이 있다는 뜻이지, 이 작가가 그 지표에서 튄다는 뜻이 아니다. 이 코퍼스의
값이 남들 밖에 있는지는 따로 물어야 하고, rules.compare 가 쌍마다 신뢰구간이
갈리는지로 그것을 낸다 (style_card 의 reference).

버리는 기준이 아니라 **표시하는 축**이다. 「브로크만은 행간을 활자높이의
1.5배로 쓴다」는 호프만도 그래도 여전히 브로크만의 규칙이다. 작가를 가르는
지표와 못 가르는 지표를 갈라 보이는 데까지가 이 모듈의 일이고, 무엇을 쓸지는
읽는 쪽이 정한다.

재는 법은 discrim 과 같은 모양이다 — 실제값을 귀무모형과 견준다. 여기서는
코퍼스 딱지를 섞는다. 코퍼스가 적고 크기가 서로 다르면 eta 는 아무것도
없어도 커지므로 절대값으로 자르면 안 된다.
"""
import numpy as np

N_NULL = 200      # 딱지를 몇 번 섞어 볼 것인가. 평균만 다시 내므로 싸다
PCT = 95          # 귀무 분포의 이 분위를 넘으면 «갈림» 로 본다
MIN_PER = 5       # 코퍼스마다 이만큼은 있어야 센다
MIN_CORPORA = 3   # 둘로는 우연히 갈릴 수 있다
SEED = 20260824


def eta2(groups):
    """전체 흩어짐 중 «어느 코퍼스냐» 로 설명되는 몫. 0=전혀 1=완전히."""
    allv = np.concatenate(groups)
    gm = allv.mean()
    sst = float(((allv - gm) ** 2).sum())
    if sst <= 0:
        return None
    ssb = sum(len(g) * (g.mean() - gm) ** 2 for g in groups)
    return float(ssb / sst)


def explained(groups, n_null=N_NULL, seed=SEED):
    """실제 eta2 와, 코퍼스 딱지를 섞었을 때의 분포를 함께 낸다."""
    gs = [np.asarray(g, dtype=float) for g in groups]
    gs = [g for g in gs if len(g) >= MIN_PER]
    if len(gs) < MIN_CORPORA:
        return None
    e = eta2(gs)
    if e is None:
        return None
    sizes = [len(g) for g in gs]
    pool = np.concatenate(gs)
    rnd = np.random.RandomState(seed)
    null = []
    for _ in range(n_null):
        p = rnd.permutation(pool)
        cut, parts = 0, []
        for s in sizes:
            parts.append(p[cut:cut + s]); cut += s
        v = eta2(parts)
        if v is not None:
            null.append(v)
    if not null:
        return None
    thr = float(np.percentile(null, PCT))
    return dict(eta2=round(e, 4), eta2_null=round(thr, 4),
                n_corpora=len(gs), n=int(sum(sizes)),
                scope=('갈림' if e > thr else '공통'))


def by_metric(values_by_corpus):
    """{지표: {코퍼스: 값목록}} → {지표: 설명력}. 셀 수 없는 지표는 뺀다."""
    out = {}
    for key, per in values_by_corpus.items():
        r = explained(list(per.values()))
        if r:
            r['corpora'] = [n for n, v in per.items() if len(v) >= MIN_PER]
            out[key] = r
    return out
