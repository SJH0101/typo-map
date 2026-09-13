"""깨끗한 세트 문구 주머니와 판 안 중복 금지 줄 채우기 — 사전등록 docs/clean_preregister.json 수정 1 (4a763c8).

render.py 의 주머니(원자 56개)로는 좁은 단 · 작은 활자 판에서 같은 문구가 한 판에 15번까지 되풀이됐다.
A · C 는 글자를 보지 않고 VLM 만 보므로 공정한 비교가 아니다. 그래서 원자를 늘리고 판 안에서 다시 쓰지 않는다.

    원자        줄 안에서 두 칸 띄어쓰기로 잇는 한 단위
    역할 6      0 공연 종류 · 1 장소 · 2 일시 · 3 작곡가 · 작품 · 4 역할 · 사람 · 5 입장권 · 안내
    줄 채우기   그 역할의 안 쓴 원자를 판마다 섞은 순서에서 잇다가 넘치는 첫 원자에서 멈춘다 (최대 6원자).
                단 폭 60% 이상이면 받고, 아니면 시작점을 옮겨 최대 40번. 끝내 못 미치면 가장 넓은 시도
    바닥날 때   단 폭에 드는 안 쓴 원자가 없으면 다음 역할에서 빌린다 (빌린 줄). 모두 바닥나면 가장 적게 쓴
                원자를 다시 쓴다 (반복)

글자는 기존 주머니와 같은 45자 (소문자 · 숫자 · «,-.» · äöü éîó) 안에서만 짓는다 — 최소 거리 1.826 x높이가 그대로다.
인명은 1950~60년대 취리히 연주회에 나올 법한 실제 음악가를 글자 채움용으로만 쓴다.
"""
SUB = ['sinfoniekonzert', 'kammermusik-abend', 'schweizerische erstaufführung', 'neuinszenierung',
       '13. konzert der tonhalle-gesellschaft', 'orgelkonzert', 'liederabend', 'klavierabend', 'violinabend',
       'chorkonzert', 'serenade', 'matinee', 'jugendkonzert', 'abonnementskonzert', 'sonderkonzert', 'festkonzert',
       'uraufführung', 'erstaufführung', 'gastspiel', 'konzertreihe', 'studiokonzert', 'hauskonzert',
       'kirchenkonzert', 'volkskonzert', 'extrakonzert', 'galakonzert', 'wiederholung', 'öffentliche hauptprobe',
       'kammerorchester', 'kammerchor', 'bläserabend', 'duoabend', 'triokonzert', 'quartettabend', 'ballettabend',
       'opernabend', 'sommerkonzert', 'neujahrskonzert', 'adventskonzert', 'passionskonzert']
SUB += [f'{n}. abonnementskonzert' for n in range(1, 21)] + [f'{n}. kammermusikabend' for n in range(1, 16)] \
     + [f'{n}. orgelvesper' for n in range(1, 9)]
VENUE = ['tonhalle grosser saal zürich', 'kunstgewerbemuseum zürich', 'schauspielhaus zürich', 'helmhaus zürich',
         'kongresshaus zürich', 'tonhalle kleiner saal', 'grossmünster', 'fraumünster', 'st. peter', 'predigerkirche',
         'stadthaus zürich', 'opernhaus zürich', 'kunsthaus zürich', 'volkshaus zürich', 'aula der universität',
         'eth hauptgebäude', 'zunfthaus zur meisen', 'rathaus zürich', 'musiksaal', 'stadttheater', 'landesmuseum',
         'kasino', 'kirche neumünster', 'wasserkirche', 'radiostudio zürich', 'zunfthaus zur zimmerleuten',
         'hotel savoy', 'haus zum rechberg', 'pestalozzianum', 'stadthaus winterthur', 'kunstmuseum bern',
         'münster basel', 'stadtcasino basel']
