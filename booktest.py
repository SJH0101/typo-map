"""책이 말한 규칙을 그의 포스터로 검사한다.

브로크만은 『Grid Systems』 에서 규칙을 스스로 적어 두었다 (docs/BROCKMANN_RULES.md).
그러면 물을 수 있다 — **그의 포스터가 그의 규칙을 지키는가.**

이 물음이 성립하려면 두 가지가 있어야 하는데 둘 다 생겼다. 규칙을 뽑아 정리한
문서와, 123장을 잰 코퍼스다.

넷 중 하나로 끝난다.

    말했고 지킨다      규칙이 실천으로 확인된다
    말했는데 안 지킨다   선언과 실천이 다르다 — 또는 적용 범위가 다르다
    안 말했는데 그런다   **암묵지.** 마인드맵의 선이 여기 산다
    안 말했고 안 그런다  할 말 없음

«적용 범위» 를 먼저 봐야 한다. 책의 상당수는 서적·브로슈어 규칙이다 (C3 이
「서적·브로슈어·카탈로그」라고 못 박는다). 그것을 포스터에 대고 재면 범주
오류이고, 실제로 R1·C1 이 그렇게 어긋났다 — 어긋난 것이 아니라 다른 물건에
대고 잰 것이다. 그래서 규칙마다 scope 를 단다.
"""
import numpy as np

BOOK, POSTER, BOTH = '책', '포스터', '둘 다'


def _blocks(raw, min_lines=3):
    """3줄 이상 블록만. 표제 한 줄짜리는 «단» 이 아니다."""
    out = []
    for name, r in raw.items():
        if abs(r.get('angle', 0)) >= 1 or not r.get('size'):
            continue
        for b in r['blocks']:
            if b['n'] < min_lines:
                continue
            w = b['x2'] - b['x1']
            xh = b.get('xh')
            L = b.get('lead_measured') or b.get('lead')
            if w > 0 and xh and xh > 0:
                out.append(dict(poster=name, w=float(w), xh=float(xh),
                                n=int(b['n']), lead=(float(L) if L else None)))
    return out


def _rank(a):
    return a.argsort().argsort() + 1.0


def _sp(a, b):
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(_rank(a), _rank(b))[0, 1])


def R1(raw, n_null=2000, seed=20260824):
    """단 폭 ∝ 활자 크기. 포스터 «안에서» 본다 — 판형 차이를 지운다."""
    bl = _blocks(raw)
    by = {}
    for b in bl:
        by.setdefault(b['poster'], []).append(b)
    def med(perm=None, rnd=None):
        v = []
        for g in by.values():
            if len(g) < 3:
                continue
            w = np.array([x['w'] for x in g])
            h = np.array([x['xh'] for x in g])
            if perm:
                h = rnd.permutation(h)
            r = _sp(w, h)
            if r is not None:
                v.append(r)
        return (float(np.median(v)) if v else None), len(v)
    real, n = med()
    if real is None:
        return dict(rule='R1', scope=BOOK, verdict='잴 수 없음', why='포스터당 블록이 모자란다')
    rnd = np.random.RandomState(seed)
    null = np.array([med(True, rnd)[0] for _ in range(n_null)])
    lo, hi = np.percentile(null, 2.5), np.percentile(null, 97.5)
    v = ('지킨다' if real > hi else ('반대로 간다' if real < lo else '우연과 구분 안 됨'))
    return dict(rule='R1', scope=BOOK, verdict=v, r=round(real, 3), n_posters=n,
                null=[round(float(lo), 3), round(float(hi), 3)],
                note=('책 규칙이다. 근거인 「행 전환 피로」는 여러 행을 연속으로 읽을 때 얘기라 '
                      '포스터에 대고 재는 것은 범주가 다르다. 포스터 안에서는 표제가 굵고 좁으며 '
                      '정보 블록이 작고 넓어 방향이 뒤집힌다.'))


