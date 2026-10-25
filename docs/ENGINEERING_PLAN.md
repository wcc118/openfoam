# Engineering plan

Planning baseline: 2026-10-24. Issue #1. Status: proposed stages; no CFD results yet.

## Purpose and owner direction

Build a headless, reproducible capability to compare drone configurations, understand
performance and aeroelastic tradeoffs, and reduce uncertainty. Eventually Codex will
operate bounded studies and optimization batches through a programmatic interface.
First establish and inspect individual engineering components. Automation must
preserve their limitations rather than manufacture confidence by repetition.

Generate new parameterized geometry; do not require existing aircraft CAD. Reuse
existing project code, input conventions, measurements, and evidence where suitable.
The owner reports suspected aileron flutter/resonance near 140 kt and wing flutter
near 163 kt. These are observations reported in conversation, not independently
diagnosed mechanisms or validated calibration targets. Speed basis, altitude,
configuration, propulsion/control state, and recorded data remain unresolved.
The immediate design motivation is a 250 kt dive; the broader earlier aspiration
was analysis through 300 kt. Neither is an approved flight capability. Do not treat
a dive speed, pullout load, or sustained level-flight performance as interchangeable.

## Stages and advancement gates

| Stage | Deliverable | Gate before advancing |
| --- | --- | --- |
| A: runtime | Pinned headless OpenFOAM installation/build and reference case | Reproducible native ARM64 run, recorded version/build and observed outputs |
| B: geometry | Generated rigid finite wing and inspected surface | Analytic dimension/area checks, closed surface, normals, explicit axes and trailing-edge treatment |
| C: one flow case | Mesh, boundary conditions, solve, pressure and integrated loads | Mesh/near-wall checks, mass balance, force histories, independently reconstructed coefficients |
| D: AoA study | Individually reviewed negative/zero/positive-incidence cases and comparisons | Resolution/domain sensitivity and independent comparison with documented limits |
| E: structural model | Wing bending/torsion and later aileron/attachment dynamics | Analytic benchmarks, mass/stiffness checks, measured static/modal comparisons where available |
| F: static coupling | Equilibrium shape and load redistribution | Force/moment/work transfer checks and convergence of coupled equilibrium |
| G: dynamic aeroelasticity | Frequency/damping versus condition, mechanism hypotheses | Independent unsteady benchmark, timestep/modal/coupling sensitivity; correlate physical evidence |
| H: aircraft studies | Trim, propulsion, loads, mission comparisons, uncertainty | Qualified subsystem interfaces and operating limits; distinguish prescribed AoA from trimmed flight |
| I: bounded optimization | Reproducible batches and candidate promotion | Failed-case handling, budgets, uncertainty screening, higher-fidelity checks of finalists |

Stage A-D is the initial rigid-wing MVP. Lightweight per-case scripts are appropriate;
a general scheduler, optimizer, mesh-adaptive loop, or replacement dashboard is not.

Immediate backlog:
- [#2 Runtime qualification](https://github.com/wcc118/openfoam/issues/2)
- [#3 Generated wing geometry](https://github.com/wcc118/openfoam/issues/3)
- [#4 One checked flow case](https://github.com/wcc118/openfoam/issues/4)
- [#5 Reviewed AoA and sensitivity study](https://github.com/wcc118/openfoam/issues/5)

Stage E can start once its inputs/contracts are concrete; it does not require completing
every aerodynamic condition. Each stage must expose its own evidence and uncertainty.

## Mesh refinement and wake envelope

See [WAKE_SWEEP_PLAN.md](./WAKE_SWEEP_PLAN.md) for the experimental plan for mesh refinement
extending away from wing, gradual transition to far field, and 3D tip/wake visualization
for angle-of-attack sensitivity studies. Trial29 REJECTED (refinement incomplete, reached cap6M, exit 137);
trial30 RUNNING/pending. See issue #5 for status and primary comments.

## Technical direction

- Use OpenFOAM for detailed flow. Select the exact distribution/version after native
  ARM64 and intended solver compatibility checks; do not conflate Foundation and
  OpenCFD release numbering or assume dictionaries interchange.
- Prefer a CPU reference initially. PC/3090 GPU acceleration is a later measured
  optimization, not a prerequisite or a guaranteed speedup. Keep cases portable.
- Reuse flight-loads atmosphere, data/provenance, load conventions, lower-order aero,
  and reporting before creating new equivalents. See REUSE_INVENTORY.md.
- Candidate future structural/FSI stack is CalculiX + preCICE + OpenFOAM. This remains
  an architecture candidate until required elements, surface reconstruction, mesh
  motion, versions, and benchmarks work. No coupling is implied by installing tools.
- Common geometry/configuration generates separate aerodynamic and structural meshes.
  A beam axis or skin midsurface is not automatically the wetted aerodynamic surface.
- For dynamic work explicitly model wing torsion, mass distribution, attachment
  flexibility, and aileron inertia/hinge/actuator behavior; examine freeplay and
  control-loop effects when evidence requires them. Start with a simpler benchmark,
  but never generalize its stability to the assembled aircraft without support.

## Evidence and decisions

Every result separately records execution status, numerical checks, physical evidence,
and satisfaction of stated design constraints. "Converged" is not "validated".
Agreement with AVL/XFOIL is a cross-check, not independent experimental validation.
Do not fit arbitrary stiffness/damping until a model reproduces the two reported speeds.

At each stage ask: which design decision does this calculation inform, which inputs
dominate uncertainty, and which additional measurement or analysis would reduce it?
Set quantitative acceptance thresholds in the issue/case contract before judging
results; document changes and reasons, never silently relax gates to pass a run.

Future physical evidence includes static stiffness and ground modal characterization.
A model-produced flutter boundary is not flight clearance. Envelope expansion needs
appropriate independent engineering assessment and physical substantiation.

## Outputs for understanding and sharing

Each reviewed study has: configuration, question, assumptions, method, comparisons,
limitations, conclusion, and next evidence needed. Show surface pressure, spanwise
loading, force histories, and sensitivity alongside attractive geometry views.
Retain raw evidence with hashes and artifact locations; serve selected outputs in a
browser rather than transferring whole CFD volumes. Reuse the flight-loads workbench.
Public demonstrations use explicitly shareable configurations and data; no automatic
publication of private aircraft evidence or implied product certification.

## Durable execution

GitHub owns issues and review state; immutable run records own numerical evidence;
shared memory holds sourced reusable lessons. Local workers implement bounded tasks
and review independently; Codex retains cross-system and engineering decisions.
Prioritize stage completion and uncertainty reduction over infrastructure expansion.

References consulted 2026-10-24:
- https://precice.org/adapter-openfoam-support (version/adapter support must be checked)
- https://precice.org/configuration-mapping (nonmatching interface data transfer)
- https://www.nasa.gov/centers-and-facilities/armstrong/flight-and-ground-experimental-test-capabilities/ (ground modal testing and structural model correlation)

For offline inspection of independently simulated steady angles, see
[the angle-comparison viewer](ANGLE_COMPARISON.md). This viewer does not replace
the CFD convergence and sensitivity gates.
