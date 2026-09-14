// 사용: build.py 로 synth_tool.html(합성 base/001 · res_1600/001 · 연습 base/002) 과 real_tool.html(posters_for_labelers.json) 을 한 폴더에 만들고
//      그 폴더를 127.0.0.1:8765 로 띄운 뒤  node docs/labeling/tool/verify_cdp.mjs <출력 폴더>
//      결과 result.json · 스크린샷 · export_v2.json 이 출력 폴더에 생긴다. 헤드리스 Chrome 경로는 macOS 기본 설치 자리.
// 가이드 긋기 도구 2.0 검증 + 스크린샷 — 헤드리스 Chrome 을 CDP 로 조작한다 (실제 입력 이벤트: Input.dispatch*)
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const OUT = process.argv[2];
const BASE = 'http://127.0.0.1:8765';
const sleep = ms => new Promise(r => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ['--headless=new', '--remote-debugging-port=9333', `--user-data-dir=${OUT}/prof`, '--window-size=1440,900',
   '--hide-scrollbars', '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
let ver = null;
for (let i = 0; i < 40 && !ver; i++) { try { ver = await (await fetch('http://127.0.0.1:9333/json/version')).json(); } catch { await sleep(250); } }
const tgt = await (await fetch('http://127.0.0.1:9333/json/new?about:blank', { method: 'PUT' })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let nid = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(res => { const i = ++nid; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(expr.slice(0, 80) + ' → ' + JSON.stringify(r.result.exceptionDetails).slice(0, 400));
  return r.result?.result?.value;
};
const shot = async name => { await sleep(350); const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(`${OUT}/${name}`, Buffer.from(r.result.data, 'base64')); };
const mouse = (type, x, y, mod = 0) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, modifiers: mod });
const move = (x, y) => send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none', buttons: 0 });
const key = async (k, mod = 0, code) => {
  const text = k.length === 1 ? k : undefined;
  await send('Input.dispatchKeyEvent', { type: text ? 'keyDown' : 'rawKeyDown', key: k, code, text, modifiers: mod, windowsVirtualKeyCode: k === 'Enter' ? 13 : k === 'Tab' ? 9 : undefined });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, modifiers: mod });
};
const wheel = (x, y, dy, mod) => send('Input.dispatchMouseEvent', { type: 'mouseWheel', x, y, deltaX: 0, deltaY: dy, modifiers: mod });
// 이미지 좌표 → 화면 좌표
const cc = async (ix, iy) => ev(`(()=>{const r=document.getElementById('pw').getBoundingClientRect();return [r.left+${ix}*zf, r.top+${iy}*zf];})()`);
// 누를 자리가 화면(캔버스) 밖이면 스크롤로 가운데로 가져온다 — 확대가 크면 대상이 보이는 영역 밖에 있을 수 있다
const ensure = (ix, iy) => ev(`(()=>{const w=document.getElementById('canvasWrap'); const x=tx+${ix}*zf, y=ty+${iy}*zf; if(x<40||x>w.clientWidth-40) tx=w.clientWidth/2-${ix}*zf; if(y<40||y>w.clientHeight-40) ty=w.clientHeight/2-${iy}*zf; clampPan(); layout(); return 1;})()`);
const click = async (ix, iy, mod = 0) => { await ensure(ix, iy); const [x, y] = await cc(ix, iy); await move(x, y); await mouse('mousePressed', x, y, mod); await mouse('mouseReleased', x, y, mod); await sleep(60); };
const drag = async (a, b) => { const [x1, y1] = await cc(...a); const [x2, y2] = await cc(...b);
  await move(x1, y1); await mouse('mousePressed', x1, y1); for (let i = 1; i <= 6; i++) await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x1 + (x2 - x1) * i / 6, y: y1 + (y2 - y1) * i / 6, button: 'left', buttons: 1 });
  await mouse('mouseReleased', x2, y2); await sleep(80); };
const lines = bi => ev(`sortedLines(R().blocks[${bi}]).map(l=>Object.fromEntries(TYPES.map(([t])=>[t,l.g[t]?(l.g[t].y??l.g[t].mark):null])))`);
const counts = () => ev(`({missing:document.getElementById('cMissing').textContent, invalid:document.getElementById('cInvalid').textContent, now:document.getElementById('nowText').innerText, msg:document.getElementById('msg').textContent})`);

const R = {};
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

// ── 합성 포스터 ─────────────────────────────────────────
await send('Page.navigate', { url: `${BASE}/synth_tool.html` }); await sleep(1500);
await ev(`localStorage.clear(); 1`);
await send('Page.navigate', { url: `${BASE}/synth_tool.html` }); await sleep(1500);
await shot('s01_home.png');
await ev(`document.getElementById('name').value='검증-Claude'; start('main'); 1`); await sleep(400);
R.fitZoom = await ev('zf');
await shot('s02_blocks_empty.png');
R.hint_blocks_empty = (await counts()).now;
await drag([18, 22], [296, 86]);
await drag([19, 125], [274, 217]);
await drag([287, 81], [544, 226]);          // 블록 T 영역 오른끝(296) 안에서 시작 — 새 블록이 생겨야 함
R.blocks = await ev(`R().blocks.map(b=>[b.x1,b.y1,b.x2,b.y2])`);
R.counts_after_blocks = await counts();
await shot('s03_blocks_drawn.png');

