"""포스터 한 장을 «잰 문서» 로 적는 형식.

IDML 은 «무엇이 어디 놓였나» 를 적는다 — 절대 좌표와 스타일이다. 그것으로는
판을 다시 그릴 수 있어도 «무슨 체계로 놓았나» 를 말할 수 없다. 좌표가 67px
간격으로 늘어서 있다는 사실이 어디에도 안 적힌다.

여기서는 체계를 적는다. 그리고 셋을 더 적는다 — 다른 형식에 칸이 없는 것들.

    ① 격자 상대 좌표와 «어긋남»
       블록이 3번 축에 서되 +2px 벗어났다. 어긋남이 자리를 갖는다.
       격자를 어기는 자리가 지키는 자리보다 말이 많다.

    ② 못 잰 칸
       가로줄은 재는 함수가 없고, 크레딧은 너무 작아 글줄을 못 찾았다.
       조용히 빠지지 않고 이유와 함께 남는다.

    ③ 반증된 것
       세로 베이스라인 격자는 «없다» — 안 찾은 것이 아니라 찾아보고 없었다.
       귀무모형과 견준 수를 함께 적는다. 형식이 «검사했고 아니었다» 를
       말할 수 있어야 한다.

값에는 출처가 붙는다. 짚기가 자동인지 사람인지, 어느 검출기인지, 어느
함수가 쟀는지. 이 문서는 저작물이 아니라 «측정 기록» 이다.
"""
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

import numpy as np

VERSION = '0.1'

# 마디의 종류. 트리에서 나오는 그대로다 — 늘리기 전에 왜 필요한지 적을 것.
KINDS = ('글줄', '그림', '색면', '묶음')

# «못 잼» 의 이유. 새 이유가 생기면 여기에 더한다 — 자유 문자열로 두면
# 나중에 세지 못한다.
WHY = {
    '너무작음': '상자가 작아 글줄을 못 찾았다',
    '재는함수없음': '이 종류를 재는 함수가 없다 (선·도형)',
    '기울어짐': '글줄이 기울어 수평 전제가 깨진다',
    '검출없음': '검출기가 상자를 내지 않았다',
    '대비없음': '잉크라 할 만한 대비가 없다',
    '그림못짚음': '줄이 아닌 것(그림·색면·선)의 자리를 짚는 함수가 없다',
}


def _e(parent, tag, **kw):
    a = {k.replace('_', '-'): ('' if v is None else
                              (f'{v:.4g}' if isinstance(v, float) else str(v)))
         for k, v in kw.items() if v is not None}
    return ET.SubElement(parent, tag, a)


def build(tree, rules=None, source=None, made=None):
    """트리 + 규칙 → 문서 나무."""
    root = ET.Element('poster', dict(version=VERSION))
    s = source or {}
    _e(root, 'source', file=s.get('file'), w=s.get('w'), h=s.get('h'),
       physical=s.get('physical'), format=s.get('format'))
    m = made or {}
    _e(root, 'made-by', grounding=m.get('grounding', 'auto'),
       detector=m.get('detector'), measurer=m.get('measurer', 'measure/ground.py'),
       date=m.get('date'))

    sysx = ET.SubElement(root, 'system')
    r = rules or {}
    ax = (r.get('단') or {})
    if ax.get('축'):
        a = _e(sysx, 'axes', n=len(ax['축']), pitch=ax.get('피치'),
               wobble=ax.get('피치흔들림'), unit='px')
        for i, c in enumerate(ax['축'], 1):
            _e(a, 'axis', id=i, at=round(float(c), 1))
        h = r.get('맞힘') or {}
        if h:
            _e(a, 'tested', how='leave-one-out', error=h.get('어긋남중앙'),
               null=h.get('귀무중앙'), ratio=h.get('배수'), n=h.get('n'))
    g = r.get('격자검사') or {}
    if g:
        found = g.get('분위', 1.0) < 0.05
        b = _e(sysx, 'baseline-grid', found=('yes' if found else 'no'),
               unit=(r.get('격자', {}) or {}).get('단위') if found else None)
        _e(b, 'tested', how='null-model', deviation=g.get('벗어남'),
           null=g.get('귀무'), percentile=g.get('분위'), n=g.get('n'))
    lv = r.get('계층') or []
    if lv:
        L = ET.SubElement(sysx, 'levels')
        for i, x in enumerate(lv, 1):
            _e(L, 'level', id=f'L{i}', xh=x.get('xh'), n=x.get('n'))
    return root, sysx


def add_content(root, tree, levels=None):
    """트리를 <content> 로. 마디마다 종류에 맞는 태그를 쓴다."""
    c = ET.SubElement(root, 'content')
    un = []

    def lvl(xh):
        if not levels or xh is None:
            return None
        i = int(np.argmin([abs((l.get('xh') or 0) - xh) for l in levels]))
        return f'L{i + 1}'

    def go(n, parent):
        m = getattr(n, 'm', None) or {}
        kind = getattr(n, 'kind', '묶음')
        box = [round(float(v), 4) for v in n.box]
        if kind == '글줄':
            if not m.get('줄'):
                un.append((n.id, 'text', '너무작음', getattr(n, 'why', None)))
                return
            el = _e(parent, 'block', id=n.id, level=lvl(m.get('xh')),
                    lines=m.get('줄'), xh=m.get('xh'), lead=m.get('행간'),
                    box=' '.join(str(v) for v in box))
        elif kind == '그림':
            el = _e(parent, 'picture', id=n.id,
                    box=' '.join(str(v) for v in box), why=getattr(n, 'why', None))
        elif kind == '색면':
            el = _e(parent, 'field', id=n.id, box=' '.join(str(v) for v in box))
        else:
            el = _e(parent, 'group', id=n.id, box=' '.join(str(v) for v in box),
                    coverage=getattr(n, '덮음', None))
        for k in getattr(n, 'kids', []):
            go(k, el)

    for k in getattr(tree, 'kids', []):
        go(k, c)
    return c, un


def add_unmeasured(root, items):
    if not items:
        return
    u = ET.SubElement(root, 'unmeasured')
    for id, what, why, note in items:
        _e(u, 'item', id=id, what=what, why=why, detail=WHY.get(why, note))


def to_xml(root):
    raw = ET.tostring(root, encoding='unicode')
    return minidom.parseString(raw).toprettyxml(indent='  ')[23:]
