"""포스터를 «잰 트리» 로 읽는다 — 재귀로 짚고, 마디마다 결정론으로 잰다.

여태 파이프라인은 평평했다. 상자를 검출하고, 각각 재고, 다 합쳐 평균했다.
그래서 「이것이 제목인가 본문인가 크레딧인가」를 한 번도 말하지 못했다.
위계가 없었다.

트리로 읽으면 역할이 공짜로 나온다 — 역할은 절대 크기가 아니라 **트리에서의
자리**다. x높이 27px 라서 제목인 것이 아니라 루트 바로 아래 첫 자식이라서
제목이다. 같은 27px 도 다른 판에서는 본문일 수 있다.

이 프로젝트의 뼈대를 재귀로 옮긴 것이다.

    어디에 무엇이 있나   VLM 이 짚는다 (짐작 허용) — 마디를 만든다
    그 안에서 얼마인가   결정론적 알고리즘 (짐작 금지) — 마디를 채운다

검사법도 분명하다. **트리로 다시 세워 원본과 맞나** 보면 된다. 안 맞으면
쪼개기가 틀렸거나 형식에 칸이 모자란 것이고, 둘 다 알아낸 것이다.

쪼개기를 언제 멈추나 — 규칙을 못 박는다. **글줄에 닿으면 멈춘다.** 마디가
한 글줄 묶음이면 더 쪼개지 않는다. 그러지 않으면 판마다 트리 깊이가
들쭉날쭉해져 견줄 수가 없다.
"""
import json

import numpy as np
from PIL import Image

from measure import ground as G

STOP = '글줄'          # 이 종류의 마디는 더 쪼개지 않는다


class Node:
    def __init__(self, id, role, box, kind='묶음', note=None):
        self.id = id            # 'r', 'r.1', 'r.1.2' — 자리가 곧 이름
        self.role = role        # 제목 · 본문 · 크레딧 · 그림 · 색면 …
        self.box = box          # [x1,y1,x2,y2] 0~1
        self.kind = kind        # 묶음 | 글줄 | 그림 | 색면
        self.note = note
        self.kids = []
        self.m = None           # 잰 것

    def add(self, *k):
        self.kids += list(k)
        return self

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()

    def leaves(self):
        return [n for n in self.walk() if not n.kids]

    def dict(self):
        d = dict(id=self.id, 역할=self.role, 종류=self.kind,
                 상자=[round(v, 4) for v in self.box])
        if self.note:
            d['말'] = self.note
        if self.m:
            d['잰것'] = self.m
        if self.kids:
            d['자식'] = [k.dict() for k in self.kids]
        return d


def measure(root, path):
    """글줄 마디마다 그 안을 잰다. 묶음 마디는 자식에서 굴려 올린다."""
    W, H = Image.open(path).size
    leaf = [n for n in root.walk() if n.kind == STOP]
    if leaf:
        r = G.measure_boxes(path, [n.box for n in leaf], coords='norm')
        for n, m in zip(leaf, r['boxes']):
            n.m = dict(줄=m.get('n_lines'), xh=m.get('xh_median'),
                       행간=m.get('lead_measured'),
                       베이스라인=m.get('baselines'),
                       잉크상자=[round(v, 1) for v in (m.get('box_ink') or [])])
    # 묶음은 자식을 굴려 올린다 — 아래에서 위로
    for n in sorted(root.walk(), key=lambda x: -len(x.id)):
        if n.kids:
            ls = [k for k in n.walk() if k.m]
            n.m = dict(줄=sum((k.m.get('줄') or 0) for k in ls),
                       xh범위=([round(min(k.m['xh'] for k in ls if k.m.get('xh')), 1),
                              round(max(k.m['xh'] for k in ls if k.m.get('xh')), 1)]
                             if any(k.m.get('xh') for k in ls) else None),
                       마디수=len(n.kids))
    root.m = root.m or {}
    root.m['크기'] = [W, H]
    return root


def summary(root):
    """트리를 사람이 읽는 줄로."""
    out = []
    for n in root.walk():
        d = n.id.count('.')
        m = n.m or {}
        bits = []
        if m.get('줄'):
            bits.append(f"줄 {m['줄']}")
        if m.get('xh'):
            bits.append(f"xh {m['xh']:.1f}")
        if m.get('xh범위'):
            bits.append(f"xh {m['xh범위'][0]}~{m['xh범위'][1]}")
        if m.get('행간'):
            bits.append(f"행간 {m['행간']:.0f}")
        out.append('  ' * d + f"{n.id:<8} {n.role:<8} [{n.kind}] " + ' · '.join(bits))
    return '\n'.join(out)