// 가이드 단계
await key('l');
await click(150, 60);                         // 블록 1 선택
// 연속 확대: 커서 자리 고정
const [cx, cy] = await cc(40, 48);
const before = await ev(`(()=>{const r=document.getElementById('pw').getBoundingClientRect();return [(${cx}-r.left)/zf,(${cy}-r.top)/zf,zf];})()`);
await move(cx, cy);
for (let i = 0; i < 9; i++) { await wheel(cx, cy, -100, 2); await sleep(40); }   // Ctrl+휠
for (let i = 0; i < 14; i++) { await wheel(cx, cy, -6, 2); await sleep(20); }     // 핀치처럼 작은 값
await sleep(200);
const after = await ev(`(()=>{const r=document.getElementById('pw').getBoundingClientRect();return [(${cx}-r.left)/zf,(${cy}-r.top)/zf,zf];})()`);
R.zoom_anchor = { before, after, drift_px: [after[0] - before[0], after[1] - before[1]] };
await move(500.6, 400.4); R.coord_probe = await ev('lastMouse');
// 스냅 (정수가 아닌 배율)
await key('1'); await click(60, 48.25); await click(60, 79.75);
await key('3'); await click(80, 26.25);
await key('4'); await click(80, 31.75); await click(80, 64.25);
R.T_lines = await lines(0);
R.counts_T = await counts();
await ev('applyZoom(4); 1'); await ensure(150, 55); await ev('paint(); 1');
await shot('s04_guides_counts.png');
// 숫자 누르기 → 그 자리로
await ev(`document.getElementById('cMissing').click(); 1`); await sleep(100);
R.jump_missing = await ev(`({selB, sel: selL && sortedLines(R().blocks[selB]).findIndex(l=>l.id===selL)+1, curT, msg:document.getElementById('msg').textContent})`);
R.blockrow = await ev(`document.getElementById('blist').innerText`);
// 상태: 줄1 캡 글자 없음, 줄2 캡 · 어센더 글자 없음
await ev(`selB=0; selL=sortedLines(R().blocks[0])[0].id; curT='cap'; paint(); 1`); await key('n');
await ev(`selL=sortedLines(R().blocks[0])[1].id; paint(); 1`); await key('n');
await ev(`curT='asc'; paint(); 1`); await key('n');
// 블록 2: 글줄 판독 불가 (⇧M, 베이스라인 선택)
await ev(`selB=1; selL=null; curT='base'; paint(); 1`); await key('M', 8);
// 블록 3: 다른 배율(비정수)로 베이스라인 · 어센더 · x높이, 캡은 ⇧N
await ev(`selB=2; selL=null; applyZoom(5.37); 1`);
await ensure(330, 96);
await key('1'); await click(330, 96.25); await click(330, 111.75);
await key('3'); await click(340, 85.25); await click(340, 100.75);
await key('4'); await click(340, 87.75); await click(340, 104.25);
await ev(`curT='cap'; paint(); 1`); await key('N', 8);
R.B_lines = await lines(2);
R.zoom_B = await ev('zf');
{ await ensure(340, 119.75); const [hx, hy] = await cc(340, 119.75); await move(hx, hy); await sleep(80); R.hover_at_119_75 = await ev('hoverY'); }
R.counts_done = await counts();
await ev('applyZoom(2.2); 1'); await ensure(280, 130); await ev('selB=0; selL=sortedLines(R().blocks[0])[0].id; curT="asc"; paint(); 1');
await shot('s05_all_entered.png');
// 좌표 · 크기 보기
await ev(`document.getElementById('showNums').click(); 1`); await sleep(150);
R.nums_visible = await ev(`({table:document.getElementById('lineTable').innerText, blist:document.getElementById('blist').innerText, fname:document.getElementById('fname').innerText})`);
await shot('s06_numbers_on.png');
await ev(`document.getElementById('showNums').click(); 1`);
// 잘못된 상태 만들기: 블록 3 영역을 줄여 선을 밖으로
await ev(`setStep('blocks'); selB=2; paint(); 1`);
await ev(`(()=>{const b=R().blocks[2]; snap(); b.y1=90; changed(); return 1;})()`);
R.counts_invalid = await counts();
R.blockrow_invalid = await ev(`document.getElementById('blist').innerText`);
await ev(`document.getElementById('cInvalid').click(); 1`); await sleep(100);
R.jump_invalid = await ev(`({selB, sel: selL && sortedLines(R().blocks[selB]).findIndex(l=>l.id===selL)+1, curT, step:R().step, msg:document.getElementById('msg').textContent})`);
await ev(`doUndo(); setStep('lines'); 1`);
R.counts_after_undo = await counts();
// 완료
await key('Enter'); await sleep(200);
R.after_finish = await ev(`({idx:S.idx.main, done1:S.recs['main/1'].done})`);
// 내보내기 (내려받기 막음)
await ev(`window.download=()=>true; S.idx.main=0; openPoster(); saveFile(); 1`);
const exp = JSON.parse(await ev(`document.getElementById('mText').value`));
await ev(`document.getElementById('modal').classList.add('hide'); 1`);
const p1 = exp.posters.find(p => p.set === 'main' && p.order === 1);
R.export = { schema: exp.schema, stateSchema: exp.state.schema, terms: exp.terms, n_missing: p1.n_missing, n_invalid: p1.n_invalid, done: p1.done,
  blocks: p1.blocks.map(b => ({ box: [b.x1, b.y1, b.x2, b.y2], flag: b.flag, base_mark: b.base_mark, lines: b.lines.map(l => ['base', 'cap', 'asc', 'xh'].map(t => l[t] && (l[t].y ?? l[t].mark))) })),
  zooms: p1.blocks[2].lines.map(l => l.base.z), zoom_ms_keys: Object.keys(p1.zoom_ms), fields_keys: Object.keys(exp.fields) };
