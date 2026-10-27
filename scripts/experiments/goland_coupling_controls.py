"""Compare predictor conventions using one saved, unconverted UVLM system.

Run inside the pinned SHARPy image. Inputs are the projected-aero.npz produced
with REMOVE_PREDICTOR=0 by goland_modal_uvlm.py. Reduction is diagnostic only.
"""

from pathlib import Path
import json, os
import numpy as np
from scipy import linalg, signal
from sharpy.linear.src import libss, lingebm
from sharpy.rom.krylov import Krylov
from sharpy.linear.utils.ss_interface import (
    LinearVector,
    StateVariable,
    InputVariable,
    OutputVariable,
)
from sharpy.utils import cout_utils

base = Path("/results")
out = base / os.environ.get("OUTPUT_CASE", "coupling-controls-v2")
out.mkdir(exist_ok=False)
cout_utils.start_writer()
cout_utils.cout_wrap.initialise(False, True, str(out), "reduction.log")
input_case = os.environ.get("MATRIX_CASE", "raw-newmark-M16-N16-W10")
d = np.load(base / input_case / "projected-aero.npz")
A = d["A"]
B = np.hstack([d["Bq"], d["Bv"]])
C = d["Cq"]
D = np.hstack([d["Dq"], d["Dv"]])
dt = float(d["dt_reference"])
omega = d["omega"]
n = len(omega)
K = np.diag(omega**2)
ss = libss.StateSpace(A, B, C, D, dt=dt)
ss.state_variables = LinearVector([StateVariable("aero", size=A.shape[0], index=0)])
ss.input_variables = LinearVector([InputVariable("modal_motion", size=2 * n, index=0)])
ss.output_variables = LinearVector([OutputVariable("modal_force", size=n, index=0)])
rom = Krylov()
rom.initialise(
    {
        "algorithm": "mimo_rational_arnoldi",
        "r": 6,
        "single_side": "observability",
        "frequency": [0.0],
        "print_info": False,
    }
)
r = rom.run(ss) if os.environ.get("REDUCE_INPUT", "1") == "1" else ss
Ar, Br, Cr, Dr = r.get_mats()
report = {
    "scope": "Numerical convention diagnostic, not shell flutter",
    "input_case": input_case,
    "reduction_performed": os.environ.get("REDUCE_INPUT", "1") == "1",
    "rom_order": Ar.shape[0],
    "rom_spectral_radius": float(max(abs(linalg.eigvals(Ar)))),
    "cases": [],
}
assert report["rom_spectral_radius"] < 1
# Check reduced transfer against the unreduced predictor-form system near the
# benchmark oscillation; this tests the ROM, not the predictor convention.
errors = []
for w in [0.0, 50.0, 70.0, 100.0] if os.environ.get("REDUCE_INPUT", "1") == "1" else []:
    z = np.exp(1j * w * dt / 166.5)
    full = C @ linalg.solve(z * np.eye(A.shape[0]) - A, B) + D
    reduced = Cr @ linalg.solve(z * np.eye(Ar.shape[0]) - Ar, Br) + Dr
    errors.append(
        {
            "frequency_rad_s": w,
            "relative_frobenius_error": float(
                linalg.norm(full - reduced) / linalg.norm(full)
            ),
        }
    )
