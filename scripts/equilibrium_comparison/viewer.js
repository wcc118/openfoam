'use strict';
(() => {
const data = JSON.parse(document.getElementById('eq-data').textContent);
const $ = id => document.getElementById(id);
const cases = data.cases, nodes = data.mesh.nodes, models = data.models;
const nNodes = nodes.length;
let modelIndex = 0, playing = false, epoch = 0, lastTime = 0;
let yaw = -0.7, pitch = -1.0, zoom = 1, pan = [0, 0], drag = null;
let displayMode = 'total'; // 'total' or 'perturbation'

// Validate data
if (!Array.isArray(nodes) || nodes.length === 0) throw new Error('mesh.nodes must be nonempty');
if (!Array.isArray(models) || Object.keys(models).length === 0) throw new Error('models must be nonempty');
if (!Array.isArray(cases) || cases.length === 0) throw new Error('cases must be nonempty');

// Get mode count for current model
function getModeCount(modelTag) {
    return models[modelTag].modes.length;
}

// Get case mode count
function getCaseModeCount(caseIdx) {
    return getModeCount(cases[caseIdx].model);
}

// Precompute max displacements per case
const caseMaxDisplacements = [];
for (let i = 0; i < cases.length; i++) {
    const c = cases[i];
    if (!Array.isArray(c.frames) || c.frames.length < 2) throw new Error(`case ${c.name}: frames must have >= 2 entries`);
    let maxMag = 0;
    for (const f of c.frames) {
        const q = f.slice(1);
        const u = computeDisplacement(q, c.model);
        for (const pt of u) {
            const mag = Math.hypot(pt[0], pt[1], pt[2]);
            if (mag > maxMag) maxMag = mag;
        }
    }
    caseMaxDisplacements.push(maxMag);
}

// Compute physical displacement u(node,t) = Σ modes[k][node] * q_k(t) / sqrt(2)
function computeDisplacement(q, modelTag) {
    const modes = models[modelTag].modes;
    const nModes = modes.length;
    if (q.length !== nModes) throw new Error(`q length ${q.length} != modes ${nModes}`);
    const u = new Array(nNodes);
    const factor = 1 / Math.sqrt(2);
    for (let p = 0; p < nNodes; p++) {
        u[p] = [0, 0, 0];
        for (let k = 0; k < nModes; k++) {
            const modePt = modes[k][p];
            const qk = q[k];
            u[p][0] += modePt[0] * qk * factor;
            u[p][1] += modePt[1] * qk * factor;
            u[p][2] += modePt[2] * qk * factor;
        }
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

// Compute tip metrics: mean z displacement and twist in degrees
function computeTipMetrics(q, modelTag, caseIdx) {
    const c = cases[caseIdx];
    const model = models[modelTag];
    const reference_q = c.reference_q;

    // Find tip nodes (max y)
    let maxY = -Infinity;
    for (let i = 0; i < nNodes; i++) {
        if (nodes[i][1] > maxY) maxY = nodes[i][1];
    }
    const tipIndices = [];
    for (let i = 0; i < nNodes; i++) {
        if (Math.abs(nodes[i][1] - maxY) < 1e-9) tipIndices.push(i);
    }
    const nTip = tipIndices.length;

    // Compute centroid of tip nodes
    let xc = 0, zc = 0;
    for (const i of tipIndices) {
        xc += nodes[i][0];
        zc += nodes[i][2];
    }
    xc /= nTip;
    zc /= nTip;

    // Compute perturbation q (q - reference_q) if display mode is perturbation
    const qEffective = displayMode === 'perturbation'
        ? q.map((v, i) => v - reference_q[i])
        : q;

    // Compute displacement at tip nodes
    const u = computeDisplacement(qEffective, modelTag);

    // Mean z displacement
    let sumZ = 0;
    for (const i of tipIndices) {
        sumZ += u[i][2];
    }
    const meanTipZ = sumZ / nTip;

    // Twist: θ_y = Σ((z−z_c)·u_x − (x−x_c)·u_z) / Σ((z−z_c)²+(x−x_c)²)
    let numerator = 0, denominator = 0;
    for (const i of tipIndices) {
        const x = nodes[i][0] - xc;
        const z = nodes[i][2] - zc;
        const ux = u[i][0];
        const uz = u[i][2];
        numerator += z * ux - x * uz;
        denominator += z * z + x * x;
    }
    const twistRad = denominator > 1e-15 ? numerator / denominator : 0;
    const twistDeg = twistRad * 180 / Math.PI;

    return { meanTipZ, twistDeg };
}

// Camera for a single canvas
function cameraForNodes(nodes, w, h) {
    const rotated = nodes.map(p => {
        const x = p[0] * Math.cos(yaw) - p[1] * Math.sin(yaw);
        const y = p[0] * Math.sin(yaw) + p[1] * Math.cos(yaw);
        return [x, -(y * Math.cos(pitch) - p[2] * Math.sin(pitch)), y * Math.sin(pitch) + p[2] * Math.cos(pitch)];
    });
    let lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
    for (const p of rotated) {
        for (let k = 0; k < 2; k++) {
            lo[k] = Math.min(lo[k], p[k]);
            hi[k] = Math.max(hi[k], p[k]);
        }
    }
    const scale = Math.min((w - 70) / Math.max(hi[0] - lo[0], 0.03), (h - 70) / Math.max(hi[1] - lo[1], 0.03)) * zoom * 0.82;
    return { scale, project(p) {
        const r = [
            p[0] * Math.cos(yaw) - p[1] * Math.sin(yaw),
            p[0] * Math.sin(yaw) + p[1] * Math.cos(yaw)
        ];
        const y3d = -(r[1] * Math.cos(pitch) - p[2] * Math.sin(pitch));
        return [(r[0] - (lo[0] + hi[0]) / 2) * scale + w / 2 + pan[0], y3d * scale + h / 2 + pan[1], y3d];
    }};
}

function color(v, range) {
    const t = range[1] === range[0] ? 0.5 : Math.max(0, Math.min(1, (v - range[0]) / (range[1] - range[0])));
    return `hsl(${240 * (1 - t)}, 85%, 58%)`;
}

function dimensions(canvas) {
    const box = canvas.getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const w = Math.round(box.width), h = Math.round(box.height);
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [ctx, w, h];
}

function drawScene(canvasId, caseIdx) {
    const canvas = $(canvasId);
    const [ctx, w, h] = dimensions(canvas);
    ctx.clearRect(0, 0, w, h);

    const c = cases[caseIdx];
    const maxDisp = caseMaxDisplacements[caseIdx];
    const defScaleFactor = Number($('defScale').value);
    const t = modelTime;

    // Interpolate q at current time
    const q = interpolateQ(c.frames, t);
    const modelTag = c.model;
    const reference_q = c.reference_q;

    // Compute effective q based on display mode
    const qEffective = displayMode === 'perturbation'
        ? q.map((v, i) => v - reference_q[i])
        : q;

    // Compute displacement
    const u = computeDisplacement(qEffective, modelTag);

    // Build geometry
    const cam = cameraForNodes(nodes, w, h);
    const wp = nodes.map(p => cam.project(p));
    const deformed = nodes.map((p, i) => cam.project([
        p[0] + u[i][0] * defScaleFactor,
        p[1] + u[i][1] * defScaleFactor,
        p[2] + u[i][2] * defScaleFactor
    ]));

    const items = [];
    for (const quad of data.mesh.quads) {
        if (quad.length !== 4) continue;
        const pts = quad.map(i => deformed[i]);
        const depth = pts.reduce((s, p) => s + p[2], 0) / 4;
        const mag = quad.reduce((s, i) => s + Math.hypot(u[i][0], u[i][1], u[i][2]), 0) / 4;
        items.push({ depth, pts, mag });
    }
    items.sort((a, b) => a.depth - b.depth);

    for (const item of items) {
        ctx.beginPath();
        item.pts.forEach((v, j) => j ? ctx.lineTo(v[0], v[1]) : ctx.moveTo(v[0], v[1]));
        ctx.closePath();
        ctx.fillStyle = color(item.mag, [0, maxDisp]);
        ctx.fill();
    }

    // Draw undeformed outline
    ctx.beginPath();
    for (let i = 0; i < nodes.length; i++) {
        const p = cam.project(nodes[i]);
        i === 0 ? ctx.moveTo(p[0], p[1]) : ctx.lineTo(p[0], p[1]);
    }
    ctx.closePath();
    ctx.strokeStyle = 'rgba(217, 231, 239, 0.2)';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Axes
    const base = [45, h - 45];
    [['x', [1, 0, 0], '#ff8a80'], ['y', [0, 1, 0], '#8ee5a4'], ['z', [0, 0, 1], '#8acaff']].forEach(([name, v, col]) => {
        const r = [
            v[0] * Math.cos(yaw) - v[1] * Math.sin(yaw),
            v[0] * Math.sin(yaw) + v[1] * Math.cos(yaw)
        ];
        const y3d = -(r[1] * Math.cos(pitch) - v[2] * Math.sin(pitch));
        ctx.strokeStyle = col;
        ctx.fillStyle = col;
        ctx.beginPath();
        ctx.moveTo(...base);
        ctx.lineTo(base[0] + r[0] * 30, base[1] + r[1] * 30);
        ctx.stroke();
        ctx.font = '13px system-ui';
        ctx.fillText(name, base[0] + r[0] * 39, base[1] + r[1] * 39);
    });

    $('legendMin').textContent = '0';
    $('legendMax').textContent = (maxDisp * 1000).toPrecision(4);
    $('legendUnits').textContent = `mm actual · geometry ${defScaleFactor}×`;
}

// Compute tip histories for all cases
function computeTipHistories() {
    const histories = [];
    for (let i = 0; i < cases.length; i++) {
        const c = cases[i];
        const modelTag = c.model;
        const reference_q = c.reference_q;
        const history = [];
        for (const f of c.frames) {
            const t = f[0];
            const q = f.slice(1);
            const qEffective = displayMode === 'perturbation'
                ? q.map((v, j) => v - reference_q[j])
                : q;
            const metrics = computeTipMetrics(qEffective, modelTag, i);
            history.push({ t, z: metrics.meanTipZ, twist: metrics.twist });
        }
        histories.push(history);
    }
    return histories;
}

function drawHistory() {
    const canvas = $('history');
    const [ctx, w, h] = dimensions(canvas);
    ctx.clearRect(0, 0, w, h);

    const histories = computeTipHistories();
    const c = cases[modelIndex];

    // Find global min/max for z and twist
    let minZ = Infinity, maxZ = -Infinity;
    let minTwist = Infinity, maxTwist = -Infinity;
    for (const hist of histories) {
        for (const pt of hist) {
            minZ = Math.min(minZ, pt.z);
            maxZ = Math.max(maxZ, pt.z);
            minTwist = Math.min(minTwist, pt.twist);
            maxTwist = Math.max(maxTwist, pt.twist);
        }
    }
    const padZ = Math.max((maxZ - minZ) * 0.1, 1e-9);
    const padTwist = Math.max((maxTwist - minTwist) * 0.1, 1e-9);
    const loZ = minZ - padZ, hiZ = maxZ + padZ;
    const loTwist = minTwist - padTwist, hiTwist = maxTwist + padTwist;

    // Time range
    let t0 = Infinity, t1 = -Infinity;
    for (const hist of histories) {
        if (hist.length > 0) {
            t0 = Math.min(t0, hist[0].t);
            t1 = Math.max(t1, hist.at(-1).t);
        }
    }
    const left = 65, right = w - 20, top = 25, bottom = h - 42;
    const x = t => left + (t - t0) / (t1 - t0) * (right - left);
    const yZ = v => bottom - (v - loZ) / (hiZ - loZ) * (bottom - top);
    const yTwist = v => bottom - (v - loTwist) / (hiTwist - loTwist) * (bottom - top);

    // Draw axes
    ctx.strokeStyle = '#496078';
    ctx.beginPath();
    ctx.moveTo(left, top);
    ctx.lineTo(left, bottom);
    ctx.lineTo(right, bottom);
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#bacbdb';
    ctx.font = '12px system-ui';
    ctx.fillText('Mean tip z (mm)', left, 16);
    ctx.fillText(hiZ.toPrecision(3), 2, top + 5);
    ctx.fillText(loZ.toPrecision(3), 2, bottom);
    ctx.fillText('Tip twist (deg)', left, bottom - (bottom - top) / 2);
    ctx.fillText(t0.toPrecision(3), left, bottom + 18);
    ctx.fillText(t1.toPrecision(3), right - 45, bottom + 18);
    ctx.fillText('Physical time (s)', left + 8, h - 4);

    // Draw traces for all cases
    const colors = ['#55d9e9', '#7bdcbe', '#e8b4b8', '#f0b44d'];
    for (let i = 0; i < histories.length; i++) {
        const hist = histories[i];
        const c = cases[i];
        const label = c.name;

        ctx.strokeStyle = colors[i % colors.length];
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let j = 0; j < hist.length; j++) {
            const pt = hist[j];
            if (j === 0) ctx.moveTo(x(pt.t), yZ(pt.z));
            else ctx.lineTo(x(pt.t), yZ(pt.z));
        }
        ctx.stroke();

        // Current point marker
        const tCurrent = modelTime;
        let currentZ = 0;
        if (hist.length > 0) {
            if (tCurrent <= hist[0].t) currentZ = hist[0].z;
            else if (tCurrent >= hist.at(-1).t) currentZ = hist.at(-1).z;
            else {
                for (let j = 0; j < hist.length - 1; j++) {
                    if (hist[j].t <= tCurrent && hist[j + 1].t >= tCurrent) {
                        const s = (tCurrent - hist[j].t) / (hist[j + 1].t - hist[j].t);
                        currentZ = hist[j].z + (hist[j + 1].z - hist[j].z) * s;
                        break;
                    }
                }
            }
        }

        ctx.fillStyle = colors[i % colors.length];
        ctx.beginPath();
        ctx.arc(x(tCurrent), yZ(currentZ), 4, 0, 2 * Math.PI);
        ctx.fill();

        // Legend
        ctx.fillStyle = colors[i % colors.length];
        ctx.font = '11px system-ui';
        ctx.fillText(`${label} (z)`, right + 15, top + 12 + i * 15);
    }

    // Draw current time marker
    ctx.strokeStyle = '#fff';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x(tCurrent), top);
    ctx.lineTo(x(tCurrent), bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    // Time display
    const currentMetrics = computeTipMetrics(
        interpolateQ(c.frames, tCurrent),
        c.model,
        modelIndex
    );
    $('time').textContent = `${tCurrent.toFixed(5)} s · mean tip z ${(currentMetrics.meanTipZ * 1000).toPrecision(5)} mm · twist ${(currentMetrics.twist).toPrecision(5)}°`;
}

let modelTime = 0;
const rateSelect = $('rate');
rateSelect.value = '0.1';

// Populate model selector
const modelSelect = $('modelSelect');
const caseMap = {}; // modelTag -> [caseIndices]
for (let i = 0; i < cases.length; i++) {
    const tag = cases[i].model;
    if (!caseMap[tag]) caseMap[tag] = [];
    caseMap[tag].push(i);
}
const modelTags = Object.keys(models);
modelTags.forEach((tag, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    const nCases = caseMap[tag] ? caseMap[tag].length : 0;
    opt.textContent = `${tag} (${nCases} case${nCases !== 1 ? 's' : ''})`;
    modelSelect.appendChild(opt);
});
modelSelect.value = 0;

// Update case info
function updateCaseInfo() {
    const c = cases[modelIndex];
    const tag = c.model;
    const model = models[tag];
    $('caseInfo').textContent = `${c.name} · ${tag} skin (${model.thickness_m * 1000} mm) · ${model.mass_kg} kg half-wing`;
    $('modelInfo').textContent = `${model.modes.length} modes · ${nNodes} nodes`;
}

updateCaseInfo();

// Initial state
const currentCases = caseMap[modelTags[modelIndex]] || [];
if (currentCases.length > 0) {
    modelTime = cases[currentCases[0]].frames[0][0];
}
$('defScale').value = 10;

// Metadata
document.getElementById('title').textContent = data.title;
$('meta').textContent = 'Recorded equilibrium comparison from native shell modes coupled to UVLM aerodynamics.';
$('provenance').textContent = data.source + ' · ' + data.scope;
$('scope').textContent = `${cases.length} cases across ${Object.keys(models).length} models; ${nNodes} nodes.`;

for (const text of (data.scope ? [data.scope] : [])) {
    const li = document.createElement('li');
    li.textContent = text;
    $('limitations').appendChild(li);
}

// Controls
function draw() {
    const modelTag = modelTags[modelIndex];
    const caseIndices = caseMap[modelTag] || [];

    // Update range based on first case for this model
    if (caseIndices.length > 0) {
        const c = cases[caseIndices[0]];
        $('scrub').min = c.frames[0][0];
        $('scrub').max = c.frames.at(-1)[0];
        $('scrub').value = modelTime;
        updateCaseInfo();
    }

    drawScene('canvas1', caseIndices[0] || 0);
    drawScene('canvas2', caseIndices[1] || 0);
    drawHistory();
}

function pause() {
    if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
    }
    playing = false;
    $('play').textContent = 'Play';
}

function tick(now) {
    if (!playing) return;
    const dt = (now - lastTime) / 1000;
    const rate = Number($('rate').value);
    modelTime += dt * rate;

    const modelTag = modelTags[modelIndex];
    const caseIndices = caseMap[modelTag] || [];
    if (caseIndices.length > 0) {
        const c = cases[caseIndices[0]];
        const tEnd = c.frames.at(-1)[0];
        if (modelTime >= tEnd) {
            modelTime = tEnd;
            draw();
            if (!$('replay').checked) {
                pause();
                return;
            }
            modelTime = c.frames[0][0];
            lastTime = now;
        }
    }
    lastTime = now;
    raf = requestAnimationFrame(tick);
    draw();
}

$('play').onclick = () => {
    if (playing) {
        pause();
        return;
    }
    playing = true;
    lastTime = performance.now();
    $('play').textContent = 'Pause';
    raf = requestAnimationFrame(tick);
    draw();
};

$('restart').onclick = () => {
    pause();
    const modelTag = modelTags[modelIndex];
    const caseIndices = caseMap[modelTag] || [];
    if (caseIndices.length > 0) {
        modelTime = cases[caseIndices[0]].frames[0][0];
    }
    draw();
};

$('defScale').onchange = draw;
$('scrub').oninput = () => {
    pause();
    modelTime = Number($('scrub').value);
    draw();
};

// Model change
modelSelect.onchange = () => {
    pause();
    modelIndex = Number(modelSelect.value);
    const modelTag = modelTags[modelIndex];
    const caseIndices = caseMap[modelTag] || [];
    if (caseIndices.length > 0) {
        modelTime = cases[caseIndices[0]].frames[0][0];
    }
    draw();
};

// Display mode change
$('displayMode').onchange = () => {
    displayMode = $('displayMode').value;
    draw();
};

// Replay checkbox
const replayLabel = document.createElement('label');
replayLabel.textContent = ' Replay';
replayLabel.style.marginLeft = '12px';
const replayInput = document.createElement('input');
replayInput.type = 'checkbox';
replayInput.id = 'replay';
replayLabel.insertBefore(replayInput, replayLabel.firstChild);
const controlsDiv = document.querySelector('.controls');
if (controlsDiv) {
    controlsDiv.appendChild(replayLabel);
}

// Rate change
$('rate').onchange = () => {
    if (playing) lastTime = performance.now();
    draw();
};

// Expose debug state
window.comparisonDebug = {
    time: 0,
    caseNames: [],
    interpolatedQ: [],
    tipZ: 0,
    tipTwist: 0,
    displayMode: 'total'
};

// Initial draw
draw();

// Update debug state on draw
const originalDraw = draw;
draw = function() {
    originalDraw();
    const modelTag = modelTags[modelIndex];
    const caseIndices = caseMap[modelTag] || [];
    const c = caseIndices.length > 0 ? cases[caseIndices[0]] : cases[0];
    const q = interpolateQ(c.frames, modelTime);
    const metrics = computeTipMetrics(q, c.model, caseIndices[0] || 0);

    window.comparisonDebug = {
        time: modelTime,
        caseNames: caseIndices.map(i => cases[i].name),
        interpolatedQ: q,
        tipZ: metrics.meanTipZ,
        tipTwist: metrics.twist,
        displayMode: displayMode,
        modelIndex: modelIndex,
        modelName: modelTag
    };
};

// Mouse interactions
const canvas1 = $('canvas1');
canvas1.onpointerdown = e => {
    drag = { x: e.clientX, y: e.clientY };
    canvas1.setPointerCapture(e.pointerId);
};
canvas1.onpointermove = e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (e.shiftKey) {
        pan[0] += dx;
        pan[1] += dy;
    } else {
        yaw += dx * 0.008;
        pitch += dy * 0.008;
    }
    drag = { x: e.clientX, y: e.clientY };
    draw();
};
canvas1.onpointerup = canvas1.onpointercancel = () => { drag = null; };
canvas1.addEventListener('wheel', e => {
    e.preventDefault();
    zoom = Math.max(0.2, Math.min(15, zoom * Math.exp(-e.deltaY * 0.001)));
    draw();
}, { passive: false });

window.addEventListener('resize', draw);
})();
