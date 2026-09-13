"""Claude 눈 판정(대문자 유무)과 EasyOCR 의 일치. 탐색용 · 논문 수치 아님.

    .venv/bin/python docs/labeling/caps_compare.py docs/labeling/caps_claude_eye.json \
        docs/labeling/ocr_easyocr.json docs/labeling/caps_compare.json

OCR 규칙은 결과를 보기 전에 정했다: conf ≥ 0.5, 두 글자 이상인 토큰에 «소문자와 모양이 다른
대문자»(A B D E F G H L M N Q R T Y Ä Ö Ü)가 하나라도 있으면 U. C K O P S U V W X Z 는 대소문자
모양이 같아 OCR 이 자주 뒤바꾸므로 뺐고, I J 는 l · j 와 헷갈려 뺐다.
둘 다 사람 판정이 아니다 — 한쪽을 정답이라 부르지 않는다.
"""
import argparse
import json

DISTINCT = set('ABDEFGHLMNQRTYÄÖÜ')
CONF, MINLEN = 0.5, 2


def ocr_cap(tokens):
    hits = [t for t in tokens
            if t['c'] >= CONF and len(t['t'].strip()) >= MINLEN and any(ch in DISTINCT for ch in t['t'])]
    return ('U' if hits else 'L'), hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('caps')
    ap.add_argument('ocr')
    ap.add_argument('out')
    a = ap.parse_args()
    eye = json.load(open(a.caps))['labels']
    ocr = json.load(open(a.ocr))['out']
    keys = sorted(eye)
    tab = {'eyeU_ocrU': 0, 'eyeU_ocrL': 0, 'eyeL_ocrU': 0, 'eyeL_ocrL': 0}
    diff = []
    for k in keys:
        o, hits = ocr_cap(ocr[k])
        e = eye[k]['cap']
        tab[f'eye{e}_ocr{o}'] += 1
        if o != e:
            diff.append(dict(key=k, eye=e, ocr=o, ocr_hits=[[t['t'], t['c']] for t in hits]))
    n = len(keys)
    po = (tab['eyeU_ocrU'] + tab['eyeL_ocrL']) / n
    pe_u = (tab['eyeU_ocrU'] + tab['eyeU_ocrL']) / n
    po_u = (tab['eyeU_ocrU'] + tab['eyeL_ocrU']) / n
    pe = pe_u * po_u + (1 - pe_u) * (1 - po_u)
    res = dict(
        note='탐색용 · 논문 수치 아님. 눈 판정은 Claude, 사람 판정이 아니다',
        rule=dict(conf=CONF, min_len=MINLEN, distinct_caps=''.join(sorted(DISTINCT))),
        n=n, table=tab, agreement=round(po, 3), kappa=round((po - pe) / (1 - pe), 3),
        disagreements=diff,
        disagreement_review=(
            'eye L · OCR U 6장은 OCR 토큰 자리를 4배 확대해 Claude 가 다시 봤다 — 모두 소문자 '
            '(«zürich», «1.konzert», «zino francescatti», «tschaikowsky», «solisten», «junifestkonzert», '
            '«bis», «tonhalle», «cantando»). eye U · OCR L 9장은 대문자가 규칙에서 뺀 글자(P S V)뿐이거나, '
            '회전 · 저대비 글자라 OCR 이 못 읽은 경우다. 눈 판정을 유지했다.'))
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(tab, res['agreement'], res['kappa'], len(diff))


if __name__ == '__main__':
    main()
