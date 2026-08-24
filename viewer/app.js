const B = __BRAINS__;
delete B._compare;
const WHO = Object.keys(B);
const FMT = {색수:v=>v.toFixed(0)+'개', 블록수:v=>v.toFixed(0)+'개', 단수:v=>v.toFixed(0)+'단',
              활자폭:v=>v.toFixed(1)+'배', 행간비:v=>v.toFixed(2)+'배', 어센더비:v=>v.toFixed(2)+'배'};
const fmt = (id,v)=> v==null ? '—' : (FMT[id] ? FMT[id](v) : (v*100).toFixed(1)+'%');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const GC = {색:'--red', 마진:'--blue', 조판:'--grey'};
const WC = ['--wA','--wB','--wC','--wD','--wE'];
const wcolor = w => css(WC[WHO.indexOf(w)] || '--grey');
const ekey = (a,b)=> [a,b].sort().join('|');

const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
let cmpOn = false, shown = [WHO[0]], sel = null, hov = null;
let pos = {}, sim = [], panels = [], view = {x:0,y:0,k:1}, drag = null, pan = null;
let EMAP = {};                       // 선 -> 가진 뇌 목록
let NB = {};                         // 뇌 -> 마디 -> 이웃 목록
let DIFF = {};                       // 마디 -> 판마다 이웃이 몇 개 다른가

// ── 배치는 «하나» 만 만든다. 판마다 같은 자리에 있어야 눈이 따라간다 ──
function layout(){
  const ids = B[shown[0]].nodes.map(n=>n.id);
  const R = 190;
  sim = ids.map((id,i)=>{
    const a = (i/ids.length)*Math.PI*2 - Math.PI/2;
    const old = pos[id];
    return {id, group:(B[shown[0]].nodes.find(n=>n.id===id)||{}).group,
            x: old?old.x:Math.cos(a)*R, y: old?old.y:Math.sin(a)*R, vx:0, vy:0};
  });
  const by = {}; sim.forEach(n=>{ by[n.id]=n; });
  EMAP = {};
  shown.forEach(function(w){
    (B[w].edges||[]).forEach(function(e){
      const k = ekey(e.a,e.b);
      if (!EMAP[k]) EMAP[k] = {a:e.a, b:e.b, own:{}};
      EMAP[k].own[w] = e;
    });
  });
  NB = {};
  shown.forEach(function(w){
    const m = {}; ids.forEach(id=>{ m[id]=[]; });
    (B[w].edges||[]).forEach(function(e){
      if (m[e.a]) m[e.a].push(e.b);
      if (m[e.b]) m[e.b].push(e.a);
    });
    for (const k in m) m[k].sort();
    NB[w] = m;
  });
  DIFF = {};
  if (shown.length>1) ids.forEach(function(id){
    const sets = shown.map(w=>(NB[w]||{})[id]||[]);
    const uni = {}; sets.forEach(s2=>s2.forEach(x=>{ uni[x]=(uni[x]||0)+1; }));
    // 모든 판에 다 있는 이웃이 아니면 «다른» 것으로 센다
    const d = Object.keys(uni).filter(x=>uni[x]<shown.length).length;
    if (d) DIFF[id] = d;
  });
  sim.forEach(n=>{ n.s = by[n.id]; });
  for (let i=0;i<420;i++) step();
  sim.forEach(n=>{ pos[n.id] = {x:n.x, y:n.y}; });
}

function step(){
  const by = {}; sim.forEach(n=>{ by[n.id]=n; });
  for (const n of sim){
    for (const m of sim){
      if (n===m) continue;
      const dx=n.x-m.x, dy=n.y-m.y, d2=dx*dx+dy*dy||0.01;
      if (d2>90000) continue;
      const d=Math.sqrt(d2), f=4800/d2;
      n.vx+=dx/d*f*0.9; n.vy+=dy/d*f*0.9;
    }
    n.vx -= n.x*0.0018; n.vy -= n.y*0.0018;
  }
  const gc={};
  for (const n of sim){ if(!gc[n.group]) gc[n.group]=[0,0,0];
    gc[n.group][0]+=n.x; gc[n.group][1]+=n.y; gc[n.group][2]++; }
  for (const n of sim){ const g=gc[n.group];
    n.vx += (g[0]/g[2]-n.x)*0.011; n.vy += (g[1]/g[2]-n.y)*0.011; }
  for (const k in EMAP){
    const e = EMAP[k], s = by[e.a], t = by[e.b];
    if (!s||!t) continue;
    const r = Math.max.apply(null, Object.keys(e.own).map(w=>e.own[w].r));
    const dx=t.x-s.x, dy=t.y-s.y, d=Math.hypot(dx,dy)||0.01;
    const f=(d-(132-r*44))*0.0072;
    s.vx+=dx/d*f; s.vy+=dy/d*f; t.vx-=dx/d*f; t.vy-=dy/d*f;
  }
  for (const n of sim){ if(n===drag){n.vx=n.vy=0;continue;}
    n.vx*=0.83; n.vy*=0.83; n.x+=n.vx; n.y+=n.vy; }
  sim.forEach(n=>{ pos[n.id] = {x:n.x, y:n.y}; });
}

