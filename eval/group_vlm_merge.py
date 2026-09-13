"""VLM 묶기 서브에이전트 출력(묶음별 파일)을 패스 파일 하나로 합치고 검증한다.

    python eval/group_vlm_merge.py --raw ~/.typo-mcp/group/vlm_raw --pass 1 --lines ~/.typo-mcp/group-lines.json \
        --prompt docs/group_vlm_prompt.md --model-note "Claude Code 서브에이전트, 부모 세션 상속" --out ~/.typo-mcp/group/vlm_pass1.json

검증: 장마다 모든 줄 번호(1..n)가 정확히 한 번씩. 어긴 장은 목록으로 내고(다시 요청할 것), 합친 파일에는
그 장의 원래 답을 그대로 두되 invalid 표시를 한다. 다시 받은 답(redo 파일)이 있으면 그것으로 바꾼다.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os


def _sha(p):
    return hashlib.sha256(open(os.path.expanduser(p), 'rb').read()).hexdigest()


def check(entry, n):
    seen = []
    for g in entry.get('groups', []):
        for v in g:
            seen.append(v)
    ok = sorted(seen) == list(range(1, n + 1))
    return ok, dict(n=n, got=len(seen), missing=sorted(set(range(1, n + 1)) - set(seen)),
                    extra=sorted(set(seen) - set(range(1, n + 1))),
                    dup=sorted({v for v in seen if seen.count(v) > 1}))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True); ap.add_argument('--pass', dest='pas', type=int, required=True)
    ap.add_argument('--lines', required=True); ap.add_argument('--prompt', required=True)
    ap.add_argument('--model-note', default=''); ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    L = json.load(open(os.path.expanduser(a.lines)))['lines']
    raw = os.path.expanduser(a.raw)
    files = sorted(glob.glob(os.path.join(raw, f'pass{a.pas}_b*.json')))
    redo = sorted(glob.glob(os.path.join(raw, f'pass{a.pas}_redo*.json')))
    posters, opened, models, notes, batches = {}, [], set(), [], []
    for f in files + redo:
        d = json.load(open(f))
        batches.append(dict(file=os.path.basename(f), sha256=_sha(f), n=len(d.get('posters', [])),
                            model=d.get('model'), files_opened=d.get('files_opened', [])))
        opened += d.get('files_opened', []); models.add(str(d.get('model')))
        if d.get('notes'): notes.append(f'{os.path.basename(f)}: {d["notes"]}')
        for e in d.get('posters', []):
            k = os.path.basename(e['file']).split('_')[0]
            e['_from'] = os.path.basename(f)
            posters[k] = e          # redo 가 뒤에 오므로 덮어쓴다
    bad = {}
    for k, e in posters.items():
        n = len(L[k]['lines'])
        ok, info = check(e, n)
        e['valid'] = ok
        if not ok:
            bad[k] = info
    out = dict(posters=list(posters.values()), files_opened=sorted(set(opened)),
               model=sorted(models), model_note=a.model_note, date=datetime.date.today().isoformat(),
               prompt=a.prompt, prompt_sha256=_sha(a.prompt), batches=batches, notes=notes,
               invalid={k: v for k, v in bad.items()}, n_posters=len(posters), n_invalid=len(bad),
               n_redo_files=len(redo))
    json.dump(out, open(os.path.expanduser(a.out), 'w'), ensure_ascii=False, indent=1)
    print(f'패스 {a.pas}: 장 {len(posters)} · 어긴 장 {len(bad)} · redo 파일 {len(redo)} · 모델 {sorted(models)}')
    for k, v in bad.items():
        print(' ', k, v)
    ext = [p for p in set(opened) if not (p.endswith('_som.png') or p.endswith('.md'))]
    print('이미지 · 지시문 · 목록 밖의 파일:', ext or '없음')
    print('→', a.out)


if __name__ == '__main__':
    main()
