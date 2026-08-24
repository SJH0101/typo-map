"""뇌 뷰어를 한 파일로 굽는다.

머리(스타일)·몸(뼈대)·app.js 를 합치고 __BRAINS__ 자리에 뇌들을 박는다.
CSP 때문에 바깥에서 아무것도 못 불러오므로 한 파일이어야 한다.

    python viewer/build.py            ~/.typo-mcp 의 뇌들로 굽는다
    python viewer/build.py out.html   경로를 정해서
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.expanduser('~'), '.typo-mcp')
ORDER = ['brockmann', 'corpus', 'rose', 'ruder', 'pooled']   # 아는 것은 이 순서로


def collect(cache=CACHE):
    """brain-*.json 을 전부 줍는다. add_designer 로 늘린 작가도 그대로 들어온다."""
    files = [f for f in os.listdir(cache) if f.startswith('brain-') and f.endswith('.json')]
    def rank(f):
        s = f[6:-5]
        return (ORDER.index(s) if s in ORDER else len(ORDER), f)
    out = {}
    for f in sorted(files, key=rank):
        try:
            b = json.load(open(os.path.join(cache, f)))
        except Exception:
            continue
        if not b.get('who') or 'nodes' not in b or 'edges' not in b:
            continue
        out[b['who']] = dict(
            who=b['who'], n=b['n_posters'], nodes=b['nodes'], edges=b['edges'],
            cannot=b['cannot_say'], rule=b['criteria']['edge_rule'],
            ok=b['edges_estimable'], need=b['edges_need'],
            have=b['edges_have'], pooled=bool(b.get('pooled_from')))
    return out


def build(dst):
    data = json.dumps(collect(), ensure_ascii=False, separators=(',', ':'))
    js = open(os.path.join(HERE, 'app.js')).read().replace('__BRAINS__', data)
    html = (open(os.path.join(HERE, 'head.html')).read() + '\n'
            + open(os.path.join(HERE, 'body.html')).read() + '\n<script>\n' + js + '\n</script>\n')
    open(dst, 'w').write(html)
    return dst, len(html)


if __name__ == '__main__':
    dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'brain.html')
    p, n = build(dst)
    print(f'{p} · {n} bytes · 뇌 {len(collect())}개')
