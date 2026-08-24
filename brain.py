"""스타일 뇌 — 한 작가의 마디와 선을 하나의 그래프로 묶는다.

rules.py 는 값의 목록을 낸다. 「행간 1.42배」「마진 3.7%」 같은 것들. 그런데
코퍼스 4종 274장을 재보니 그런 값으로는 작가가 거의 안 갈렸다. 몰린 값은
넷이 다 같았고(폰트 상수), 갈리는 값은 흩어져 있었다.

목록에는 담을 자리가 없는 것이 하나 있다 — **무엇이 무엇과 함께 움직이는가.**
브로크만의 마진은 CV 1.0 을 넘게 흩어져서 「얼마를 쓴다」고 말할 수 없는데,
그 흩어진 값들 사이에는 선이 걸려 있다. 목록을 그래프로 바꾸면 그 자리가
생긴다.

    목록:   행간 1.42배            — 넷이 다 그러니 쓸모가 없다
    그래프: 행간이 마진과 같이 움직인다 — 값이 같아도 묶임은 다를 수 있다

생성이 전에 실패한 이유도 이것이었다. 독립된 범위에서 따로 뽑으니 각 값은
브로크만 범위 안인데 합쳐 놓으면 브로크만이 아니었다. 선을 지키면서 뽑아야
한다.

**자기가 모르는 것을 함께 싣는다.** cannot_say 가 그것이다. 오늘 하루에만
귀무모형 없이 본 숫자로 판단을 여섯 번 뒤집었다. 뇌를 받아 쓰는 쪽이
그 한계를 모르면 같은 실수를 반복한다.
"""
import numpy as np

import features
import rules

MIN_PAIR = 20      # 쌍마다 둘 다 실제로 잰 포스터가 이만큼은 있어야 본다
N_NULL = 4000
FDR = 0.05
SEED = 20260824

GROUP = {n: '색' for n in features.COLOR}
GROUP.update({n: '마진' for n in features.MARGIN})
GROUP.update({n: '조판' for n in features.CONTENT})

METRIC = {'색수': 'n_colors', '밝기': 'value', '최빈색': 'ground_share',
          '채도': 'saturation', '무채색': 'gray_share',
          '마진좌': 'margin_left', '마진우': 'margin_right',
          '마진상': 'margin_top', '마진하': 'margin_bottom',
          '덮음': 'text_area', '블록수': 'n_blocks', '단수': 'n_columns',
          '활자폭': 'cap_range', '행간비': 'lead_over_cap', '어센더비': 'asc_over_xh'}