ORT = ['enge', 'fluntern', 'oberstrass', 'wollishofen', 'altstetten', 'höngg', 'wiedikon', 'aussersihl', 'hottingen',
       'hirslanden', 'riesbach', 'unterstrass', 'wipkingen', 'seebach', 'oerlikon', 'schwamendingen', 'affoltern',
       'albisrieden', 'witikon', 'leimbach', 'kilchberg', 'küsnacht', 'thalwil', 'horgen', 'meilen', 'uster',
       'dübendorf', 'winterthur', 'baden', 'zug']
VENUE += [f'kirche {o}' for o in ORT] + [f'kirchgemeindehaus {o}' for o in ORT[:12]]
WEEK = ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']
MONTH = ['januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli', 'august', 'september', 'oktober', 'november',
         'dezember']
HOUR = ['11.00 uhr', '16.00 uhr', '17.00 uhr', '17.30 uhr', '19.30 uhr', '20.00 uhr', '20.15 uhr', '20.30 uhr',
        '10.30 uhr', '15.00 uhr']
DATES = [f'{w} {d}. {m} {y}' for w in WEEK for d in (1, 8, 14, 21, 28) for m in MONTH for y in (1956, 1958, 1961, 1964)] \
      + [f'{d}. {m}' for d in range(1, 29) for m in MONTH]
COMPOSER = ['anton webern', 'alban berg', 'arnold schönberg', 'igor strawinsky', 'béla bartók', 'paul hindemith',
            'olivier messiaen', 'frank martin', 'karlheinz stockhausen', 'jacques wildberger', 'wolfgang fortner', 'bach',
            'händel', 'haydn', 'mozart', 'beethoven', 'schubert', 'schumann', 'brahms', 'bruckner', 'mahler', 'debussy',
            'ravel', 'honegger', 'othmar schoeck', 'luciano berio', 'pierre boulez', 'luigi nono', 'bohuslav martinu',
            'prokofjew', 'schostakowitsch', 'benjamin britten', 'darius milhaud', 'albert roussel', 'leos janacek',
            'antonin dvorak', 'giuseppe verdi', 'richard strauss', 'max reger', 'conrad beck', 'willy burkhard',
            'rudolf kelterborn', 'klaus huber', 'armin schibler', 'heinrich sutermeister', 'hans werner henze',
            'ernst krenek', 'carl orff', 'werner egk', 'boris blacher', 'györgy ligeti', 'vivaldi', 'monteverdi',
            'purcell', 'telemann']
WORK = ['sechs stücke für orchester', 'kammerkonzert', 'variationen op. 31', 'agon', 'musik für saiteninstrumente',
        'turangalîla-sinfonie', 'petite symphonie concertante', 'gruppen für drei orchester', 'requiem',
        'messe in h-moll', 'stabat mater', 'te deum', 'magnificat', 'jeux', 'la mer', 'boléro',
        'le sacre du printemps', 'pierrot lunaire', 'wozzeck', 'lulu', 'mathis der maler', 'die schöpfung',
        'die jahreszeiten', 'matthäus-passion', 'johannes-passion', 'ein deutsches requiem', 'sinfonie nr. 5',
        'sinfonie nr. 9', 'klavierkonzert nr. 3', 'violinkonzert', 'cellokonzert', 'streichquartett', 'bläserquintett',
        'klaviertrio', 'oktett', 'divertimento', 'concerto grosso', 'passacaglia', 'fantasie', 'toccata', 'partita',
        'suite', 'ouvertüre', 'nocturnes', 'images', 'vesper', 'kantate', 'motette', 'oratorium', 'capriccio']