// ── 판 나누기 — 1개면 전면, 2개면 좌우, 3~4개면 2x2 ──
function rects(w,h){
  const n = shown.length;
  const cols = n<=1?1 : (n===2?2 : (n<=4?2:3));
  const rows = Math.ceil(n/cols);
  const pw = w/cols, ph = h/rows;
  return shown.map(function(who,i){
    const c = i%cols, r = Math.floor(i/cols);
    return {who, cx:pw*c+pw/2, cy:ph*r+ph/2, w:pw, h:ph,
            k: Math.min(pw, ph)/(n===1?520:560)};
  });
}

function draw(){
  const dpr=Math.min(devicePixelRatio||1,2), W=cv.clientWidth, H=cv.clientHeight;
  if (cv.width!==W*dpr){ cv.width=W*dpr; cv.height=H*dpr; }
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,W,H);
  panels = rects(W,H);
  const INK=css('--ink'), DIM=css('--dim'), EDGE=css('--edge'), HAIR=css('--hair');
  const multi = shown.length>1;

  // 판 사이 칸막이
  if (multi){
    ctx.strokeStyle = HAIR; ctx.lineWidth = 1;
    const cols = shown.length===2?2:2, rows = Math.ceil(shown.length/cols);
    for (let c=1;c<cols;c++){ ctx.beginPath(); ctx.moveTo(W/cols*c,0); ctx.lineTo(W/cols*c,H); ctx.stroke(); }
    for (let r=1;r<rows;r++){ ctx.beginPath(); ctx.moveTo(0,H/rows*r); ctx.lineTo(W,H/rows*r); ctx.stroke(); }
  }

  panels.forEach(function(P){
    const b = B[P.who];
    ctx.save();
    ctx.translate(P.cx+view.x, P.cy+view.y);
    ctx.scale(P.k*view.k, P.k*view.k);
    const own = {}; (b.edges||[]).forEach(e=>{ own[ekey(e.a,e.b)] = e; });

    for (const k in EMAP){
      const e = EMAP[k], mine = own[k];
      if (!mine) continue;
      const s = pos[e.a], t = pos[e.b];
      const all = Object.keys(e.own).length === shown.length;
      const lit = !sel || e.a===sel || e.b===sel;
      // 구분은 둘뿐이다 — 모두에게 있는 선(옅은 회색)과 이 뇌에만 있는 선(색).
      // 부호는 선에 싣지 않는다. 파선까지 얹으면 무엇이 무엇인지 안 갈린다.
      const solo = multi && !all;
      ctx.globalAlpha = lit ? (solo?0.92:0.42) : 0.05;
      ctx.strokeStyle = solo ? wcolor(P.who) : EDGE;
      ctx.lineWidth = (solo?1.6:0.9) + mine.r*(solo?4.4:2.2);
      ctx.beginPath(); ctx.moveTo(s.x,s.y); ctx.lineTo(t.x,t.y); ctx.stroke();
    }
    ctx.setLineDash([]);

    b.nodes.forEach(function(n){
      const p = pos[n.id]; if(!p) return;
      const deg = Object.keys(own).filter(k=>k.split('|').indexOf(n.id)>=0).length;
      const r = 7 + Math.min(deg,8)*1.6;
      const lit = !sel || n.id===sel || Object.keys(own).some(k=>{
        const [a,c]=k.split('|'); return (a===sel&&c===n.id)||(c===sel&&a===n.id); });
      ctx.globalAlpha = lit ? 1 : 0.15;
      if (n.id===sel){ ctx.beginPath(); ctx.arc(p.x,p.y,r+8,0,7); ctx.fillStyle=css('--glow'); ctx.fill(); }
      ctx.beginPath(); ctx.arc(p.x,p.y,r,0,7);
      ctx.fillStyle = css(GC[n.group]||'--grey'); ctx.fill();
      const z = P.k*view.k;
      ctx.font = (n.id===sel?700:500)+' '+(12.5/z)+'px Archivo, "Noto Sans KR", sans-serif';
      ctx.fillStyle = (n.id===sel||n.id===hov) ? INK : DIM;
      ctx.textAlign='center'; ctx.textBaseline='top';
      ctx.fillText(n.id, p.x, p.y+r+4);
      if (n.id===sel){
        ctx.font='600 '+(12/z)+'px "IBM Plex Mono", monospace';
        ctx.fillStyle = INK;
        ctx.fillText(fmt(n.id,n.median), p.x, p.y+r+4+15/z);
      }
      ctx.globalAlpha=1;
    });
    ctx.restore();
  });

  // ── 판 사이는 «같은 것» 만 잇는다 ────────────────────────────
  //
  // 다른 것을 이을 이유가 없다. 두 판에서 이웃이 «같은» 마디만 이어 주면
  // 이어지지 않은 마디가 곧 다른 마디다. 선이 절반으로 줄고 뜻은 더 분명해진다.
  if (multi){
    const at2 = (P,id)=>({ x:P.cx+view.x+pos[id].x*P.k*view.k,
                           y:P.cy+view.y+pos[id].y*P.k*view.k });
    ctx.save(); ctx.setLineDash([4,5]);
    for (let i=0;i<panels.length-1;i++){
      const A = panels[i], Bp = panels[i+1];
      for (const id in pos){
        if (DIFF[id]) continue;                    // 다르면 잇지 않는다
        const p1 = at2(A,id), p2 = at2(Bp,id);
        const on = (sel===id || hov===id);
        ctx.strokeStyle = on ? css(GC[(sim.find(n=>n.id===id)||{}).group]||'--grey') : EDGE;
        ctx.lineWidth = on ? 1.8 : 1;
        ctx.globalAlpha = on ? 0.9 : (sel||hov ? 0.13 : 0.34);
        ctx.beginPath(); ctx.moveTo(p1.x,p1.y); ctx.lineTo(p2.x,p2.y); ctx.stroke();
      }
    }
    ctx.restore();
  }

  // 판 이름표
  panels.forEach(function(P){
    const b = B[P.who];
    ctx.save();
    ctx.textAlign='left'; ctx.textBaseline='top';
    ctx.font='700 15px Archivo, "Noto Sans KR", sans-serif';
    ctx.fillStyle = multi ? wcolor(P.who) : INK;
    const x = P.cx-P.w/2+18, y = P.cy-P.h/2+16;
    ctx.fillText(b.who, x, y);
    ctx.font='500 11.5px "IBM Plex Mono", monospace'; ctx.fillStyle=DIM;
    ctx.fillText(b.ok ? (b.n+'장 · 선 '+b.edges.length) : (b.n+'장 · 선을 잴 수 없음'), x, y+20);
    ctx.restore();
  });
}

