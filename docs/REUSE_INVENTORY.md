# Reuse inventory

Inspected 2026-10-24. This is a scoped inventory of relevant existing engineering
assets, not a claim that every project or function has been audited. Inspect and
run relevant verification before adoption. Local worktrees are not separate products.

## Primary source: flight-loads

Path: /home/connellwc83/projects/panel_solver
Repository: wcc118/flight-loads
Inspected HEAD: 7fe19f0761e00dd54238100461effa2533fc62c8 (clean at inspection).
GitHub: https://github.com/wcc118/flight-loads

Paths below are relative to that repository; source names identify candidates,
not a blanket claim of verification or portability.

| Need | Existing source | Reuse decision / limit |
| --- | --- | --- |
| Vehicle input provenance | VEHICLE_NOTES.md; data/vehicles; aircraft_workspace.py | Reuse conceptual dimensions and input distinctions; generate fresh geometry, do not import old CAD |
| Atmosphere and flow state | src/flightloads/atmosphere.py; aero_dataset.py:flow_state | Adapt through explicit imperial/SI conversions, verify outputs before CFD use |
| Frames and mass/load accounting | conventions.py, mass.py, loads.py, recovery.py under src/flightloads; docs/mechanics/CONVENTIONS.md | Preserve force/moment origins and frame transforms; do not invent a conflicting convention |
| AVL geometry and loads | src/flightloads/avl_model.py; third_party/aero_engines.json | Existing feet-based geometry, axis transforms, strip forces and engine manifests; use as lower-order cross-check within bounds |
| Section polars | src/flightloads/xfoil_polars.py; third_party/aero_engines.json | Reuse runner/hash/parser concepts; known transition-output issue below |
| Aerodynamic data/provenance | src/flightloads/aero_dataset.py; aero_snapshot.py | Located loads, dataset hashes, evidence labels, bounded snapshots; consider CFD export adapter rather than a competing dataset system |
| Elastic reference | src/flightloads/beam.py; aircraft_structure.py; wing_elastic_production.py | Existing bending and modal infrastructure; production adapter explicitly omits torsion/axial/chordwise response and is not a flutter solver |
| Reporting/workspace | src/flightloads/workbench.py; dashboard.py; saved_review.py; docs/mechanics/BENCHMARK_RUN.md | Reuse presentation/archive patterns after individual CFD outputs are credible; no new general dashboard in MVP |
| Verification and uncertainty | scripts/verify_*.py; src/flightloads/uncertainty.py, monte_carlo.py | Reuse evidence conventions and bounded-study patterns; do not assume model-validity transfers |

Important live limitation: flight-loads issue #243 is OPEN. The pinned XFOIL run
can emit out-of-range Bot_Xtr/transition columns. The issue reports CL/CD/CDp/CM
agreement with console for its observed case, not universal solver validation.
Never use the affected transition output as boundary-layer validation evidence.
Source: https://github.com/wcc118/flight-loads/issues/243 (inspected 2026-10-24).

The many panel_solver-wt-* directories, flight-loads-stubby-baseline, and
flight-loads-envelope-dashboard are related work areas. Resume from authoritative
GitHub state; do not copy stale worktree implementations over current ones.

## Earlier panel-method project

Path: /home/connellwc83/projects/aero
Inspected HEAD: 79c1236252fe12e0518384a33cd45c181e2df740.

- panel_solver/geometry.py: airfoil generation/import and transformations.
- panel_solver/solver_vlm/geometry.py and steady.py: finite-wing representations.
- panel_solver/solver_vlm/unsteady.py: candidate future unsteady work, NOT qualified
  for flutter. Its module and class documentation disagree about wake convection;
  resolve actual behavior and benchmarks before use.
- panel_solver/validation and test_geometry*.py: candidates for independent checks.
- panel_solver/aero_gui: existing browser presentation; do not confuse this with
  /home/connellwc83/projects/aero_gui, which contains only a static directory at inspection.

Directly inspected geometry code includes a thickness helper using twice a single
surface ordinate. That is not a general upper-minus-lower thickness calculation for
cambered sections. Audit selected functions rather than importing this module as a
trusted geometry authority. New export must establish watertightness and tip closure;
airfoil coordinates alone do not provide either.

## Other relevant infrastructure

- /home/connellwc83/projects/digitizer, HEAD
  84c557ffcd86f2838eb84542236be39659b95dab: README documents calibrated image-to-curve
  workflows, deterministic JSON/CSV exports and no extrapolation. Candidate for
  extracting published comparison curves; retain source rights, calibration and
  digitization uncertainty. Not a substitute for raw experimental data.
- /home/connellwc83/projects/memory/MEMORY.md: shared sourced findings and preferences;
  retain applicability and source revisions. No matching OpenFOAM memory found in
  the initial search. GitHub and current source remain authoritative.
- Existing codex-local-* harness: use installed worker routing, issue logs, sequential
  independent review and completion acknowledgments. Do not build a second agent runtime.
- tlm, wolverine, xplane, drive-sys: empty at top-level inspection; no reusable solver
  was identified there. LG48 contains evidence; its contents were not assessed here.
- REA and other non-aerodynamic projects were not exhaustively inspected. Revisit
  narrowly when a specific integration need arises; avoid copying unrelated infrastructure.

## Structural analysis solver

**MYSTRAN**
- Path: https://github.com/MystranSolver/MYSTRANSolver
- Source tag commit: 3a5913a904ee1adbda9fbcaf9c0a6af8e10f0f9f (MIT)
- Repository: wcc118/openfoam issue #24 structural benchmarks
- Version: 19.0.0

| Need | Existing source | Reuse decision / limit |
| --- | --- | --- |
| Structural solver | MYSTRAN 19.0.0 solver source | Use as native executable; build separately (not from this repository) |
| Deck format | Nastran free-field (NASTRAN compatibility) | MYSTRAN supports GRID, CBAR, PBAR, MAT1, SPC1, FORCE2, MOMENT2, LOAD, EIGRL |
| BDF card compatibility | dev_docs/bdf_card_compatibility.md | No CBEAM, PBEAM, MOMENT1, FORCE1 support; OFFT not supported for CBAR |
| Static analysis | SOL101 | Supported; used for bending/torsion benchmarks |
| Modal analysis | SOL103 | Supported via EIGRL; used for eigenmode benchmarks |
| Flutter prediction | Not available | MYSTRAN does not provide flutter analysis capability |

**Limitations:**
- No flutter prediction (separate aeroelastic solver required)
- No CBEAM/PBEAM support (use CBAR/PBAR)
- No moment/force cards with line 2 (MOMENT1/FORCE1 unsupported)

## Integration rule

Before implementing each component, record reuse/adapt/new and its rationale in the
issue. Prefer a pinned package interface or a versioned export. If extracting a small
module is appropriate, preserve attribution/license and tests and document the fork
boundary. Never commit absolute-path dependencies, credentials, or private source data.
Do not modify upstream projects without a separately scoped issue. Only write genuinely
new pieces where existing assets cannot meet the contract (notably OpenFOAM cases,
volume meshing, force extraction and runtime qualification).
