"""Bounded Goland modal/UVLM diagnostic; requires the pinned SHARPy runtime.

This is an evidence experiment, not a qualified shell flutter solver. See
 docs/DIRECT_UVLM_VERIFICATION.md for inputs, provenance and interpretation.
REMOVE_PREDICTOR=0 deliberately reproduces the upstream benchmark convention;
it is not a recommendation to treat predictor-form matrices as causal.
"""

from pathlib import Path
import os, json, time, traceback
import numpy as np
from scipy import linalg, signal
from sharpy.utils.datastructures import AeroTimeStepInfo
from sharpy.aero.utils import uvlmlib
from sharpy.solvers.staticuvlm import StaticUvlm
from sharpy.linear.src import linuvlm, libss, lingebm
from sharpy.utils import cout_utils

base = Path(os.environ.get("RESULTS_DIR", "/results"))
tag = os.environ.get("CASE_TAG", "controlled")
predictor = os.environ.get("REMOVE_PREDICTOR", "1") == "1"
method = os.environ.get("STRUCTURAL_METHOD", "newmark")
M = int(os.environ.get("PANELS_M", 4))
N = int(os.environ.get("PANELS_N", 8))
wake = int(os.environ.get("WAKE_FACTOR", 8))
nm = 2
shift = float(os.environ.get("PANEL_SHIFT", "0.25"))
use_rom = os.environ.get("USE_ROM", "1") == "1"
out = base / f"{tag}-M{M}-N{N}-W{wake}"
out.mkdir(exist_ok=False)
cout_utils.start_writer()
cout_utils.cout_wrap.initialise(False, True, str(out), "assembly.log")
assert method in ("newmark", "bilinear")
assert M > 0 and N > 0 and wake > 0
start = time.monotonic()
report = {
    "scope": "Direct physical mode/UVLM Goland benchmark, symmetric paired semispans; no shell flutter result",
    "M": M,
    "semispan_panels": N,
    "wake_factor": wake,
    "modes_per_half": nm,
    "panel_shift_fraction": shift,
    "use_rom": use_rom,
    "remove_predictor": predictor,
    "structural_method": method,
    "newmark_algorithmic_damping": 5e-5 if method == "newmark" else None,
}
try:
    d = np.load(base / "goland-native.npz")
    freq = np.sqrt(d["EIGEN_VA"].ravel()[:nm])
    P = d["EIGEN_VE"][:, :nm].reshape(17, 6, nm)
    R = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    L = 6.096
    c = 1.8288
    rho = 1.02
    dt = c / M
    zeta = np.zeros((3, M + 1, 2 * N + 1))
    H = np.zeros((3, M + 1, 2 * N + 1, nm))
    for i in range(M + 1):
        x = c * ((i + shift) / M - 0.33)
        for j, y in enumerate(np.linspace(-L, L, 2 * N + 1)):
            zeta[:, i, j] = [x, y, 0.0]
            station = abs(y) / L * 16
            k = min(int(station), 15)
            t = station - k
            mode = (1 - t) * P[k] + t * P[k + 1]
            trans = R @ mode[:3]
            rot = R @ mode[3:]
            u = trans + np.cross(rot.T, np.array([x, 0.0, 0.0])).T
            if y < 0:
                u[1] *= -1
            H[:, i, j] = u / np.sqrt(
                2
            )  # two mirrored half-mass-normalized modes => full modal mass1
    h = H.reshape(-1, nm)
    rng = np.random.default_rng(36)
    q = rng.normal(size=nm)
    f = rng.normal(size=h.shape[0])
    work_error = float(abs((h @ q) @ f - q @ (h.T @ f)))
    report["virtual_work_absolute_error"] = work_error
    assert work_error < 1e-10
    report["native_frequencies_hz"] = (freq / (2 * np.pi)).tolist()
    report["root_motion_max"] = float(np.max(abs(H[:, :, N, :])))
    assert report["root_motion_max"] < 1e-12
    ts = AeroTimeStepInfo(
        np.array([[M, 2 * N]], dtype=int), np.array([[M * wake, 2 * N]], dtype=int)
    )
    ts.rho = rho
    ts.zeta[0][:] = zeta
    ts.u_ext[0][0] = 1.0
    ts.u_ext_star[0][0] = 1.0
    for i in range(M * wake + 1):
        ts.zeta_star[0][:, i, :] = (
            zeta[:, -1, :] + np.array([dt * i, 0.0, 0.0])[:, None]
        )
    opts = dict(StaticUvlm.settings_default)
    opts.update(
        rho=rho,
        rollup_dt=dt,
        num_cores=2,
        n_rollup=0,
        rbm_vel_g=np.zeros(6),
        centre_rot_g=np.zeros(3),
    )
    uvlmlib.vlm_solver(ts, opts)
    assert np.max(abs(ts.forces[0])) < 1e-9
    aero = linuvlm.Dynamic(
        ts,
        dynamic_settings={
            "dt": dt,
            "integr_order": 2,
            "density": rho,
            "remove_predictor": predictor,
            "use_sparse": False,
        },
    )
    aero.assemble_ss()
    ss = aero.SS
    A, B, C, D = ss.get_mats()
    nv = h.shape[0]
    assert B.shape[1] == 3 * nv and C.shape[0] == nv
    # Base speed1m/s. x_a scaled circulation gamma/U; atV inputsdotzeta/V and outputforceV^2.
    Bq = B[:, :nv] @ h
    Bv = B[:, nv : 2 * nv] @ h
    Cq = h.T @ C
    Dq = h.T @ D[:, :nv] @ h
    Dv = h.T @ D[:, nv : 2 * nv] @ h
    if use_rom:
        from sharpy.rom.krylov import Krylov
        from sharpy.linear.utils.ss_interface import (
            LinearVector,
            StateVariable,
            InputVariable,
            OutputVariable,
        )

        projected = libss.StateSpace(
            A, np.hstack([Bq, Bv]), Cq, np.hstack([Dq, Dv]), dt=dt
        )
        projected.state_variables = LinearVector(
            [StateVariable("aero", size=A.shape[0], index=0)]
        )
        projected.input_variables = LinearVector(
            [InputVariable("modal_motion", size=2 * nm, index=0)]
        )
        projected.output_variables = LinearVector(
            [OutputVariable("modal_force", size=nm, index=0)]
        )
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
        reduced = rom.run(projected)
        A, Br, Cq, Dr = reduced.get_mats()
        Bq = Br[:, :nm]
        Bv = Br[:, nm:]
        Dq = Dr[:, :nm]
        Dv = Dr[:, nm:]
        report["reduced_states"] = A.shape[0]
    radius = float(max(abs(linalg.eigvals(A))))
    report["aerodynamic_spectral_radius"] = radius
    assert radius < 1.000001
    np.savez(
        out / "projected-aero.npz",
        A=A,
        Bq=Bq,
        Bv=Bv,
        Cq=Cq,
        Dq=Dq,
        Dv=Dv,
        omega=freq,
        dt_reference=dt,
    )
    K = np.diag(freq**2)
    As = np.block([[np.zeros((nm, nm)), np.eye(nm)], [-K, np.zeros((nm, nm))]])
    Bs = np.vstack([np.zeros((nm, nm)), np.eye(nm)])
    Cs = np.eye(2 * nm)
    Ds = np.zeros((2 * nm, nm))
    rows = []
    for V in [
        float(v)
        for v in os.environ.get(
            "SPEEDS", "100,110,120,130,140,150,160,170,180,190,200,210,220"
        ).split(",")
    ]:
        step = dt / V
        ad, bd, cd, dd, _ = signal.cont2discrete(
            (As, Bs, Cs, Ds), step, method="bilinear"
        )

        if method == "newmark":
            ad, bd, cd, dd = lingebm.newmark_ss(
                np.eye(nm), np.zeros((nm, nm)), K, step, num_damp=5e-5
            )
        astr = libss.StateSpace(ad, bd, cd, dd, dt=step)
        aair = libss.StateSpace(
            A,
            np.hstack([Bq, Bv / V]),
            V * V * Cq,
            np.hstack([V * V * Dq, V * Dv]),
            dt=step,
        )
        coupled = libss.couple(aair, astr, np.eye(2 * nm), np.eye(nm))
        ev = linalg.eigvals(coupled.A)
        ev = ev[abs(ev) > 1e-10]
        lam = np.log(ev.astype(complex)) / step
        positive = lam[lam.imag > 1e-5]
        dominant = positive[np.argmax(positive.real)]
        rows.append(
            [float(V), float(dominant.real), float(dominant.imag / (2 * np.pi))]
        )
        print(rows[-1], flush=True)
    report["sweep_speed_growth_frequency"] = rows
    cross = [i for i in range(1, len(rows)) if rows[i - 1][1] < 0 <= rows[i][1]]
    report["crossing_brackets_m_s"] = [[rows[i - 1][0], rows[i][0]] for i in cross]
    report["status"] = "executed_not_yet_mesh_verified"
    np.savez(
        out / "projected-aero.npz",
        A=A,
        Bq=Bq,
        Bv=Bv,
        Cq=Cq,
        Dq=Dq,
        Dv=Dv,
        omega=freq,
        dt_reference=dt,
    )
except Exception as e:
    report.update(status="failed", error=repr(e), traceback=traceback.format_exc())
    raise
finally:
    report["elapsed_seconds"] = time.monotonic() - start
    (out / "assessment.json").write_text(json.dumps(report, indent=2) + "\n")
    cout_utils.finish_writer()