function detail(id){
  const el = document.getElementById('detail');
  if (!id){ el.className='panel'; el.innerHTML=''; return; }
  const base = B[shown[0]].nodes.find(x=>x.id===id) || {};
  const col = 'var(' + (GC[base.group]||'--grey') + ')';
  let h = '<div class="dh"><p class="dgrp" style="color:'+col+'">'+base.group+'</p>'
    + '<h2 class="dname">'+id+'</h2><p class="dlab">'+(base.label||'')+'</p></div>';

  h += '<div class="dv"><p class="sech" style="margin-bottom:9px">'
     + (shown.length>1?'뇌별 값':'값')+'</p>';
  shown.forEach(function(w){
    const v = B[w].nodes.find(x=>x.id===id) || {};
    h += '<div class="cmprow"><span class="swatch" style="background:'
      + (shown.length>1?wcolor(w):css(GC[base.group]||'--grey'))+'"></span>'
      + '<span class="cw">'+w+'</span><span class="cv num">'+fmt(id,v.median)+'</span>'
      + '<span class="cn num">'+(v.n_posters||0)+'/'+(v.of||0)+'</span></div>';
  });
  h += '</div>';

  // 선을 뇌별로 갈라 보여준다 — 어디는 이어지고 어디는 아닌지
  const mine = Object.keys(EMAP).filter(k=>k.split('|').indexOf(id)>=0);
  const rows = mine.map(function(k){
    const e = EMAP[k];
    const other = e.a===id ? e.b : e.a;
    const has = shown.filter(w=>e.own[w]);
    return {other, has, r: Math.max.apply(null, has.map(w=>e.own[w].r)),
            sign: e.own[has[0]].sign};
  }).sort((a,b)=> (b.has.length-a.has.length) || (b.r-a.r));

  h += '<div class="sec"><p class="sech">직접 이어진 것 '+rows.length+'</p>';
  if (rows.length) h += rows.map(function(x){
      const dots = shown.map(w=> x.has.indexOf(w)>=0
        ? '<span class="swatch sm" style="background:'+wcolor(w)+'"></span>'
        : '<span class="swatch sm off"></span>').join('');
      const tag = (shown.length>1 && x.has.length===shown.length)
        ? '<span class="both">모두</span>'
        : (shown.length>1 && x.has.length===1 ? '<span class="both solo">'+x.has[0]+'</span>' : '');
      const sg = shown.length>1 ? '' : (x.sign<0?'<span class="sg">반대로</span> ':'<span class="sg">같이</span> ');
      return '<div class="link" data-go="'+x.other+'"><span>'+sg+x.other+tag+'</span>'
           + '<span class="r">'+(shown.length>1?dots:'<span class="num">'+x.r.toFixed(2)+'</span>')+'</span></div>';
    }).join('');
  else h += '<p class="note caveat">없음.</p>';
  if (shown.length>1) h += '<p class="note caveat" style="margin-top:10px">'
    + '점이 켜진 뇌에만 그 선이 있다. 모두에게 있는 선은 셈법에서 오는 관계일 가능성이 높다.</p>';
  h += '</div>';

  if (base.note) h += '<div class="sec"><p class="sech">이게 뭔가</p><p class="note">'+base.note['뜻']+'</p>'
    + '<p class="sech" style="margin-top:12px">읽는 법</p><p class="note">'+base.note['읽는법']+'</p>'
    + '<p class="sech" style="margin-top:12px">주의</p><p class="note caveat">'+base.note['주의']+'</p></div>';
  el.className='panel on'; el.innerHTML = h;
  el.querySelectorAll('[data-go]').forEach(function(x){
    x.onclick = function(){ sel = x.dataset.go; detail(sel); }; });
}