NOTE = {
    '색수': dict(뜻='판면의 2% 이상을 차지한 색이 몇 개인가',
        읽는법='200px 로 줄여 64색으로 뭉갠 뒤 셈한다. 많으면 색을 여럿 쓴 판, 적으면 두세 색으로 짠 판이다.',
        주의='포스터가 아니라 포스터의 «스캔» 에서 나온다. 같은 출처끼리만 견줄 수 있다.'),
    '밝기': dict(뜻='화소 밝기의 중앙값',
        읽는법='낮으면 어두운 바탕에 밝은 활자, 높으면 밝은 바탕이다.',
        주의='종이 노화와 스캔 노출이 섞인다. 호프만 108장에서 연대 효과는 2.0% 로 작았다.'),
    '최빈색': dict(뜻='가장 많이 쓰인 색 하나가 판면의 몇 %를 덮는가',
        읽는법='높으면 큰 색면 하나가 판을 지배한다. 낮으면 여러 색이 나눠 가진다.',
        주의='색 계급이 64칸이라 가까운 색조가 한 칸에 뭉칠 수 있다.'),
    '채도': dict(뜻='화소 채도의 중앙값',
        읽는법='높으면 원색을 쓴 판, 낮으면 무채색 위주다.',
        주의='인쇄 잉크의 바램과 스캔 색보정이 섞인다.'),
    '무채색': dict(뜻='채도가 거의 없는 화소의 비율',
        읽는법='높으면 흑·백·회색으로 짠 판이다.',
        주의='문턱이 채도 0.12 로 고정이라 옅은 색이 무채색으로 셈해질 수 있다.'),
    '마진좌': dict(뜻='글자 영역의 왼쪽 바깥 여백 / 판면 폭',
        읽는법='글자가 닿은 가장 왼쪽 지점까지의 거리다. 작으면 글자가 판 끝에 붙는다.',
        주의='회전 보정을 받은 포스터는 빠진다. 색면·그림은 세지 않고 «글자» 만 본다.'),
    '마진우': dict(뜻='글자 영역의 오른쪽 바깥 여백 / 판면 폭',
        읽는법='작으면 글자가 오른쪽 끝까지 간다.',
        주의='회전된 포스터는 빠진다.'),
    '마진상': dict(뜻='글자 영역의 위쪽 바깥 여백 / 판면 높이',
        읽는법='크면 위를 비워 두고 아래에 앉힌 구성이다.',
        주의='회전된 포스터는 빠진다.'),
    '마진하': dict(뜻='글자 영역의 아래쪽 바깥 여백 / 판면 높이',
        읽는법='작으면 판 바닥까지 글자가 내려간다.',
        주의='회전된 포스터는 빠진다.'),
    '덮음': dict(뜻='타이포 덩어리 상자 면적의 합 / 판면 면적',
        읽는법='글자가 판을 얼마나 차지하는가. 높으면 활자로 꽉 찬 판이다.',
        주의='상자가 겹치면 겹친 만큼 두 번 세어 1.0 을 넘을 수 있다. 마진과 «같은 상자» 에서 계산되므로 둘 사이 관계에는 셈법에서 오는 몫이 섞인다.'),
    '블록수': dict(뜻='검출된 타이포 덩어리의 개수',
        읽는법='많으면 잘게 나뉜 판, 적으면 큰 덩어리 몇 개로 짠 판이다.',
        주의='검출기가 쪼개거나 붙이면 그대로 반영된다. 사진이 많은 판에서 부풀기 쉽다.'),
    '단수': dict(뜻='판면이 세로 빈 띠로 갈린 단의 개수',
        읽는법='브로크만이 말한 «단» 과 뜻은 같지만, 격자의 단이 아니라 실제로 비어 있는 띠로 센 값이다.',
        주의='보고용 지표다. 과분할 때문에 값이 뭉개진다고 기록돼 있다.'),
    '활자폭': dict(뜻='한 판 안에서 가장 큰 활자 / 가장 작은 활자',
        읽는법='크면 표제와 본문의 낙차가 큰 판이다. 호프만은 판을 덮는 표제와 8px 본문을 같이 쓴다.',
        주의='x높이로 재므로 폰트가 섞이면 흔들린다.'),
    '행간비': dict(뜻='행간 / 활자 높이 (캡 높이)',
        읽는법='1.4배면 활자 높이의 1.4배 간격으로 줄이 내려간다. 크면 성긴 조판, 작으면 빽빽하다.',
        주의='3줄 이상 블록에서만 나온다. 그래서 일부 포스터에서만 값이 있고, 값이 나온 쪽은 검출이 쉬운 얌전한 조판에 쏠린다.'),
    '어센더비': dict(뜻='어센더 높이 / x높이',
        읽는법='폰트의 성질이다. 악치덴츠·헬베티카 계열이면 1.35~1.40 근처로 고정된다.',
        주의='작가의 선택이 아니다. 가장 안 흔들려서 «제약» 으로 먼저 채택되지만 네 작가가 모두 같다 — 이 값으로는 아무도 못 가른다.'),
}


def _rank(a):
    return a.argsort().argsort() + 1.0


def edges(X, min_pair=MIN_PAIR, n_null=N_NULL, seed=SEED, fdr=FDR):
    """한 작가 «안» 에서 같이 움직이는 쌍을 찾는다. 참조 코퍼스가 필요 없다.

    귀무모형은 한 쪽 열만 포스터 사이에서 섞는다. 각 속성의 분포는 그대로
    두고 짝만 끊는 것이라, 「원래 그런 값이라서」와 「같이 다녀서」가 갈린다.
    """
    P = X.shape[1]
    rnd = np.random.RandomState(seed)
    out = []
    for i in range(P):
        for j in range(i + 1, P):
            ok = ~np.isnan(X[:, i]) & ~np.isnan(X[:, j])
            if ok.sum() < min_pair:
                continue
            a, b = X[ok, i], X[ok, j]
            if a.std() == 0 or b.std() == 0:
                continue
            ra, rb = _rank(a), _rank(b)
            ca = ra - ra.mean(); cb = rb - rb.mean()
            r = abs(float(ca @ cb) / (np.linalg.norm(ca) * np.linalg.norm(cb)))
            # 순열을 한꺼번에 — 섞어도 노름이 같으므로 행렬곱 한 번이면 된다
            perm = np.array([rnd.permutation(cb) for _ in range(n_null)])
            nulls = np.abs(perm @ ca) / (np.linalg.norm(ca) * np.linalg.norm(cb))
            p = (float((nulls >= r).sum()) + 1) / (n_null + 1)
            out.append(dict(a=features.NAMES[i], b=features.NAMES[j],
                            r=round(r, 3), p=round(p, 5), n=int(ok.sum())))
    if not out:
        return []
    ps = np.array([e['p'] for e in out])
    o = np.argsort(ps)
    crit = fdr * np.arange(1, len(ps) + 1) / len(ps)
    below = np.where(ps[o] <= crit)[0]
    cut = ps[o][below[-1]] if len(below) else -1
    for e in out:
        e['keep'] = bool(e['p'] <= cut)
    return out


