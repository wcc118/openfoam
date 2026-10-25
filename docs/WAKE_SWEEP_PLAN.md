# Wake envelope sweep plan

Planning baseline: 2026-10-25. Issue #5. Status: accepted plan; trial29/trial30 parameters documented, outcome pending.

## Objective

Establish wake visualization diagnostic distinct from complete aerodynamic qualification, FSI, or flutter analysis.
Focus on resolved wake volume and structure for angle-of-attack sensitivity studies.

## Current limitation

Existing 34-frame transient ends at 0.226ms (0.067 chord transits); this is initial adjustment from unconverged
baseline, not a developed wake. Longer transients require frequent full-restart checkpoints before timeout.

## Accepted mesh parameters: trial29

- **Outer domain**: fixed isolation domain (same as trial12 baseline).
- **Snappy octree levels** with 2:1 size jumps; more buffer cells to space transitions, not continuously graded cells.
- **Distance envelope**: 20/60/120 mm → levels 4/3/2 respectively.
- **Surface feature**: level 7; first layers 12 → 15, first layer 20 μm, adaptive final fraction 0.1.
- **nCellsBetweenLevels**: 5 (buffer cells to space level transitions).
- **Target cell count**: ~6 million cap; trial29 intentionally stopped at exit 137 (resource limit), not OOM.
- **No OOM-proof guarantee**: this is an exploratory parameter set, not a resolved configuration.

## Accepted mesh parameters: trial30 (proposed revision)

Narrows level-4 tip corridors and extends wake regions to improve containment per angle:

- **Level-4 tip corridor**: x 0.03..0.6, |y| 0.56..0.67, z -0.07..0.16 m.
- **Level-3 wake**: x 0.08..0.8, y ±0.75, z -0.12..0.24 m.
- **Level-2 outer wake**: x 0.1..1.2, y ±0.8, z -0.18..0.35 m.
- **All other parameters**: identical to trial29.

Trial30 outcome is PENDING; see issue #5 for status.

## Angle-of-attack study sequence

1. **Refinement inspection**: examine trial29/trial30 mesh sections, verify gradual transition to far field.
2. **Baseline**: settled 4° case with meaningful transient duration (chord/wake-transit times).
3. **Matched angles**: run -4, 0, 4, 8, 12 degrees at current provisional 30 m/s.
4. **Sensitivity**: mesh/domain/time-step variation on selected cases.

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

## Tools and reuse

- **Native runners**: reuse existing OpenFOAM scripts.
- **Meshparser**: reuse `scripts/summarize_mesh.py`.
- **Viewer**: reuse `scripts/build_flow_playback.py`.
- **Forceextractor**: reuse existing force extraction tooling.
- **Flight-loads**: reuse atmosphere, data/provenance, load conventions, lower-order aero.

No new solver or dashboard framework; lightweight per-case scripts appropriate.

## Acceptance criteria

This plan is accepted when:

- `docs/WAKE_SWEEP_PLAN.md` created with clear prospective vs observed.
- `docs/ENGINEERING_PLAN.md` updated with one link to this document.
- Trial29/trial30 parameters accurately documented as experiment configurations, not outcomes.
- Units, limits, and reference frames explicit.
- Issue #5 and primary sources linked.

No CFD execution, code changes, or dependency additions required for this documentation delivery.

## Evidence and provenance

- Trial29: experiment parameter set, stopped at 6M cell cap (exit 137), outcome PENDING.
- Trial30: proposed refinement to trial29 tip/wake corridors, outcome PENDING.
- All trials use pinned OpenCFD v2412 native ARM64; same outer domain for isolation.
- Boundary-distance sensitivity remains outstanding; wakepath containment must be checked per angle.

## Limitations

- This plan documents mesh and simulation parameters; it does not validate flow results.
- Wake visualization quality depends on achieved mesh, convergence, and transient duration.
- RANS turbulence modeling uncertainty remains; no claim of resolved eddy structure.
- No flutter or structural qualification implied by this wake diagnostic.