function refresh(){
  const b = B[shown[0]];
  document.getElementById('sV').textContent = sim.length;
  document.getElementById('fl').innerHTML = b.cannot.map(t=>'<li>'+t+'</li>').join('');
  document.getElementById('rule').textContent = b.rule;
  const warn = document.getElementById('nowarn');
  const bad = shown.filter(w=>!B[w].ok);
  warn.style.display = bad.length ? 'block' : 'none';
  warn.innerHTML = bad.map(w=>'<b>'+w+'</b> '+B[w].n+'장 — 편상관을 재려면 최소 '
    + B[w].need + '장이 필요하다. <b>선이 없는 게 아니라 못 잰 것이다.</b>').join('<br>');
  listing();
  const k = document.getElementById('wkey');
  k.style.display = shown.length>1 ? 'block' : 'none';
  k.innerHTML =
    '<div class="lgr"><span class="ln" style="border-top-width:2px;border-color:var(--edge);opacity:.5"></span>고른 뇌 <b style="margin-left:3px">모두</b>에 있는 선</div>'
  + '<div class="lgr"><span class="ln" style="border-top-width:3px;border-color:var(--wA)"></span>그 뇌<b style="margin-left:3px">에만</b> 있는 선</div>'
  + '<p class="lgt" style="margin-top:12px">판 사이</p>'
  + '<div class="lgr"><span class="ln" style="border-top-width:1px;border-color:var(--edge);border-top-style:dashed"></span>이 마디는 이웃이 같다</div>'
  + '<div class="lgr" style="color:var(--dim);font-size:11px">이어지지 않은 마디 = 이웃이 다르다</div>'
  + '<p class="note caveat" style="font-size:11px;margin-top:7px">판마다 마디 자리가 같다.</p>';
  document.getElementById('sgkey').style.display = shown.length>1 ? 'none' : 'block';
  document.getElementById('cmp').textContent = shown.length>1 ? '하나만 보기' : '나란히 놓고 보기';
  document.getElementById('cmp').setAttribute('aria-pressed', String(shown.length>1));
}

