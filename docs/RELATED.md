# 선행연구 — 세 갈래와 그 사이의 빈 자리

> **물음.** 작품에서 작가를 역산하는 계산 연구가 그래픽 디자인에 있는가

2026-08-30 · 웹 검색 3회 + Google Scholar 4회 (영어·독일어·일본어)

세 갈래가 각각 절반씩 갖고 있고 교집합이 비어 있다. 스타일로메트리는 작가를 묻지만 손이 남는 매체만 다루고, 디자인 계량 연구는 포스터를 재지만 작가를 묻지 않으며, 디자인사는 작가를 다루지만 계량하지 않는다.

---

## 갈래

### A. 시각 스타일로메트리 — 작가를 묻는다. 다만 손이 남는 매체만

- **재는 것** 실행의 흔적 (붓질 질감, 획, 그림체)
- **작가 개념** True
- **우리와의 차이** 인쇄 그래픽 디자인에는 손이 없다. 오프셋으로 찍힌 판에서 컨투어렛·웨이블릿을 재면 인쇄 망점이 나온다. 어휘가 통째로 옮겨오지 않는다. 그리고 표현이 신경망·변환 계수라 사람이 읽을 수 없다.
- 모은 것 8건

### B. 그래픽 디자인 계산 연구 — 포스터를 잰다. 다만 작가를 묻지 않는다

- **재는 것** 「좋은 디자인인가」 — 정렬도, 미적 점수, 레이아웃 품질
- **작가 개념** False
- **우리와의 차이** 누가 만들었나를 묻지 않는다. 생성도 「명세에 맞는 레이아웃」이지 「이 사람의 레이아웃」이 아니다.
- 모은 것 17건

### C. 디자인사·질적 연구 — 작가를 다룬다. 다만 계량하지 않는다

- **재는 것** 역사, 이념, 기호학적 독해
- **작가 개념** True
- **우리와의 차이** 코퍼스를 쓰더라도 세지 않는다. 귀무모형이 없다.
- 모은 것 4건

### D. 일본 디자인학 정량 연구 — 포스터도 재고 디자이너도 비교한다. 다만 둘을 잇지 않는다

- **재는 것** 우수 포스터의 구성 요소 / 디자이너의 스케치 기법
- **작가 개념** 부분적
- **우리와의 차이** 작가를 비교할 때는 과정(스케치)을 보고, 작품을 잴 때는 작가를 안 본다.
- 모은 것 4건

### E. 인접 — 암묵지와 원전

- **재는 것** 디자이너의 말할 수 없는 앎 / 작가 자신이 적은 규칙
- **작가 개념** True
- **우리와의 차이** 우리 연구의 근거이자 검증 대상이다. 적대적 선행연구가 아니라 재료.
- 모은 것 3건

---

## 목록

### A — 시각 스타일로메트리

- **CNN-based classification of illustrator style in graphic novels: Which features contribute most?**  
  J Laubrock, D Dubray · 2019 · MMM 2019, LNCS 11296 (Springer)  
  https://easychair.org/publications/preprint/BLds  
  요지: Graphic Narrative Corpus 의 만화책 약 200권·5만 쪽을 일러스트레이터 약 200명으로 분류. Inception V3 의 어느 mixed-layer 까지 쓰는지를 바꿔가며 어느 층위 특징이 기여하는지 봤다. 정확도 92%(층0) → 97%(상위층). mixed-layer 5 위로는 과적합 조짐. 「page layout and coloring scheme are important contributors」 라고 명시.  
  **가깝다**: 제일 가깝고, 우리 전제를 **뒷받침한다** — 작가를 가르는 데 «판면 배치» 가 기여한다는 것을 5만 쪽 규모로 보였다. 초록에 「CNN features are general enough to provide the foundation of a visual stylometry」.  
  **차이**: ① 배치가 «기여한다» 까지고 «배치의 무엇이» 는 못 말한다 — CNN 특징이라 읽을 수 없다. ② 분류만 하고 생성으로 되돌려 검증하지 않는다. ③ 만화는 손그림이라 그림체가 남는다. 실제로 색 배합과 텍스처 같은 중간층 특징으로 충분했다.  
  쓰임: 적대적 선행연구가 아니라 근거로 인용한다 — 「배치가 작가를 나른다」는 우리 전제의 대규모 증거.  
  *확인: 초록 전문 + 검색 요약. 본문 PDF 는 아직*
