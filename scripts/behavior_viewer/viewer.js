'use strict';
(() => {
const data = JSON.parse(document.getElementById('behavior-data').textContent);
const $ = id => document.getElementById(id);
const speeds = data.speeds, geometry = data.geometry;
const points = geometry.points_m, basis = geometry.basis_xyz_per_q, triangles = geometry.triangles;

let currentSpeedIndex = 0;
let currentCfdIndex = -1; // -1 = UVLM
let deformScale = 1, perturbScale = 1;
let yaw = -0.7, pitch = -1.0, zoom = 1, pan = [0, 0], drag = null;

// Camera state
function camera(w, h) {
  const fit = points.map(rotated);
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

function rotated(p) {
  const x = p[0] * Math.cos(yaw) - p[1] * Math.sin(yaw), y = p[0] * Math.sin(yaw) + p[1] * Math.cos(yaw);
  return [x, -(y * Math.cos(pitch) - p[2] * Math.sin(pitch)), y * Math.sin(pitch) + p[2] * Math.cos(pitch)];
}

function dimensions(canvas) {
  const box = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
  const w = Math.round(box.width), h = Math.round(box.height);
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, w, h];
}

// Compute deformed point: undeformed + modal deformation + perturbation
function deformedPoint(q, qDelta, i) {
  const base = points[i];
  let result = [base[0], base[1], base[2]];
  // Modal deformation
  for (let m = 0; m < 20; m++) {
    result[0] += q[m] * basis[m][i][0];
    result[1] += q[m] * basis[m][i][1];
    result[2] += q[m] * basis[m][i][2] * deformScale;
  }
  // Perturbation (only z for tip/twist, but apply full basis for shape)
  if (qDelta && qDelta.length > 0) {
    result[0] += qDelta[i] * basis[0][i][0] * perturbScale;
    result[1] += qDelta[i] * basis[0][i][1] * perturbScale;
    result[2] += qDelta[i] * basis[0][i][2] * perturbScale;
  }
  return result;
}

function drawWingMesh(ctx, cam, color, width = 0.5, alpha = 0.6) {
  const wp = points.map(cam.project);
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.globalAlpha = alpha;
  for (const tri of triangles) {
    const p = tri.map(i => wp[i]);
    ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
    ctx.lineTo(p[1][0], p[1][1]); ctx.lineTo(p[2][0], p[2][1]); ctx.closePath();
    ctx.fillStyle = color; ctx.fill(); ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawScene() {
  const [ctx, w, h] = dimensions($('scene')); ctx.clearRect(0, 0, w, h);
  const cam = camera(w, h);
  const speed = speeds[currentSpeedIndex];

  // Draw undeformed wing (blue)
  drawWingMesh(ctx, cam, '#566b82');

  // Get current state
  let q = speed.uvlm.q;
  let qDelta = null;
  if (currentCfdIndex >= 0 && speed.cfd[currentCfdIndex]) {
    q = speed.cfd[currentCfdIndex].q_pose;
  }

  // Draw deformed UVLM wing (cyan)
  const uvlmQ = speed.uvlm.q;
  const uvlmWP = points.map(p => {
    let result = [p[0], p[1], p[2]];
    for (let m = 0; m < 20; m++) {
      result[0] += uvlmQ[m] * basis[m][points.indexOf(p)] * 0; // Already applied in deformedPoint
    }
    return result;
  });

  // Actually we need to compute deformed points for UVLM
  const uvlmDeformed = points.map(i => deformedPoint(uvlmQ, null, i));
  const uvlmWP2 = uvlmDeformed.map(cam.project);

  ctx.strokeStyle = '#00bcd4'; ctx.lineWidth = 1; ctx.globalAlpha = 0.7;
  for (const tri of triangles) {
    const p = tri.map(i => uvlmWP2[i]);
    ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
    ctx.lineTo(p[1][0], p[1][1]); ctx.lineTo(p[2][0], p[2][1]); ctx.closePath();
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Draw CFD held pose (yellow) if selected
  if (currentCfdIndex >= 0 && speed.cfd[currentCfdIndex]) {
    const cfdQ = speed.cfd[currentCfdIndex].q_pose;
    const cfdDeformed = points.map(i => deformedPoint(cfdQ, null, i));
    const cfdWP = cfdDeformed.map(cam.project);
    ctx.strokeStyle = '#ffeb3b'; ctx.lineWidth = 1; ctx.globalAlpha = 0.7;
    for (const tri of triangles) {
      const p = tri.map(i => cfdWP[i]);
      ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
      ctx.lineTo(p[1][0], p[1][1]); ctx.lineTo(p[2][0], p[2][1]); ctx.closePath();
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // Draw transient perturbation (purple) if available
  if (speed.transient && speed.transient.time_s && speed.transient.time_s.length > 0) {
    // Use first sample of transient
    const qDelta = speed.transient.q_delta[0];
    const tipDelta = speed.transient.tip_delta_in[0];
    const twistDelta = speed.transient.twist_delta_deg[0];

    // We need to map q_delta to actual deformation
    // q_delta is [K][20] for K samples
    const perturbDeformed = points.map(i => deformedPoint(uvlmQ, qDelta, i));
    const perturbWP = perturbDeformed.map(cam.project);
    ctx.strokeStyle = '#9c27b0'; ctx.lineWidth = 1; ctx.globalAlpha = 0.5;
    for (const tri of triangles) {
      const p = tri.map(i => perturbWP[i]);
      ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
      ctx.lineTo(p[1][0], p[1][1]); ctx.lineTo(p[2][0], p[2][1]); ctx.closePath();
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // Draw coordinate axes
  const base = [45, h - 45];
  [['x', [1, 0, 0], '#ff8a80'], ['y', [0, 1, 0], '#8ee5a4'], ['z', [0, 0, 1], '#8acaff']].forEach(([name, v, col]) => {
    const r = rotated(v);
    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(...base);
    ctx.lineTo(base[0] + r[0] * 30, base[1] + r[1] * 30); ctx.stroke();
    ctx.font = '12px system-ui'; ctx.fillText(name, base[0] + r[0] * 39, base[1] + r[1] * 39);
  });

  // Draw legend for scales
  $('deformScaleLabel').textContent = `Deformation: ${deformScale.toFixed(1)}×`;
  $('perturbScaleLabel').textContent = `Perturbation: ${perturbScale.toFixed(1)}×`;
}

function drawTrendChart() {
  const canvas = $('chartCanvas');
  const [ctx, w, h] = dimensions(canvas);
  ctx.clearRect(0, 0, w, h);

  // Extract data for all speeds
  const speedsData = speeds.map((s, i) => ({
    speed_kn: s.speed_kn,
    uvLM_tip: s.uvlm.tip_in,
    uvLM_twist: s.uvlm.twist_deg,
    uvLM_lift: s.uvlm.lift_lbf,
    uvLM_alpha: s.uvlm.alpha_deg,
    cfd_tip: s.cfd.length > 0 ? s.cfd.map(c => c.tip_in) : null,
    cfd_lift: s.cfd.length > 0 ? s.cfd.map(c => c.lift_lbf) : null
  }));

  // Draw UVLM tip deflection trend
  ctx.strokeStyle = '#00bcd4'; ctx.lineWidth = 2;
  ctx.beginPath();
  speedsData.forEach((d, i) => {
    const x = (d.speed_kn - 60) / (250 - 60) * (w - 60) + 40;
    const y = h - 40 - (d.uvLM_tip - Math.min(...speedsData.map(s => s.uvLM_tip)) * 0.9) /
      ((Math.max(...speedsData.map(s => s.uvLM_tip)) - Math.min(...speedsData.map(s => s.uvLM_tip))) * 1.2) * (h - 100);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Draw UVLM twist trend
  ctx.strokeStyle = '#ff9800'; ctx.lineWidth = 2;
  ctx.beginPath();
  speedsData.forEach((d, i) => {
    const x = (d.speed_kn - 60) / (250 - 60) * (w - 60) + 40;
    const y = h - 40 - (d.uvLM_twist - Math.min(...speedsData.map(s => s.uvLM_twist)) * 0.9) /
      ((Math.max(...speedsData.map(s => s.uvLM_twist)) - Math.min(...speedsData.map(s => s.uvLM_twist))) * 1.2) * (h - 100);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Draw UVLM lift trend
  ctx.strokeStyle = '#4caf50'; ctx.lineWidth = 2;
  ctx.beginPath();
  speedsData.forEach((d, i) => {
    const x = (d.speed_kn - 60) / (250 - 60) * (w - 60) + 40;
    const y = h - 40 - (d.uvLM_lift - Math.min(...speedsData.map(s => s.uvLM_lift)) * 0.9) /
      ((Math.max(...speedsData.map(s => s.uvLM_lift)) - Math.min(...speedsData.map(s => s.uvLM_lift))) * 1.2) * (h - 100);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Labels
  ctx.fillStyle = '#dce7f2'; ctx.font = '11px system-ui';
  ctx.fillText('Tip deflection (cyan)', 10, 20);
  ctx.fillText('Twist (orange)', 10, 35);
  ctx.fillText('Lift (green)', 10, 50);
}

function updateUI() {
  const speed = speeds[currentSpeedIndex];
  const cfd = currentCfdIndex >= 0 && speed.cfd[currentCfdIndex] ? speed.cfd[currentCfdIndex] : null;

  // Update speed selector
  const speedSelect = $('speedSelect');
  while (speedSelect.firstChild) speedSelect.removeChild(speedSelect.firstChild);
  speeds.forEach((s, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `${s.speed_kn} kn (Mach ${s.mach.toFixed(3)})`;
    speedSelect.appendChild(opt);
  });
  speedSelect.value = currentSpeedIndex;

  // Update CFD selector
  const cfdSelect = $('cfdSelect');
  while (cfdSelect.firstChild) cfdSelect.removeChild(cfdSelect.firstChild);

  const uvlmOption = document.createElement('option');
  uvlmOption.value = '-1';
  uvlmOption.textContent = 'UVLM equilibrium';
  cfdSelect.appendChild(uvlmOption);

  speed.cfd.forEach((c, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `${c.label} (${c.id})`;
    cfdSelect.appendChild(opt);
  });
  cfdSelect.value = currentCfdIndex;

  // Update speed label
  $('speedLabel').textContent = `${speed.speed_kn} kn (Mach ${speed.mach.toFixed(3)})`;

  // Update metrics
  $('metricTip').textContent = `${speed.uvlm.tip_in.toFixed(3)} in`;
  $('metricTwist').textContent = `${speed.uvlm.twist_deg.toFixed(3)}°`;
  $('metricLift').textContent = `${speed.uvlm.lift_lbf.toFixed(2)} lbf`;
  $('metricAlpha').textContent = `${speed.uvlm.alpha_deg.toFixed(3)}°`;

  // Update compare list
  const compareList = $('compareList');
  compareList.innerHTML = '';

  // UVLM reference
  const uvlmItem = document.createElement('div');
  uvlmItem.id = 'compareItem';
  uvlmItem.innerHTML = `
    <strong style="color:#00bcd4">UVLM equilibrium</strong>
    <span class="muted">Alpha: ${speed.uvlm.alpha_deg.toFixed(3)}° | Lift: ${speed.uvlm.lift_lbf.toFixed(2)} lbf</span>
    <span class="muted">Timing: ${speed.uvlm.timing_scope}</span>
  `;
  compareList.appendChild(uvlmItem);

  // CFD comparisons
  if (speed.cfd.length > 0) {
    speed.cfd.forEach((c, i) => {
      const item = document.createElement('div');
      item.id = 'compareItem';
      let statusText = '';
      if (!c.stationary) statusText += 'Force history not stationary. ';
      if (!c.loaded_gate) statusText += 'Loaded-reference failed. ';
      if (c.status.length > 2) statusText += c.status[2] || '';

      item.innerHTML = `
        <strong style="color:#ffeb3b">${c.label}</strong>
        <span class="muted">Alpha: ${c.alpha_deg.toFixed(3)}° | Lift: ${c.lift_lbf.toFixed(2)} lbf</span>
        <span class="muted">Lift error: ${c.lift_error_pct.toFixed(2)}% | Balance correction: ${c.balance_correction_in.toFixed(4)} in</span>
        <span class="muted">${statusText}</span>
        <span class="muted">Pose match: ${c.matched_uvlm_inputs ? 'Yes' : 'No'} | ${c.comparison_label}</span>
        <span class="muted">Iterations: ${c.iterations} | Time: ${c.timing_scope}</span>
      `;
      compareList.appendChild(item);
    });
  }

  // Update chart
  drawTrendChart();

  // Update case info
  $('caseInfo').innerHTML = `
    <span class="stat">Speed: ${speed.speed_kn} kn</span>
    <span class="stat">Method: ${currentCfdIndex < 0 ? 'UVLM' : 'CFD fixed-pose'}</span>
    <span class="stat">Modes: 20</span>
    <span class="stat">Points: ${points.length.toLocaleString()}</span>
    <span class="stat">Triangles: ${triangles.length.toLocaleString()}</span>
  `;

  $('scope').textContent = `Showing ${speeds.length} speeds (60–250 kn). ${currentCfdIndex < 0 ? 'UVLM equilibrium solution.' : 'CFD held-pose snapshot.'}`;
  $('limitations').innerHTML = '';
  data.limits.forEach(l => {
    const li = document.createElement('li'); li.textContent = l; $('limitations').appendChild(li);
  });
}

function draw() {
  drawScene();
  updateUI();
}

function resetView() {
  yaw = -0.7; pitch = -1.0; zoom = 1; pan = [0, 0];
  draw();
}

function spanView() {
  yaw = 0; pitch = -Math.PI / 2; zoom = 1; pan = [0, 0];
  draw();
}

function isometricView() {
  yaw = -0.7; pitch = -1.0; zoom = 1; pan = [0, 0];
  draw();
}

// Event handlers
$('speedSelect').onchange = () => { currentSpeedIndex = Number($('speedSelect').value); currentCfdIndex = -1; $('cfdSelect').value = '-1'; draw(); };
$('cfdSelect').onchange = () => { currentCfdIndex = Number($('cfdSelect').value); draw(); };
$('deformScale').oninput = () => { deformScale = parseFloat($('deformScale').value); draw(); };
$('perturbScale').oninput = () => { perturbScale = parseFloat($('perturbScale').value); draw(); };

$('view').onchange = () => {
  const v = $('view').value;
  if (v === 'iso') isometricView();
  else if (v === 'span') spanView();
  else if (v === 'reset') resetView();
};

$('reset').onclick = resetView;

// Scene interaction
$('scene').onpointerdown = e => { drag = { x: e.clientX, y: e.clientY }; $('scene').setPointerCapture(e.pointerId); };
$('scene').onpointermove = e => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (e.shiftKey) { pan[0] += dx; pan[1] += dy; } else { yaw += dx * 0.008; pitch += dy * 0.008; }
  drag = { x: e.clientX, y: e.clientY }; draw();
};
$('scene').onpointerup = $('scene').onpointercancel = () => { drag = null; };
$('scene').addEventListener('wheel', e => { e.preventDefault(); zoom = Math.max(0.2, Math.min(15, zoom * Math.exp(-e.deltaY * 0.001))); draw(); }, { passive: false });

window.addEventListener('resize', draw);
draw();
})();
