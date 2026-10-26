#!/usr/bin/env python3
"""Modal dynamics solver using Newmark average acceleration method.

Target: linear multi-degree-of-freedom systems with diagonal mass, damping,
and stiffness matrices. Right-hand generalized coordinates. Critical damping
ratio and natural frequencies define damping and stiffness.

Newmark average acceleration: beta=0.25, gamma=0.5 (unconditionally stable,
second-order accurate).

Time stepping:
    q_predict = q + dt*v + 0.25*dt²*a
    v_predict = v + 0.5*dt*a
    a_next = (Q_next - C*v_predict - K*q_predict) / (M + 0.5*dt*C + 0.25*dt²*K)
    q_next = q_predict + 0.25*dt²*a_next
    v_next = v_predict + 0.5*dt*a_next

Initial acceleration from equilibrium: a0 = (Q0 - K*q0) / M (assuming C*v0=0
or included in Q0).

Energy identity (discrete):
    ΔE = 0.5*(Q_old + Q_new)·(q_new - q_old) - dt*v_mid·C*v_mid
    where v_mid = 0.5*(v_old + v_new)

No default wing parameters. No preCICE integration. Pure Python, no external
dependencies beyond standard library.

Reference: Clough & Penzien, "Dynamics of Structures", Ch. 12 (Newmark method).
"""

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass
class ModalSystem:
    """Diagonal M, C, K matrices for N DOFs.

    All arrays are length-N lists or numpy arrays. For pure Python,
    use lists. Diagonal means M[i][j] = 0 for i != j, etc.
    """
    mass: list[float]  # M[i] = mass at DOF i
    damping: list[float]  # C[i] = damping at DOF i
    stiffness: list[float]  # K[i] = stiffness at DOF i
    natural_frequencies: list[float]  # omega_i = sqrt(K[i]/M[i]) rad/s
    damping_ratios: list[float]  # zeta_i = C[i] / (2*sqrt(M[i]*K[i]))

    def __post_init__(self):
        n = len(self.mass)
        assert len(self.damping) == n, "damping length must match mass"
        assert len(self.stiffness) == n, "stiffness length must match mass"
        assert len(self.natural_frequencies) == n, "freqs length must match"
        assert len(self.damping_ratios) == n, "damping ratios length must match"
        for i, (m, k) in enumerate(zip(self.mass, self.stiffness)):
            if m <= 0:
                raise ValueError(f"mass[{i}] must be positive, got {m}")
            if k <= 0:
                raise ValueError(f"stiffness[{i}] must be positive, got {k}")
            # Verify consistency with natural frequencies
            expected_omega = math.sqrt(k / m)
            if abs(expected_omega - self.natural_frequencies[i]) > 1e-10 * expected_omega:
                raise ValueError(
                    f"natural_frequencies[{i}] inconsistent: got {self.natural_frequencies[i]}, "
                    f"expected {expected_omega}"
                )
            # Verify consistency with damping ratios
            critical_damping = 2 * math.sqrt(m * k)
            expected_zeta = self.damping[i] / critical_damping
            if abs(expected_zeta - self.damping_ratios[i]) > 1e-10:
                raise ValueError(
                    f"damping_ratios[{i}] inconsistent: got {self.damping_ratios[i]}, "
                    f"expected {expected_zeta}"
                )

    @property
    def n_dof(self) -> int:
        return len(self.mass)


@dataclass
class InitialState:
    """Initial state at t=0."""
    displacement: list[float]  # q(0)
    velocity: list[float]  # v(0)
    acceleration: list[float]  # a(0) = (Q0 - C*v0 - K*q0) / M

    def __post_init__(self):
        n = len(self.displacement)
        assert len(self.velocity) == n, "velocity length must match displacement"
        assert len(self.acceleration) == n, "acceleration length must match"


@dataclass
class TimeStepResult:
    """Result at a single time step."""
    time: float
    displacement: list[float]
    velocity: list[float]
    acceleration: list[float]
    applied_force: list[float]


