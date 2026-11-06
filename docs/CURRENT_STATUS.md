# Current project status

Checkpoint: 2026-11-06. [GitHub issues](https://github.com/wcc118/openfoam/issues)
and their latest evidence comments remain authoritative. This summary distinguishes
working components from numerical qualification and actual-wing validation.

## Delivered capability

- Pinned OpenCFD v2412 runtime and generated wing geometry have documented checks.
  Rigid-wing flow and angle viewers exist, but the aerodynamic qualification gates
  in [#4](https://github.com/wcc118/openfoam/issues/4) and
  [#5](https://github.com/wcc118/openfoam/issues/5) remain unfinished.
- The owner-selected hollow aluminum structural surrogate has native bending and
  torsional modes and checked modal/load interfaces. It is not a calibrated model
  of the actual composite wing, overlap joint or aileron system.
- The [three estimating milestones](THREE_MILESTONE_CONTRACT.md), delivered through
  merged PRs [#43](https://github.com/wcc118/openfoam/pull/43) and
  [#44](https://github.com/wcc118/openfoam/pull/44), include a loaded first-bending
  CFD reference at 58.3 knots (0.56790 in tip displacement) and several-cycle
  releases near 8.84–8.86 Hz. Halving timestep changed fitted decay rate by
  0.29–0.32%. These no-wall-layer results do not establish spatial/viscous
  convergence or a complete flutter boundary.
- Separate UVLM experiments demonstrate decay/growth under explicitly hypothetical
  torsional softening. That is an instability demonstration, not a physical redesign.
- Merged [PR #46](https://github.com/wcc118/openfoam/pull/46) adds an experimental
  multimode CFD participant. Twenty-original-mode explicit and implicit coupling
  protocols passed force, energy and sampled mesh checks over **1 ms**. That short
  check does not establish multimode damping or flutter.

## Current engineering priority: original stiffness

[#45](https://github.com/wcc118/openfoam/issues/45) requests 60–250 knots in
10-knot increments, preserving original masses/stiffnesses and 15 lbf lift per
half-wing. Each solver must establish its own loaded equilibrium and angle of
attack; perturbations hold that angle fixed. This is a clamped-wing load condition,
not full-aircraft trim.

UVLM screening covers all twenty speeds. No growing resolved oscillatory pole
was found in the assessed symmetric, incompressible surrogate model. Modal,
time and lattice checks do not make its small, spatially sensitive damping a
validated physical prediction. CFD stability remains **unassessed at every speed**.

The owner paused PC computation on October 31 and explicitly resumed it on
November 6. The [selected-speed plan](https://github.com/wcc118/openfoam/issues/45#issuecomment-6678387889)
prioritizes:

1. Matched 60-knot numerical controls, pressure-reference checks and loaded balance.
2. The 250-knot candidate mesh/mode map and compressible loaded reference, then
   the corresponding 150-knot checks.
3. Measured sustained cost and bounded processor/timestep comparisons.
4. Conditional dynamic histories at 60, 250 and 150 knots, long enough to assess
   modal participation and growth/decay, only after prerequisites pass.

The [first resumed checkpoint](https://github.com/wcc118/openfoam/issues/45#issuecomment-6678705245)
records a completed matched compressible 60-knot control at 30.08709 lbf versus
29.99967 lbf for the earlier incompressible reference, and passing native mapping
on the 250-knot candidate mesh. The 60-knot control still needs loaded-balance
adjustment; the 250-knot mapping result is not a CFD equilibrium. Consult later
issue comments for subsequent runs rather than interpreting this snapshot as live status.

Failed guards remain failures; original stiffness and acceptance limits are retained.
Three selected speeds do not exclude instability between them or cancel the eventual
twenty-speed request. Actual modal/tunnel data are later correlation/validation inputs,
not prerequisites for these explicitly scoped surrogate experiments. No optimization
loop or flight envelope is established.

## Issue and PR housekeeping

[#24](https://github.com/wcc118/openfoam/issues/24) remains the umbrella engineering
issue. #4/#5 are backlog; [#38](https://github.com/wcc118/openfoam/issues/38) remains
backlog for periodic/viscous qualification. [#34](https://github.com/wcc118/openfoam/issues/34)
is closed after its accepted PR #35 merged into the structural branch. #45 is resumed.

The November 6 comparison against main `3639042` found unique material in every
older open PR below. None is automatically redundant or authorized to merge.

| PR | Retained work / disposition |
| --- | --- |
| [#22](https://github.com/wcc118/openfoam/pull/22) | Dense-flow viewer and documentation remain absent from main; retain for integration review. |
| [#23](https://github.com/wcc118/openfoam/pull/23) | Native 3D viewer, vendor licenses and checks remain absent from main. |
| [#25](https://github.com/wcc118/openfoam/pull/25) | Structural benchmarks/evidence remain absent; reconcile shared inventory changes. |
| [#27](https://github.com/wcc118/openfoam/pull/27) | Surface-load transfer implementation, tests and documentation remain absent. |
| [#29](https://github.com/wcc118/openfoam/pull/29) | Modal integrator and tests match main; its explanatory documentation remains absent. |
| [#31](https://github.com/wcc118/openfoam/pull/31) | Modal-surface utility/tests match main; shell generator and structural documentation/evidence remain absent. |
| [#33](https://github.com/wcc118/openfoam/pull/33) | Standalone structural viewer and publication manifest remain absent. |
| [#37](https://github.com/wcc118/openfoam/pull/37) | UVLM implementation/evidence/viewers remain absent; stacked on #31 and requires its own review. |

Merge decisions require exact-head review and owner authorization. A merged child
PR or an artifact delivered to the PC does not imply every parent branch is in main.

## Evidence and navigation

- [Three estimating milestones](THREE_MILESTONE_CONTRACT.md): loaded response,
  timestep checks, retained failures and limits.
- [Earlier coupled baseline](COUPLED_BASELINE_20261030.md): historical short pilot,
  superseded in duration by the milestone releases, not rewritten as a long run.
- [Engineering plan](ENGINEERING_PLAN.md): historical stages and advancement gates.
- [Reuse inventory](REUSE_INVENTORY.md): provenance and integration boundaries.
- [PC compute](PC_COMPUTE.md): historical runtime/location evidence; current resource
  settings and archival actions are recorded on #45.
