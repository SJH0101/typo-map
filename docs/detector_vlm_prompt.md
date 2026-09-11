너는 포스터 이미지 26장에 «눈에 보이는 타이포 덩어리» 마다 상자를 긋는다. 결과는 JSON 파일 하나로 쓴다.

## 지켜야 할 것
- 아래 목록의 이미지 26장만 Read 도구로 연다. 그 밖의 파일·폴더는 열지도 찾지도(ls·grep·glob·find) 말라. 저장소 코드, CSV, 라벨, 캐시, 문서 전부 금지다. 셸 명령도 쓰지 말라.
- 쓰기는 지정한 출력 파일 하나만 한다.
- 이미지는 원본 배율 그대로 본다. 확대·축소·자르기를 하지 않는다. 좌표는 원본 픽셀(왼쪽 위가 0,0)이고 목록의 img_w, img_h 안에 있어야 한다.
- 26장 모두 긋는다. 건너뛰지 않는다.

## 판정 규칙
- 줄들이 서로 붙어 있고, 그 덩어리 둘레에 훨씬 넓은 틈이 있으면 한 덩어리다. 안쪽 간격보다 두 배 넘게 벌어지는 자리에서 끊는다.
- 틈만 본다. 틈을 몇 px 로 재지 않고 이웃한 틈끼리 견준다.
- 크기는 보지 않는다. 줄마다 크기가 달라도 붙어 있으면 한 덩어리다.
- 정렬도 보지 않는다. 다만 줄들이 가로로 전혀 안 겹치면 따로다 (표에서 단이 나뉜 경우).
- 줄이 하나뿐이어도 덩어리다.
- 애매하면 끊는다. 나중에 합칠 수는 있어도 쪼갤 수는 없다.
- 상자는 잉크 전체를 감싼다. 글자의 진짜 맨 위와 맨 아래까지 — 디센더(g·y·p·j 의 꼬리)와 발음기호(ä·ü·ö 의 점)를 포함한다.
- 역할(제목·본문 등)은 따지지 않는다.

## 출력
지정한 경로에 아래 모양의 JSON 을 쓴다.

{"posters": [{"file": "<목록의 file 그대로>", "img_w": <정수>, "img_h": <정수>,
              "boxes": [[x1, y1, x2, y2], ...]}, ...],
 "files_opened": ["<열어 본 파일 경로 전부>"],
 "notes": "<짧게. 판정이 어려웠던 장이 있으면>"}

마지막 보고에는 출력 파일 경로, 장별 상자 수, 열어 본 파일 목록만 적는다.

## 포스터 26장
- file: 1985_Richard Paul Lohse - Kunstmuseum Luzern.jpg
  path: /Users/junhyeoksong/Documents/연구2/로제정리/corpus/코어/Ausstellung/1985_Richard Paul Lohse - Kunstmuseum Luzern.jpg
  img_w: 567  img_h: 800
- file: 1952_Gewerbemuseum Basel - 14. Juni - 13. Juli 1952 - Die Ausbild.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/F4/Gewerbemuseum_Basel/1952_Gewerbemuseum Basel - 14. Juni - 13. Juli 1952 - Die Ausbild.jpg
  img_w: 554  img_h: 800
- file: 1961_Basel und die Stadtstrassen der Zukunft - Gewerbemuseum Base.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Gewerbemuseum_Basel/1961_Basel und die Stadtstrassen der Zukunft - Gewerbemuseum Base.jpg
  img_w: 565  img_h: 800
- file: 1953_Tonhalle Zürich - 5. Frühjahrskonzert - Leitung Erich Schmid.jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/F4/Tonhalle_Konzert/1953_Tonhalle Zürich - 5. Frühjahrskonzert - Leitung Erich Schmid.jpg
  img_w: 560  img_h: 800
- file: 1952_de Boer-Reitz-Quartett - Tonhalle Kleiner Saal - 8. Kammermu.jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/F4/Tonhalle_Konzert/1952_de Boer-Reitz-Quartett - Tonhalle Kleiner Saal - 8. Kammermu.jpg
  img_w: 560  img_h: 800
- file: 1956_Kunsthalle Basel - Bauchant - Bombois - Séraphine - Vivin - .jpg
  path: /Users/junhyeoksong/Documents/연구2/루더정리/corpus/코어/Kunsthalle_Basel/1956_Kunsthalle Basel - Bauchant - Bombois - Séraphine - Vivin - .jpg
  img_w: 566  img_h: 800
- file: 1960_Musica viva - Donnerstag, 10. März 1960 - Tonhalle Grosser S.jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/코어/Musica_Viva/1960_Musica viva - Donnerstag, 10. März 1960 - Tonhalle Grosser S.jpg
  img_w: 563  img_h: 800
- file: 1957_Basler Privatbesitz - Kunsthalle Basel - 4. Juli - 29. Septe.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Kunsthalle_Basel/1957_Basler Privatbesitz - Kunsthalle Basel - 4. Juli - 29. Septe.jpg
  img_w: 566  img_h: 800
- file: 1958_Stadt Theater Basel - Saison-Beginn 19. September 1958 - Sin.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Stadttheater_Basel/1958_Stadt Theater Basel - Saison-Beginn 19. September 1958 - Sin.jpg
  img_w: 562  img_h: 800
