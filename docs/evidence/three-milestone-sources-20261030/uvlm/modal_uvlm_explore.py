"""Exploratory native-mode UVLM pipeline, using the pinned SHARPy runtime.

An untrimmed cambered shell is deliberately allowed. Reports distinguish its
reference imbalance from perturbation dynamics. No physical flutter claim.
"""

from pathlib import Path
import hashlib
import json
import os
import time
import traceback
import numpy as np
from scipy import linalg, signal, sparse
from scipy.sparse.linalg import splu
from sharpy.utils.datastructures import AeroTimeStepInfo
from sharpy.aero.utils import uvlmlib
from sharpy.solvers.staticuvlm import StaticUvlm
from sharpy.linear.src import linuvlm, libss, lingebm
from sharpy.linear.utils.ss_interface import (
    LinearVector,
    StateVariable,
    InputVariable,
    OutputVariable,
)
from sharpy.rom.krylov import Krylov
from sharpy.utils import cout_utils


def geometry(base, model, M, N, nm):
    if model == "shell":
        source = base / f"camber-M{M}-N{N}.npz"
        d = np.load(source)
        coords = d["coords"].reshape(M + 1, N + 1, 3).copy()
        modes = d["H"][:nm].reshape(nm, M + 1, N + 1, 3).transpose(1, 2, 3, 0).copy()
        assert np.allclose(d["generalized_mass"][:nm], 1)
        omega = 2 * np.pi * d["frequencies_Hz"][:nm]
        # Differentiate SHARPy's uniform lattice quarter-panel shift itself.
        # This retains local camber motion; no rigid-section beam fit.
        coords += 0.25 * (coords[-1] - coords[0])[None, :, :] / M
        modes += 0.25 * (modes[-1] - modes[0])[None, :, :, :] / M
        chord = 0.1016
    else:
        source = base / "goland-native.npz"
        d = np.load(source)
        omega = np.sqrt(d["EIGEN_VA"].ravel()[:nm])
        p = d["EIGEN_VE"][:, :nm].reshape(17, 6, nm)
        R = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        chord = 1.8288
        coords = np.zeros((M + 1, N + 1, 3))
        modes = np.zeros((M + 1, N + 1, 3, nm))
        for i in range(M + 1):
            x = chord * ((i + 0.25) / M - 0.33)
            for j, y in enumerate(np.linspace(0, 6.096, N + 1)):
                s = y / 6.096 * 16
                k = min(int(s), 15)
                t = s - k
                pm = (1 - t) * p[k] + t * p[k + 1]
                coords[i, j] = [x, y, 0]
                modes[i, j] = R @ pm[:3] + np.cross((R @ pm[3:]).T, [x, 0, 0]).T
    left = coords[:, 1:][:, ::-1].copy()
    left[:, :, 1] *= -1
    lmode = modes[:, 1:][:, ::-1].copy()
    lmode[:, :, 1, :] *= -1
    zeta = np.concatenate([left, coords], axis=1).transpose(2, 0, 1)
    H = np.concatenate([lmode, modes], axis=1).transpose(2, 0, 1, 3) / np.sqrt(2)
    return zeta, H, omega, chord, source


def state_space(A, B, C, D, dt):
    ss = libss.StateSpace(A, B, C, D, dt=dt)
    ss.state_variables = LinearVector([StateVariable("aero", size=A.shape[0], index=0)])
    ss.input_variables = LinearVector(
        [InputVariable("motion", size=B.shape[1], index=0)]
    )
    ss.output_variables = LinearVector(
        [OutputVariable("force", size=C.shape[0], index=0)]
    )
    return ss


def structural(omega, step, damping=0.0):
    n = len(omega)
    return lingebm.newmark_ss(
        np.eye(n), np.diag(2 * damping * omega), np.diag(omega**2), step, num_damp=0
    )


def coupled_system(A, B, C, D, omega, dt, V, causal=True, damping=0.0):
    n = len(omega)
    step = dt / V
    bs = B @ np.diag([1.0] * n + [1.0 / V] * n)
    cs = V**2 * C
    ds = V**2 * D @ np.diag([1.0] * n + [1.0 / V] * n)
    if causal:
        aa, bb, cc, dd = libss.SSconv(A, None, bs, cs, ds)
    else:
        aa, bb, cc, dd = A, bs, cs, ds
    st = structural(omega, step, damping)
    cp = libss.couple(
        libss.StateSpace(aa, bb, cc, dd, dt=step),
        libss.StateSpace(*st, dt=step),
        np.eye(2 * n),
        np.eye(n),
    )
    return cp, (bs, cs, ds), st