- **On the track of visual style: A diachronic study of page composition in comics and its functional motivation**  
  J A Bateman, F O D Veloso, Y L Lau · 2021 · Visual Communication  
  요지: 만화 페이지 구성의 통시적 변화를 분석  
  **차이**: 레이아웃을 재지만 작가가 아니라 시대를 본다  
  *확인: 제목·초록 조각*
- **A survey of computational methods for iconic image analysis**  
  N Van Noord · 2022 · Digital Scholarship in the Humanities  
  요지: 도상 이미지 계산 분석 서베이. 포스터를 예시로 언급  
  **차이**: 서베이이고 포스터는 지나가는 예시  
  *확인: 제목·초록 조각*
- **Geometric Tight Frame based Stylometry for Art Authentication of van Gogh Paintings**  
  H Li 외 · 2014 · arXiv 1407.0439  
  https://arxiv.org/pdf/1407.0439  
  요지: 기하 타이트 프레임 계수 통계로 반 고흐 진위 감정  
  *확인: 제목·초록*
- **Visual stylometry using background selection and wavelet-HMT-based Fisher information distances for attribution and dating of impressionist paintings**  
  — · 2012 · Signal Processing (Elsevier)  
  요지: 웨이블릿 HMT 로 인상주의 회화 귀속·연대추정  
  *확인: 제목*
- **Stylometry of paintings using hidden Markov modelling of contourlet transforms**  
  — · 2012 · Signal Processing (Elsevier)  
  요지: 컨투어렛 변환으로 붓질을 표현. 컨투어렛을 쓰는 이유가 붓질 같은 조각적 매끄러운 윤곽을 잘 담아서라고 명시  
  *확인: 제목·초록 조각*
- **Stylometrics of artwork: uses and limitations**  
  J Hughes 외 · 2010 · SPIE  
  https://people.hws.edu/graham/SPIE2010_print_JH.pdf  
  요지: 시각 스타일로메트리의 한계를 다룬다. 귀속·연대 정확도가 70~80% 수준이며 더 나아가야 한다고 적음  
  **가깝다**: 물음의 형태가 같다 — 「어디까지 되는가」  
  **차이**: 회화 대상  
  *확인: 제목·초록 조각*
- **Surveying Stylometry Techniques and Applications**  
  T Neal, K Sundararajan, A Fatima, Y Yan · 2017 · ACM Computing Surveys  
  https://dl.acm.org/doi/10.1145/3132039  
  요지: 텍스트 스타일로메트리 전반 서베이. 이 분야의 표준 인용  
  *확인: 제목·출처*

### B — 그래픽 디자인 계산 연구

- **From Fragment to One Piece: A Survey on AI-Driven Graphic Design**  
  2025 · arXiv 2503.18641  
  https://arxiv.org/html/2503.18641v1  
  요지: AI 그래픽 디자인 서베이. 지각 과제와 생성 과제로 나눔  
  **차이**: 작가라는 축이 아예 없다  
  *확인: 제목·초록*
- **Design-o-meter: Towards Evaluating and Refining Graphic Designs**  
  2024 · arXiv 2411.14959  
  https://arxiv.org/html/2411.14959v1  
  요지: 디자인의 «좋음» 을 데이터로 수치화하고 개선안을 제시  
  **차이**: 품질을 재지 정체를 재지 않는다  
  *확인: 제목·초록*
- **Evaluation Metrics for Automated Typographic Poster Generation**  
  2024 · arXiv 2402.06945 / Springer  
  https://arxiv.org/pdf/2402.06945  
  요지: 타이포 포스터의 가독성·미적 특징·의미 적합성을 재는 휴리스틱 지표  
  **가깝다**: 재는 항목이 우리와 겹친다 (정렬·균형·여백)  
  **차이**: 「좋은 조판인가」를 묻지 「누구의 조판인가」를 묻지 않는다  
  *확인: 제목·초록*
- **Composition-aware Graphic Layout GAN for Visual-textual Presentation Designs**  
  2022 · arXiv 2205.00303  
  https://arxiv.org/pdf/2205.00303  
  *확인: 제목*
- **PosterLLaVa: Constructing a Unified Multi-modal Layout Generator with LLM**  
  2024 · arXiv 2406.02884  
  *확인: 제목*
- **CreatiPoster: Towards Editable and Controllable Multi-Layer Graphic Design Generation**  
  2026 · arXiv 2506.10890  
  *확인: 제목*
