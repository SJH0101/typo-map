"""포스터에 사진이 들어 있는지 판정한다. 선택 기능이다.

TYPO_MCP_PHOTO=1 일 때만 켜진다. 켜지 않으면 아무것도 받지 않고 아무것도
바뀌지 않는다.

무엇을 재는가
    깊이 기울기   사진은 3차원 장면을 찍은 것이라 깊이 지도에 굴곡이 있다.
                 종이 위의 잉크는 평평하다. 의미와 무관한 기하학적 근거다.
    COCO 검출     사람·자전거·병 같은 것을 직접 찾는다. 의미 쪽 근거다.

둘은 서로 독립적이고, 합치면 각각보다 낫다. 네 코퍼스에서 손으로 라벨한
71장(사진 20 · 삽화 15 · 없음 36)으로 문턱을 절반에서 정하고 나머지
절반에서 평가한 값:

    깊이 + COCO   정밀 88%  재현 69%   ← 채택
    깊이만        정밀 78%  재현 67%
    CLIP          정밀 62%  재현 84%
    COCO만        정밀 98%  재현 42%
    우리 라벨로 학습한 ResNet  정밀 44%  재현 79%

마지막 줄이 중요하다. 브로크만 안에서 교차검증하면 오분류 6% 로 가장
좋았지만, 사진 포스터가 대부분 어둡고 무채색이라 「어두운 바탕 = 사진」 을
배웠고 어두운 바탕을 즐겨 쓰는 호프만에서 무너졌다(중앙 54%). 라벨을 한
코퍼스에서만 만들면 특징을 바꿔도 이 함정은 피해지지 않는다.

판정만 하고 측정은 바꾸지 않는다. 사진 위의 글줄을 지우면 사진에 얹힌
진짜 글자도 함께 지워진다 — Volg 포스터의 캡션이 그렇다. 「이 장에는
사진이 있다」 는 사실만 내고, 그것을 어떻게 쓸지는 읽는 쪽이 정한다.
"""
import os

import numpy as np
from PIL import Image

DEPTH_GRAD = 0.0030   # 깊이 기울기 문턱. 71장에서 정밀 88% · 재현 70% 로,
                      # 절반-절반 교차검증 추정치(88%/69%)와 일치하는 자리다.
                      # 0.0026 이 F1 최고(0.82)지만 그 표의 봉우리라 고르면
                      # 이 표본에 맞춘 값이 된다.
COCO_SCORE = 0.90     # 이 신뢰도 이상만 본다. 아래로 내려가면 추상 도형을
                      # clock·kite·baseball bat 으로 부르기 시작한다.
COCO_LABELS = {'person', 'bicycle', 'motorcycle', 'car', 'bottle', 'wine glass',
               'bus', 'truck', 'dog', 'cat', 'horse', 'bird', 'train', 'boat'}

ON = os.environ.get('TYPO_MCP_PHOTO', '0') not in ('0', 'false', 'False')

_depth = None
_det = None
_meta = None


def _load():
    """무거운 모델은 처음 쓸 때만 올린다."""
    global _depth, _det, _meta
    if _depth is not None:
        return True
    try:
        import torch
        from transformers import pipeline
        from torchvision.models.detection import (maskrcnn_resnet50_fpn_v2,
                                                  MaskRCNN_ResNet50_FPN_V2_Weights)
    except ImportError:
        return False
    dev = 'mps' if torch.backends.mps.is_available() else 'cpu'
    _depth = pipeline('depth-estimation',
                      model='depth-anything/Depth-Anything-V2-Small-hf', device=dev)
    w = MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT
    _det = maskrcnn_resnet50_fpn_v2(weights=w).eval().to(dev)
    _meta = dict(names=w.meta['categories'], tf=w.transforms(), dev=dev, torch=torch)
    return True


def depth_grad(img):
    """깊이 지도의 평균 기울기. 평평한 인쇄면은 0 에 가깝다."""
    d = np.asarray(_depth(img)['depth'], dtype=float)
    rng = d.max() - d.min()
    if rng <= 0:
        return 0.0
    d = (d - d.min()) / rng
    gy, gx = np.gradient(d)
    return float(np.hypot(gx, gy).mean())


def objects(img):
    """COCO 가 확신하는 물체만 돌려준다."""
    torch = _meta['torch']
    with torch.no_grad():
        o = _det([_meta['tf'](img).to(_meta['dev'])])[0]
    k = o['scores'] >= COCO_SCORE
    out = []
    for i, s in zip(o['labels'][k].tolist(), o['scores'][k].tolist()):
        name = _meta['names'][i]
        if name in COCO_LABELS:
            out.append((name, round(float(s), 2)))
    return out


def look(path):
    """한 장을 본다. 켜져 있지 않거나 모델이 없으면 None."""
    if not ON or not _load():
        return None
    img = Image.open(path).convert('RGB')
    g = depth_grad(img)
    objs = objects(img)
    return dict(depth_grad=round(g, 5),
                objects=[{'label': n, 'score': s} for n, s in objs],
                has_photo=bool(g >= DEPTH_GRAD or objs))