def sweep(A, B, C, D, omega, dt, speeds, causal, damping):
    n = len(omega)
    rows = []
    previous = None
    for V in speeds:
        cp, _, _ = coupled_system(A, B, C, D, omega, dt, V, causal, damping)
        ev, vec = linalg.eig(cp.A)
        keep = abs(ev) > 1e-10
        ev = ev[keep]
        vec = vec[:, keep]
        lam = np.log(ev.astype(complex)) / (dt / V)
        candidates = np.flatnonzero((lam.imag > 1e-5) & (np.angle(ev) < 0.95 * np.pi))
        assert len(candidates)
        dom = candidates[np.argmax(lam[candidates].real)]
        # Character measured in physical q and v/omega rather than ROM coordinates.
        physical = cp.C[n:] @ vec
        shapes = np.vstack([physical[:n], physical[n:] / omega[:, None]])
        norms = linalg.norm(shapes, axis=0)
        norms[norms == 0] = 1
        shapes = shapes / norms
        if previous is None:
            tracked = dom
            mac = 1.0
        else:
            macs = abs(previous.conj() @ shapes[:, candidates]) ** 2
            tracked = candidates[np.argmax(macs)]
            mac = float(max(macs))
        previous = shapes[:, tracked]
        real = lam[abs(lam.imag) < 1e-5]
        rows.append(
            {
                "speed_m_s": float(V),
                "dominant_growth_per_s": float(lam[dom].real),
                "dominant_frequency_hz": float(lam[dom].imag / (2 * np.pi)),
                "tracked_growth_per_s": float(lam[tracked].real),
                "tracked_frequency_hz": float(lam[tracked].imag / (2 * np.pi)),
                "tracked_adjacent_mac": mac,
                "largest_nonoscillatory_growth_per_s": float(max(real.real))
                if len(real)
                else None,
            }
        )
    brackets = [
        [a["speed_m_s"], b["speed_m_s"]]
        for a, b in zip(rows, rows[1:])
        if a["dominant_growth_per_s"] < 0 <= b["dominant_growth_per_s"]
    ]
    return {
        "causal": causal,
        "assumed_modal_damping_ratio": damping,
        "rows": rows,
        "oscillatory_crossing_brackets_m_s": brackets,
    }