def C1(raw, per_word_em=2.75, xh_em=0.52):
    """행당 7~10 낱말. 낱말 폭을 활자 크기에서 어림한다 — 어림이므로 크기만 본다."""
    bl = _blocks(raw)
    if not bl:
        return dict(rule='C1', scope=BOOK, verdict='잴 수 없음')
    w = np.array([b['w'] / b['xh'] for b in bl]) * xh_em / per_word_em
    inb = float(((w >= 7) & (w <= 10)).mean())
    return dict(rule='C1', scope=BOOK, verdict=('지킨다' if inb > 0.5 else '안 지킨다'),
                median_words=round(float(np.median(w)), 1),
                in_band=round(inb, 3), n_blocks=len(bl),
                note=('책 규칙이다. 낱말 폭은 활자 크기에서 어림한 값이라 절대값을 믿으면 안 되고 '
                      '크기 차이만 본다. 독일어는 낱말이 길어 실제로는 더 적을 것이다.'))


def R2(raw, n_null=2000, seed=20260824, tol=0.05):
    """활자 크기가 여럿일 때 행간들이 하나의 격자를 정수배로 공유하는가."""
    got = []
    for name, r in raw.items():
        if abs(r.get('angle', 0)) >= 1:
            continue
        bs = [b for b in r['blocks'] if b['n'] >= 3 and (b.get('lead_measured') or b.get('lead'))]
        if len(bs) < 2:
            continue
        xh = [b['xh'] for b in bs if b.get('xh')]
        if len(set(round(x) for x in xh)) < 2:       # 크기가 여럿인 판만
            continue
        got.append([float(b.get('lead_measured') or b['lead']) for b in bs])
    if len(got) < 8:
        return dict(rule='R2', scope=BOTH, verdict='잴 수 없음',
                    why=f'조건에 맞는 포스터가 {len(got)}장뿐이다')

    def dev(leads):
        u = min(leads)
        if u <= 0:
            return None
        return float(np.mean([abs(L / u - round(L / u)) / max(round(L / u), 1) for L in leads]))

    err = np.array([dev(g) for g in got if dev(g) is not None])
    pool = [L for g in got for L in g]
    rnd = np.random.RandomState(seed)
    null = np.array([float(np.median([dev(list(rnd.choice(pool, size=len(g), replace=True)))
                                      for g in got])) for _ in range(n_null)])
    lo = float(np.percentile(null, 2.5))
    real = float(np.median(err))
    return dict(rule='R2', scope=BOTH,
                verdict=('지킨다' if real < lo else '우연과 구분 안 됨'),
                deviation=round(real, 4), within_tol=round(float((err < tol).mean()), 3),
                n_posters=len(err), null_lo=round(lo, 4),
                note=('행간이 독립 변수가 아니라 시스템 변수라는 주장이다. 다른 판에서 뽑아온 '
                      '행간을 섞으면 벗어남이 커지므로, 낮게 나온다는 것은 한 판 안에서 '
                      '서로 맞췄다는 뜻이다.'))


NOT_TESTABLE = {
    'R4': ('도판 크기 = f(중요도)', '「중요도」가 의미 이해를 요구한다. VLM 이 짚어 줘야 잰다'),
    'R5': ('도판 크기 종류 수 ↓ → 고요함 ↑', '「고요함」이 사람의 판정이다. 크기 종류 수는 재도 결과를 못 잰다'),
    'R10': ('마진 비례가 균형', '「균형」의 정의가 없다. 같음인지 비례 조화인지에 따라 답이 뒤집힌다'),
    'R11': ('유사 계열 서체 혼용 금지', '서체 식별이 필요하다'),
    'R7': ('필드 정수 산술', '필드 경계를 아직 검출하지 못한다. 베이스라인 격자는 R2 로 대신 본다'),
}

TESTS = [R1, C1, R2]


def run(raw, tests=None):
    out = [t(raw) for t in (tests or TESTS)]
    return dict(n_posters=len(raw), results=out,
                not_testable=[dict(rule=k, what=v[0], why=v[1]) for k, v in NOT_TESTABLE.items()],
                note=('scope 가 「책」인 규칙이 포스터에서 어긋나는 것은 규칙이 틀렸다는 뜻이 '
                      '아니라 다른 물건에 대고 쟀다는 뜻이다. 판정을 읽기 전에 scope 를 보라.'))
