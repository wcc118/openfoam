# Rigid-wing MVP contract

Goal: make individual generated-wing OpenFOAM cases interpretable and reproducible,
then assemble a small reviewed angle-of-attack study. No optimization or FSI yet.

## Starting geometry and conditions

Provisional demonstration: isolated unswept rectangular NACA 4412 wing, 1.2192 m
total span, 0.1016 m chord, zero geometric twist; S = 0.12387072 m^2. These reuse
conceptual dimensions from flight-loads, not a certified geometry or a design choice.
For this isolated wing, total span is unambiguous: no fuselage gap/root-spacing addition.
The parent aircraft reference-area convention must be mapped explicitly at integration.
Choose a symmetric NACA 0012 verification case as well; zero lift at zero incidence
is a useful symmetry check there, but is not expected for the cambered 4412.

Choose airfoil point spacing, tip caps, and finite/sharp trailing-edge handling
explicitly. Audit existing airfoil generation before reuse. Generate a watertight
surface and inspect sections and a browser-compatible preview before volume meshing.

Provisional initial angles: -4, 0, 4, 8 degrees. These are demonstration points,
not an assertion that all remain attached. Qualify one 0 or 4 degree case first.
Start with a declared low-Mach condition (for example 30 m/s at ISA sea level),
then a separately labeled 250 KTAS/ISA-sea-level demonstration: 128.611 m/s,
approximately Mach 0.38. This is not the owner's unresolved dive condition.
Record Reynolds number, Mach, density, viscosity, temperature, and pressure for
every case. Do not use incompressible assumptions at the upper speed without
quantifying their suitability. A low-speed case has different Reynolds/transition
behavior and is not a validation of the high-speed case.

## Geometry and flow coordinate contract

Declare CFD axes explicitly; proposed axes are x downstream from leading to
trailing edge, y along span, z upward. Positive incidence uses incoming fluid
velocity U = V*(cos(alpha), 0, sin(alpha)) with stationary geometry.
Drag direction d = (cos(alpha),0,sin(alpha)); lift direction l = (-sin(alpha),0,cos(alpha)).
Report force ON the wing. Fix moment origin at the midspan quarter-chord and record
the moment vector and sign convention; do not assume CFD and flight-loads axes match.
At alpha=0, transformation to flight-loads body axes (x forward,y right,z down)
is diag(-1,1,-1) if span orientation is matched. Verify with known force/moment vectors.

q = 0.5*rho*V^2; CL = dot(F,l)/(q*S); CD = dot(F,d)/(q*S).
Moment coefficients use declared axis and q*S*c. Preserve reference values in outputs.
Pressure may be dimensional or kinematic depending on solver; verify units and
reference pressure before integrating. Include viscous traction as well as pressure.
Half-wing models must explicitly document area, force, and moment scaling; prefer
a full wing for initial clarity and use symmetry only after a comparison check.

## Mesh and model qualification

- External domain with documented upstream, downstream, lateral and vertical extents;
  compare enlarged-domain results rather than accepting a default box on faith.
- Surface refinement at leading/trailing edges and tips; wake refinement downstream.
- Layered near-wall mesh. For a wall-resolved RANS baseline target y+ near 1, calculate
  initial cell spacing, check achieved y+ distribution, layer coverage and total thickness.
  Record failed layer insertion; never silently accept a nominal setting as achieved.
- Candidate turbulence baseline: SST with near-wall conditions appropriate to the
  chosen solver. Fully turbulent is an assumption; assess transition/roughness
  sensitivity and reference data especially at small chord Reynolds numbers.
- Record checkMesh results, cell counts, quality statistics, boundary patch names,
  and inspected slices through leading edge, trailing edge, tip, and wake.
- Use at least three systematically related resolutions at representative conditions;
  report CL/CD/Cm and pressure/span-load changes. Estimate convergence order only
  if the results justify it. Study domain size separately.

## Individual solve and acceptance evidence

Choose the exact solver, numerical schemes, BCs, convergence window, mass-balance
tolerance and force/moment tolerances in the implementation issue before production
runs. The plan deliberately does not fabricate case-independent accuracy thresholds.

Retain solver residual histories AND CL/CD/Cm histories. Check flux/mass balance,
finite/bounded fields, solver warnings, force stabilization, and independent force
integration/normalization. Compare a tighter numerical setting on representative cases.
If steady loads do not settle, preserve that result; do not call the last iterate a
converged polar. Decide whether a transient solve with timestep and averaging-window
sensitivity is appropriate. Report mean, variability, and sampling interval explicitly.

Cross-check sectional Cp/polars against applicable reference data or XFOIL, and
finite-wing trends/spanwise loads against existing AVL/VLM where their assumptions
hold. Section drag is not total finite-wing drag. Match geometry, Re/Mach, transition,
reference axes, and normalizations. Acquire independently sourced experimental data
with uncertainty and conditions before claiming physical validation.

## Run artifact contract

For each case retain:
- run ID, UTC timestamps, source revision and clean/dirty state;
- exact geometry/flow/model inputs with units and hashes;
- runtime/build/compiler or image identity, machine architecture and resource limits;
- complete generated case dictionaries and geometry/mesh hashes, mesh statistics;
- command lines, exit codes, logs, residuals, forces, moments, Cp and spanwise loads;
- quality/convergence/sensitivity checks, assumptions, warnings and evidence level;
- immutable output location, summary JSON/CSV and lightweight visual report.

Do not commit large meshes/fields to Git. Keep small manifests and reviewed evidence
summaries in Git with content hashes and retrievable artifact locations. A rerun must
use a new run ID, preserve the original, and agree within predeclared tolerances.

## Completion

MVP acceptance requires a reproducible runtime, generated and inspected wing,
individually reviewed AoA points, mesh/domain evidence at representative conditions,
independent comparison, and a report that states what the results do and do not show.
Unconverged points remain explicit failures/unresolved cases; they are not interpolated
away. Passing this gate permits a bounded sweep wrapper, not a flutter/250-kt claim.
