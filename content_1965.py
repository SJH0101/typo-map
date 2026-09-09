"""브로크만 1965 판의 «내용» — 생성 시험의 브리프.

이 저장소에서 유일하게 «잰 것이 아닌» 자료다. 그래서 따로 둔다.

    글자 내용   easyocr 로 읽고 눈으로 고쳤다
    칸 나눔     내가 뜻으로 갈랐다. 원본의 탭 자리를 보고 정한 것이 아니다
    위계 순위   머리글(1)과 본문(2) 둘뿐이다. 이 판의 브리프가 그렇다

배치는 아무것도 안 들어 있다 — 자리·크기·행간·여백은 전부 generate.py 가
코퍼스 규칙에서 낸다. 그것이 시험의 조건이다.

한 줄이 여러 칸이면 낱말이 축에 붙는다는 뜻이다 (원본이 그렇게 짜여 있다).
"""

C=[
 dict(level=1, lines=[['internationale juni-festwochen 1965 zürich'],
                      ['konzerte der tonhalle-gesellschaft']]),
 dict(level=2, lines=[['1. konzert','dienstag, den 1. juni, 20.15 uhr'],
                      ['leitung','robert f. denzler','solist','zino francescatti'],
                      ['beethoven','dritte leonoren-ouvertüre'],
                      ['brahms','violinkonzert d-dur','strawinski','feuervogel-suite']]),
 dict(level=2, lines=[['2. konzert','donnerstag, den 10. juni, 20.15 uhr'],
                      ['leitung','eugene ormandy','solist','isaac stern'],
                      ['weber','ouvertüre zur oper «der freischütz»'],
                      ['dvořák','violinkonzert a-moll','brahms','zweite sinfonie d-dur']]),
 dict(level=2, lines=[['3. konzert','dienstag, den 15. juni, 20.15 uhr'],
                      ['leitung','alceo galliera','solist','arthur rubinstein'],
                      ['beethoven','fünftes klavierkonzert in es-dur'],
                      ['mahler','erste sinfonie in d-dur']]),
 dict(level=2, lines=[['4. konzert','dienstag, den 22. juni, 20.15 uhr'],
                      ['leitung','zubin mehta','solist','claudio arrau'],
                      ['webern','sechs orchesterstücke','liszt','klavierkonzert a-dur'],
                      ['tschaikowsky','fünfte sinfonie in e-moll']]),
 dict(level=2, lines=[['5. konzert','dienstag, den 29. juni, 20.15 uhr'],
                      ['','mittwoch, den 30. juni, 20.15 uhr'],
                      ['leitung','rudolf kempe','solisten:','gundula janowitz sopran'],
                      ['margrit conrad','alt, ernst häfliger','tenor, kim borg','bass'],
                      ['chor','gemischter chor zürich'],
                      ['beethoven','neunte sinfonie in d-moll']]),
 dict(level=2, lines=[['extra-kammermusikabend'],
                      ['donnerstag, den 17. juni, 20.15 uhr'],
                      ['gedenkkonzert zum 10. todestag von willy burkhard'],
                      ['tonhalle-quartett','ursula buckel','sopran'],
                      ['ursula burkhard','flöte, simon burkhard','klavier'],
                      ['willy burkhard: zweites streichquartett, herbst-kantate'],
                      ['neun morgenstern-lieder, lyrische musik']]),
]
