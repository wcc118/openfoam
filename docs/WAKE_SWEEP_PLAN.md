# Wake envelope sweep plan

Planning baseline: 2026-10-25. Issue #5. Status: experimental parameters documented; trial29 REJECTED (refinement incomplete, reached cap6M), trial30 RUNNING/pending.

## Objective

Establish wake visualization diagnostic distinct from complete aerodynamic qualification, FSI, or flutter analysis.
Focus on resolved wake volume and structure for angle-of-attack sensitivity studies.

## Current limitation

Existing 34-frame transient ends at 0.226ms (0.067 chord transits); this is initial adjustment from unconverged
baseline, not a developed wake. Longer transients require frequent full-restart checkpoints before timeout.

## Experimental mesh parameters: trial29

- **Outer domain**: x [-0.508, 1.524], y [-1.1176, 1.1176], z [-0.508, 0.508] m (same as medium trial21, not trial12 baseline).
- **Snappy octree levels** with 2:1 size jumps; more buffer cells to space transitions, not continuously graded cells.
- **Distance envelope**: 20/60/120 mm → levels 4/3/2 respectively.
- **Wing SURFACE**: levels 5/6; FEATURE level 7; exactly 12 layers, first layer 20 μm, thicknessModel firstAndRelativeFinal, finalLayerThickness 0.15.
- **nCellsBetweenLevels**: 5 (buffer cells to space level transitions).
- **Refinement threshold**: 6 million cap; trial29 pre-subset actual 6,731,101 cells, refinement incomplete, exit 137 (resource limit), not OOM.
- **Native execution**: PC AMD64 OpenCFD v2412; 2 CPU / 12 GiB / 1100 s mesh bound.
- **NOT accepted/qualified mesh**: trial29 parameters did not meet quality gates; do not call accepted mesh.

## Experimental mesh parameters: trial30 (narrowing trial29 proposal)

Narrows level-4 tip corridors from trial29; wider wake domains unchanged from trial29 domain bounds:

- **Level-4 tip corridor**: x 0.03..0.8, |y| 0.53..0.72, z -0.12..0.24 m.
- **Level-3 wake**: x 0.08..0.8, y ±0.75, z -0.12..0.24 m.
- **Level-2 outer wake**: x 0.1..1.2, y ±0.8, z -0.18..0.35 m.
- **All other parameters**: identical to trial29 (12 layers, first 20 μm, finalLayerThickness 0.15, thicknessModel firstAndRelativeFinal).

Trial30 is RUNNING/pending; see issue #5 for status.

## Angle-of-attack study sequence

1. **Refinement inspection**: examine trial29/trial30 mesh sections, verify gradual transition to far field.
2. **Baseline**: settled 4° case with meaningful transient duration (chord/wake-transit times).
3. **Matched angles**: run -4, 0, 4, 8, 12 degrees at current provisional 30 m/s.
4. **Sensitivity**: mesh/domain/time-step variation on selected cases.

**Important**: Each angle is independently simulated; NO interpolation across angles. Stationary angle cases are NOT actual pitching trajectories. 12° is exploratory only. Separate unsteady/separated cases; do not force steady convergence.

All cases use:

- **Body frame**: x downstream, y span, z up.
- **Freestream**: U∞ = 30(cos α, 0, sin α) m/s.
- **Vector glyphs**: actual native per-case velocity fields, not rotated duplicates.
- **Visualization**: common camera, arrow scale, scalar ranges across cases; labeled freestream.
- **Preservation**: angle, mesh/source hashes, time, and evidence state retained.

## Numerical-quality requirements (unchanged)

- Capacity for wake volume prioritized over fine wall-drag accuracy.
- Native yPlus failures remain recorded; don't conflate diagnostic visualization with qualification.
- RANS models produce turbulence; no claim of resolved eddies from visualization.
- **Quality gate**: >= 90% wall AREA coverage required.
- **Visual diagnostic**: distinct from aerodynamic qualification; RANS effects of turbulent fluctuations; does not resolve all turbulent eddies.
- Surface flow influences wake even when wall-drag accuracy is not priority.

## Tools and reuse

- **Native runners**: reuse existing OpenFOAM scripts.
- **Meshparser**: reuse `scripts/summarize_mesh.py`.
- **Viewer**: reuse `scripts/build_flow_playback.py`.
- **Forceextractor**: reuse existing force extraction tooling.
- **Flight-loads**: reuse atmosphere, data/provenance, load conventions, lower-order aero.

No new solver or dashboard framework; lightweight per-case scripts appropriate.

## Acceptance criteria

This plan is accepted when engineering milestones are reached:

- Inspect achieved mesh quality and wall-area coverage (>= 90% gate).
- Settled baseline with meaningful transient duration and checkpoints.
- Actual per-case velocity vectors visualized.
- Mesh/domain/timestep sensitivity verified.

**Not acceptance**: claim of completed study, converged solution, or validated results. Document evidence and uncertainty.

## Evidence and provenance

- Trial29: experimental parameter set, pre-subset 6,731,101 cells, refinement incomplete, exit 137 (resource limit, cap6M overshoot), REJECTED; not OOM.
- Trial30: proposed refinement to trial29 tip/wake corridors, RUNNING/pending.
- All trials use pinned OpenCFD v2412 native AMD64; domain x [-0.508, 1.524], y [-1.1176, 1.1176], z [-0.508, 0.508] m.
- Boundary-distance sensitivity remains outstanding; wakepath containment must be checked per angle.

**GitHub issue and comments**: [wcc118/openfoam#5](https://github.com/wcc118/openfoam/issues/5); primary comments: [#6400333629](https://github.com/wcc118/openfoam/issues/5#issuecomment-6400333629), [#6400372310](https://github.com/wcc118/openfoam/issues/5#issuecomment-6400372310), [#6400409920](https://github.com/wcc118/openfoam/issues/5#issuecomment-6400409920).

## Limitations

- This plan documents mesh and simulation parameters; it does not validate flow results.
- Wake visualization quality depends on achieved mesh, convergence, and transient duration.
- RANS turbulence modeling uncertainty remains; no claim of resolved eddy structure.
- No flutter or structural qualification implied by this wake diagnostic.
