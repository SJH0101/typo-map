"""Surya 가 준 «줄» 을 우리 «블록» 으로 묶는다.

옛 경로(baseline/detect.py)는 영역 전체를 잉크 문턱으로 훑어 줄을 찾았다.
그래서 사진·색면·도형 위에서도 줄이 나왔다 — 사람이 라벨한 200개로 재보니
상자의 37% 가 글자가 아니었고, 작가별로 브로크만 10% · 루더 53% 로
다섯 배 차이가 났다. 작가 비교가 그 차이를 싣고 있었다.

Surya 는 사진·도형 위에 상자를 치지 않는다. 대신 거대 표제를 더러 놓친다.
**두 실패의 성격이 다르다** — 옛것은 조용히 틀린 값을 내고 Surya 는 빠진다.
빠지는 것은 셀 수 있고 기록할 수 있다.

Surya 는 «줄» 단위라 우리 지표(블록수·행간·단)를 내려면 묶어야 한다.
묶는 규칙은 셋이고, 전부 옛 detect.py 가 쓰던 것과 같은 생각이다.

    크기 계층   높이가 서로 이 배수 안에 들어야 한다 (제목과 본문을 안 섞는다)
    가로 겹침   x 범위가 겹쳐야 한다 (다른 단을 안 붙인다)
    세로 간격   행간이 제 높이의 이 배 안이어야 한다 (떨어진 덩어리를 안 붙인다)

묶은 상자는 measure/ground.py 로 넘긴다 — 짚어준 상자를 재는 그 경로다.
찾기와 재기가 갈라진다.
"""
import numpy as np

H_RATIO = (0.60, 1.70)   # 높이가 이 배수 안이면 같은 크기 계층
X_OVER = 0.15            # 좁은 쪽 폭의 이 비율 넘게 겹쳐야 한 단
Y_GAP = (-0.40, 1.60)    # 세로 틈이 제 높이의 이 배수 안이면 잇는다.
                         # 음수는 겹침을 허용한다 — 큰 글자는 상자가 서로 물린다.
MIN_AREA = 200           # 이보다 작은 상자는 부스러기


def _norm(b):
    x1, y1, x2, y2 = b
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def group(lines):
    """줄상자 목록 → 블록 상자 목록. 각 블록은 (x1,y1,x2,y2,줄수)."""
    L = [_norm(b) for b in lines]
    L = [b for b in L if (b[2] - b[0]) * (b[3] - b[1]) >= MIN_AREA]
    L.sort(key=lambda b: (b[1], b[0]))
    used = [False] * len(L)
    out = []
    for i, a in enumerate(L):
        if used[i]:
            continue
        used[i] = True
        g = [a]
        moved = True
        while moved:
            moved = False
            gx1 = min(b[0] for b in g); gx2 = max(b[2] for b in g)
            gy2 = max(b[3] for b in g)
            gh = float(np.median([b[3] - b[1] for b in g]))
            for j, b in enumerate(L):
                if used[j]:
                    continue
                bh = b[3] - b[1]
                if not (H_RATIO[0] <= bh / max(gh, 1) <= H_RATIO[1]):
                    continue
                if min(gx2, b[2]) - max(gx1, b[0]) <= X_OVER * min(gx2 - gx1, b[2] - b[0]):
                    continue
                if not (Y_GAP[0] * gh <= b[1] - gy2 <= Y_GAP[1] * gh):
                    continue
                g.append(b); used[j] = True; moved = True
        out.append((min(b[0] for b in g), min(b[1] for b in g),
                    max(b[2] for b in g), max(b[3] for b in g), len(g)))
    return out


def boxes_norm(lines, size):
    """묶은 블록을 0~1 좌표로. measure.ground 가 먹는 꼴."""
    W, H = size
    return [[b[0] / W, b[1] / H, b[2] / W, b[3] / H] for b in group(lines)]
