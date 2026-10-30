# Loaded-reference airspeed and mode-count sweep

Issue #36 / stacked PR #37, 2026-10-30. This advances the exploratory
[single-speed loaded-shell experiment](SHELL_LOADED_EQUILIBRIUM.md).
No OpenFOAM runs or new physical redesign were used.

The baseline .050-inch aluminum surrogate was tested at 10, 20, 30, 40, 50,
55, 60, 80 and 100 m/s with both 10 and 20 native structural modes. Each case
solves its own clamped loaded equilibrium before applying the same +1 mm first
bending mean-tip displacement, zero physical velocity and zero initial incremental
circulation. The structure has zero assumed damping. UVLM supplies unsteady
circulation/wake feedback about each loaded reference.

**All twelve completed histories (10–55 m/s, two mode counts) decay. No growing
coupled poles were found in these cases.** The visible first-bending motion
becomes more strongly damped with speed. The least-damped oscillatory mode is
instead around 56 Hz, and remains decaying in this model. This is not a flutter
boundary for the real wing, nor proof that every higher speed is stable.

| Speed (m/s) | Loaded tip z, 10 / 20 modes (mm) | First-bending growth, 10 / 20 (1/s) | First-bending frequency, 10 modes (Hz) |
|---:|---:|---:|---:|
| 10 | 1.4116 / 1.4116 | -1.5521 / -1.5521 | 8.8113 |
| 20 | 5.6274 / 5.6278 | -3.5562 / -3.5561 | 8.8531 |
| 30 | 12.5909 / 12.5923 | -5.6509 / -5.6507 | 8.8655 |
| 40 | 22.2085 / 22.2122 | -7.7672 / -7.7665 | 8.8624 |
| 50 | 34.3502 / 34.3586 | -9.9120 / -9.9108 | 8.8496 |
| 55 | 41.3171 / 41.3291 | -11.0003 / -10.9985 | 8.8402 |

Negative growth means decay of amplitude proportional to exp(growth × time).
These are tracked eigenvalue rates, not ratios of successive raw total-deflection
peaks. First-modal perturbation peak fits corroborate these rates. The dominant
resolved oscillatory rate is much closer to zero: about -0.0041 to -0.0217/s
across this range, near 56.2–56.4 Hz. It is distinct from the first-bending curve.
All real poles examined are decaying too, and there are no growing poles in the
excluded high-discrete-phase band. No crossing bracket was observed; none was
invented or extrapolated.

## Cases without a stability verdict

The experiment retains a 50 mm maximum absolute **native-node displacement
component**, not a physical allowable. Reference and initial disturbed shapes
are checked before assembling linear dynamics. Both mode counts exceed this
guard at 60, 80 and 100 m/s; the report records their solved reference shapes
but deliberately omits transient/pole stability results.

At 60 m/s, the 10-mode mean loaded tip z is 48.85 mm; the maximum node component
is 49.03 mm. Adding the standard 1 mm mean-tip disturbance produces a maximum
node component of **50.032 mm**, just over the declared guard. The 20-mode
initial maximum is 50.047 mm. Thus this is an experiment-boundary decision,
not a discovered physical instability. At 80 and 100 m/s, even the loaded
reference itself exceeds the guard (mean tip approximately 84 and 126 mm).
A smaller kick could examine 60 m/s without changing the guard, but that would
be a separate amplitude experiment. The present comparison keeps its kick fixed.

## Controlled settings and limits

All cases use the same baseline native shell mass, stiffness, material,
undeformed midsurface, clamp, and 30-mode source extraction; only the retained
basis changes (first 10 or 20 modes). Half-wing mass is 0.905143 kg. This is not
the previous thickness redesign. Aerodynamics: M8/N16 per half, eight-chord
straight wake, rho 1.225 kg/m³, one full mirrored surface, symmetric motion,
paired-skin camber mapping and full-mass normalization q/sqrt(2). No finite
fuselage, antisymmetric-wing mechanisms, measured structural damping, prestress
or nonlinear structural stiffness are introduced. Axes remain x downstream,
y span, z up; twist is the fitted small-angle rotation about +y.

CFL is fixed at .5, so the physical timestep varies with speed:
`dt = .5 × .1016 / (8 × V)` seconds. **This is not timestep convergence.**
The first bending frequency is well resolved by the structural integration,
but high modes show appreciable Newmark phase error at the lowest speeds.
For example, the 20th native frequency is 657.9004 Hz; the uncoupled discrete
Newmark frequency is 461.0242 Hz at 10 m/s, 620.1739 Hz at 30 m/s and
645.8228 Hz at 55 m/s. Agreement of 10/20 modes for this bending kick does not
qualify the high-frequency dynamics or arbitrary loading.