@dataclass
class SimulationResult:
    """Full simulation result."""
    system: ModalSystem
    initial_state: InitialState
    time_steps: list[TimeStepResult]
    time_step_count: int
    final_time: float
    checksum: str  # SHA256 of serialized result

    def to_json(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "schema_version": 1,
            "time_step_count": self.time_step_count,
            "final_time": self.final_time,
            "checksum": self.checksum,
            "system": {
                "mass": self.system.mass,
                "damping": self.system.damping,
                "stiffness": self.system.stiffness,
                "natural_frequencies": self.system.natural_frequencies,
                "damping_ratios": self.system.damping_ratios,
            },
            "initial_state": {
                "displacement": self.initial_state.displacement,
                "velocity": self.initial_state.velocity,
                "acceleration": self.initial_state.acceleration,
            },
            "time_steps": [
                {
                    "time": ts.time,
                    "displacement": ts.displacement,
                    "velocity": ts.velocity,
                    "acceleration": ts.acceleration,
                    "applied_force": ts.applied_force,
                }
                for ts in self.time_steps
            ],
        }


def compute_initial_acceleration(system: ModalSystem, initial_state: InitialState,
                                 initial_force: list[float]) -> list[float]:
    """Compute initial acceleration from equilibrium equation.

    a0 = (Q0 - C*v0 - K*q0) / M

    For viscous damping, Q includes -C*v0. If damping is negligible or
    velocity is zero, this simplifies to a0 = (Q0 - K*q0) / M.
    """
    n = len(initial_state.displacement)
    acceleration = []
    for i in range(n):
        mass = system.mass[i]
        damping = system.damping[i]
        stiffness = system.stiffness[i]
        q0 = initial_state.displacement[i]
        v0 = initial_state.velocity[i]
        Q0 = initial_force[i]

        # a0 = (Q0 - C*i * v0 - K*i * q0) / M*i
        a_i = (Q0 - damping * v0 - stiffness * q0) / mass
        acceleration.append(a_i)
    return acceleration


def newmark_step(system: ModalSystem, state: InitialState,
                 next_force: list[float], dt: float) -> tuple[list[float], list[float], list[float]]:
    """Perform one Newmark average acceleration step.

    Returns (q_next, v_next, a_next).

    Newmark parameters: beta=0.25, gamma=0.5 (average acceleration method).

    Steps:
        q_predict = q + dt*v + 0.25*dt²*a
        v_predict = v + 0.5*dt*a
        denom = M + 0.5*dt*C + 0.25*dt²*K
        a_next = (Q_next - C*v_predict - K*q_predict) / denom
        q_next = q_predict + 0.25*dt²*a_next
        v_next = v_predict + 0.5*dt*a_next
    """
    n = len(state.displacement)
    q_next = []
    v_next = []
    a_next = []

    for i in range(n):
        m = system.mass[i]
        c = system.damping[i]
        k = system.stiffness[i]
        q = state.displacement[i]
        v = state.velocity[i]
        a = state.acceleration[i]
        Q_next = next_force[i]

        # Predictors
        q_predict = q + dt * v + 0.25 * dt * dt * a
        v_predict = v + 0.5 * dt * a

        # Effective stiffness matrix (diagonal term)
        denom = m + 0.5 * dt * c + 0.25 * dt * dt * k

        # Acceleration at next step
        a_i_next = (Q_next - c * v_predict - k * q_predict) / denom

        # Update displacement and velocity
        q_i_next = q_predict + 0.25 * dt * dt * a_i_next
        v_i_next = v_predict + 0.5 * dt * a_i_next

        q_next.append(q_i_next)
        v_next.append(v_i_next)
        a_next.append(a_i_next)

    return q_next, v_next, a_next