- **POSTA: A Go-to Framework for Customized Artistic Poster Generation**  
  2025 · arXiv 2503.14908  
  *확인: 제목*
- **AutoPoster: A Highly Automatic and Content-aware Design System for Advertising Poster Generation**  
  2023 · arXiv 2308.01095  
  *확인: 제목*
- **COLE: A Hierarchical Generation Framework for Multi-Layered and Editable Graphic Design**  
  2023 · arXiv 2311.16974  
  *확인: 제목*
- **LayoutRectifier: An Optimization-based Post-processing for Graphic Design Layout Generation**  
  2025 · arXiv 2508.11177  
  *확인: 제목*
- **DesignProbe: A Graphic Design Benchmark for Multimodal Large Language Models**  
  2024 · arXiv 2404.14801  
  *확인: 제목*
- **PRISM: Learning Design Knowledge from Data for Stylistic Design Improvement**  
  2026 · arXiv 2601.11747  
  https://arxiv.org/abs/2601.11747  
  요지: 실제 디자인 데이터에서 지식 베이스를 만든다 — 디자인을 군집하고, 디자인 원리를 요약하고, 개선할 때 꺼내 쓴다. Crello 데이터셋. style alignment 평가에서 평균 순위 1.49.  
  **가깝다**: 방법의 결이 가깝다 — 데이터에서 «디자인 원리» 를 뽑아 언어로 요약하고 다시 쓴다. 「VLM 은 미니멀리즘을 추상 디자인과 엮지만 디자이너는 형태와 색 선택을 강조한다」 는 문제의식도 우리와 비슷하다.  
  **차이**: 결정적으로 다르다 — «양식» 이 명명된 범주(미니멀리즘 등)지 «개인» 이 아니다. 특정 디자이너를 기술하거나 귀속하지 않는다. 그리고 뽑은 원리가 맞는지 생성으로 반증하지 않고 선호 평가로 확인한다.  
  *확인: 초록 전문*
- **Aesthetics++: Refining Graphic Designs by Exploring Design Principles and Human Preference**  
  2022 · IEEE TVCG  
  *확인: 제목*
- **Computational aesthetics and applications**  
  PMC7099549  
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7099549/  
  *확인: 제목·초록*
- **System and method for using design features to search for page layout designs**  
  US Patent 9367523  
  https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9367523  
  요지: 페이지 레이아웃마다 «style dimension» 별 점수를 내어 검색  
  **가깝다**: 양식을 여러 축의 점수로 쪼갠다는 발상이 우리와 같다  
  **차이**: 작가가 아니라 검색용 태그. 특허라 검증 절차가 없다  
  *확인: 제목·초록*
- **Research and Extraction on Intelligent Generation Rules of Posters in Graphic Design**  
  2019 · Springer  
  요지: 격자 체계로 포스터 레이아웃 유형별 규칙을 뽑음  
  *확인: 제목*
- **Reconstructing Graphic Design Posters via Visual Decomposition and Semantic Layer Translation**  
  2025 · SIGGRAPH Posters (ACM)  
  https://dl.acm.org/doi/full/10.1145/3721250.3743040  
  요지: 포스터를 분해해 편집 가능한 층으로 되돌림  
  **가깝다**: «되돌린다» 는 말이 겹친다  
  **차이**: 한 장을 층으로 분해하는 것이지 작가를 기술하지 않는다  
  *확인: 제목*

### C — 디자인사·질적 연구

- **Funktion des Bildstils von politischen Plakaten**  
  S Demarmels · 2006 · —  
  요지: 정치 포스터의 이미지 양식을 코퍼스로 통시 분석  
  **가깝다**: 포스터 코퍼스를 쓴다  
  **차이**: 기호학·담론 분석이지 계량이 아니다  
  *확인: 제목·초록 조각*
- **Der Typografiestreit von 1946**  
  U Jonischeit · 2000 · Univ. Oldenburg  
  요지: 1950~60년대 스위스 타이포그래피와 이념 논쟁  
  *확인: 제목*
- **Typografische Landschaften / Cultural stereotypes in letter forms in public space**  
  I Wachendorff · 2018, 2025 · NERD – New Experimental Research in Design / DuEPublico  
  요지: 공공 공간의 활자 25,500점 코퍼스. 사회적 행위자들이 활자를 어떻게 쓰는가  
  **가깝다**: 큰 코퍼스를 계량한다  
  **차이**: 작가가 아니라 사회적 사용을 본다  
  *확인: 제목·초록 조각*
