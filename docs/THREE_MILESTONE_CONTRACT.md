# Three estimating milestones

Owner authorizes continuing through loaded baseline, useful cyclic response and
bending/torsion airspeed/stiffness comparisons. These are estimating experiments,
not flight clearance. User-facing results use imperial units; canonical quantities
remain SI. The small existing nearest-shell moment defect is accepted and visible.

Primary owns equilibrium, coupling physics, model changes, runtime experiments and
interpretation. Reuse main907675c native preCICE/modal/transfer components, the
unchanged native source NPZ, and inspect pinned PR37 source28d70e8 for UVLM controls.
Do not merge unrelated pending PRs or import mutable sibling checkouts.

Loaded state must satisfy measured aerodynamic generalized loads versus structural
restoring loads within a reported practical residual. Frozen Q/K is an initial
estimate only. Check geometry at that pose and over the intended perturbation
range before interpreting cyclic response. Preserve geometry failures.

Cyclic classification needs several usable same-sign extrema about an explicitly
stated reference, with recorded fitting interval, frequency and growth rate. A
short, failed, guarded or nonoscillatory history is not stable flutter evidence.
Check practical timestep/coupling sensitivity rather than require negligible error.
Separate native live CFD, prescribed-motion, frozen-load and UVLM controls.

Design deltas must include torsional participation and distinguish a hypothetical
generalized-stiffness change from an actual physical structural redesign. Preserve
geometry/load reference and solver assumptions when comparing cases. No optimizer
or side-quest aerodynamic feature is added. Work-machine modal/tunnel correlation
and commercial adapters remain subsequent work.

## Estimating results, 2026-10-30/31

The loaded baseline, several-cycle native CFD response, and UVLM bending/torsion
comparisons are separate experiments. SI remains canonical; previews use inches,
pounds-force and knots. Raw outputs stay outside Git; compact assessments and
source hashes are in `docs/evidence/three-milestone-sources-20261030/`.

At 58.3 knots, the native first-bending loaded tip reference is 0.56790 in.
Measured aerodynamic modal force is 4.51352 lbf; total vertical aerodynamic force
is 12.32254 lbf. These are different quantities. The restoring-load mismatch is
0.01328%, after recomputing flow on the deformed surface. Gravity and structural
damping are omitted. Release starts 0.019685 in above this reference, from rest,
with the flow initialized at that release pose.

The scoped CFD mesh has 304,186 cells and no wall layers. Native-mode mapping
retains the original 1 mm guard: measured maximum mismatch is 0.002497 in.
Sampled mesh quality passed at the loaded/release poses and through 0.59055 in;
0.62992 in and 1.10236 in pose trials failed and remain recorded. These are mesh
handling limits, not physical structural limits.

The coarse coupled release completes 1,300 steps through 0.65 s. Both solvers
returned zero, but reconstruction initially failed because step 1,300 was not a
field-write step. Original failure evidence remains intact. Separate recovery
reconstructs saved fields through 0.60 s, with seven sampled mesh passes. Fits
and matched-motion comparisons exclude the unsaved tail; raw motion through
0.65 s is retained and plotted. Future driver writes use gcd(steps, 200) so the
terminal step receives full fields. This does not alter the already-run physics.

| Native CFD timestep | Fit interval (s) | Growth (1/s) | Frequency (Hz) | Positive peaks | Fitted center (in) |
|---|---|---:|---:|---:|---:|
| 0.50 ms | 0.05–0.60 | -5.06536 | 8.85657 | 5 | 0.56499 |
| 0.50 ms | 0.15–0.60 | -5.06700 | 8.85656 | 4 | 0.56499 |
| 0.25 ms | 0.05–0.60 | -5.05083 | 8.83959 | 5 | 0.56546 |
| 0.25 ms | 0.15–0.60 | -5.05084 | 8.83964 | 4 | 0.56546 |

The fine run completes all 2,600 steps to 0.65 s with solver/postprocessing exit0,
two sampled mesh passes, and native force mismatch below 1.7e-13 lbf. Maximum
sampled wall-shape residual is approximately 4.4e-15 in; the saved wall matches
the previous structural step, as expected for the explicit scheme. Both runs
use identical initial flow fields. Halving timestep changes fitted growth by
0.29–0.32% and frequency by 0.19%; maximum common-time displacement difference
is 0.000801 in. Maximum Courant numbers are 9.24 and 4.62 respectively. These
are practical timestep checks on the scoped no-layer mesh, not spatial or
viscous-flow validation.

Two fitting starts (0.05 and 0.15 s) and independent positive-peak fits are
reported. A fitted transient center is distinct from the steady SIMPLE reference;
coarse center is 0.56499 in, approximately 0.00291 in lower. Near-zero fitted
rates within +/-0.05/s stay indeterminate: this is a diagnostic deadband, not a
physical error bar. No structural damping was added to obtain decay. Agreement on decay sign is
distinct from convergence of its magnitude; timestep differences are reported
as observed sensitivity, not a physical uncertainty bound.

A short implicit pilot provides a coupling check: 20 accepted windows, 233
rollbacks, maximum 14 iterations against a cap of 30, and two sampled mesh passes.
Its maximum tip difference from the matching explicit pilot is 0.00001364 in.
This 0.01 s control does not establish full-history implicit damping convergence.

For UVLM, the native fifth mode is predominantly torsional at 169.48 Hz. Scaling
its generalized stiffness to 1% while preserving modal mass/shapes gives 16.95 Hz;
this is a hypothetical parameter change, not a structural redesign. With ten
modes and a separately recomputed loaded reference, the softened model decays
at 38.9 knots (growth -2.250/s, about 13.41 Hz) and grows at 48.6 knots
(+3.430/s, about 11.45 Hz). The original-stiffness 48.6-knot comparison decays.
Halving UVLM timestep preserves these signs; selected growth rates change by
less than 0.2%. The 58.3-knot softened case hits its displacement guard and is
retained as guarded growth, not an unrestricted completed or stable run.

Matched-motion comparison uses the CFD initial geometry and recorded explicit
wall lag. It prescribes that motion to a 40-state UVLM aerodynamic model, rather
than comparing unrelated free-response paths. UVLM's starting modal force is
10.86% lower. Over 0.05–0.60 s the coarse incremental-load RMS difference is
0.02314 lbf (0.01934 lbf for the finer CFD path). This load-comparison metric
remains more timestep-sensitive than the fitted motion decay. The CFD transient also contains flow-initialization relaxation;
subtracting each model's starting force does not remove that effect. A short,
separately verified frozen-wall control helps identify it. The 40-state transfer
error at first-bending frequency is 0.67% relative to the full UVLM model;
this reduction check is not CFD accuracy evidence. Closed viscous surface vs
inviscid camber surface, wake and turbulence assumptions remain different.
Nonperiodic release work is not a converged periodic damping coefficient.

The native CFD results currently cover one bending mode. Torsional participation
and deliberate instability are demonstrated in UVLM. These experiments support
pipeline operation and design-delta exploration, not a real wing flutter limit.
The original issue's stricter periodic-repeatability/viscous qualification remains
open. Next work is measured modal/tunnel correlation and a deliberate multimode
CFD extension; NX Nastran, STAR-CCM+ and FlightStream adapters remain future work.