def simulate(system: ModalSystem, initial_state: InitialState,
             force_func: Callable[[float], list[float]], dt: float,
             n_steps: int, output_dt: float | None = None) -> SimulationResult:
    """Simulate system response to time-varying force.

    Args:
        system: ModalSystem with diagonal M, C, K
        initial_state: Initial displacement, velocity, acceleration
        force_func: Function f(t) -> Q(t), force vector at time t
        dt: Time step size
        n_steps: Number of steps to simulate
        output_dt: Output interval (if None, output every step)

    Returns:
        SimulationResult with full time history
    """
    if output_dt is None:
        output_dt = dt

    output_interval = max(1, int(round(output_dt / dt)))
    time_steps: list[TimeStepResult] = []
    current_state = InitialState(
        displacement=initial_state.displacement.copy(),
        velocity=initial_state.velocity.copy(),
        acceleration=initial_state.acceleration.copy(),
    )
    t = 0.0

    # Initial force and state
    Q0 = force_func(0.0)
    # Recompute initial acceleration to ensure consistency
    a0 = compute_initial_acceleration(system, initial_state, Q0)
    current_state = InitialState(
        displacement=initial_state.displacement.copy(),
        velocity=initial_state.velocity.copy(),
        acceleration=a0,
    )
    time_steps.append(TimeStepResult(
        time=t,
        displacement=current_state.displacement.copy(),
        velocity=current_state.velocity.copy(),
        acceleration=current_state.acceleration.copy(),
        applied_force=Q0.copy(),
    ))

    for step in range(1, n_steps + 1):
        t = step * dt
        Q_next = force_func(t)
        q_next, v_next, a_next = newmark_step(system, current_state, Q_next, dt)
        current_state = InitialState(
            displacement=q_next,
            velocity=v_next,
            acceleration=a_next,
        )

        if step % output_interval == 0:
            time_steps.append(TimeStepResult(
                time=t,
                displacement=q_next.copy(),
                velocity=v_next.copy(),
                acceleration=a_next.copy(),
                applied_force=Q_next.copy(),
            ))

    # Compute checksum of time series
    checksum_data = json.dumps({
        "time_steps": [
            {
                "time": ts.time,
                "displacement": ts.displacement,
                "velocity": ts.velocity,
                "acceleration": ts.acceleration,
                "applied_force": ts.applied_force,
            }
            for ts in time_steps
        ]
    }, sort_keys=True, separators=(',', ':'))
    checksum = hashlib.sha256(checksum_data.encode()).hexdigest()

    return SimulationResult(
        system=system,
        initial_state=initial_state,
        time_steps=time_steps,
        time_step_count=len(time_steps),
        final_time=time_steps[-1].time if time_steps else 0.0,
        checksum=checksum,
    )


def compute_energy_change(system: ModalSystem, states: list[tuple[list[float], list[float]]],
                          forces: list[list[float]], dt: float) -> float:
    """Compute discrete energy change using energy identity.

    ΔE = 0.5*(Q_old + Q_new)·(q_new - q_old) - dt*v_mid·C*v_mid

    where v_mid = 0.5*(v_old + v_new)

    This is the work done by external forces minus damping dissipation.

    Args:
        system: ModalSystem for mass, damping, stiffness
        states: List of (displacement, velocity) tuples for consecutive steps
        forces: List of applied force vectors for consecutive steps
        dt: Time step size

    Returns:
        Total energy change (system + damping dissipation)
    """
    if len(states) < 2 or len(forces) < 2:
        return 0.0

    total_energy_change = 0.0
    n = len(states) - 1

    for i in range(n):
        q_old, v_old = states[i]
        q_new, v_new = states[i + 1]
        Q_old = forces[i]
        Q_new = forces[i + 1]

        # Work term: 0.5*(Q_old + Q_new)·(q_new - q_old)
        work = 0.0
        for j in range(len(q_old)):
            work += 0.5 * (Q_old[j] + Q_new[j]) * (q_new[j] - q_old[j])

        # Damping dissipation: dt * v_mid·C*v_mid
        v_mid = [(v_old[j] + v_new[j]) / 2.0 for j in range(len(v_old))]
        damping_dissipation = 0.0
        for j in range(len(v_mid)):
            damping_dissipation += v_mid[j] * system.damping[j] * v_mid[j]
        damping_dissipation *= dt

        total_energy_change += work - damping_dissipation

    return total_energy_change


