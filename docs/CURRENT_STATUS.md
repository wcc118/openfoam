# Current status — 2026-11-06

> Documentation-only status checkpoint. This document summarizes the current
> state of the wing aerodynamics and aeroelastic engineering project as of
> the coupled CFD-modal baseline milestone. It is not a flight clearance,
> physical validation, or flutter qualification.

## Overview

The project has completed the rigid-wing MVP through the coupled CFD-modal
baseline and established estimating milestones for loaded response and UVLM
comparisons. The current state supports design-delta exploration and pipeline
operation, not actual-wing flutter prediction or flight capability.

## Completed stages

| Stage | Status | Key deliverables |
| --- | --- | --- |
| A: runtime | **Complete** | Pinned headless OpenCFD v2412 runtime verified on ARM64 and AMD64; cavity tutorial passes reproducibility gate |
| B: geometry | **Complete** | NACA 4412 closed-TE half-wing geometry generated; passes documented checks (surface closure, normals, axes) |
| C: one flow case | **Complete** | Mesh, boundary conditions, solve, pressure field, integrated loads; issue #4 remains for near-wall resolution validation |
| D: AoA study | **Complete** | Independent steady simulations at negative/zero/positive incidence; angle comparison viewer available; no interpolated fields |
| E: structural model | **Complete** | Modal system with mass-normalized bending mode; portable modal case fixture validated; modal_dynamics.py and modal_surface.py tested |
| F: static coupling | **Complete** | Loaded equilibrium baseline established; measured restoring/load residual 0.01328%; release from rest documented |
| G: dynamic aeroelasticity (estimating) | **Complete** | Native loaded response and UVLM bending/torsion comparisons delivered; decay/growth signs established; issue #38 remains for stricter periodic/viscous qualification |

## Current baseline

### Coupled CFD-modal baseline (issue #38)

- **Mode**: Native first-bending mode, q = mean tip z in metres
- **Frequency**: 8.810675 Hz
- **Mass**: 0.45423328577302213 kg (half-wing generalized)
- **Stiffness**: 1392.057119541888 N/m
- **Mesh**: 304,186 cells, no wall layers
- **Flow conditions**: 30 m/s TAS, zero incidence, k-omega SST, fully turbulent
- **Coupling**: OpenCFD–preCICE two-way feedback; explicit and implicit controls validated

### Loaded baseline results

At 58.3 knots:
- Native first-bending loaded tip reference: 0.56790 in
- Measured aerodynamic modal force: 4.51352 lbf
- Total vertical aerodynamic force: 12.32254 lbf
- Restoring-load mismatch: 0.01328%

### Cyclic response evidence

| Timestep | Fit interval (s) | Growth (1/s) | Frequency (Hz) | Peaks | Center (in) |
| --- | --- | --- | --- | --- | --- |
| 0.50 ms | 0.05–0.60 | -5.06536 | 8.85657 | 5 | 0.56499 |
| 0.25 ms | 0.05–0.60 | -5.05083 | 8.83959 | 5 | 0.56546 |

Halving timestep changes growth by 0.29–0.32% and frequency by 0.19%. These are
practical timestep checks, not asymptotic convergence or damping uncertainty.

### UVLM comparison

- **Native fifth mode**: Predominantly torsional at 169.48 Hz
- **Softened stiffness (1%)**: 16.95 Hz
- **Decay speed**: 38.9 knots (growth -2.250/s, ~13.41 Hz)
- **Growth speed**: 48.6 knots (growth +3.430/s, ~11.45 Hz)

UVLM demonstrates bending/torsion airspeed/stiffness comparisons; this is a
separate experiment from the matched native CFD loaded baseline.

## Open issues

| Issue | Status | Description |
| --- | --- | --- |
| #38 | **Backlog** | Stricter periodic/viscous qualification; periodic repeatability and flutter limit |
| #4 | **Backlog** | Near-wall resolution validation; wall-layer coverage and yPlus |
| #5 | **Backlog** | Angle-of-attack sweep; resolution/domain sensitivity |
| #2 | **Backlog** | Runtime qualification for flow cases |
| #3 | **Backlog** | Generated wing geometry for full aircraft |

## Active branches

| Branch | Purpose |
| --- | --- |
| `main` | Stable baseline; merged work |
| `issue-48-current-status` | Documentation-only status checkpoint |
| `issue-45-original-stiffness` | Original stiffness UVLM experiments (pending PR) |
| `issue-38-loaded-results` | Loaded CFD response and UVLM comparisons (pending PR) |
| `issue-38-coupled-baseline` | Native explicit and implicit coupled baseline (pending PR) |

## Evidence locations

| Artifact | Location |
| --- | --- |
| Coupled baseline evidence | `docs/evidence/coupled-baseline-20261030.json` |
| Native CFD milestone evidence | `docs/evidence/native-cfd-milestone-20261030.json` |
| Three milestone sources | `docs/evidence/three-milestone-sources-20261030/` |
| PC archive | `G:\projects\openfoam\build\three-milestone-results-20261030.tar.gz` |
| PC viewer | `G:\projects\openfoam\viewers\three-milestones-20261030\index.html` |

## Limitations and disclaimers

- **Not flight qualified**: No flutter prediction, physical validation, or flight
  capability has been demonstrated.
- **Estimating only**: Results support pipeline operation and design-delta
  exploration, not certification.
- **Torsion not represented**: The current native baseline uses one bending mode;
  torsional participation requires additional modes.
- **Short-window sensitivity**: Current runs cover 0.44% of a natural period;
  full-cycle damping and periodic stability remain open.
- **No wall layers**: The coupled baseline uses a no-layer mesh; near-wall
  resolution and yPlus remain unverified.

## Next steps

1. **Issue #38 follow-on**: Periodic repeatability, viscous qualification, and
   flutter limit with bending/torsion modes.
2. **Issue #4 follow-on**: Near-wall resolution validation with wall-layer mesh.
3. **Issue #5 follow-on**: Angle-of-attack sweep with resolution sensitivity.

## References

- [Engineering plan](ENGINEERING_PLAN.md): stages A-I with gates
- [Rigid-wing MVP](RIGID_WING_MVP.md): first detailed analysis contract
- [Three milestone contract](THREE_MILESTONE_CONTRACT.md): loaded baseline,
  cyclic response, UVLM comparisons
- [Coupled baseline](COUPLED_BASELINE_20261030.md): native explicit/implicit
  feedback pilot evidence
- [Native CFD milestone](NATIVE_CFD_MILESTONE_20261030.md): prescribed-motion
  CFD and transfer diagnostic evidence
