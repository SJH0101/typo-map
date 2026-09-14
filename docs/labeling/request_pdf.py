"""요청서(md)를 그림이 박힌 PDF 한 파일로 만든다 — 공동 연구자에게 도구 파일과 함께 보내는 용도.

    .venv/bin/python docs/labeling/request_pdf.py docs/LABELING_REQUEST.md ~/Documents/poster/labeler/가이드긋기_요청서.pdf

md 안의 그림 경로(상대 경로)를 data URI 로 바꿔 HTML 로 만든 뒤, 헤드리스 Chrome 에 CDP(Page.printToPDF)로 A4 PDF 를 찍게 한다.
Chrome 의 --print-to-pdf 명령줄 옵션은 이 기계에서 끝나지 않고 멈췄다 (2026-09-14). CDP 에는 node 22 가 필요하다.
원본은 늘 md 다. md 를 고치면 이 명령으로 PDF 를 다시 만든다.
"""
import argparse
import base64
import mimetypes
import os
import re
import subprocess
import tempfile

from markdown_it import MarkdownIt

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

CSS = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
body { font-family: -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; font-size: 10pt; line-height: 1.55; color: #171614; }
h1 { font-size: 17pt; margin: 0 0 10pt; }
h2 { font-size: 13pt; margin: 18pt 0 6pt; padding-top: 4pt; border-top: 1px solid #ccc; break-after: avoid; }
h3 { font-size: 11pt; margin: 10pt 0 4pt; }
p, li { margin: 3pt 0; }
ul, ol { padding-left: 18pt; margin: 3pt 0; }
code { font-family: Menlo, monospace; font-size: 8.5pt; background: #f1eee8; padding: 0 2pt; border-radius: 2pt; word-break: break-all; }
pre { background: #f1eee8; padding: 6pt 8pt; border-radius: 3pt; white-space: pre-wrap; font-size: 9pt; }
pre code { background: none; padding: 0; }
blockquote { margin: 6pt 0; padding: 2pt 10pt; border-left: 3pt solid #d2ccc1; color: #3a3833; background: #faf8f4; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 8.5pt; }
th, td { border: 1px solid #d2ccc1; padding: 2pt 4pt; vertical-align: top; text-align: left; }
th { background: #efebe4; }
tr { break-inside: avoid; }
img { max-width: 100%; border: 1px solid #d2ccc1; border-radius: 3pt; }
kbd { font-family: Menlo, monospace; font-size: 8pt; border: 1px solid #c9c2b6; border-bottom-width: 2px; border-radius: 3px; padding: 0 3px; background: #f8f6f2; }
"""

PRINT_JS = r"""
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const [,, chromePath, html, out, prof, port] = process.argv;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(chromePath, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
try {
  let ok = false;
  for (let i = 0; i < 80 && !ok; i++) { try { await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); ok = true; } catch { await sleep(250); } }
  if (!ok) throw new Error('Chrome 이 뜨지 않았다');
  const t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let id = 0; const pend = new Map(); const events = [];
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } else if (m.method) events.push(m.method); };
  const send = (method, params = {}) => new Promise(res => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Page.enable');
  await send('Page.navigate', { url: 'file://' + html });
  for (let i = 0; i < 80 && !events.includes('Page.loadEventFired'); i++) await sleep(100);
  await sleep(500);
  const r = await send('Page.printToPDF', { printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false });
  if (!r.result) throw new Error(JSON.stringify(r.error));
  fs.writeFileSync(out, Buffer.from(r.result.data, 'base64'));
  ws.close();
} finally { chrome.kill(); }
"""


def inline_images(md, base):
    def repl(m):
        alt, src = m.group(1), m.group(2)
        path = os.path.join(base, src)
        if src.startswith(('http:', 'https:', 'data:')) or not os.path.exists(path):
            return m.group(0)
        mime = mimetypes.guess_type(path)[0] or 'image/png'
        return f'![{alt}](data:{mime};base64,{base64.b64encode(open(path, "rb").read()).decode()})'
    return re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', repl, md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('md')
    ap.add_argument('out')
    ap.add_argument('--port', default='9344')
    a = ap.parse_args()
    md_path = os.path.abspath(a.md)
    md = inline_images(open(md_path, encoding='utf-8').read(), os.path.dirname(md_path))
    body = MarkdownIt('commonmark', {'html': True}).enable('table').render(md)
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith('# ')), '요청서')
    html = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>'
    out = os.path.abspath(os.path.expanduser(a.out))
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, 'request.html')
        js = os.path.join(d, 'print.mjs')
        open(src, 'w', encoding='utf-8').write(html)
        open(js, 'w', encoding='utf-8').write(PRINT_JS)
        subprocess.run(['node', js, CHROME, src, out, os.path.join(d, 'prof'), a.port], check=True, timeout=180)
    print(out, os.path.getsize(out))


if __name__ == '__main__':
    main()
