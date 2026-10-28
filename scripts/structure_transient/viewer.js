'use strict';
(() => {
const data = JSON.parse(document.getElementById('struct-data').textContent);
const $ = id => document.getElementById(id);
const cases = data.cases, nodes = data.mesh.nodes, modes = data.modes, modalScale = data.modal_scale;
const nNodes = nodes.length, nModes = modes.length;
let scenarioIndex = 0, playing = false, epoch = 0, lastTime = 0;
let yaw = -0.7, pitch = -1.0, zoom = 1, pan = [0, 0], drag = null;

// Validate data
if (!Array.isArray(nodes) || nodes.length === 0) throw new Error('mesh.nodes must be nonempty');
if (!Array.isArray(modes) || modes.length === 0) throw new Error('modes must be nonempty');
if (!Array.isArray(cases) || cases.length === 0) throw new Error('cases must be nonempty');

// Precompute mode magnitudes for color scaling per case
const caseMaxDisplacements = [];
for (const c of cases) {
  if (!Array.isArray(c.frames) || c.frames.length < 2) throw new Error(`case ${c.name}: frames must have >= 2 entries`);
  if (c.frames[0].length < 2) throw new Error(`case ${c.name}: first frame missing time and q`);
  // Find max displacement magnitude across all frames
  let maxMag = 0;
  for (const f of c.frames) {
    const time = f[0];
    if (typeof time !== 'number' || !isFinite(time) || time < 0) throw new Error(`case ${c.name}: invalid time`);
    const q = f.slice(1);
    if (q.length !== nModes) throw new Error(`case ${c.name}: q length ${q.length} != modes ${nModes}`);
    // Compute displacement at this frame
    const u = computeDisplacement(q);
    for (const pt of u) {
      const mag = Math.hypot(pt[0], pt[1], pt[2]);
      if (mag > maxMag) maxMag = mag;
    }
  }
  caseMaxDisplacements.push(maxMag);
}

// Compute physical displacement u(node,t) = modal_scale * Σ modes[k][node] * q_k(t)
function computeDisplacement(q) {
  if (q.length !== nModes) throw new Error(`q length ${q.length} != modes ${nModes}`);
  const u = new Array(nNodes);
  for (let p = 0; p < nNodes; p++) {
    u[p] = [0, 0, 0];
    for (let k = 0; k < nModes; k++) {
      const modePt = modes[k][p];
      if (modePt.length !== 3) throw new Error(`modes[${k}][${p}] must have 3 components`);
      const qk = q[k];
      if (typeof qk !== 'number' || !isFinite(qk)) throw new Error(`q[${k}] must be finite number`);
      u[p][0] += modePt[0] * qk;
      u[p][1] += modePt[1] * qk;
      u[p][2] += modePt[2] * qk;
    }
    u[p][0] *= modalScale;
    u[p][1] *= modalScale;
    u[p][2] *= modalScale;
  }
  return u;
}

// Linear interpolation of q values
function interpolateQ(frames, t) {
  if (t <= frames[0][0]) return frames[0].slice(1);
  if (t >= frames.at(-1)[0]) return frames.at(-1).slice(1);
  let lo = 0, hi = frames.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (frames[mid][0] <= t) lo = mid; else hi = mid;
  }
  const t0 = frames[lo][0], t1 = frames[hi][0];
  const q0 = frames[lo].slice(1), q1 = frames[hi].slice(1);
  const s = (t - t0) / (t1 - t0);
  return q0.map((v, i) => v + (q1[i] - v) * s);
}

// Camera
const scene = $('scene'), history = $('history');

// Populate scenario selector
const scenarioSelect = $('scenario');
cases.forEach((c, i) => {
  const opt = document.createElement('option');
  opt.value = i;
  opt.textContent = `${c.name} (${c.speed_m_s.toFixed(1)} m/s)`;
  scenarioSelect.appendChild(opt);
});
scenarioSelect.value = 0;

// Initial state
const currentCase = cases[scenarioIndex];
$('speedDisplay').textContent = `${currentCase.speed_m_s.toFixed(1)} m/s`;
const defScaleSelect = $('defScale');
for (const c of cases) {
  const v=String(c.default_deformation_scale);
  if (![...defScaleSelect.options].some(o=>o.value===v)) defScaleSelect.add(new Option(v+'×',v));
}
defScaleSelect.value = currentCase.default_deformation_scale;

// Metadata
$('meta').textContent = 'Recorded structural motion from native shell modes coupled to unsteady lifting-surface aerodynamics.';
$('provenance').textContent=data.source+' · '+data.scope;
$('scope').textContent = `${cases.length} scenarios; ${nNodes} nodes; ${nModes} retained modes. Zero assumed structural damping.`;

for (const text of currentCase.note ? [currentCase.note] : []) {
  const li = document.createElement('li'); li.textContent = text; $('limitations').appendChild(li);
}

// Case info display
function updateCaseInfo() {
  const c=cases[scenarioIndex];
  $('caseInfo').textContent = `${c.name} · ${c.baseline_force_applied ? 'Steady-load' : 'Small-disturbance'} experiment · stopped at motion guard: ${c.stopped_at_20mm_motion_guard ? 'yes' : 'no'}`;
}

updateCaseInfo();

function dimensions(canvas) {
  const box = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
  const w = Math.round(box.width), h = Math.round(box.height);
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, w, h];
}