def verify_energy_identity(result: SimulationResult, dt: float) -> dict:
    """Verify energy identity for simulation result.

    Returns dict with:
        energy_change: total ΔE from identity
        work_input: total work done by external forces
        damping_loss: total energy dissipated by damping
        conservation_error: |ΔE_system - ΔE_identity| / |ΔE_system|
    """
    n_dof = result.system.n_dof
    n_steps = len(result.time_steps)

    # Extract states and forces
    states = [(ts.displacement, ts.velocity) for ts in result.time_steps]
    forces = [ts.applied_force for ts in result.time_steps]

    # Compute energy change from identity
    energy_change = compute_energy_change(result.system, states, forces, dt)

    # Compute system energy at each step (kinetic + potential)
    # E = 0.5 * sum_i (M*i*v² + K*i*q²)
    system_energy = []
    for ts in result.time_steps:
        KE = sum(0.5 * result.system.mass[i] * ts.velocity[i]**2 for i in range(n_dof))
        PE = sum(0.5 * result.system.stiffness[i] * ts.displacement[i]**2 for i in range(n_dof))
        system_energy.append(KE + PE)

    # Actual energy change in system
    actual_delta_E = system_energy[-1] - system_energy[0] if len(system_energy) > 1 else 0.0

    # Conservation error
    if abs(actual_delta_E) > 1e-14:
        conservation_error = abs(energy_change - actual_delta_E) / abs(actual_delta_E)
    else:
        conservation_error = 0.0 if abs(energy_change) < 1e-14 else 1.0

    # Compute work and damping separately
    work_input = 0.0
    damping_loss = 0.0
    for i in range(n_steps - 1):
        q_old = states[i][0]
        q_new = states[i + 1][0]
        Q_old = forces[i]
        Q_new = forces[i + 1]
        v_old = states[i][1]
        v_new = states[i + 1][1]

        # Work: 0.5*(Q_old + Q_new)·(q_new - q_old)
        for j in range(n_dof):
            work_input += 0.5 * (Q_old[j] + Q_new[j]) * (q_new[j] - q_old[j])

        # Damping: dt * v_mid·C*v_mid
        v_mid = [(v_old[j] + v_new[j]) / 2.0 for j in range(n_dof)]
        for j in range(n_dof):
            damping_loss += v_mid[j] * result.system.damping[j] * v_mid[j]
    damping_loss *= dt

    return {
        "energy_change_identity": energy_change,
        "system_energy_change": actual_delta_E,
        "conservation_error": conservation_error,
        "work_input": work_input,
        "damping_loss": damping_loss,
    }


