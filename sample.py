"""뇌에서 «한 장 분량의 값 묶음» 을 뽑는다.

전에 생성이 실패한 이유가 여기 있었다. 값을 지표마다 따로 뽑으니 각 값은
브로크만 범위 안인데 합쳐 놓으면 브로크만이 아니었다. 「그냥 배끼는 거잖아」
소리를 들은 그 시도다.

뇌가 더한 것이 선이다. 선을 지키며 뽑으려면 «같이» 뽑아야 한다.

    ① 뇌의 선만 남긴 정밀도 행렬을 세운다 (선이 아닌 칸은 0)
    ② 그것을 뒤집어 그 그래프가 함의하는 상관 행렬을 얻는다
    ③ 그 상관으로 다변량 정규를 뽑는다
    ④ 각 값을 그 지표의 «실제 분포» 로 되돌린다 (순위 → 분위수)

④ 가 있어야 주변분포도 맞는다. ③ 만 하면 관계는 맞는데 값이 정규분포가
되어 버린다. 코퓰러라고 부르는 방식이고, 여기서 쓰는 이유는 하나다 —
브로크만의 마진은 정규분포가 아니라 0 에 붙어 있고 꼬리가 길다.

비교를 위해 «따로 뽑기» 도 함께 둔다. 둘을 같은 잣대로 재봐야 선이 일을
하는지 알 수 있다.
"""
import numpy as np

import brain
import features


def _corr_from_edges(X, edges, names, shrink=brain.SHRINK):
    """뇌의 선만 남긴 정밀도 행렬 → 그 그래프가 함의하는 상관 행렬."""
    R = brain._ranks(X)
    masks = [~np.isnan(R[:, j]) for j in range(R.shape[1])]
    C = brain._corr(R, masks)
    Pc = brain._partial(C, shrink)

    ix = {n: i for i, n in enumerate(names)}
    keep = np.zeros_like(Pc, dtype=bool)
    for e in edges:
        if e['a'] in ix and e['b'] in ix:
            keep[ix[e['a']], ix[e['b']]] = keep[ix[e['b']], ix[e['a']]] = True

    # 선이 아닌 칸의 편상관을 0 으로 — 그래프가 말한 것만 남긴다
    P = Pc.shape[0]
    T = np.eye(P)
    for i in range(P):
        for j in range(i + 1, P):
            if keep[i, j]:
                T[i, j] = T[j, i] = -Pc[i, j]
    w = np.linalg.eigvalsh(T)
    if w.min() <= 1e-6:                      # 양정치가 아니면 대각을 키운다
        T = T + (abs(w.min()) + 0.05) * np.eye(P)
    S = np.linalg.inv(T)
    d = np.sqrt(np.diag(S))
    return S / np.outer(d, d)


def _quantile(col, u):
    """그 지표의 실제 값 분포에서 u 분위를 꺼낸다."""
    v = np.sort(col[~np.isnan(col)])
    if not len(v):
        return float('nan')
    return float(np.interp(u, np.linspace(0, 1, len(v)), v))


def draw(raw, edges, n=1, seed=0, joint=True):
    """joint=True 면 선을 지키며, False 면 지표마다 따로 뽑는다."""
    X, _keys, names = features.matrix(raw)
    rnd = np.random.RandomState(seed)
    P = X.shape[1]
    if joint:
        C = _corr_from_edges(X, edges, names)
        L = np.linalg.cholesky(C + 1e-9 * np.eye(P))
        Z = rnd.normal(size=(n, P)) @ L.T
    else:
        Z = rnd.normal(size=(n, P))
    from scipy.stats import norm
    U = norm.cdf(Z)
    out = []
    for r in range(n):
        out.append({names[j]: _quantile(X[:, j], U[r, j]) for j in range(P)})
    return out