function rotated(p) {
  const x = p[0] * Math.cos(yaw) - p[1] * Math.sin(yaw), y = p[0] * Math.sin(yaw) + p[1] * Math.cos(yaw);
  return [x, -(y * Math.cos(pitch) - p[2] * Math.sin(pitch)), y * Math.sin(pitch) + p[2] * Math.cos(pitch)];
}

function camera(w, h) {
  const fit = nodes.map(rotated);
  const lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
  for (const p of fit) {
    for (let k = 0; k < 2; k++) {
      lo[k] = Math.min(lo[k], p[k]); hi[k] = Math.max(hi[k], p[k]);
    }
  }
  const scale = Math.min((w - 70) / Math.max(hi[0] - lo[0], 0.03), (h - 70) / Math.max(hi[1] - lo[1], 0.03)) * zoom * 0.82;
  return { scale, project(p) {
    const r = rotated(p);
    return [(r[0] - (lo[0] + hi[0]) / 2) * scale + w / 2 + pan[0], (r[1] - (lo[1] + hi[1]) / 2) * scale + h / 2 + pan[1], r[2]];
  }};
}

function color(v, range) {
  const t = range[1] === range[0] ? 0.5 : Math.max(0, Math.min(1, (v - range[0]) / (range[1] - range[0])));
  return `hsl(${240 * (1 - t)}, 85%, 58%)`;
}

