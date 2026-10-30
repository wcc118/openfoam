# Stable and unstable aeroelastic motion

Issue36, PR37, 2026-10-30 overnight continuation. Both previews contain actual
integrated coupled responses. The original aluminum baseline remains unchanged.
These are linear modal–UVLM experiments, not flight-clearance results.

## What to open

- `viewers/goland-instability-comparison.html`: verified benchmark, 150 versus175m/s.
- `viewers/wing-instability-comparison.html`: hypothetical soft-torsion wing,
  20 versus25m/s, using the finer M12/N24 aerodynamic grid and20 structural modes.
- [Computed histories and growth curves](evidence/instability-comparison-20261030.png).

The previews use a shared clock, camera, magnification, displacement colors and
physical trace axes. Play at0.1× or scrub toward the end to see increasing twist
and bending. Magnification changes the drawing, not the measured displacement.
The wireframe is the undeformed reference. Benchmark geometry is its aerodynamic
lattice; the wing diagnostic displays the native shell surface.

## Two different models

The Goland benchmark reuses the pinned native MYSTRAN two-mode export and verified
projected aerodynamic matrices from the earlier temporal study. Native frequencies
are7.63739 and15.21947Hz. The flat, unloaded reference is an equilibrium. Its
full mirrored generalized mass is one; native half-wing amplitudes are q/sqrt(2).
The new initial condition is exactly0.1mm mean tip bending displacement and zero
physical velocity, including Newmark feedthrough and zero raw incremental
circulation. It is integrated for two seconds rather than synthesized from an
exponential. Density is1.02kg/m³, chord1.8288m, semispan6.096m; incompressibility is
an explicit benchmark approximation even at these high speeds.

The wing diagnostic is deliberately hypothetical. It retains the original native
mode shapes, mass and all other modal stiffnesses, but multiplies the fifth
(torsion-dominated) generalized stiffness by0.01. Its frequency therefore drops
from169.4779 to16.94779Hz; first bending stays8.810675Hz. The aerodynamic reference
is explicitly flattened to zero camber, giving zero static load at zero incidence.
The original paired-skin displacement map is retained, with its transpose for
forces. This isolates coupling behavior; it is not a realizable material/geometry
redesign, a new MYSTRAN solve, or the original loaded cambered aluminum wing.
Density is1.225kg/m³, chord0.1016m and semispan1.2192m. Initial tip bending is0.01mm,
with zero velocity and zero raw incremental circulation.

Physical structural damping is zero in both models. Causal UVLM feedback changes
the force with displacement, velocity and circulation/wake history. Structural
mode shapes/stiffness remain fixed. No nonlinear saturation or limit cycle is
predicted. Both displayed unstable cases have decaying real poles: the observed
growth is oscillatory, not static divergence.

## Observed response

| Model / speed | Tracked pole growth (1/s) | Frequency (Hz) | Late positive-peak fitted growth (1/s) |
|---|---:|---:|---:|
| Goland150m/s | -2.791951 |11.85355| -2.790383 |
| Goland175m/s | +2.822836 |10.89552| +2.822746 |
| Soft torsion M12/N24,20m/s | -2.281333 |13.58293| -2.219354 |
| Soft torsion M12/N24,25m/s | +2.847258 |11.45842| +2.847264 |

The stable soft-torsion transient contains multiple modes, so fitting one modal
coordinate's peaks differs by0.06198/s from the tracked eigenvalue. This discrepancy
is retained; a peak fit is not exact modal identification. The unstable history
agrees within6.5e-6/s. The least-damped stable pole is a weakly excited in-plane
mode near56Hz, distinct from this tracked bending–torsion branch.

The finer diagnostic grows from0.01mm initial tip bending to about0.772mm peak
absolute tip motion and0.359degrees twist over two seconds. The coarser M8/N16
case grows faster, reaching about2.41mm and1.13degrees. The Goland growing case
reaches about10.29mm and0.544degrees. None of these histories reaches its50mm
maximum displacement-component guard. The guard is an experimental stop, not a
physical allowable.

The tracked diagnostic branch has adjacent modal-state correlation above0.9993
at0.25m/s increments from20 to25m/s. At25m/s, first bending and fifth-mode torsion
account for nearly all of its normalized displacement/velocity modal-state norm.
Those fractions are not aerodynamic work fractions or strain-energy fractions.
Integrated aerodynamic work is positive in the growing cases and negative in
the decaying cases. The stored energy/work discrepancy reflects time integration
and trapezoidal power quadrature; it is not assumed to be identically zero.

## Numerical sensitivity and retained failures

| Soft-torsion configuration | Oscillatory crossing (m/s) |
|---|---:|
| M8/N16,10modes,CFL0.125,wake8chords |22.56975|
| M8/N16,10modes,CFL0.0625,wake8 |22.56643|
| M8/N16,20modes,CFL0.0625,wake8 |22.56636|
| M12/N24,20modes,CFL0.09375,wake8 |23.10665|
| M8/N16,20modes,CFL0.0625,wake12 |22.54561|
| M16/N32,20modes,CFL0.125,wake8 (later completed retry) |23.34976|

