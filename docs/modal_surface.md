# Modal surface algebra

`scripts/modal_surface.py` implements the explicit small-motion relation u=Hq,
its work-conjugate force map Q=H^T f, and the translational mass Gram matrix
Phi^T M Phi. Python nested lists store the basis as `[mode][point][xyz]`;
mathematically each mode is one column of H after flattening point/xyz rows.

All inputs must be finite and dimensionally consistent. Point masses are strictly
positive **kilograms**. Zero basis entries at constrained points are valid.
Outputs are owned lists; inputs are not modified. Summation uses `math.fsum`.
No hidden mass conversion, normalization, interpolation or frame rotation occurs.

```python
from scripts.modal_surface import displacements, generalized_forces, mass_gram
basis = [[[1., 0., 0.], [.5, 0., 0.]]]
q = [.01]  # m for this dimensionless basis
u = displacements(basis, q)  # [[.01, 0, 0], [.005, 0, 0]] m
Q = generalized_forces(basis, [[10., 0., 0.], [4., 0., 0.]])  # [12.] N
M = mass_gram(basis, [.1, .05])  # [[.1125]] kg
```

Physical translations use m and nodal forces N in a shared right-handed frame
(x downstream, y span, z up for this wing). Generalized force units follow from
Q*dq having energy units: for dimensionless H and q in m, Q is N; for q
dimensionless and H in m, Q is N*m. For mass-normalized translations H has units
kg^-1/2, q has m*kg^1/2 and Q has N*kg^-1/2, giving a unit numerical modal mass.
Do not assign Q a torque unit just because it is called generalized force.

Input forces are already nodal forces at the basis points. Pressure-to-force
integration, area weights, reference point offsets and aerodynamic interpolation
belong upstream; moments or lever arms are not inferred here. Velocity uses the
same displacement map with q-dot. This utility does not integrate motion or solve
flutter. See [SHELL_MODAL_INTERFACE.md](SHELL_MODAL_INTERFACE.md) for native shell
checks and the separately assessed shell-to-camber map.

Run `python3 -m unittest discover -s tests -p test_modal_surface.py`.