function drawScene() {
  const [ctx, w, h] = dimensions(scene); ctx.clearRect(0, 0, w, h);
  const cam = camera(w, h);
  const c = cases[scenarioIndex];
  const maxDisp = caseMaxDisplacements[scenarioIndex];
  const defScaleFactor = Number($('defScale').value);
  const t = scenarioTime;

  // Interpolate q at current time
  const q = interpolateQ(c.frames, t);
  const u = computeDisplacement(q);

  // Build geometry with deformation
  const wp = nodes.map(p => cam.project(p)); // undeformed
  const deformed = nodes.map((p, i) => cam.project([p[0] + u[i][0] * defScaleFactor, p[1] + u[i][1] * defScaleFactor, p[2] + u[i][2] * defScaleFactor]));
  const items = [];

  // Draw undeformed outline (ghost)
  const nPerim = data.mesh.perimeter_nodes || nodes.length;
  if ($('ghost').checked) {
    for (let i of [0, nPerim / 2]) {
      ctx.beginPath();
      for (let j = 0; j < nodes.length; j += nPerim) {
        const p = cam.project(nodes[j + i]);
        j === 0 ? ctx.moveTo(p[0], p[1]) : ctx.lineTo(p[0], p[1]);
      }
      ctx.closePath(); ctx.strokeStyle = '#d9e7ef'; ctx.lineWidth = 1; ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.beginPath();
    for (let i = 0; i < nPerim; i++) {
      const p = cam.project(nodes[nodes.length - nPerim + i]);
      i === 0 ? ctx.moveTo(p[0], p[1]) : ctx.lineTo(p[0], p[1]);
    }
    ctx.closePath(); ctx.strokeStyle = '#d9e7ef'; ctx.lineWidth = 1; ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
  }

  // Compute magnitudes
  const magnitudes = u.map(v => Math.hypot(v[0], v[1], v[2]));

  // Draw quads (using simple triangulation internally)
  // For viewer.html compatibility, assume quads list exists
  if (data.mesh.quads && Array.isArray(data.mesh.quads)) {
    for (const quad of data.mesh.quads) {
      if (quad.length !== 4) continue;
      const pts = quad.map(i => deformed[i]);
      const depth = pts.reduce((s, p) => s + p[2], 0) / 4;
      const mag = quad.reduce((s, i) => s + magnitudes[i], 0) / 4;
      items.push({ depth, pts, mag });
    }
  } else {
    // Fallback: draw nodes as points
  }

  items.sort((a, b) => a.depth - b.depth);
  for (const item of items) {
    ctx.beginPath(); item.pts.forEach((v, j) => j ? ctx.lineTo(v[0], v[1]) : ctx.moveTo(v[0], v[1]));
    ctx.closePath(); ctx.fillStyle = color(item.mag, [0, maxDisp]); ctx.fill();
  }

  // Wireframe edges if checked
  if ($('wire').checked && data.mesh.quads && Array.isArray(data.mesh.quads)) {
    const drawn = new Set();
    for (const quad of data.mesh.quads) {
      if (quad.length !== 4) continue;
      for (let i = 0; i < 4; i++) {
        const a = quad[i], b = quad[(i + 1) % 4];
        const key = `${Math.min(a,b)}:${Math.max(a,b)}`;
        if (drawn.has(key)) continue;
        drawn.add(key);
        const pa = deformed[a], pb = deformed[b];
        ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]);
        ctx.strokeStyle = 'rgba(8,22,32,0.24)'; ctx.lineWidth = 0.35; ctx.stroke();
      }
    }
  }

  // Axes
  const base = [45, h - 45];
  [['x', [1, 0, 0], '#ff8a80'], ['y', [0, 1, 0], '#8ee5a4'], ['z', [0, 0, 1], '#8acaff']].forEach(([name, v, col]) => {
    const r = rotated(v);
    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(...base);
    ctx.lineTo(base[0] + r[0] * 30, base[1] + r[1] * 30); ctx.stroke();
    ctx.font = '13px system-ui'; ctx.fillText(name, base[0] + r[0] * 39, base[1] + r[1] * 39);
  });

  $('legendMin').textContent = '0'; $('legendMax').textContent = (maxDisp*1000).toPrecision(4); $('legendUnits').textContent = `mm actual · geometry ${defScaleFactor}×`;
}