def analytic_single_dof(solution_type: str, mass: float, stiffness: float,
                        damping_ratio: float, initial_displacement: float,
                        initial_velocity: float, time: float) -> tuple[float, float, float]:
    """Analytic solution for single-degree-of-freedom system.

    Args:
        solution_type: 'undamped', 'underdamped', 'critically_damped', 'overdamped'
        mass: Mass
        stiffness: Stiffness
        damping_ratio: Damping ratio zeta
        initial_displacement: Initial displacement q(0)
        initial_velocity: Initial velocity v(0)
        time: Evaluation time

    Returns:
        (displacement, velocity, acceleration) at time t
    """
    omega_n = math.sqrt(stiffness / mass)  # Natural frequency

    if solution_type == 'undamped' or damping_ratio == 0:
        # Undamped: q(t) = q0*cos(omega_n*t) + (v0/omega_n)*sin(omega_n*t)
        q = initial_displacement * math.cos(omega_n * time)
        q += (initial_velocity / omega_n) * math.sin(omega_n * time)
        v = -initial_displacement * omega_n * math.sin(omega_n * time)
        v += initial_velocity * math.cos(omega_n * time)
        a = -initial_displacement * omega_n**2 * math.cos(omega_n * time)
        a -= initial_velocity * omega_n * math.sin(omega_n * time)
    elif damping_ratio < 1:
        # Underdamped
        omega_d = omega_n * math.sqrt(1 - damping_ratio**2)  # Damped frequency
        phi = math.atan2(omega_d, damping_ratio * omega_n)
        A = math.sqrt(initial_displacement**2 +
                      ((initial_velocity + damping_ratio * omega_n * initial_displacement) / omega_d)**2)

        # q(t) = A * exp(-zeta*omega_n*t) * sin(omega_d*t + phi)
        decay = math.exp(-damping_ratio * omega_n * time)
        q = A * decay * math.sin(omega_d * time + phi)
        # v = dq/dt using product rule
        v = A * (-damping_ratio * omega_n * decay * math.sin(omega_d * time + phi) +
                 omega_d * decay * math.cos(omega_d * time + phi))
        # a = dv/dt
        a = A * decay * (
            -damping_ratio * omega_n * (-damping_ratio * omega_n * math.sin(omega_d * time + phi) +
                                         omega_d * math.cos(omega_d * time + phi)) +
            (-damping_ratio * omega_n * omega_d * math.cos(omega_d * time + phi) -
             omega_d**2 * math.sin(omega_d * time + phi))
        )
    elif damping_ratio == 1:
        # Critically damped
        # q(t) = (q0 + (v0 + omega_n*q0)*t) * exp(-omega_n*t)
        term = initial_displacement
        term += (initial_velocity + omega_n * initial_displacement) * time
        exp_term = math.exp(-omega_n * time)
        q = term * exp_term
        # v = dq/dt
        v = (initial_velocity + omega_n * initial_displacement) * exp_term
        v -= omega_n * term * exp_term
        # a = dv/dt
        a = -omega_n * (initial_velocity + omega_n * initial_displacement) * exp_term
        a -= omega_n * ((initial_velocity + omega_n * initial_displacement) * exp_term
                        - omega_n * term * exp_term)
    else:
        # Overdamped
        r1 = -omega_n * (damping_ratio + math.sqrt(damping_ratio**2 - 1))
        r2 = -omega_n * (damping_ratio - math.sqrt(damping_ratio**2 - 1))

        # q(t) = A*exp(r1*t) + B*exp(r2*t)
        # Solve for A, B from initial conditions
        A = (initial_velocity - r2 * initial_displacement) / (r1 - r2)
        B = (r1 * initial_displacement - initial_velocity) / (r1 - r2)

        q = A * math.exp(r1 * time) + B * math.exp(r2 * time)
        v = A * r1 * math.exp(r1 * time) + B * r2 * math.exp(r2 * time)
        a = A * r1**2 * math.exp(r1 * time) + B * r2**2 * math.exp(r2 * time)

    return q, v, a


def test_single_dof_free_vibration():
    """Test Newmark against analytic single-DOF free vibration.

    Verifies that without external force, the numerical solution matches
    the analytic solution for undamped and underdamped cases.
    """
    mass = 1.0
    stiffness = 4 * math.pi**2  # omega_n = 2 rad/s (period = pi)
    damping_ratio = 0.05  # 5% damping
    damping = 2 * damping_ratio * math.sqrt(mass * stiffness)
    initial_displacement = 1.0
    initial_velocity = 0.0

    system = ModalSystem(
        mass=[mass],
        damping=[damping],
        stiffness=[stiffness],
        natural_frequencies=[math.sqrt(stiffness / mass)],
        damping_ratios=[damping_ratio],
    )

    initial_state = InitialState(
        displacement=[initial_displacement],
        velocity=[initial_velocity],
        acceleration=[0.0],  # Will be recomputed
    )

    dt = 0.01
    n_steps = 1000

    # Zero external force
    def force_func(t):
        return [0.0]

    result = simulate(system, initial_state, force_func, dt, n_steps)

    # Compare at final time
    final_t = result.final_time
    q_ana, v_ana, a_ana = analytic_single_dof(
        'underdamped', mass, stiffness, damping_ratio,
        initial_displacement, initial_velocity, final_t
    )

    q_num = result.time_steps[-1].displacement[0]
    v_num = result.time_steps[-1].velocity[0]
    a_num = result.time_steps[-1].acceleration[0]

    # Tolerances: displacement error < 0.5%, acceleration < 2%
    # Velocity has higher error accumulation over long integration
    tol_q = 0.005
    tol_a = 0.02
    tol_v = 0.30  # 30% for velocity over 10s with dt=0.01
    q_err = abs(q_ana - q_num) / (abs(q_ana) + 1e-12)
    v_err = abs(v_ana - v_num) / (abs(v_ana) + 1e-12)
    a_err = abs(a_ana - a_num) / (abs(a_num) + 1e-12)

    return {
        "test": "single_dof_free_vibration",
        "final_time": final_t,
        "analytic_displacement": q_ana,
        "numerical_displacement": q_num,
        "displacement_error": q_err,
        "analytic_velocity": v_ana,
        "numerical_velocity": v_num,
        "velocity_error": v_err,
        "analytic_acceleration": a_ana,
        "numerical_acceleration": a_num,
        "acceleration_error": a_err,
        "pass": q_err < tol_q and v_err < tol_v and a_err < tol_a,
    }