Krylov uses the same rank-six observability procedure. Its reduced aerodynamic
radius remains below one for every analyzed case. Full/reduced transfer
comparisons at zero frequency, the first, tenth and highest retained native
frequencies are recorded. Maximum sampled relative Frobenius error is 3.08%
for 10 modes and 0.636% for 20 modes. These norms use reference-speed projected displacement/velocity coordinates,
not an energy-weighted physical error bound. These sparse checks do not
establish broadband ROM convergence, especially where the timestep itself
poorly resolves higher native frequencies. Potential-flow attached-flow
assumptions remain; viscosity, separation and stall are not resolved.

## Verification and provenance

- 10-mode 30 m/s replay matches the previous loaded-perturbation q history to
  2.0e-16 maximum absolute coordinate difference.
- Equilibrium relative force residual is at most 1.22e-14 across the attempted
  grid, including guarded reference solves.
- The first-mode physical character fraction exceeds .999997 in completed
  cases. Adjacent tracked physical-shape MAC is at least .999637.
- First-modal transient peak fits differ from tracked pole growth by at most
  .00430/s and from frequency by less than .082%.
- In completed cases, 10/20-mode loaded tip differences stay below .0292%
  (largest absolute difference .0121 mm); perturbation tip histories differ
  by at most 5.71e-8 m. This is load-dependent agreement, not universal modal
  completeness.
- Physical initialization includes Newmark force feedthrough and the UVLM
  predictor conversion. Every completed case starts with +1 mm mean tip
  displacement relative to its own equilibrium and zero physical velocity.

The exact source is `scripts/experiments/shell_loaded_speed_sweep.py`, reusing
`modal_uvlm_explore.py` and `shell_loaded_equilibrium.py` with pinned SHARPy
commit `a4154d471c30f15db9af6524763ea250bb46c7b8` and container
`sha256:53f45db26c471d5d35b1aac8b77826f642f2b4dd74b8a1311838a3bb31e8de9a`.
Native modal inputs are the same MYSTRAN 19 results used in the preceding
loaded-equilibrium experiment, not new or frequency-scaled structural results.

Large artifacts remain under `runs/loaded-speed-sweep-20261030/`: native inputs,
`sweep/n{modes}-V{speed}/assessment.json`, actual `motion.json` and reduced
`model.npz` for completed cases, summary, raw logs and independent persisted-data
checks. The runner refuses an existing `sweep` output directory. Failed or guarded
cases retain explicit status and cannot silently become favorable data points.

Next useful numerical step: independent timestep refinement at fixed speed and
wake geometry, particularly for the higher modes and weakly damped 56 Hz branch.
A later amplitude-controlled 60 m/s experiment could extend the current guard
coverage. Neither a guard change nor higher-speed extrapolation is needed to
learn from this completed sweep.

## Preview and replay

[Speed sweep plots](evidence/shell-loaded-speed-sweep-20261030.png) distinguish
completed dynamics from guarded static solutions. Black dots show independently
fitted transient peaks; curves show coupled pole predictions.

Download [wing-speed-comparison.html](../viewers/wing-speed-comparison.html) and
open locally. It contains twelve actual histories, sorted by speed then retained
mode count. Compare 10 and 20 modes at the same speed, or compare different speeds
in perturbation mode to see the decay difference. Model keys `modes10` and
`modes20` refer to two retained bases of the same physical wing, not two thicknesses.
The generic comparison builder now accepts supplied model names while retaining
strict reference, dimensional, finite-value and common-time-interval validation.
The previous thickness viewer remains unchanged.

The PC export is `G:\projects\openfoam\viewers\wing-speed-comparison.html`,
with `wing-speed-sweep.png` alongside it. Both exports were SHA-256 verified.
The source payload stays outside Git and can be regenerated from native artifacts:

```sh
python3 scripts/experiments/export_loaded_speed_sweep.py runs/loaded-speed-sweep-20261030
python3 scripts/build_equilibrium_comparison.py \
  --data runs/loaded-speed-sweep-20261030/speed-comparison-data.json \
  --output viewers/wing-speed-comparison.html
```

The builder refuses existing output files. [Evidence JSON](evidence/shell-loaded-speed-sweep-20261030.json)
records reports, checks, source/artifact hashes and runtime provenance. All 193
repository tests pass. Headless Chromium checked both panels for 96 actual
case/display-mode/time combinations against independently computed NumPy values:
q interpolation, mean tip z, fitted twist, shared projection, magnification
invariance, unequal-speed history endpoint stopping, mobile horizontal layout
and zero external network requests. Browser and independent-check sources and
hashes are retained with the run.

The local export worker's first draft passed its limited tests but failed the
actual plotting CLI (missing pyplot binding) and parsed speeds from labels
containing `m/s`, producing empty curves. Primary corrected plotting to read
numerical report fields, preserve NaN gaps, display guarded static references,
and test actual curve coordinates and the default plotting CLI. Additional
validation rejects inconsistent history dimensions/times and insufficient native
basis sizes. The initial export log is retained; no solver results were changed.