// Cache a linear projection onto mean tip-ring z displacement. No reference
// coordinate or visual magnification enters the physical trace.
const tipModes=modes.map(mode=>mode.slice(-data.mesh.perimeter_nodes).reduce((sum,v)=>sum+v[2],0)/data.mesh.perimeter_nodes*modalScale);
const tipDisplacement=q=>q.reduce((sum,v,k)=>sum+v*tipModes[k],0);
const histories=cases.map(c=>c.frames.map(f=>[f[0],tipDisplacement(f.slice(1))]));
function drawHistory() {
  const [ctx,w,h]=dimensions(history);ctx.clearRect(0,0,w,h);
  const c=cases[scenarioIndex],trace=histories[scenarioIndex];
  const times=trace.map(f=>f[0]),values=trace.map(f=>f[1]*1000);
  const t0=times[0],t1=times.at(-1);
  const lo=Math.min(...values),hi=Math.max(...values),pad=Math.max((hi-lo)*.1,1e-7);
  const low=lo-pad,high=hi+pad,left=65,right=w-20,top=25,bottom=h-42;
  const x=t=>left+(t-t0)/(t1-t0)*(right-left);
  const y=v=>bottom-(v-low)/(high-low)*(bottom-top);
  ctx.strokeStyle='#496078';ctx.beginPath();ctx.moveTo(left,top);ctx.lineTo(left,bottom);ctx.lineTo(right,bottom);ctx.stroke();
  ctx.fillStyle='#bacbdb';ctx.font='12px system-ui';
  ctx.fillText('Mean tip z displacement (mm)',left,16);
  ctx.fillText(high.toPrecision(3),2,top+5);ctx.fillText(low.toPrecision(3),2,bottom);
  ctx.fillText(t0.toPrecision(3),left,bottom+18);ctx.fillText(t1.toPrecision(3),right-45,bottom+18);
  ctx.fillText('Physical time (s)',left+8,h-4);
  ctx.strokeStyle='#55d9e9';ctx.lineWidth=1.5;ctx.beginPath();
  trace.forEach((f,i)=>i?ctx.lineTo(x(f[0]),y(f[1]*1000)):ctx.moveTo(x(f[0]),y(f[1]*1000)));ctx.stroke();
  ctx.strokeStyle='#fff';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(x(scenarioTime),top);ctx.lineTo(x(scenarioTime),bottom);ctx.stroke();ctx.setLineDash([]);
  const current=tipDisplacement(interpolateQ(c.frames,scenarioTime));
  $('time').textContent=`${scenarioTime.toFixed(5)} s · mean tip z ${(current*1000).toPrecision(5)} mm`;
}

let scenarioTime = cases[0].frames[0][0];
const rateSelect = $('rate');
rateSelect.value = '0.1'; // default 0.1x

function draw() {
  const c=cases[scenarioIndex];
  $('scrub').min=c.frames[0][0];$('scrub').max=c.frames.at(-1)[0];$('scrub').value=scenarioTime;
  updateCaseInfo();
  drawScene();
  drawHistory();
}

function pause() {
  if (raf) { cancelAnimationFrame(raf); raf = 0; }
  playing = false; $('play').textContent = 'Play';
}

function tick(now) {
  if (!playing) return;
  const dt = (now - lastTime) / 1000;
  const rate = Number($('rate').value);
  scenarioTime += dt * rate;
  const c = cases[scenarioIndex];
  const tEnd = c.frames.at(-1)[0];
  if (scenarioTime >= tEnd) {
    scenarioTime = tEnd;
    draw();
    if (!$('replay').checked) { pause(); return; }
    scenarioTime = c.frames[0][0];
    lastTime = now;
  }
  lastTime = now;
  raf = requestAnimationFrame(tick);
  draw();
}

$('play').onclick = () => {
  if (playing) { pause(); return; }
  playing = true; lastTime = performance.now();
  $('play').textContent = 'Pause';
  raf = requestAnimationFrame(tick);
  draw();
};

$('restart').onclick = () => {
  pause();
  scenarioTime = cases[scenarioIndex].frames[0][0];
  draw();
};

$('defScale').onchange = draw;
$('scrub').oninput = () => { pause();scenarioTime=Number($('scrub').value);draw(); };

