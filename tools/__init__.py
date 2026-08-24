"""MCP 도구 — 스키마와 구현을 한 자리에 둔다.

도구마다 제 모듈이 TOOLS(스키마)와 FUNCS(구현)를 함께 내고, 여기서 모은다.
스키마와 구현이 떨어져 있으면 하나만 고치는 일이 생긴다.
"""
from tools import brain, corpus, grounding, layout

_MODULES = (grounding, brain, corpus, layout)

TOOLS = [t for m in _MODULES for t in m.TOOLS]
FUNCS = {k: v for m in _MODULES for k, v in m.FUNCS.items()}
