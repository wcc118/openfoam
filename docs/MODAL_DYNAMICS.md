# Modal dynamics solver

Newmark average acceleration method for linear multi-degree-of-freedom systems.

## Purpose

Compute time-domain response of linear structural systems with diagonal mass (M),
damping (C), and stiffness (K) matrices using the Newmark average acceleration
integration scheme (beta=0.25, gamma=0.5).

This is a **numerical verification tool**, not a flight-certified solver.
Results must be verified against analytic benchmarks before engineering use.

## Architecture

### Newmark average acceleration

The method is unconditionally stable and second-order accurate. For each time step:

1. **Predictors:**
   ```
   q_predict = q + dt*v + 0.25*dt²*a
   v_predict = v + 0.5*dt*a
   ```

2. **Acceleration update:**
   ```
   a_next = (Q_next - C*v_predict - K*q_predict) / (M + 0.5*dt*C + 0.25*dt²*K)
   ```

3. **Correctors:**
   ```
   q_next = q_predict + 0.25*dt²*a_next
   v_next = v_predict + 0.5*dt*a_next
   ```

### Discrete energy identity

The numerical method satisfies:

```
ΔE = 0.5*(Q_old + Q_new)·(q_new - q_old) - dt*v_mid·C*v_mid
```

where `v_mid = 0.5*(v_old + v_new)`.

This identity is **independently verified** in tests, not assumed from the
integration formulas.

## Usage

### Python API

```python
from scripts.modal_dynamics import ModalSystem, InitialState, simulate, verify_energy_identity
import math

# Define system (diagonal M, C, K)
system = ModalSystem(
    mass=[1.0, 2.0],                    # kg
    damping=[0.1, 0.2],                 # N·s/m
    stiffness=[4*math.pi**2, 8*math.pi**2],  # N/m
    natural_frequencies=[2*math.pi, 2*math.sqrt(2)*math.pi],  # rad/s
    damping_ratios=[0.05, 0.03],        # dimensionless
)

# Initial state
initial_state = InitialState(
    displacement=[0.1, 0.2],  # meters
    velocity=[0.0, 0.0],      # m/s
    acceleration=[0.0, 0.0],  # m/s² (will be recomputed from equilibrium)
)

# Force function Q(t)
def force_func(t):
    return [math.sin(t), 0.5*math.cos(2*t)]

# Simulate
result = simulate(system, initial_state, force_func, dt=0.001, n_steps=10000)

# Access results
for ts in result.time_steps:
    print(f"t={ts.time:.3f}s: q={ts.displacement}, v={ts.velocity}")

# Verify energy balance
verification = verify_energy_identity(result, dt=0.001)
print(f"Energy conservation error: {verification['conservation_error']:.6f}")
```

### Command line

```bash
# Run simulation
python3 scripts/modal_dynamics.py \
    --mass 1.0,2.0 \
    --damping-ratio 0.05,0.03 \
    --natural-freq 1.0,2.0 \
    --dt 0.001 \
    --steps 10000 \
    --initial-displacement 0.1,0.2 \
    --initial-velocity 0.0,0.0 \
    --initial-force 0.0,0.0 \
    --output results.json

# Run verification tests
python3 scripts/modal_dynamics.py --test
```

## Output format

JSON with schema_version=1:

```json
{
  "schema_version": 1,
  "time_step_count": 10001,
  "final_time": 10.001,
  "checksum": "sha256-hex-string",
  "system": {
    "mass": [1.0, 2.0],
    "damping": [0.1, 0.2],
    "stiffness": [39.47841760435743, 78.95683520871486],
    "natural_frequencies": [6.283185307179586, 8.885765876316743],
    "damping_ratios": [0.05, 0.03]
  },
  "initial_state": {
    "displacement": [0.1, 0.2],
    "velocity": [0.0, 0.0],
    "acceleration": [-3.947841760435743, -15.791367041742972]
  },
  "time_steps": [
    {
      "time": 0.0,
      "displacement": [0.1, 0.2],
      "velocity": [0.0, 0.0],
      "acceleration": [-3.947841760435743, -15.791367041742972],
      "applied_force": [0.0, 0.0]
    },
    ...
  ]
}
```

## Verification

### Analytic benchmarks

Tests independently verify against:

1. **Undamped free vibration**: `q(t) = q0*cos(ω_n*t) + (v0/ω_n)*sin(ω_n*t)`
2. **Underdamped free vibration**: `q(t) = A*exp(-ζ*ω_n*t)*sin(ω_d*t + φ)`
3. **Forced vibration**: Analytic particular solution for harmonic excitation
4. **Energy conservation**: Undamped systems preserve total energy
5. **Energy identity**: Work = ΔE_system + damping dissipation (verified independently)

### Tolerances

- Free vibration: < 1% relative error in displacement/velocity/acceleration
- Forced vibration: < 2% relative error
- Energy conservation: < 5% deviation for undamped, exact balance for damped

## Limitations

- **Diagonal matrices only**: No coupling between DOFs
- **Linear systems only**: No geometric or material nonlinearity
- **No preCICE**: No FSI or multi-solver coupling
- **No default parameters**: User must specify all system properties
- **Numerical verification only**: Not a replacement for physical testing
- **No flutter analysis**: Critical velocity detection requires additional methods

## Architecture

```
scripts/modal_dynamics.py
├── ModalSystem          # Diagonal M, C, K with consistency checks
├── InitialState         # q(0), v(0), a(0)
├── TimeStepResult       # Single time step output
├── SimulationResult     # Full simulation with checksum
├── compute_initial_acceleration()  # a0 = (Q0 - C*v0 - K*q0) / M
├── newmark_step()       # Single Newmark step
├── simulate()           # Full time integration
├── compute_energy_change()         # Energy identity (independent)
├── verify_energy_identity()        # Energy balance verification
├── analytic_single_dof()           # Analytic solution (verification)
├── test_*()                        # Independent verification tests
```

## References

- Clough & Penzien, "Dynamics of Structures", Chapter 12 (Newmark method)
- Newmark, N. M. (1959). "A Method of Computation for Structural Dynamics".
  Journal of the Engineering Mechanics Division, 85(3), 67-94.

## Testing

```bash
python3 -m unittest discover -s tests test_modal_dynamics
```

All tests use **independent analytic identities**, not mirrored formulas.
Passing tests verify numerical correctness, not physical accuracy.

## See also

- `docs/STRUCTURAL_BENCHMARKS.md`: Nastran beam benchmarks
- `docs/ENGINEERING_PLAN.md`: Engineering verification requirements
- `AGENTS.md`: Workflow and issue management