def transient(A, B, C, D, omega, dt, V, H, seconds, static_force=None):
    n = len(omega)
    step = dt / V
    cp, (bs, cs, ds), (ad, bd, cd, dd) = coupled_system(A, B, C, D, omega, dt, V)
    na = A.shape[0]
    yx = linalg.solve(np.eye(n) - ds @ dd, cs)
    ys = linalg.solve(np.eye(n) - ds @ dd, ds @ cd)
    ux = dd @ yx
    us = cd + dd @ ys
    E = np.block(
        [[np.eye(na) - bs @ ux, -bs @ us], [np.zeros((2 * n, na)), np.eye(2 * n)]]
    )
    F = np.block([[A, np.zeros((na, 2 * n))], [bd @ yx, ad + bd @ ys]])
    # Original predictor states: zero circulation, small structural displacement.
    original = np.zeros(na + 2 * n)
    original[na] = 1e-5
    transformed = original.copy()
    transformed[:na] -= bs @ (ux @ original[:na] + us @ original[na:])
    lu = linalg.lu_factor(E)
    frames = []
    max_error = 0.0
    peak_motion = 0.0
    stopped = False
    force = np.zeros(n) if static_force is None else static_force
    # Constant physical baseline force is supplied at the structural input.
    input_vector = np.r_[np.zeros(2 * n), force]
    count = int(np.ceil(seconds / step))
    stride = max(1, count // 800)
    for k in range(count + 1):
        y = cp.C @ transformed + cp.D @ input_vector
        q = y[n : 2 * n]
        motion = (H.reshape(-1, n) @ q).reshape(H.shape[:-1])
        peak_motion = max(peak_motion, float(np.max(abs(motion))))
        if k % stride == 0:
            frames.append([k * step, *q.tolist()])
        if not np.all(np.isfinite(q)) or peak_motion > 0.02:
            stopped = True
            break
        if static_force is None:
            yoriginal = yx @ original[:na] + ys @ original[na:]
            uoriginal = cd @ original[na:] + dd @ yoriginal
            max_error = max(max_error, float(np.max(abs(uoriginal - y[n:]))))
            original = linalg.lu_solve(lu, F @ original)
        transformed = cp.A @ transformed + cp.B @ input_vector
    frames = np.array(frames)
    peaks, _ = signal.find_peaks(frames[:, 1])
    peaks = peaks[(frames[peaks, 0] > 0.4 * frames[-1, 0]) & (frames[peaks, 1] > 0)]
    fit = None
    if len(peaks) >= 4:
        fit = {
            "growth_per_s": float(
                np.polyfit(frames[peaks, 0], np.log(frames[peaks, 1]), 1)[0]
            ),
            "frequency_hz": float(1 / np.mean(np.diff(frames[peaks, 0]))),
            "positive_peaks": len(peaks),
        }
    return {
        "speed_m_s": V,
        "requested_seconds": seconds,
        "recorded_seconds": float(frames[-1, 0]),
        "stopped_at_20mm_motion_guard": stopped,
        "peak_vertex_component_m": peak_motion,
        "descriptor_causal_response_max_error": max_error
        if static_force is None
        else None,
        "late_positive_peak_fit": fit,
        "baseline_force_applied": static_force is not None,
        "frames_time_and_q": frames.tolist(),
    }


def main():
    base = Path(os.environ.get("RESULTS_DIR", "/results"))
    model = os.environ.get("MODEL", "goland")
    M = int(os.environ.get("PANELS_M", 16))
    N = int(os.environ.get("PANELS_N", 16))
    wake = int(os.environ.get("WAKE_FACTOR", 10))
    nm = int(os.environ.get("MODES", 2))
    cfl = float(os.environ.get("CFL", "1"))
    rank = int(os.environ.get("ROM_ORDER", 6))
    tag = os.environ.get("CASE_TAG", f"{model}-M{M}-N{N}-W{wake}-n{nm}-cfl{cfl:g}")
    out = base / tag
    out.mkdir(exist_ok=False)
    assert model in ("goland", "shell") and 0 < cfl <= 1 and nm > 0
    cout_utils.start_writer()
    cout_utils.cout_wrap.initialise(False, True, str(out), "assembly.log")
    report = {
        "model": model,
        "scope": "Exploratory pipeline test; not qualified flutter",
        "M": M,
        "N_per_half": N,
        "wake_chords": wake,
        "modes": nm,
        "cfl": cfl,
        "status": "running",
    }
    start = time.monotonic()
    try:
        zeta, H, omega, chord, source = geometry(base, model, M, N, nm)
        h = H.reshape(-1, nm)
        dt = cfl * chord / M
        spacing = chord / M
        rho = 1.02 if model == "goland" else 1.225
        report.update(
            input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            dt_at_1m_s=dt,
            geometry_sha256=hashlib.sha256(zeta.tobytes()).hexdigest(),
            wake_spacing_m=spacing,
            rho_kg_m3=rho,
            frequencies_hz=(omega / (2 * np.pi)).tolist(),
        )
        rng = np.random.default_rng(36)
        q = rng.normal(size=nm)
        f = rng.normal(size=h.shape[0])
        report["work_absolute_error"] = float(abs((h @ q) @ f - q @ (h.T @ f)))
        assert report["work_absolute_error"] < 1e-10
        assert np.max(abs(H[:, :, N])) < 1e-12
        ts = AeroTimeStepInfo(np.array([[M, 2 * N]]), np.array([[M * wake, 2 * N]]))
        ts.rho = rho
        ts.zeta[0][:] = zeta
        ts.u_ext[0][0] = 1.0
        ts.u_ext_star[0][0] = 1.0
        for i in range(M * wake + 1):
            ts.zeta_star[0][:, i] = zeta[:, -1] + np.array([spacing * i, 0, 0])[:, None]
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
        static = ts.forces[0][:3].reshape(-1)
        Q0 = h.T @ static
        report["reference_force_at_1m_s_N"] = ts.forces[0][:3].sum(axis=(1, 2)).tolist()
        report["reference_generalized_force_at_1m_s"] = Q0.tolist()
        report["equilibrium"] = (
            "unloaded flat equilibrium"
            if model == "goland"
            else "untrimmed cambered native reference; nonzero load imbalance deliberately retained"
        )
        if model == "goland":
            assert np.max(abs(static)) < 1e-9
        aero = linuvlm.Dynamic(
            ts,
            dynamic_settings={
                "dt": dt,
                "integr_order": 2,
                "density": rho,
                "remove_predictor": False,
                "use_sparse": False,
                "cfl1": False,
            },
        )
        aero.assemble_ss(wake_prop_settings={"cfl1": False, "dt": dt})
        A, B, C, D = aero.SS.get_mats()
        nv = h.shape[0]
        B = np.hstack([B[:, :nv] @ h, B[:, nv : 2 * nv] @ h])
        C = h.T @ C
        D = np.hstack([h.T @ D[:, :nv] @ h, h.T @ D[:, nv : 2 * nv] @ h])
        report["full_aero_states"] = len(A)
        rom = Krylov()
        rom.initialise(
            {
                "algorithm": "mimo_rational_arnoldi",
                "r": rank,
                "single_side": "observability",
                "frequency": [0.0],
                "print_info": False,
            }
        )
        reduced = rom.run(state_space(A, B, C, D, dt))
        Ar, Br, Cr, Dr = reduced.get_mats()
        # Zero-frequency Krylov uses complex dtype even for real matrices.
        # Refuse genuinely complex coordinates rather than discarding them.
        mats = [np.real_if_close(m, tol=1000) for m in (Ar, Br, Cr, Dr)]
        assert all(np.isrealobj(m) for m in mats)
        Ar, Br, Cr, Dr = mats
        report["rom_aero_states"] = len(Ar)
        report["rom_radius"] = float(max(abs(linalg.eigvals(Ar))))
        report["rom_stable"] = report["rom_radius"] < 1.000001
        Vref = 166.5 if model == "goland" else 30.0
        transfer = []
        for freq in [50.0, 70.0, 100.0] if model == "goland" else [55.0, 340.0, 1065.0]:
            z = np.exp(1j * freq * dt / Vref)
            full = (
                z
                * C
                @ splu(
                    z * sparse.eye(len(A), format="csc") - sparse.csc_matrix(A)
                ).solve(B)
                + D
            )
            red = z * Cr @ linalg.solve(z * np.eye(len(Ar)) - Ar, Br) + Dr
            transfer.append(
                {
                    "frequency_rad_s": freq,
                    "relative_frobenius_error": float(
                        linalg.norm(full - red) / max(linalg.norm(full), 1e-30)
                    ),
                }
            )
        report["causal_full_rom_transfer_checks"] = transfer
        # Save reduced unconverted matrices and direct physical map for replay.
        np.savez(
            out / "model.npz",
            A=Ar,
            B=Br,
            C=Cr,
            D=Dr,
            omega=omega,
            dt=dt,
            H=H,
            zeta=zeta,
            Q0=Q0,
        )
        speeds = np.array(
            [
                float(v)
                for v in os.environ.get(
                    "SPEEDS", "145,150,155,160,162,164,166,168,170,175"
                ).split(",")
            ]
        )
        report["sweeps"] = [
            sweep(Ar, Br, Cr, Dr, omega, dt, speeds, causal, 0.0)
            for causal in (True, False)
        ]
        print(
            json.dumps(
                {
                    "case": tag,
                    "brackets": [
                        s["oscillatory_crossing_brackets_m_s"] for s in report["sweeps"]
                    ],
                    "transfer": transfer,
                }
            ),
            flush=True,
        )
        trans = []
        for V in [
            float(v)
            for v in os.environ.get("TRANSIENT_SPEEDS", "150,175").split(",")
            if v
        ]:
            trans.append(
                transient(
                    Ar,
                    Br,
                    Cr,
                    Dr,
                    omega,
                    dt,
                    V,
                    H,
                    float(os.environ.get("DURATION", "2")),
                )
            )
        if model == "shell":
            trans.append(
                transient(Ar, Br, Cr, Dr, omega, dt, 30.0, H, 0.5, 30.0**2 * Q0)
            )
            report["uncoupled_static_q_at_30m_s"] = (900 * Q0 / omega**2).tolist()
        (out / "motion.json").write_text(
            json.dumps(
                {
                    "model": model,
                    "modal_coordinate_normalization": "unit full mirrored mass; native half-wing mode amplitude q/sqrt(2)",
                    "transients": trans,
                },
                indent=2,
            )
            + "\n"
        )
        report["transients"] = [
            {k: v for k, v in t.items() if k != "frames_time_and_q"} for t in trans
        ]
        report["status"] = "executed_exploratory_not_qualified"
    except Exception as e:
        report.update(status="failed", error=repr(e), traceback=traceback.format_exc())
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - start
        (out / "assessment.json").write_text(json.dumps(report, indent=2) + "\n")
        cout_utils.finish_writer()


if __name__ == "__main__":
    main()