function at(e){
  const r = cv.getBoundingClientRect();
  const mx = e.clientX-r.left, my = e.clientY-r.top;
  let best = null;
  panels.forEach(function(P){
    const x = (mx - P.cx - view.x)/(P.k*view.k), y = (my - P.cy - view.y)/(P.k*view.k);
    for (const id in pos){
      const d = Math.hypot(pos[id].x-x, pos[id].y-y);
      if (d < 19 && (!best || d < best.d)) best = {id, d, x, y};
    }
  });
  return best;
}
cv.addEventListener('pointerdown', e=>{
  const n = at(e);
  if (n){ drag = sim.find(s=>s.id===n.id); sel=n.id; detail(sel); }
  else { pan={x:e.clientX-view.x,y:e.clientY-view.y}; sel=null; detail(null); }
  cv.classList.add('drag'); cv.setPointerCapture(e.pointerId);
});
cv.addEventListener('pointermove', e=>{
  if (drag){ const n = at(e); if (n){ drag.x=n.x; drag.y=n.y; pos[drag.id]={x:n.x,y:n.y}; } }
  else if (pan){ view.x=e.clientX-pan.x; view.y=e.clientY-pan.y; }
  else { const n=at(e); hov=n?n.id:null; const t=document.getElementById('tip');
    if(n){ t.style.display='block'; t.style.left=(e.clientX+13)+'px'; t.style.top=(e.clientY+13)+'px';
           t.textContent = n.id; } else t.style.display='none'; }
});
addEventListener('pointerup', ()=>{ drag=null; pan=null; cv.classList.remove('drag'); });
cv.addEventListener('wheel', e=>{ e.preventDefault();
  view.k = Math.max(0.45, Math.min(2.4, view.k*(e.deltaY<0?1.09:0.917))); }, {passive:false});

// ── 작가 목록 ────────────────────────────────────────────────────
// 버튼 격자로는 넷까지가 한계였다. 코퍼스는 앞으로 계속 늘어나므로 목록으로
// 두고 찾기까지 붙인다. 판은 최대 넷까지만 나눈다 — 그 이상은 안 읽힌다.
const MAX_PANEL = 4;

function listing(){
  const q = (document.getElementById('q').value||'').trim().toLowerCase();
  const box = document.getElementById('who');
  const hit = WHO.filter(w=>!q || w.toLowerCase().indexOf(q)>=0);
  box.innerHTML = hit.length ? hit.map(function(w){
    const b = B[w], on = shown.indexOf(w)>=0;
    const meta = b.ok ? (b.n+'장 · 선'+b.edges.length)
                      : '<span class="no">'+b.n+'장 · 선 못 잼</span>';
    return '<button data-w="'+w+'" aria-pressed="'+on+'">'
      + '<span class="mark" style="'+(on?'background:'+wcolor(w):'')+'"></span>'
      + '<span class="nm">'+w+'</span><span class="meta">'+meta+'</span></button>';
  }).join('') : '<button disabled><span class="nm" style="color:var(--dim)">없다</span></button>';
  box.querySelectorAll('button[data-w]').forEach(function(b){
    b.onclick = function(){
      const w = b.dataset.w, i = shown.indexOf(w);
      if (i>=0){ if (shown.length>1) shown.splice(i,1); }
      else if (shown.length>=MAX_PANEL){ shown.shift(); shown.push(w); }
      else shown.push(w);
      layout(); refresh(); if (sel) detail(sel);
    };
  });
  document.getElementById('ln').innerHTML = shown.length>1
    ? ('판 '+shown.length+'개 · 최대 '+MAX_PANEL+'개까지 나란히 놓는다')
    : ('작가를 더 누르면 나란히 놓고 견준다 · 모두 '+WHO.length+'명');
  document.getElementById('q').style.display = WHO.length>7 ? 'block' : 'none';
}
document.getElementById('q').oninput = listing;
document.getElementById('cmp').onclick = function(){
  shown = shown.length>1 ? [shown[0]] : WHO.slice(0,2);
  layout(); refresh(); if (sel) detail(sel);
};
[['rh','rule2','rc'],['fh','foot','fc']].forEach(function(t){
  document.getElementById(t[0]).onclick = function(){
    const el=document.getElementById(t[1]); el.classList.toggle('on');
    document.getElementById(t[2]).textContent = el.classList.contains('on')?'－':'＋'; };
});

(document.fonts ? document.fonts.ready : Promise.resolve()).then(function(){
  layout(); refresh();
  (function loop(){ step(); draw(); requestAnimationFrame(loop); })();
});
