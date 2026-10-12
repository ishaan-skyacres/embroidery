"""Self-contained HTML sewing-order simulator."""
from __future__ import annotations

import json
from pathlib import Path

from .stitchplan import JUMP, STITCH, TRIM, StitchPlan

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stitch simulator: __TITLE__</title>
<style>
 :root { --bg:#f4f1ea; --ink:#222; --panel:#fff; --accent:#1f6f8b; }
 body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background:var(--bg); color:var(--ink); }
 header { padding:10px 16px; background:var(--panel); border-bottom:1px solid #ddd; display:flex; flex-wrap:wrap; gap:10px 18px; align-items:center; }
 header h1 { font-size:16px; margin:0 12px 0 0; }
 button { font-size:15px; padding:6px 12px; border-radius:6px; border:1px solid #999; background:#fff; cursor:pointer; }
 button:active { background:#eee; }
 label { font-size:13px; }
 #wrap { display:flex; flex-wrap:wrap; }
 canvas { background:#e8e2d4; margin:12px; border:1px solid #bbb; max-width:100%; height:auto; touch-action:none; }
 #side { padding:12px 16px; min-width:240px; font-size:14px; }
 #scrub { width:100%; }
 .stop { display:flex; align-items:center; gap:8px; padding:4px 0; }
 .sw { width:18px; height:18px; border:1px solid #666; border-radius:3px; display:inline-block; }
 .cur { font-weight:bold; }
 #status { font-variant-numeric: tabular-nums; margin:6px 0; }
 .legend { font-size:12px; color:#555; margin-top:10px; }
</style></head>
<body>
<header>
 <h1>__TITLE__</h1>
 <button id="play">Play</button>
 <button id="step">+1</button>
 <button id="stepback">-1</button>
 <button id="restart">Restart</button>
 <label>Speed <input id="speed" type="range" min="1" max="400" value="40"> <span id="speedv">40</span> st/frame</label>
 <label><input id="showjumps" type="checkbox" checked> jumps (dashed)</label>
 <label><input id="showtrims" type="checkbox" checked> trims (x)</label>
 <label><input id="showgrid" type="checkbox" checked> 10 mm grid</label>
</header>
<div id="wrap">
 <canvas id="c" width="900" height="900"></canvas>
 <div id="side">
  <input id="scrub" type="range" min="0" max="0" value="0">
  <div id="status"></div>
  <div><b>Colour stops</b> (sewing order)</div>
  <div id="stops"></div>
  <div class="legend">Drag the slider to scrub. Dashed red = jump (no stitching). Red x = trim. Each colour stop is a manual thread change on the EOC06.</div>
 </div>
</div>
<script>
const DATA = __DATA__;
const c = document.getElementById('c'); const ctx = c.getContext('2d');
let W = c.width, H = c.height;
const b = DATA.bounds; const pad = 10;
const sx = (W - 2*pad) / (b[2]-b[0]), sy = (H - 2*pad) / (b[3]-b[1]); const S = Math.min(sx, sy);
const ox = pad + ((W-2*pad) - (b[2]-b[0])*S)/2, oy = pad + ((H-2*pad) - (b[3]-b[1])*S)/2;
function X(x){ return ox + (x - b[0]) * S; } function Y(y){ return oy + (y - b[1]) * S; }
// flatten
const flat = []; // [x,y,cmd,block]
DATA.blocks.forEach((blk, bi) => blk.s.forEach(s => flat.push([s[0], s[1], s[2], bi])));
const N = flat.length;
let pos = 0, playing = false;
const scrub = document.getElementById('scrub'); scrub.max = N;
const speedEl = document.getElementById('speed'); const speedv = document.getElementById('speedv');
const stopsEl = document.getElementById('stops');
DATA.blocks.forEach((blk, i) => {
  const d = document.createElement('div'); d.className='stop'; d.id = 'stop'+i;
  d.innerHTML = `<span class="sw" style="background:${blk.color}"></span> ${i+1}. ${blk.name} <span style="color:#666">(${blk.count} st)</span>`;
  stopsEl.appendChild(d);
});
function grid(){
  if(!document.getElementById('showgrid').checked) return;
  ctx.strokeStyle='rgba(0,0,0,0.12)'; ctx.lineWidth=1; ctx.setLineDash([]);
  const x0 = Math.ceil(b[0]/10)*10, x1 = Math.floor(b[2]/10)*10, y0 = Math.ceil(b[1]/10)*10, y1 = Math.floor(b[3]/10)*10;
  for(let x=x0;x<=x1;x+=10){ ctx.beginPath(); ctx.moveTo(X(x),Y(b[1])); ctx.lineTo(X(x),Y(b[3])); ctx.stroke(); }
  for(let y=y0;y<=y1;y+=10){ ctx.beginPath(); ctx.moveTo(X(b[0]),Y(y)); ctx.lineTo(X(b[2]),Y(y)); ctx.stroke(); }
  ctx.strokeStyle='rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.moveTo(X(0),Y(b[1])); ctx.lineTo(X(0),Y(b[3])); ctx.moveTo(X(b[0]),Y(0)); ctx.lineTo(X(b[2]),Y(0)); ctx.stroke();
}
function draw(){
  ctx.clearRect(0,0,W,H); grid();
  const showJ = document.getElementById('showjumps').checked, showT = document.getElementById('showtrims').checked;
  const lw = Math.max(1.2, 0.4*S);
  let prev=null, curBlock=-1;
  for(let i=0;i<pos;i++){
    const s = flat[i];
    if(s[3]!==curBlock){ curBlock=s[3]; ctx.strokeStyle = DATA.blocks[curBlock].color; }
    if(s[2]===0){ // stitch
      if(prev){ ctx.lineWidth=lw; ctx.setLineDash([]); ctx.strokeStyle = DATA.blocks[curBlock].color; ctx.beginPath(); ctx.moveTo(X(prev[0]),Y(prev[1])); ctx.lineTo(X(s[0]),Y(s[1])); ctx.stroke(); }
      prev = s;
    } else if(s[2]===1){ // jump
      if(showJ && prev){ ctx.lineWidth=1; ctx.setLineDash([4,4]); ctx.strokeStyle='rgba(200,0,0,0.8)'; ctx.beginPath(); ctx.moveTo(X(prev[0]),Y(prev[1])); ctx.lineTo(X(s[0]),Y(s[1])); ctx.stroke(); ctx.setLineDash([]); }
      prev = s;
    } else if(s[2]===2){ // trim
      if(showT && prev){ ctx.strokeStyle='rgba(200,0,0,0.9)'; ctx.lineWidth=1.5; ctx.setLineDash([]); const px=X(prev[0]), py=Y(prev[1]); ctx.beginPath(); ctx.moveTo(px-5,py-5); ctx.lineTo(px+5,py+5); ctx.moveTo(px-5,py+5); ctx.lineTo(px+5,py-5); ctx.stroke(); }
    }
  }
  // needle
  if(pos>0 && prev){ ctx.strokeStyle='#000'; ctx.lineWidth=1; ctx.beginPath(); ctx.arc(X(prev[0]),Y(prev[1]),6,0,Math.PI*2); ctx.stroke(); }
  // status
  let stitches=0, blk = pos>0 ? flat[Math.min(pos,N)-1][3] : 0;
  for(let i=0;i<pos;i++) if(flat[i][2]===0) stitches++;
  document.getElementById('status').innerHTML = `Stitch <b>${stitches}</b> of ${DATA.total} &nbsp; | &nbsp; stop <b>${blk+1}</b> of ${DATA.blocks.length}: <b>${DATA.blocks[blk].name}</b>`;
  DATA.blocks.forEach((_,i)=>{ document.getElementById('stop'+i).classList.toggle('cur', i===blk); });
  scrub.value = pos;
}
function tick(){ if(!playing) return; pos = Math.min(N, pos + parseInt(speedEl.value)); draw(); if(pos>=N){ playing=false; document.getElementById('play').textContent='Play'; return; } requestAnimationFrame(tick); }
document.getElementById('play').onclick = ()=>{ playing=!playing; document.getElementById('play').textContent = playing?'Pause':'Play'; if(playing){ if(pos>=N) pos=0; requestAnimationFrame(tick);} };
document.getElementById('step').onclick = ()=>{ pos=Math.min(N,pos+1); draw(); };
document.getElementById('stepback').onclick = ()=>{ pos=Math.max(0,pos-1); draw(); };
document.getElementById('restart').onclick = ()=>{ pos=0; playing=false; document.getElementById('play').textContent='Play'; draw(); };
scrub.oninput = ()=>{ pos=parseInt(scrub.value); draw(); };
speedEl.oninput = ()=>{ speedv.textContent = speedEl.value; };
['showjumps','showtrims','showgrid'].forEach(id => document.getElementById(id).onchange = draw);
pos = N; draw();
</script></body></html>
"""


def write_simulator(plan: StitchPlan, path: Path, title: str = "design") -> Path:
    blocks = []
    for b in plan.blocks:
        s = []
        for st in b.stitches:
            cmd = 0 if st.cmd == STITCH else (1 if st.cmd == JUMP else 2)
            s.append([round(st.x, 2), round(st.y, 2), cmd])
        blocks.append({"name": b.group, "color": b.color, "count": b.stitch_count(), "s": s})
    x0, y0, x1, y1 = plan.bounds()
    data = {"blocks": blocks, "bounds": [x0 - 3, y0 - 3, x1 + 3, y1 + 3], "total": plan.stitch_count()}
    html = TEMPLATE.replace("__TITLE__", title).replace("__DATA__", json.dumps(data, separators=(",", ":")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
