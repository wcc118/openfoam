'use strict';
(() => {
const data = JSON.parse(document.getElementById('angle-data').textContent);
const $ = id => document.getElementById(id);
const cases = data.cases, points = data.samples.points, groups = data.samples.groups;
const angles = cases.map(c => c.alpha_deg);
const angleIndex = new Map(angles.map((a, i) => [a, i]));
let currentIndex = 0;
let yaw = -0.7, pitch = 1.0, zoom = 1, pan = [0, 0], drag = null;
const scene = $('scene');

// Populate angle selector
const angleSelect = $('angle');
angles.forEach((alpha, i) => {
  const opt = document.createElement('option');
  opt.value = i;
  opt.textContent = `${alpha.toFixed(2)}° (id: ${cases[i].id})`;
  angleSelect.appendChild(opt);
});
angleSelect.value = 0;
angleSelect.onchange = () => { currentIndex = Number(angleSelect.value); draw(); preserveCamera(); };

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

function color(v, range) {
  const t = range[1] === range[0] ? 0.5 : Math.max(0, Math.min(1, (v - range[0]) / (range[1] - range[0])));
  return `hsl(${240 * (1 - t)}, 85%, 58%)`;
}

function camera(w, h) {
  const g = $('group').value;
  const selected = points.filter((p, i) => g === 'all' || groups[i] === g);
  const fit = (g === 'all' ? selected.concat(data.wing.points) : selected).map(rotated);
  const lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
  for (const p of fit) {
    for (let k = 0; k < 2; k++) {
      lo[k] = Math.min(lo[k], p[k]); hi[k] = Math.max(hi[k], p[k]);
    }
  }
  const scale = Math.min((w - 70) / Math.max(hi[0] - lo[0], 0.03), (h - 70) / Math.max(hi[1] - lo[1], 0.03)) * zoom;
  return { scale, project(p) {
    const r = rotated(p);
    return [(r[0] - (lo[0] + hi[0]) / 2) * scale + w / 2 + pan[0], (r[1] - (lo[1] + hi[1]) / 2) * scale + h / 2 + pan[1], r[2]];
  }};
}

function drawScene() {
  const [ctx, w, h] = dimensions(scene); ctx.clearRect(0, 0, w, h);
  const cam = camera(w, h), f = cases[currentIndex], field = $('field').value, range = data.color_ranges[field], g = $('group').value;
  const wp = data.wing.points.map(cam.project), items = [];
  for (const tri of data.wing.triangles) {
    const p = tri.map(i => wp[i]);
    items.push({ depth: p.reduce((a, v) => a + v[2], 0) / 3, tri: p });
  }
  const stride = Math.max(1, Math.ceil(points.length / 180));
  for (let i = 0; i < points.length; i++) {
    if (g !== 'all' && groups[i] !== g) continue;
    const q = cam.project(points[i]); if (q[0] < -30 || q[0] > w + 30 || q[1] < -30 || q[1] > h + 30) continue;
    const val = field === 'speed' ? Math.hypot(...f.U[i]) : (f.p[i] - data.reference.reference_pressure_kinematic) / data.reference.dynamic_pressure_kinematic;
    items.push({ depth: q[2], q, i, col: color(val, range), arrow: $('arrows').checked && i % stride === 0 });
  }
  items.sort((a, b) => a.depth - b.depth);
  for (const item of items) {
    if (item.tri) {
      ctx.beginPath(); item.tri.forEach((v, j) => j ? ctx.lineTo(v[0], v[1]) : ctx.moveTo(v[0], v[1]));
      ctx.closePath(); ctx.fillStyle = '#566b82'; ctx.fill(); ctx.strokeStyle = '#899aaa'; ctx.lineWidth = 0.25; ctx.stroke();
    } else {
      const [x, y] = item.q; ctx.fillStyle = item.col; ctx.beginPath(); ctx.arc(x, y, g === 'all' ? 2.0 : 2.7, 0, Math.PI * 2); ctx.fill();
      if (item.arrow) {
        const p = points[item.i], u = f.U[item.i], end = cam.project(p.map((v, k) => v + u[k] * 0.0007));
        const dx = end[0] - x, dy = end[1] - y, L = Math.hypot(dx, dy);
        if (L > 2) {
          ctx.strokeStyle = item.col; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(end[0], end[1]);
          ctx.moveTo(end[0] - dx / L * 5 - dy / L * 3, end[1] - dy / L * 5 + dx / L * 3);
          ctx.lineTo(end[0], end[1]); ctx.lineTo(end[0] - dx / L * 5 + dy / L * 3, end[1] - dy / L * 5 - dx / L * 3);
          ctx.stroke();
        }
      }
    }
  }
  const base = [45, h - 45];
  [['x', [1, 0, 0], '#ff8a80'], ['y', [0, 1, 0], '#8ee5a4'], ['z', [0, 0, 1], '#8acaff']].forEach(([name, v, col]) => {
    const r = rotated(v);
    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(...base);
    ctx.lineTo(base[0] + r[0] * 30, base[1] + r[1] * 30); ctx.stroke();
    ctx.font = '13px system-ui'; ctx.fillText(name, base[0] + r[0] * 39, base[1] + r[1] * 39);
  });
  $('legendMin').textContent = range[0].toPrecision(4); $('legendMax').textContent = range[1].toPrecision(4);
  $('legendUnits').textContent = field === 'speed' ? 'm/s · fixed across all cases' : 'Cp · fixed across all cases';
}

function draw() {
  drawScene();
  const c = cases[currentIndex];
  const alpha = c.alpha_deg;
  $('meta').textContent = `${c.id} · ${c.solver} · source ${c.source_revision}`;
  $('scope').textContent = `Case ${currentIndex + 1}/${cases.length}; ${points.length.toLocaleString()} fixed sample points. Read the limitations before interpreting these steady results.`;
  for (const text of c.limitations) {
    const li = document.createElement('li'); li.textContent = text; $('limitations').append(li);
  }
  const f = c;
  $('caseInfo').innerHTML = `<span class="stat">Alpha: ${alpha.toFixed(3)}°</span> <span class="stat">Steady iteration: ${c.steady_iteration}</span> <span class="stat">U∞: [${f.freestream_velocity_m_s.map(v => v.toFixed(3)).join(', ')}] m/s</span>`;
}

function preset() {
  const v = $('view').value;
  [yaw, pitch] = ({ iso: [-0.7, 1.0], top: [0, 0], side: [0, Math.PI / 2], tip: [Math.PI / 2, Math.PI / 2] })[v];
  zoom = 1; pan = [0, 0]; draw();
}

$('view').onchange = preset; $('reset').onclick = () => { $('view').value = 'iso'; preset(); };
scene.onpointerdown = e => { drag = { x: e.clientX, y: e.clientY }; scene.setPointerCapture(e.pointerId); };
scene.onpointermove = e => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (e.shiftKey) { pan[0] += dx; pan[1] += dy; } else { yaw += dx * 0.008; pitch += dy * 0.008; }
  drag = { x: e.clientX, y: e.clientY }; draw();
};
scene.onpointerup = scene.onpointercancel = () => { drag = null; };
scene.addEventListener('wheel', e => { e.preventDefault(); zoom = Math.max(0.2, Math.min(15, zoom * Math.exp(-e.deltaY * 0.001))); draw(); }, { passive: false });

function preserveCamera() {
  // Preserve yaw, pitch, zoom, pan when switching cases
  draw();
}

window.addEventListener('resize', draw);
draw();
})();
