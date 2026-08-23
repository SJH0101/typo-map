"""짚어준 상자를 재는 도구.

파이프라인에서 «어디를 잴지» 를 정하는 자리다. 이 서버는 그것을 정하지
않는다 — 부르는 쪽이 포스터를 보고 상자를 준다. API 키가 필요하지 않은 것도
그래서다. 모델을 코드가 부르는 것이 아니라 모델이 코드를 부른다.
"""
import os

from measure import ground, region
from tools.shared import GROUNDED


def measure_boxes(args):
    """짚어준 상자 안만 잰다. 어디를 잴지는 이 서버가 정하지 않는다.

    부르는 쪽이 포스터를 보고 상자를 준다. 그것이 이 파이프라인의 설계다 —
    덩어리를 찾는 일은 보는 쪽이 낫고, 그 안의 행간·정렬을 재는 일은
    추정이 들어가면 안 되므로 코드가 한다.
    """
    path = os.path.expanduser(args.get("image") or "")
    if not path or not os.path.exists(path):
        return {"ok": False, "error": f"이미지를 찾을 수 없다: {path}"}
    boxes = args.get("boxes") or []
    if not boxes:
        return {"ok": False, "error": "상자가 비었다. 포스터를 보고 타이포 덩어리를 짚어 달라"}
    store = bool(args.get("store"))
    cache = os.path.expanduser(args.get("cache")) if args.get("cache") else GROUNDED
    try:
        r = ground.ground(path, boxes, cache=cache,
                          coords=args.get("coords", "norm"), store=store)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    r["note"] = ("상자 안에서 잰 값이다. lead_measured 는 베이스라인 간격의 중앙값, "
                 "align 은 왼쪽·오른쪽·가운데 중 가장 고른 축이며 어느 것도 "
                 f"{region.ALIGN_EPS}px 안에 들지 않으면 none 이다. "
                 "n_lines 0 은 상자가 빗나갔거나 글자가 너무 작다는 뜻이다")
    if not store:
        r["hint"] = "store=true 로 주면 이 포스터를 코퍼스에 쌓고 규칙을 다시 뽑는다"
    return r


TOOLS = [
    {"name": "measure_boxes",
     "description": ("포스터를 직접 보고 타이포 덩어리를 상자로 짚어 주면 그 안의 조판을 잰다. "
                     "행간·베이스라인·x높이·정렬축을 상자마다 낸다. 상자 밖은 보지 않는다. "
                     "store 로 쌓으면 짚어준 상자만으로 코퍼스와 규칙이 만들어진다. "
                     "자동 검출(measure_corpus)과 달리 어디를 잴지는 부르는 쪽이 정한다."),
     "inputSchema": {"type": "object", "properties": {
         "image": {"type": "string", "description": "포스터 이미지 경로"},
         "coords": {"type": "string", "enum": ["norm", "px"],
                    "description": ("norm(기본)은 판면 대비 0~1 비율, px 는 원본 픽셀. "
                                    "원본 해상도를 모르면 norm 을 써라")},
         "store": {"type": "boolean",
                   "description": "true 면 코퍼스에 쌓고 규칙을 다시 뽑는다 (기본 false)"},
         "cache": {"type": "string",
                   "description": "쌓을 코퍼스 파일. 생략하면 짚기 전용 캐시를 쓴다"},
         "boxes": {"type": "array", "description": "눈에 보이는 타이포 덩어리 하나마다 상자 하나",
                   "items": {"type": "object", "properties": {
                       "id": {"type": "string", "description": "덩어리 이름 (예: 제목, 날짜)"},
                       "role": {"type": "string",
                                "description": "역할 (제목/부제/본문/일시/장소/출판정보 등). 기록만 한다"},
                       "box": {"type": "array", "items": {"type": "number"},
                               "minItems": 4, "maxItems": 4,
                               "description": "[x1, y1, x2, y2]. 디센더와 발음기호까지 잉크 전체를 감싼다"}},
                       "required": ["box"]}}},
         "required": ["image", "boxes"]}},
]

FUNCS = dict(measure_boxes=measure_boxes)