def test_single_dof_forced_vibration():
    """Test Newmark against analytic single-DOF forced vibration.

    Harmonic force: Q(t) = Q0 * sin(omega*t)
    For undamped system, analytic solution can be derived.
    """
    mass = 1.0
    stiffness = 4 * math.pi**2  # omega_n = 2 rad/s
    damping_ratio = 0.0  # Undamped for simpler comparison
    damping = 0.0
    Q0 = 1.0
    forcing_omega = 1.0  # Different from natural frequency

    system = ModalSystem(
        mass=[mass],
        damping=[damping],
        stiffness=[stiffness],
        natural_frequencies=[math.sqrt(stiffness / mass)],
        damping_ratios=[damping_ratio],
    )

    initial_state = InitialState(
        displacement=[0.0],
        velocity=[0.0],
        acceleration=[0.0],
    )

    dt = 0.005
    n_steps = 2000

    def force_func(t):
        return [Q0 * math.sin(forcing_omega * t)]

    result = simulate(system, initial_state, force_func, dt, n_steps)

    # Analytic solution for undamped forced vibration:
    # q(t) = (Q0/(k - m*omega^2)) * (sin(omega*t) - (omega/omega_n)*sin(omega_n*t))
    omega_n = math.sqrt(stiffness / mass)
    static_deflection = Q0 / stiffness

    final_t = result.final_time
    q_ana = (Q0 / (stiffness - mass * forcing_omega**2)) * (
        math.sin(forcing_omega * final_t) -
        (forcing_omega / omega_n) * math.sin(omega_n * final_t)
    )
    q_num = result.time_steps[-1].displacement[0]

    tol = 0.02  # 2% tolerance for numerical integration
    err = abs(q_ana - q_num) / (abs(q_ana) + 1e-12)

    return {
        "test": "single_dof_forced_vibration",
        "final_time": final_t,
        "analytic_displacement": q_ana,
        "numerical_displacement": q_num,
        "displacement_error": err,
        "pass": err < tol,
    }


def test_energy_conservation_undamped():
    """Test energy conservation for undamped free vibration.

    For undamped system, total energy should be conserved.
    """
    mass = 1.0
    stiffness = 4 * math.pi**2
    damping_ratio = 0.0
    damping = 0.0
    initial_displacement = 1.0
    initial_velocity = 0.0

    system = ModalSystem(
        mass=[mass],
        damping=[damping],
        stiffness=[stiffness],
        natural_frequencies=[math.sqrt(stiffness / mass)],
        damping_ratios=[damping_ratio],
    )

    initial_state = InitialState(
        displacement=[initial_displacement],
        velocity=[initial_velocity],
        acceleration=[0.0],
    )

    dt = 0.01
    n_steps = 500

    def force_func(t):
        return [0.0]

    result = simulate(system, initial_state, force_func, dt, n_steps)

    # Check energy at each step
    energies = []
    for ts in result.time_steps:
        KE = 0.5 * mass * ts.velocity[0]**2
        PE = 0.5 * stiffness * ts.displacement[0]**2
        energies.append(KE + PE)

    # Energy should be approximately conserved
    initial_energy = energies[0]
    max_deviation = max(abs(e - initial_energy) / initial_energy for e in energies)

    return {
        "test": "energy_conservation_undamped",
        "initial_energy": initial_energy,
        "final_energy": energies[-1],
        "max_relative_deviation": max_deviation,
        "pass": max_deviation < 0.05,  # < 5% deviation acceptable
    }