def build(raw, who, references=None, derived=None):
    """원자료 하나에서 뇌 하나. references 를 주면 선마다 «누구에게도» 를 붙인다."""
    R = derived or rules.derive(raw, references=references)
    ent = {**R['rules'], **R['not_rules']}
    X, keys, _ = features.matrix(raw)

    nodes = []
    for name, key in METRIC.items():
        v = ent.get(key)
        if not v:
            continue
        nodes.append(dict(
            id=name, group=GROUP.get(name, '기타'), label=v.get('label'),
            unit=v.get('unit'), median=v.get('median'),
            lo=v.get('lo'), hi=v.get('hi'), cv=v.get('cv'),
            verdict=v.get('verdict'), scope=v.get('scope'), note=NOTE.get(name),
            n=v.get('n'), n_posters=v.get('n_posters'), of=R['n_posters']))

    es = [e for e in edges(X) if e['keep']]
    if references:
        for name, rr in references.items():
            Y, _k, _n = features.matrix(rr)
            other = {(e['a'], e['b']) for e in edges(Y) if e['keep']}
            for e in es:
                e.setdefault('also', [])
                if (e['a'], e['b']) in other:
                    e['also'].append(name)
    for e in es:
        e['also'] = e.get('also', [])
        e['exclusive'] = (references is not None) and not e['also']
        e.pop('keep', None)

    low = [n['id'] for n in nodes if (n['n_posters'] or 0) < R['n_posters'] * 0.9]
    return dict(
        who=who, n_posters=R['n_posters'], nodes=nodes, edges=es,
        criteria=dict(**R.get('criteria', {}), edge_fdr=FDR,
                      edge_min_pair=MIN_PAIR, edge_n_null=N_NULL),
        cannot_say=_limits(nodes, es, low, references),
        how_to_use=_howto())


def _limits(nodes, es, low, references):
    out = [
        '선은 «함께 움직인다» 까지다. 어느 쪽이 먼저인지는 상관으로 알 수 없다 — '
        '「마진을 먼저 정하고 내용을 담는다」 같은 말은 이 데이터가 뒷받침하지 않는다.',
        '한 작가의 코퍼스는 연작이 섞여 있다. 연작이 판형을 고정하면 그 안에서 '
        '값이 안 변하고, 그것이 «그의 방법» 처럼 보인다. 계열마다 한 장씩 뽑아 '
        '다시 재보면 결합도가 달라진다.',
        '마진과 덮음은 같은 검출 상자에서 계산된다. 둘 사이의 관계에는 '
        '설계가 아니라 셈법에서 오는 몫이 섞여 있다.',
    ]
    if low:
        out.append(f'다음 마디는 일부 포스터에서만 값이 나왔다 — {", ".join(low)}. '
                   f'그 마디에 걸린 선은 표본이 그만큼 적고, 값이 나온 포스터가 '
                   f'무작위 표본도 아니다 (검출이 쉬운 쪽에 쏠린다).')
    if not references:
        out.append('참조 코퍼스를 주지 않아 «이 사람만의 선» 을 가리지 않았다. '
                   '지금 선들은 기계적인 것과 양식적인 것이 섞여 있다.')
    out.append('색 지표는 포스터가 아니라 포스터의 스캔에서 나온다. 같은 출처의 '
               '코퍼스끼리만 견줄 수 있다.')
    return out


def _howto():
    return {
        '읽기': 'verdict 는 값이 몰렸는가, scope 는 그 값이 다른 작가와 갈리는가다. '
                '둘은 다른 질문이고 자주 엇갈린다 — 몰린 값이 폰트 상수일 수 있다.',
        '생성': '자유 마디는 lo~hi 안에서 골라도 된다. 다만 선으로 묶인 마디는 '
                '따로 뽑으면 안 된다 — 각 값이 범위 안이어도 합치면 그 사람이 '
                '아니게 된다. 선을 지키며 함께 뽑아라.',
        '검사': '후보 배치를 놓고 두 가지를 물어라. 값이 범위 안인가, 그리고 '
                '선으로 묶인 쌍이 같은 방향으로 움직였는가.',
        '주의': 'cannot_say 를 먼저 읽어라. 여기 적힌 것을 넘어서 말하면 안 된다.',
    }