// Scenario change: reset time and use default scale
scenarioSelect.onchange = () => {
  pause();
  scenarioIndex = Number(scenarioSelect.value);
  const c = cases[scenarioIndex];
  scenarioTime = c.frames[0][0];
  $('speedDisplay').textContent = `${c.speed_m_s.toFixed(1)} m/s`;
  defScaleSelect.value = c.default_deformation_scale;
  // Update limitations from new case note
  $('limitations').innerHTML = '';
  if (c.note) {
    const li = document.createElement('li'); li.textContent = c.note; $('limitations').appendChild(li);
  }
  draw();
};

// Other controls
let raf = 0;
$('rate').onchange = () => { if (playing) lastTime = performance.now(); draw(); };

const wireCheckbox = document.createElement('input'); wireCheckbox.type = 'checkbox'; wireCheckbox.id = 'wire'; wireCheckbox.checked = true;
const ghostCheckbox = document.createElement('input'); ghostCheckbox.type = 'checkbox'; ghostCheckbox.id = 'ghost'; ghostCheckbox.checked = true;
wireCheckbox.onchange = draw; ghostCheckbox.onchange = draw;
// Insert into DOM - find controls div and add
const controlsDiv = $('viewControls');
controlsDiv.appendChild(document.createTextNode(' '));
controlsDiv.appendChild(wireCheckbox);
controlsDiv.appendChild(document.createTextNode(' Quadrilateral edges '));
controlsDiv.appendChild(ghostCheckbox);
controlsDiv.appendChild(document.createTextNode(' Undeformed outline '));

function preset() {
  const v = $('view').value;
  [yaw, pitch] = ({ iso: [-0.7, -1.0], top: [0, 0], side: [0, -Math.PI / 2], tip: [Math.PI / 2, -Math.PI / 2] })[v];
  zoom = 1; pan = [0, 0]; draw();
}

// Add view selector
const viewSelect = document.createElement('select'); viewSelect.id = 'view';
['iso', 'top', 'side', 'tip'].forEach(v => {
  const opt = document.createElement('option'); opt.value = v; opt.textContent = v; viewSelect.appendChild(opt);
});
viewSelect.value = 'iso';
viewSelect.onchange = preset;

// Find controls and insert view selector and reset
controlsDiv.appendChild(document.createTextNode(' View '));
controlsDiv.appendChild(viewSelect);
const resetBtn=document.createElement('button');resetBtn.textContent='Reset view';resetBtn.id='reset';resetBtn.onclick=()=>{viewSelect.value='iso';preset();};controlsDiv.appendChild(resetBtn);

// Replay checkbox
const replayCheckbox = document.createElement('label'); replayCheckbox.textContent = ' Replay'; replayCheckbox.style.marginLeft = '12px';
const replayInput = document.createElement('input'); replayInput.type = 'checkbox'; replayInput.id = 'replay'; replayCheckbox.insertBefore(replayInput, replayCheckbox.firstChild);
controlsDiv.appendChild(replayCheckbox);

scene.onpointerdown = e => { drag = { x: e.clientX, y: e.clientY }; scene.setPointerCapture(e.pointerId); };
scene.onpointermove = e => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (e.shiftKey) { pan[0] += dx; pan[1] += dy; } else { yaw += dx * 0.008; pitch += dy * 0.008; }
  drag = { x: e.clientX, y: e.clientY }; draw();
};
scene.onpointerup = scene.onpointercancel = () => { drag = null; };
scene.addEventListener('wheel', e => { e.preventDefault(); zoom = Math.max(0.2, Math.min(15, zoom * Math.exp(-e.deltaY * 0.001))); draw(); }, { passive: false });

window.addEventListener('resize', draw);
draw();

// Expose API
window.structureTransientViewer = {
  data,
  draw,
  getState: () => ({ caseIndex: scenarioIndex, time: scenarioTime, playing, deformationScale: Number($('defScale').value), tipDisplacementM:tipDisplacement(interpolateQ(cases[scenarioIndex].frames,scenarioTime)), q:interpolateQ(cases[scenarioIndex].frames,scenarioTime), maximumDisplacementM:caseMaxDisplacements[scenarioIndex] })
};

})();