ROLE = ['musikalische leitung', 'inszenierung', 'bühnenbild', 'kostüme', 'choreographie', 'solist', 'chorleitung',
        'solistin', 'dirigent', 'klavier', 'violine', 'viola', 'violoncello', 'kontrabass', 'flöte', 'oboe', 'klarinette',
        'fagott', 'horn', 'orgel', 'cembalo', 'sopran', 'alt', 'tenor', 'bass', 'sprecher', 'einstudierung', 'regie',
        'ausstattung', 'trompete', 'harfe', 'schlagzeug', 'posaune', 'tuba', 'celesta', 'gitarre', 'laute', 'blockflöte',
        'mezzosopran', 'bariton', 'knabenchor', 'frauenchor', 'männerchor', 'streichorchester', 'bläserensemble',
        'continuo', 'gesang', 'rezitation', 'tanz', 'bühnenmusik', 'chorsolisten', 'orchesterleitung', 'assistenz',
        'lichtregie', 'maske', 'souffleuse', 'inspizienz', 'technik', 'dramaturgie', 'übersetzung', 'orgelsolo',
        'klaviersolo', 'violinsolo', 'cellosolo', 'flötensolo', 'hornsolo', 'oboesolo', 'sprechchor', 'kinderchor',
        'vokalensemble', 'solisten', 'organist', 'pianist', 'cembalist', 'geiger', 'cellist', 'sängerin', 'sänger']
PERSON = ['hans rosbaud', 'erich schmid', 'charles dutoit', 'paul burkhard', 'nicolas beriozoff', 'max stubenrauch',
          'elisabeth liechti', 'paul sacher', 'ernest ansermet', 'edmond de stoutz', 'rudolf baumgartner',
          'clara haskil', 'dinu lipatti', 'wilhelm backhaus', 'maria stader', 'ernst haefliger', 'margrit weber',
          'aurele nicolet', 'heinz holliger', 'paul baumgartner', 'sandor vegh', 'andré jaunet', 'luc balmer',
          'victor desarzens', 'silvio varviso', 'josef krips', 'rafael kubelik', 'karl böhm', 'eugen jochum',
          'ferenc fricsay', 'hermann scherchen', 'zino francescatti', 'isaac stern', 'arthur rubinstein',
          'claudio arrau', 'pierre fournier', 'andrés segovia', 'dietrich fischer-dieskau', 'elisabeth schwarzkopf',
          'irmgard seefried', 'lisa della casa', 'christa ludwig', 'hugues cuénod', 'august wenzinger', 'marcel dupré',
          'peter lukas graf', 'kurt rothenbühler', 'johannes fuchs', 'hans vogt', 'ursula mamlok']
SALE = ['vorverkauf tonhalle, hug, jecklin', 'karten fr. 3.- bis 12.-', 'eintritt frei',
        'geöffnet täglich 10-12 und 14-18 uhr', 'tonhallekasse und depositenkasse', 'abendkasse ab 19 uhr',
        'numerierte plätze', 'freie platzwahl', 'kollekte', 'studenten halber preis', 'programm fr. 1.-',
        'karten bei jecklin', 'reservation telefon 32 24 75', 'keine abendkasse', 'schüler fr. 2.-', 'mitglieder frei',
        'saalöffnung 19.30 uhr', 'ende gegen 22 uhr', 'dauer 90 minuten', 'ohne pause', 'mit pause',
        'türöffnung 19.45 uhr', 'platzmiete inbegriffen', 'karten fr. 4.- bis 15.-', 'karten fr. 2.- bis 6.-',
        'vorverkauf ab montag', 'kasse eine stunde vorher', 'garderobe inbegriffen', 'jugendliche fr. 1.50',
        'abonnement gültig']
PRICE = [('2.-', '6.-'), ('3.-', '8.-'), ('3.-', '12.-'), ('4.-', '15.-'), ('5.-', '18.-'), ('2.50', '9.-'),
         ('3.50', '10.-'), ('4.50', '14.-'), ('6.-', '20.-'), ('1.50', '5.-')]