fs.writeFileSync(`${OUT}/export_v2.json`, JSON.stringify(exp, null, 1));
// 계속하기 (브라우저 기록)
await send('Page.navigate', { url: `${BASE}/synth_tool.html` }); await sleep(1500);
R.resume_banner = await ev(`document.getElementById('resume').innerText`);
await ev(`resumeLocal(); 1`); await sleep(300);
R.resume_lines = await lines(2);
// 도구 1.0 파일 불러오기 (옛 이름 → 코드)
const v1 = JSON.parse(JSON.stringify(exp.state));
v1.schema = 'typo-guides-state/1'; v1.updated = '2099-01-01T00:00:00.000Z';
const rr = v1.recs['main/1'];
for (const b of rr.blocks) { if (b.base_mark) b.base_mark = '못 가림'; for (const l of b.lines) for (const t of ['cap', 'asc', 'xh']) if (l.g[t] && l.g[t].mark) l.g[t].mark = l.g[t].mark === 'no_glyph' ? '없음' : '못 가림'; }
rr.blocks[1].flag = '가로 아님';
fs.writeFileSync(`${OUT}/state_v1.json`, JSON.stringify(v1));
await ev(`S=null; localStorage.removeItem(SKEY); 1`);
await send('Page.navigate', { url: `${BASE}/synth_tool.html` }); await sleep(1500);
R.import_v1 = await ev(`(async()=>{const txt=${JSON.stringify(JSON.stringify(v1))}; const inp=document.getElementById('importFile'); const dt=new DataTransfer(); dt.items.add(new File([txt],'v1.json')); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); await new Promise(r=>setTimeout(r,800)); const r=S.recs['main/1']; return {schema:S.schema, migrated:S.migrated_from, flag:r.blocks[1].flag, base_mark:r.blocks[1].base_mark, marks:r.blocks[0].lines.map(l=>[l.g.cap&&l.g.cap.mark,l.g.asc&&l.g.asc.mark]), missing:document.getElementById('cMissing').textContent, invalid:document.getElementById('cInvalid').textContent};})()`);
await ev(`S=null; localStorage.clear(); 1`);

// ── 실물 포스터 (연습 포스터 2) — 화면 모양만 ──────────────────
await send('Page.navigate', { url: `${BASE}/real_tool.html` }); await sleep(2000);
await ev(`localStorage.clear(); 1`);
await send('Page.navigate', { url: `${BASE}/real_tool.html` }); await sleep(2000);
await shot('r01_home.png');
await ev(`document.getElementById('name').value='화면 확인'; start('practice'); S.idx.practice=1; openPoster(); 1`); await sleep(500);
R.real_poster = await ev(`P().folder+'/'+P().file`);
await drag([4, 4], [192, 36]);
await drag([4, 98], [178, 214]);
await drag([420, 16], [560, 214]);
await shot('r02_blocks.png');
await key('l'); await click(80, 150);
await ev(`applyZoom(4, ...(()=>{const r=document.getElementById('pw').getBoundingClientRect();return [r.left+60*zf, r.top+150*zf];})()); 1`); await sleep(200);
await shot('r03_guides_start.png');
await ev(`S=null; localStorage.clear(); 1`);

fs.writeFileSync(`${OUT}/result.json`, JSON.stringify(R, null, 1));
console.log('done', Object.keys(R).length);
ws.close(); chrome.kill();
