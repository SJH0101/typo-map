"""봉인 결과 파일에서 바뀐 키 경로만 알린다 — 값 · 수 · 판 · 틀 이름은 찍지 않는다.

    python eval/sealed_keydiff.py docs/brockmann_group_explore.json --script eval/brockmann_group_explore.py
    python eval/sealed_keydiff.py docs/brockmann_group_explore.json --script eval/brockmann_group_explore.py --rev 93c378a

커밋본(--rev, 기본 HEAD)과 작업 트리 파일을 견준다. 결과 파일을 만들지 않는 확인용 도구다.

접는 규칙: 키가 산출 스크립트(--script)의 문자열 상수 · 키워드 인자 이름에 없고, 방식 짝 이름(A · C · VLM1 · 오라클 을
«·» 로 이은 것)도 아니면 * 로 접는다. 판 이름 · 틀(포스터 묶음) 이름 · 순서 번호처럼 자료에서 온 키는 스크립트
상수에 없으므로 모두 접힌다. 리스트 자리는 [] 로 접는다. 바뀐 자리의 수도 크기를 드러내므로 찍지 않는다.

2026-09-15 — 처음 쓴 대조는 숫자 · 파일 이름 · 긴 키만 접어 틀 이름이 경로에 나왔다 (docs/legacy_numbers.md 7절).
그 뒤 이 규칙으로 고쳤다.
"""
import argparse
import ast
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIR = re.compile(r'^(A|C|VLM\d*|오라클)(·(A|C|VLM\d*|오라클))*$')


def vocab(script):
    """산출 스크립트가 코드에 적은 이름 — 문자열 상수와 dict(키=…) 의 키워드 이름."""
    out = set()
    for n in ast.walk(ast.parse(open(script).read())):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
        elif isinstance(n, ast.keyword) and n.arg:
            out.add(n.arg)
    return out


def changed_paths(old, new, V):
    fold = lambda k: k if (k in V or PAIR.match(k)) else '*'
    out = set()

    def walk(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                p = path + (fold(str(k)),)
                if k not in a or k not in b:
                    out.add('/'.join(p) + ' (키 있음/없음)')
                else:
                    walk(a[k], b[k], p)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                out.add('/'.join(path + ('[]',)) + ' (길이)')
            for x, y in zip(a, b):
                walk(x, y, path + ('[]',))
        elif a != b:
            out.add('/'.join(path))

    walk(old, new, ())
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description='봉인 결과 파일의 바뀐 키 경로 (값 없음)')
    ap.add_argument('file', help='저장소 안 결과 파일 경로')
    ap.add_argument('--script', required=True, help='그 파일을 만든 스크립트 — 접지 않을 키 이름의 출처')
    ap.add_argument('--rev', default='HEAD')
    a = ap.parse_args(argv)
    old = json.loads(subprocess.check_output(['git', 'show', f'{a.rev}:{a.file}'], cwd=ROOT))
    new = json.load(open(os.path.join(ROOT, a.file)))
    paths = changed_paths(old, new, vocab(os.path.join(ROOT, a.script)))
    if not paths:
        print(f'{a.file}: {a.rev} 와 같다')
        return
    print(f'{a.file}: {a.rev} 와 다르다. 바뀐 키 경로 (값 · 수 · 판 · 틀 이름은 찍지 않음):')
    for p in paths:
        print('  ', p)


if __name__ == '__main__':
    main()
