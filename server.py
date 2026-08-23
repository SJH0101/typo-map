"""브로크만 조판 MCP 서버 — JSON-RPC 전송과 도구 디스패치.

도구의 스키마와 구현은 tools/ 에 있다. 이 파일은 줄 단위 JSON-RPC 를
읽고 쓰는 일만 한다.

실행:  python server.py
등록:  claude mcp add brockmann -- python /경로/server.py
"""
import json
import sys

from tools import TOOLS, FUNCS

VERSION = '0.5.0'


def rpc(req):
    m, i = req.get("method"), req.get("id")
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": i, "result": {
            "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "brockmann", "version": VERSION}}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": i, "result": {"tools": TOOLS}}
    if m == "tools/call":
        p = req.get("params", {})
        fn = FUNCS.get(p.get("name"))
        r = fn(p.get("arguments", {})) if fn else {"error": f'unknown tool {p.get("name")}'}
        return {"jsonrpc": "2.0", "id": i, "result": {
            "content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}}
    if i is None:
        return None
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"unknown method {m}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            res = rpc(json.loads(line))
        except Exception as e:
            res = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
        if res is not None:
            print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