- file: 1959_Stadttheater Basel - Halbe Saison - Halbes Abonnement - Halb.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Stadttheater_Basel/1959_Stadttheater Basel - Halbe Saison - Halbes Abonnement - Halb.jpg
  img_w: 566  img_h: 800
- file: 1957_Die Schweiz zur Römerzeit - Mustermesse Baslerhalle.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Sonstige/1957_Die Schweiz zur Römerzeit - Mustermesse Baslerhalle.jpg
  img_w: 567  img_h: 800
- file: 1966_Opernhaus Zürich - Wenn ich König wär... - Oper von Adolphe .jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/코어/Opernhaus/1966_Opernhaus Zürich - Wenn ich König wär... - Oper von Adolphe .jpg
  img_w: 564  img_h: 800
- file: 1953_Tonhalle Grosser Saal - Juni-Festwochen Zürich 1953 - Tonhal.jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/코어/Juni_Festwochen/1953_Tonhalle Grosser Saal - Juni-Festwochen Zürich 1953 - Tonhal.jpg
  img_w: 569  img_h: 800
- file: 1956_Verborgene Schätze des Gewerbemuseums - Gewerbemuseum Basel.jpg
  path: /Users/junhyeoksong/Documents/연구2/루더정리/corpus/코어/Gewerbemuseum_Basel/1956_Verborgene Schätze des Gewerbemuseums - Gewerbemuseum Basel.jpg
  img_w: 563  img_h: 800
- file: 1958_Kunstmuseum Winterthur - Ungegenständliche Malerei in der Sc.jpg
  path: /Users/junhyeoksong/Documents/연구2/로제정리/corpus/코어/Ausstellung/1958_Kunstmuseum Winterthur - Ungegenständliche Malerei in der Sc.jpg
  img_w: 568  img_h: 800
- file: 1961_René Auberjonois - Ernest Bolens - Kunsthalle Basel.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Kunsthalle_Basel/1961_René Auberjonois - Ernest Bolens - Kunsthalle Basel.jpg
  img_w: 568  img_h: 800
- file: 1963_Kreis 48 - Ernst Messerli - Werner Witschi - (...) Kunsthall.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Kunsthalle_Basel/1963_Kreis 48 - Ernst Messerli - Werner Witschi - (...) Kunsthall.jpg
  img_w: 566  img_h: 800
- file: 1950_Zürcher Künstler im Helmhaus.jpg
  path: /Users/junhyeoksong/Documents/연구2/로제정리/corpus/코어/Ausstellung/1950_Zürcher Künstler im Helmhaus.jpg
  img_w: 572  img_h: 800
- file: 1965_Sektion Basel der Gesellschaft Schweizer Maler Bildhauer und.jpg
  path: /Users/junhyeoksong/Documents/연구2/루더정리/corpus/코어/Kunsthalle_Basel/1965_Sektion Basel der Gesellschaft Schweizer Maler Bildhauer und.jpg
  img_w: 563  img_h: 800
- file: 1950_100 Jahre Eisenbeton - Kunstgewerbemuseum Zürich.jpg
  path: /Users/junhyeoksong/Documents/연구2/로제정리/corpus/코어/Gewerbemuseum_etc/1950_100 Jahre Eisenbeton - Kunstgewerbemuseum Zürich.jpg
  img_w: 570  img_h: 800
- file: 1949_Ausstellung im Gewerbemuseum Basel - Photographie in der Sch.jpg
  path: /Users/junhyeoksong/Documents/연구2/호프만정리/corpus/코어/Gewerbemuseum_Basel/1949_Ausstellung im Gewerbemuseum Basel - Photographie in der Sch.jpg
  img_w: 565  img_h: 800
- file: 1958_Kunststoffe - Gewerbemuseum Winterthur.jpg
  path: /Users/junhyeoksong/Documents/연구2/로제정리/corpus/코어/Gewerbemuseum_etc/1958_Kunststoffe - Gewerbemuseum Winterthur.jpg
  img_w: 563  img_h: 800
- file: 1953_3. Frühjahrskonzert der Tonhalle-Gesellschaft - Dienstag 28..jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/F4/Tonhalle_Konzert/1953_3. Frühjahrskonzert der Tonhalle-Gesellschaft - Dienstag 28..jpg
  img_w: 554  img_h: 800
- file: 1962_Neue Wirtshausschilder - Gewerbemuseum Basel.jpg
  path: /Users/junhyeoksong/Documents/연구2/루더정리/corpus/코어/Gewerbemuseum_Basel/1962_Neue Wirtshausschilder - Gewerbemuseum Basel.jpg
  img_w: 563  img_h: 800
- file: 1959_Musica Viva - Kleiner Tonhallesaal - Matthias Hauer - Werner.jpg
  path: /Users/junhyeoksong/Documents/연구2/브로크만 정리/corpus/코어/Musica_Viva/1959_Musica Viva - Kleiner Tonhallesaal - Matthias Hauer - Werner.jpg
  img_w: 563  img_h: 800
- file: 1970_Lohse - Kunsthalle Bern.jpg
  path: /Users/junhyeoksong/Documents/연구2/로제정리/corpus/코어/Ausstellung/1970_Lohse - Kunsthalle Bern.jpg
  img_w: 565  img_h: 800