- **From Edo period to present: Tracing the development of Japanese graphic design in posters**  
  N Lin, S A B C Cobé · 2024 · Herança  
  요지: 질적 역사 연구  
  *확인: 제목*

### D — 일본 디자인학 정량 연구

- **優秀ポスターを構成するデザイン要素の研究**  
  Yang 외 · 2009 · 日本デザイン学会  
  요지: 포스터 코퍼스에서 대표적 디자인 요소 8개를 추출  
  **가깝다**: 포스터를 요소로 분해해 센다  
  **차이**: «우수한» 포스터의 요소지 «누구의» 요소가 아니다  
  *확인: 제목·초록 조각*
- **スケッチスキルの構造モデルを用いたデザイナーのスケッチ分析**  
  Izu 외 · 2013 · デザイン学研究  
  요지: 디자이너 6명의 스케치 기법을 구조 모델로 비교  
  **가깝다**: 디자이너 여럿을 나란히 놓고 비교한다  
  **차이**: 작품이 아니라 과정(스케치)을 본다. 기법 분류지 역산이 아니다  
  *확인: 제목·초록 조각*
- **研究ポスターのデザインに関する評価と分析**  
  Sato 외 · 2025 · 科学技術コミュニケーション  
  요지: 학술 포스터 평가  
  *확인: 제목*
- **服飾デザイン画における頭身数とプロポーションの関係**  
  Morishita, Nakamura · 2015 · デザイン学研究  
  요지: 패션 도판의 비례를 정량 분석  
  *확인: 제목*

### E — 인접

- **Demystifying Tacit Knowledge in Graphic Design: Characteristics, Instances, Approaches, and Guidelines**  
  Kihoon Son, DaEun Choi, Tae Soo Kim, Juho Kim · 2024 · CHI '24 (KAIST)  
  https://arxiv.org/html/2403.06252v1  
  요지: 디자이너 10명 인터뷰, 암묵지 사례 123개. 4범주 14특성. 표현(Expression) = 말로 설명하기 어렵고 비언어 경로로만 나온다. 암묵지는 공유될 수 있으나 «inner design elements» 가 코드화 최난이라고 명시  
  **가깝다**: 우리 연구의 전제 — 말로 못 하는 것이 있다는 것  
  쓰임: 「왜 잴 수 없는 것이 있는가」의 근거로 인용  
  *확인: 본문 요약까지 읽음*
- **Grid Systems in Graphic Design**  
  Josef Müller-Brockmann · 1981 · 원전  
  요지: 작가 자신이 적은 규칙. 상수 8개·조건부 관계 14개·판단 원리 6개로 정리했다 (docs/BROCKMANN_RULES.md)  
  쓰임: 검증 대상. booktest.py 가 R1·C1·R2 를 그의 포스터로 검사한다  
  *확인: OCR 전문 기준 정리본*
- **Graphic Design Manual: Principles and Practice**  
  Armin Hofmann · 1965 · 원전  
  요지: 통제실험 형태의 도판. 판마다 무엇을 붙들고 무엇을 바꿨는지가 캡션에 적혀 있다 (docs/HOFMANN.md)  
  쓰임: 지각 층위 지표의 순서쌍 정답지 후보  
  *확인: 도판 12장 사진으로 확인*

---

## 못 본 곳

「없다」가 아니라 「이 범위에서 찾지 못했다」로 쓴다.

- ACM DL·IEEE Xplore 전문 검색 (초록만 색인되는 것)
- 디자인 학회 논문집 중 온라인에 없는 것 — DRS, Design Issues, Visible Language, Journal of Design History
- 한국어 논문
- 학위논문 데이터베이스 전반

## 쓴 질의

```
reverse engineering designer style graphic design computational analysis generation poster
computational style attribution graphic design generation designer signature layout corpus
visual stylometry quantifying artist style measurable features limits authorship attribution
stylometry poster typography graphic design authorship attribution computational designer identification
"visual stylometry" OR "computational stylometry" poster OR typography OR "graphic design"
computational analysis "poster design" corpus designer style quantitative "design history"
Stilometrie OR Stylometrie Grafikdesign OR Plakat OR Typografie Zuschreibung Stil quantitativ
computergestützte Stilanalyse Plakat Korpus Gestalter Schweizer Typografie
ポスター デザイン 定量的 分析 様式 デザイナー
```

*대부분 제목·출처·초록 조각까지만 확인했다. 본문을 읽은 것은 표시했다.*