SALE += [f'karten fr. {a} bis {b}' for a, b in PRICE] \
      + [f'vorverkauf ab {d}. {m}' for d in (1, 10, 20) for m in ('mai', 'juni', 'oktober', 'november')] \
      + [f'abendkasse ab {h} uhr' for h in ('18.30', '19.00', '19.15', '19.30', '19.45')] \
      + [f'dauer {n} minuten' for n in (45, 60, 75, 80, 100, 110, 120)] \
      + [f'telefon {a} {b} {c}' for a, b, c in (('32', '24', '75'), ('34', '17', '20'), ('27', '05', '66'),
                                                ('47', '11', '10'), ('23', '89', '41'))] \
      + ['fr. 2.-', 'fr. 3.-', 'fr. 4.-', 'fr. 5.-', 'fr. 6.-', 'fr. 8.-', 'fr. 10.-', 'fr. 12.-', 'fr. 15.-',
         'abendkasse', 'vorverkauf', 'reservation', 'platzmiete', 'garderobe', 'kollekte frei', 'keine pause',
         'eine pause', 'zwei pausen', 'programmheft', 'sitzplätze', 'stehplätze', 'balkon fr. 5.-', 'parkett fr. 8.-',
         'galerie fr. 3.-', 'loge fr. 12.-']

ROLES = [sorted(set(SUB)), sorted(set(VENUE)), sorted(set(DATES + HOUR)), sorted(set(COMPOSER + WORK)),
         sorted(set(ROLE + PERSON)), sorted(set(SALE))]
ROLE_NAMES = ('공연 종류', '장소', '일시', '작곡가 · 작품', '역할 · 사람', '입장권 · 안내')
SEP = '  '
MAX_ATOMS = 6
FILL_MIN = 0.60
TRIES = 40


def charset():
    return sorted({ch for r in ROLES for s in r for ch in s if not ch.isspace()})


class Filler:
    """판 하나의 줄 채우기. 판마다 새로 만든다 (쓴 원자를 기억한다)."""

    def __init__(self, rnd):
        self.order = [[r[i] for i in rnd.permutation(len(r))] for r in ROLES]
        self.used = {}
        self.width = {}
        self.stats = dict(lines=0, borrowed=0, repeated=0, short=0)

    def _w(self, font, s):
        key = (font.size, s)
        if key not in self.width:
            self.width[key] = font.getlength(s)
        return self.width[key]

    def _fill(self, cands, font, width):
        best, bw = [], 0.0
        for start in range(min(TRIES, len(cands))):
            parts = []
            for a in cands[start:]:
                if len(parts) >= MAX_ATOMS or font.getlength(SEP.join(parts + [a])) > width:
                    break
                parts.append(a)
            if not parts:
                continue
            w = font.getlength(SEP.join(parts))
            if w >= FILL_MIN * width:
                return parts
            if w > bw:
                best, bw = parts, w
        return best

    def line(self, role, font, width):
        self.stats['lines'] += 1
        for step in range(len(ROLES)):
            r = (role + step) % len(ROLES)
            cands = [a for a in self.order[r] if a not in self.used and self._w(font, a) <= width]
            parts = self._fill(cands, font, width)
            if parts:
                if step:
                    self.stats['borrowed'] += 1
                return self._take(parts, role, r, False, font, width)
        pool = sorted((self.used.get(a, 0), ri, a) for ri, r in enumerate(ROLES) for a in r if self._w(font, a) <= width)
        if pool:
            self.stats['repeated'] += 1
            return self._take([pool[0][2]], role, pool[0][1], True, font, width)
        ri, a = min(((ri, a) for ri, r in enumerate(ROLES) for a in r), key=lambda t: self._w(font, t[1]))
        self.stats['repeated'] += 1
        return self._take([a], role, ri, True, font, width)

    def _take(self, parts, role, used_role, repeated, font, width):
        for a in parts:
            self.used[a] = self.used.get(a, 0) + 1
        text = SEP.join(parts)
        if font.getlength(text) < FILL_MIN * width:
            self.stats['short'] += 1
        return text, dict(role=role, role_used=used_role, atoms=list(parts), repeated=repeated)