M12/N24 uses the same physical timestep as the M8/N16 CFL0.0625 case at any given
speed. Geometry and wake spacing remain fixed for the timestep comparison;
non-CFL1 wake propagation is explicitly assembled. The timestep change moves the
crossing about0.015%, mode-count change about0.0003%, and wake extension about0.092%.
Aerodynamic-grid refinement moves it about2.4%, so a fully converged boundary is
not claimed. This remaining sensitivity is much larger than root-finder precision.
Stable20/growing25m/s survives all these completed checks. The later M16/N32
run changes the crossing a further1.05% from M12/N24, still too much to claim
a converged threshold. At25m/s its growth is2.549896/s and peak-fit growth
2.549900/s; at20m/s the tracked branch decays at-2.536842/s while the mixed-mode
peak fit gives-2.458407/s. Both actual two-second histories stay below the guard.
[Supplemental evidence](evidence/instability-M16-supplement-20261030.json) retains
these results separately; the preview remains the explicitly labeled M12/N24 case.

Goland's fixed-mesh causal crossings are163.9402,163.7959,163.7182m/s at relative
steps1,0.5,0.25. The preview uses the quarter-step matrices. Independent original-
predictor descriptor stepping and causal-state stepping agree to about1.1e-11 in
the new growing benchmark response. Full-versus-reduced transfer checks for the
soft-torsion cases are recorded at zero, first-bending, near-response, softened-
torsion and highest retained native frequencies. At response/softened-torsion
frequencies the sampled relative Frobenius errors are below6e-6; high-frequency
errors reach a few percent. These are coordinate-norm samples, not broadband or
energy-weighted error bounds.

The broad stiffness scan also produces real-pole divergence at some higher
speeds. It is kept separate from flutter. The flat model with unchanged stiffness
has a tiny near56Hz sign crossing around94–95m/s that is not qualified here and
must not be transferred to the loaded cambered aluminum baseline.

An M16/N32 trial was stopped by the primary agent when shared Spark memory fell
below1GiB available during simultaneous local-worker/CFD activity. Exit137 is
recorded as an interrupted experiment, with no result. A later fresh M16/N32
run completed after host memory became available; it does not erase the failed
attempt. CFD meshing moved to the
PC. A first aligned-grid meshing attempt stalled in feature refinement; translating
the background grid by-5mm x/-3mm z progressed beyond that stage. This supports an
alignment hypothesis, not a general OpenFOAM defect diagnosis.

## Reproduction and verification

Primary numerical drivers: `scripts/experiments/instability_demo.py` and
`instability_checked_replay.py`. They reuse `coupled_system` and the existing
projected UVLM assembler. Run in image
`sha256:53f45db26c471d5d35b1aac8b77826f642f2b4dd74b8a1311838a3bb31e8de9a`,
with pinned SHARPy commit`a4154d471c30f15db9af6524763ea250bb46c7b8` mounted read-only
at`/src`, script directory read-only at`/experiment`, artifact directory at`/results`,
`PYTHONPATH=/src`, `OPENBLAS_NUM_THREADS=1`, and Docker networking disabled.

The artifact directory contains native-modal.npz, paired-skin camber-M*-N*.npz
exports, and earlier goland-cfl1-v2/goland-cfl05/goland-cfl025 model.npz files.
Hashes identify these inputs; no mutable sibling repository is imported.
Set MODEL=goland OUTPUT_CASE=benchmark for the benchmark sweep/replay.
Set MODEL=shell MODES=20 PANELS_M=12 PANELS_N=24 CFL=.09375 WAKE_FACTOR=8
OUTPUT_CASE=flat-M12N24-n20 for the finer diagnostic. Output directories must be
new. `instability_checked_replay.py` reads saved matrices; CASES is a comma-separated
list of model-directory names and creates new checked/ subdirectories. Exported
viewer-data.json feeds `scripts/build_equilibrium_comparison.py`.

Full solver histories, scripts, logs and browser checks remain under
`runs/instability-20261030/`. [Committed evidence](evidence/instability-demonstration-20261030.json)
contains reports, hashes and failures, not the large raw histories.203 repository
tests pass. Browser checks cover32 case/display-mode/time combinations across
both previews, both panels, native-basis physical metrics, shared camera,
magnification invariance, description-only/combined metadata, mobile layout and
no external network requests or JavaScript errors. Preview downsampling's maximum
tip error is below0.18% of each case's peak versus its full stored history.

PC exports are placed under`G:\projects\openfoam\viewers`; verify their hashes
against the source copies. Review/publication outcome is tracked on PR37; passing
local tests does not itself mean independent review or merge.