report["transfer_checks"] = errors
for predictor in [False, True]:
    if predictor:
        aa, bb, cc, dd = libss.SSconv(Ar, None, Br, Cr, Dr)
    else:
        aa, bb, cc, dd = Ar, Br, Cr, Dr
    for method in ["bilinear", "newmark_zero", "newmark_reference"]:
        rows = []
        for V in np.arange(145.0, 175.01, 0.5):
            step = dt / V
            if method == "bilinear":
                ast = np.block([[np.zeros((n, n)), np.eye(n)], [-K, np.zeros((n, n))]])
                bst = np.vstack([np.zeros((n, n)), np.eye(n)])
                ads, bds, cds, dds, _ = signal.cont2discrete(
                    (ast, bst, np.eye(2 * n), np.zeros((2 * n, n))),
                    step,
                    method="bilinear",
                )
            else:
                ads, bds, cds, dds = lingebm.newmark_ss(
                    np.eye(n),
                    np.zeros((n, n)),
                    K,
                    step,
                    num_damp=0 if method == "newmark_zero" else 5e-5,
                )
            air = libss.StateSpace(
                aa,
                bb @ np.diag([1.0] * n + [1.0 / V] * n),
                V**2 * cc,
                V**2 * dd @ np.diag([1.0] * n + [1.0 / V] * n),
                dt=step,
            )
            structure = libss.StateSpace(ads, bds, cds, dds, dt=step)
            coupled = libss.couple(air, structure, np.eye(2 * n), np.eye(n))
            ev = linalg.eigvals(coupled.A)
            ev = ev[abs(ev) > 1e-10]
            lam = np.log(ev.astype(complex)) / step
            oscillatory = lam[lam.imag > 1e-5]
            dom = oscillatory[np.argmax(oscillatory.real)]
            rows.append([float(V), float(dom.real), float(dom.imag / (2 * np.pi))])
        brackets = [
            [rows[i - 1][0], rows[i][0]]
            for i in range(1, len(rows))
            if rows[i - 1][1] < 0 <= rows[i][1]
        ]
        case = {
            "predictor_removed": predictor,
            "structural_method": method,
            "crossing_brackets_m_s": brackets,
            "rows": rows,
        }
        report["cases"].append(case)
        print(predictor, method, brackets, flush=True)
# Independent descriptor equation keeps the original u[n+1] predictor.
# Its eigenvalues must match the causally converted feedback system.
V = 166.5
step = dt / V
ads, bds, cds, dds = lingebm.newmark_ss(
    np.eye(n), np.zeros((n, n)), K, step, num_damp=0
)
bs = Br @ np.diag([1.0] * n + [1.0 / V] * n)
cs = V**2 * Cr
ds = V**2 * Dr @ np.diag([1.0] * n + [1.0 / V] * n)
yx = linalg.solve(np.eye(n) - ds @ dds, cs)
ys = linalg.solve(np.eye(n) - ds @ dds, ds @ cds)
ux = dds @ yx
us = cds + dds @ ys
na = Ar.shape[0]
E = np.block([[np.eye(na) - bs @ ux, -bs @ us], [np.zeros((2 * n, na)), np.eye(2 * n)]])
F = np.block([[Ar, np.zeros((na, 2 * n))], [bds @ yx, ads + bds @ ys]])
descriptor = linalg.eigvals(F, E)
aa, bb, cc, dd = libss.SSconv(Ar, None, bs, cs, ds)
causal = libss.couple(
    libss.StateSpace(aa, bb, cc, dd, dt=step),
    libss.StateSpace(ads, bds, cds, dds, dt=step),
    np.eye(2 * n),
    np.eye(n),
)
causal_eigs = linalg.eigvals(causal.A)
from scipy.optimize import linear_sum_assignment

cost = abs(descriptor[:, None] - causal_eigs[None, :])
ii, jj = linear_sum_assignment(cost)
report["predictor_descriptor_eigenvalue_max_error"] = float(max(cost[ii, jj]))
assert report["predictor_descriptor_eigenvalue_max_error"] < 1e-9
# For average-acceleration Newmark, recover the exact continuous oscillator
# frequencies using the inverse bilinear map, not log(z)/dt.
ez = linalg.eigvals(ads)
recovered = 2 / step * (ez - 1) / (ez + 1)
positive = np.sort(recovered.imag[recovered.imag > 0])
report["zero_load_frequency_relative_error"] = float(
    max(abs(positive - np.sort(omega)) / np.sort(omega))
)
assert report["zero_load_frequency_relative_error"] < 1e-10
report["zero_load_max_growth"] = float(max(abs(recovered.real)))
(out / "assessment.json").write_text(json.dumps(report, indent=2) + "\n")
cout_utils.finish_writer()