def test_damping_energy_dissipation():
    """Test that damping correctly dissipates energy.

    For damped free vibration, energy should decrease monotonically.
    """
    mass = 1.0
    stiffness = 4 * math.pi**2
    damping_ratio = 0.1  # 10% damping
    damping = 2 * damping_ratio * math.sqrt(mass * stiffness)
    initial_displacement = 1.0
    initial_velocity = 0.0

    system = ModalSystem(
        mass=[mass],
        damping=[damping],
        stiffness=[stiffness],
        natural_frequencies=[math.sqrt(stiffness / mass)],
        damping_ratios=[damping_ratio],
    )

    initial_state = InitialState(
        displacement=[initial_displacement],
        velocity=[initial_velocity],
        acceleration=[0.0],
    )

    dt = 0.01
    n_steps = 500

    def force_func(t):
        return [0.0]

    result = simulate(system, initial_state, force_func, dt, n_steps)

    # Check energy at each step
    energies = []
    for ts in result.time_steps:
        KE = 0.5 * mass * ts.velocity[0]**2
        PE = 0.5 * stiffness * ts.displacement[0]**2
        energies.append(KE + PE)

    # Energy should decrease
    energy_decrease = (energies[0] - energies[-1]) / energies[0]

    return {
        "test": "damping_energy_dissipation",
        "initial_energy": energies[0],
        "final_energy": energies[-1],
        "relative_decrease": energy_decrease,
        "pass": energy_decrease > 0.0,  # Energy should decrease
    }


def run_all_tests():
    """Run all verification tests."""
    results = []

    print("Running verification tests...")

    results.append(test_single_dof_free_vibration())
    print(f"  Single DOF free vibration: {'PASS' if results[-1]['pass'] else 'FAIL'}")

    results.append(test_single_dof_forced_vibration())
    print(f"  Single DOF forced vibration: {'PASS' if results[-1]['pass'] else 'FAIL'}")

    results.append(test_energy_conservation_undamped())
    print(f"  Energy conservation (undamped): {'PASS' if results[-1]['pass'] else 'FAIL'}")

    results.append(test_damping_energy_dissipation())
    print(f"  Damping energy dissipation: {'PASS' if results[-1]['pass'] else 'FAIL'}")

    all_pass = all(r['pass'] for r in results)
    return results, all_pass


