# First-flow case setup

`scripts/generate_flow_case.py` writes an **unqualified setup**, not a solved or
accepted aerodynamic case. It copies a supplied native mesh into a new directory,
writes OpenCFD v2412 dictionaries, and records provenance. It never launches a
solver. Follow [mesh acceptance](MESH_ACCEPTANCE.md) and the
[rigid-wing contract](RIGID_WING_MVP.md) before interpreting results.

```bash
python3 scripts/generate_flow_case.py \
  --mesh-dir /path/to/mesh/constant/polyMesh \
  --output /path/to/new-flow-case --alpha-deg 4 --iterations 500
```

The output must not exist, even as an empty directory or symlink, and must not be
inside the source mesh directory. Required regular files are points, faces,
owner, neighbour and boundary; optional zone files are copied if present.
Symlinks are rejected. The limited boundary reader requires a native counted
ASCII list with inlet/outlet/farfield of type patch and wing of type wall. It
rejects mismatches, duplicates and unsupported syntax; native checkMesh still
owns topology and geometry validation.

The manifest records source and copied hashes independently, generated-file
hashes, generator hash and repository revision/dirty state when available,
conditions, axes and reference values. A copied-byte mismatch fails generation.
Failures after output creation retain partial files and, where writable, a
`setup_failed` manifest. Success means `unqualified_setup` only. Keep each run
immutable and use a new output directory for a repeat.

## Fixed demonstration conditions

The provisional full wing is NACA4412, span 1.2192 m, chord 0.1016 m and reference
area 0.12387072 m². Moment origin is midspan quarter-chord `(0.0254, 0, 0)` m.
These are not an owner-approved design or flight-envelope definition.

Speed is 30 m/s; density 1.2250532683653954 kg/m³; kinematic viscosity
1.4605775310347254e-5 m²/s; chord Reynolds number 208684.5741; Mach 0.0881609.
ISA inputs reuse flight-loads revision
`7fe19f0761e00dd54238100461effa2533fc62c8`; source path and SHA are in the manifest.

Axes are x downstream, y span and z upward. Positive incidence uses
`U = 30(cos(alpha), 0, sin(alpha))`. Drag follows that unit direction; lift is
`(-sin(alpha), 0, cos(alpha))`. Positive pitching moment is about +y. Both native
force outputs use the quarter-chord origin. Kinematic pressure has units m²/s²;
dimensional pressure traction multiplies by density. Reference dynamic pressure
is 551.273970764428 Pa. Do not assume arbitrary aircraft-frame signs match.

The candidate solver is steady incompressible simpleFoam with fully turbulent
kOmegaSST. Turbulence intensity is 0.001 and length scale 0.07 chord:
`k = 1.5(V I)^2`, `omega = sqrt(k)/(0.09^0.25 L)`. Transition, roughness and
freestream-turbulence sensitivity remain unresolved, especially at this low Re.
This incompressible demonstration does not establish suitability at 250 knots.

## Boundary conditions and numerics

| Field | Inlet | Outlet | Farfield | Wing |
| --- | --- | --- | --- | --- |
| U | fixed freestream | inletOutlet | freestream | noSlip |
| p | zeroGradient | fixed zero | freestreamPressure | zeroGradient |
| k | fixed freestream | inletOutlet | freestream | fixed zero |
| omega | fixed freestream | inletOutlet | freestream | omegaWallFunction, binomial n=2 |
| nut | calculated | calculated | calculated | nutLowReWallFunction |

Wall k=0 follows the [SST reference](https://tmbwg.github.io/turbmodels/sst.html).
The pinned native kqRWallFunction is a zero-gradient wrapper described for high-Re
wall-function cases; it is not used here. Native omegaWallFunction blends its
viscous/log contributions, while nutLowReWallFunction sets wall nut=0 and exposes
a velocity-gradient-based yPlus. Document this native treatment rather than
claiming identity to every SST reference variant.

Momentum uses bounded linearUpwindV with cell-limited velocity gradients;
turbulence advection uses bounded upwind. Laplacian and surface-normal gradient
corrections are limited to 0.5. SIMPLE uses consistent correction and one
non-orthogonal correction. Pressure GAMG tolerance is 1e-8, relative tolerance
0.05; U/k/omega smoothSolver tolerance is 1e-9, relative tolerance 0.1.
Relaxation is 0.3 for p and 0.7 for U/k/omega. These are planned setup choices,
not conclusions from a convergence study.

There is no early residualControl stop. CLI iterations must be 500–5000; labels
in a steady case are SIMPLE iterations, **not physical seconds**. Native forces,
forceCoeffs and solverInfo write histories each iteration. yPlus and
wallShearStress fields write with the case fields every 100 iterations; ASCII
precision is 12. Preserve solver logs and warnings as well as these outputs.

## Native execution and acceptance

Run only in the qualified pinned native runtime with explicit resource limits.
The following are solver commands inside that runtime, not a complete launcher:

```bash
checkMesh -allTopology -meshQuality
checkMesh -allGeometry -allTopology
simpleFoam
```

Supply the unchanged canonical meshQualityDict and retain both full logs before
using the first command as an acceptance gate. Parallel execution additionally
requires a declared decomposition, MPI run and reconstruction; retain those
commands and outputs. A process exit of zero is never a mesh/flow pass.

Predeclared first-flow checks:

- At least 500 iterations; evaluate the final 200-step window.
- Residuals p <=1e-5 and U/k/omega <=1e-6; finite fields and physically permitted
  turbulence values, with wall-zero exceptions explicit.
- CL/CD/Cmy peak-to-peak <=max(1e-4, 0.005 times absolute window mean).
- Relative net boundary mass flux <=1e-4 using total inflow.
- Area-weighted yPlus median <=1 and 95th percentile <=2; retain spatial deficits.
- Independent pressure-plus-viscous traction coefficients agree within 0.1%,
  using an absolute coefficient floor of 1e-6; verify moment origin and signs.
- A repeat agrees in window means within max(1e-4, 0.002 times absolute mean).

These checks are not yet automated by this generator. Unconverged cases remain
unconverged; do not relax gates to obtain a favorable result. Mesh/domain and
model sensitivity, reference comparisons and independent physical validation
remain separate work. No polar, flutter point or flight capability is established
by creating this setup.
