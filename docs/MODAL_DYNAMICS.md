# Linear modal time integration

`scripts/modal_dynamics.py` integrates independent modal coordinates satisfying
`M*a + C*v + K*q = Q`, with explicit diagonal coefficients and consistent
right-hand coordinates. It uses NumPy and Newmark average acceleration
(beta=1/4, gamma=1/2). There are no default material, damping, or wing properties.
Units must be consistent with the supplied modal normalization; generalized
coordinates and loads need not have translation units.

```python
from scripts.modal_dynamics import ModalSystem
system = ModalSystem(mass=[2.0], damping=[0.1], stiffness=[8.0])
state = system.initial_state(q=[0.01], v=[0.0], force=[0.0])
checkpoint = system.checkpoint(state)
candidate = system.step(state, next_force=[0.2], dt=0.001)
# Accept by assigning state=candidate; reject by restoring the saved endpoint.
state = system.restore(checkpoint)
```

The numbers above are a synthetic oscillator, not wing inputs. Coefficients,
state, and endpoint loads are owned immutable tuples; caller arrays cannot alter
them. A step returns a new state and never changes its input. Checkpoints include
q, v, a, force, and time. Restore validates dimensions and endpoint equilibrium
against the receiving system. Initial acceleration includes damping. Zero
stiffness supports rigid modes. Invalid dimensions, nonfinite values, nonpositive
mass/time step, negative damping/stiffness, and inconsistent acceleration fail.

The caller supplies external generalized force Q at each endpoint; do not subtract
viscous damping from Q a second time. For a linear surface displacement map H,
work-conjugate loading is Q=H.T*F. This module does not construct or validate H.

For equilibrium endpoint states, the discrete energy identity is
`E_next-E = (Q+Q_next)/2 dot (q_next-q) - dt*v_mid dot C*v_mid`.
Tests check this with varying loads, damping and a rigid mode. Independent
undamped and underdamped analytic solutions with nonzero initial velocity verify
second-order convergence at a non-period endpoint. The initial 40/80/160-step
experiment met the order check but missed the declared absolute error bound;
80/160/320 steps meet both without relaxing the tolerance. Replay tests reject a
different trial load/step, restore, and reproduce the clean accepted state.

Unconditional stability for the linear structural problem is not coupled FSI
stability, time accuracy, damping calibration, modal truncation adequacy or flutter
validation. No preCICE participant, force history interpolation, nonlinear rotation,
fluid rollback, or coupled convergence controller is included. This deliberately
replaces the rejected draft's CLI and embedded analytic/self-test framework.

Validation: `python3 -m unittest tests.test_modal_dynamics -v`.