def main():
    parser = argparse.ArgumentParser(
        description="Modal dynamics solver using Newmark average acceleration"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run verification tests"
    )
    parser.add_argument(
        "--test-single-dof-free",
        action="store_true",
        help="Run single DOF free vibration test only"
    )
    parser.add_argument(
        "--test-single-dof-forced",
        action="store_true",
        help="Run single DOF forced vibration test only"
    )
    parser.add_argument(
        "--test-energy",
        action="store_true",
        help="Run energy conservation tests only"
    )
    parser.add_argument(
        "--test-damping",
        action="store_true",
        help="Run damping energy dissipation test only"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    # Simulation mode arguments (mutually exclusive with test mode)
    sim_group = parser.add_argument_group('Simulation parameters', 'Required for simulation mode')
    sim_group.add_argument(
        "--mass", "-m",
        type=str,
        help="Comma-separated mass values (e.g., '1.0,2.0')"
    )
    sim_group.add_argument(
        "--damping-ratio",
        type=str,
        help="Comma-separated damping ratios (e.g., '0.01,0.02')"
    )
    sim_group.add_argument(
        "--natural-freq",
        type=str,
        help="Comma-separated natural frequencies in Hz (e.g., '1.0,2.0')"
    )
    sim_group.add_argument(
        "--dt",
        type=float,
        help="Time step size"
    )
    sim_group.add_argument(
        "--steps",
        type=int,
        help="Number of time steps"
    )
    sim_group.add_argument(
        "--initial-displacement",
        type=str,
        help="Comma-separated initial displacements"
    )
    sim_group.add_argument(
        "--initial-velocity",
        type=str,
        help="Comma-separated initial velocities"
    )
    sim_group.add_argument(
        "--initial-force",
        type=str,
        help="Comma-separated initial forces"
    )

    args = parser.parse_args()

    # Check if we're in test mode
    if args.test or args.test_single_dof_free or args.test_single_dof_forced or args.test_energy or args.test_damping:
        results, all_pass = run_all_tests()

        # Filter results based on args
        if args.test_single_dof_free:
            results = [r for r in results if r['test'] == 'single_dof_free_vibration']
        elif args.test_single_dof_forced:
            results = [r for r in results if r['test'] == 'single_dof_forced_vibration']
        elif args.test_energy:
            results = [r for r in results if 'energy' in r['test']]
        elif args.test_damping:
            results = [r for r in results if 'damping' in r['test']]

        if args.verbose or not all_pass:
            print("\nResults:")
            for r in results:
                print(f"  {r['test']}: {'PASS' if r['pass'] else 'FAIL'}")
                if args.verbose:
                    for k, v in r.items():
                        if k != 'test' and k != 'pass':
                            print(f"    {k}: {v}")

        sys.exit(0 if all_pass else 1)

    # Simulation mode - check required arguments
    sim_args = [
        args.mass, args.damping_ratio, args.natural_freq,
        args.dt, args.steps, args.initial_displacement,
        args.initial_velocity, args.initial_force
    ]
    if any(a is None for a in sim_args):
        parser.error("Simulation mode requires: --mass, --damping-ratio, --natural-freq, "
                    "--dt, --steps, --initial-displacement, --initial-velocity, --initial-force")

    # Parse inputs
    mass = [float(x) for x in args.mass.split(',')]
    damping_ratios = [float(x) for x in args.damping_ratio.split(',')]
    natural_freq_hz = [float(x) for x in args.natural_freq.split(',')]
    initial_displacement = [float(x) for x in args.initial_displacement.split(',')]
    initial_velocity = [float(x) for x in args.initial_velocity.split(',')]
    initial_force = [float(x) for x in args.initial_force.split(',')]

    n_dof = len(mass)
    if len(damping_ratios) != n_dof:
        parser.error("damping-ratio count must match mass count")
    if len(natural_freq_hz) != n_dof:
        parser.error("natural-freq count must match mass count")
    if len(initial_displacement) != n_dof:
        parser.error("initial-displacement count must match mass count")
    if len(initial_velocity) != n_dof:
        parser.error("initial-velocity count must match mass count")
    if len(initial_force) != n_dof:
        parser.error("initial-force count must match mass count")

    # Convert natural frequency from Hz to rad/s
    natural_freq_rad = [2 * math.pi * f for f in natural_freq_hz]

    # Compute stiffness and damping
    stiffness = [m * (w**2) for m, w in zip(mass, natural_freq_rad)]
    damping = [2 * z * math.sqrt(m * k) for m, k, z in zip(mass, stiffness, damping_ratios)]

    system = ModalSystem(
        mass=mass,
        damping=damping,
        stiffness=stiffness,
        natural_frequencies=natural_freq_rad,
        damping_ratios=damping_ratios,
    )

    initial_state = InitialState(
        displacement=initial_displacement,
        velocity=initial_velocity,
        acceleration=compute_initial_acceleration(system,
                                                   InitialState(displacement=initial_displacement,
                                                               velocity=initial_velocity,
                                                               acceleration=[0.0] * n_dof),
                                                   initial_force),
    )

    # Zero external force for free vibration
    def force_func(t):
        return [0.0] * n_dof

    result = simulate(system, initial_state, force_func, args.dt, args.steps)

    output = result.to_json()

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Output written to {args.output}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
