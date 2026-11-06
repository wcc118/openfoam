# Wing aerodynamics and aeroelastic engineering

Headless, evidence-driven aircraft analysis on DGX Spark and a PC.

Initial focus: generate a rigid wing, qualify an OpenFOAM runtime, and inspect
individual angle-of-attack cases before building a sweep or optimization loop.

## Start here

- [Current project status](docs/CURRENT_STATUS.md): delivered evidence, active work and outstanding PRs.

- [Engineering roadmap](docs/ENGINEERING_PLAN.md): stages, decisions, and evidence gates.
- [Rigid-wing MVP](docs/RIGID_WING_MVP.md): the first detailed analysis contract.
- [Reuse inventory](docs/REUSE_INVENTORY.md): existing code to inspect and adapt before writing replacements.
- [Environment observations](docs/ENVIRONMENT.md): actual setup status and runtime selection work.

## OpenFOAM Runtime Qualification

Run the OpenFOAM runtime qualification launcher:

```bash
python3 scripts/qualify_runtime.py --output runs/unique-name
```

**Pinned runtime (multi-arch):** `opencfd/openfoam-default@sha256:<digest>` (v2412, native Linux)

- **Linux/arm64**: `b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4`
- **Linux/amd64**: `adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b`

- [Runtime qualification documentation](docs/RUNTIME_QUALIFICATION.md): usage, acceptance criteria, and output artifacts.

This module verifies the Docker-based OpenFOAM runtime with the cavity tutorial.
Passing acceptance criteria confirms the runtime is operational but does not
validate physical accuracy or flight capability.

## Wing surface

```bash
python3 scripts/generate_wing.py --output runs/wing-unique
```

Open the resulting `preview.html` in a browser. See [geometry checks and native evidence](docs/WING_GEOMETRY.md) and [PC compute integration](docs/PC_COMPUTE.md).

For achieved wall-layer coverage and retained checkMesh results, use the
[mesh evidence reader](docs/MESH_EVIDENCE.md). This limited gate does not establish
near-wall resolution, flow convergence, or physical validity.
See the [mesh acceptance contract](docs/MESH_ACCEPTANCE.md) for numerical checks,
extended diagnostics and required coverage before a first flow run.

## First-flow case setup

Generate a complete OpenFOAM case for first-flow analysis:

```bash
python3 scripts/generate_flow_case.py --mesh-dir MESH_DIR --output CASE_DIR
```

See the [first-flow case documentation](docs/FIRST_FLOW_CASE.md) for usage,
boundary conditions, solver settings, and reference values.

## Status

The structural/CFD pipeline has demonstrated a loaded first-bending reference and
several-cycle decay with a practical timestep comparison. A separate twenty-mode
CFD coupling protocol has passed short force, energy and mesh checks; it does not
establish multimode damping. Original-stiffness UVLM screening covers 60–250 knots,
with no growing resolved oscillatory pole in the assessed surrogate model.

Issue #45 has resumed for selected-speed CFD baseline qualification and conditional
dynamics. CFD stability remains unassessed at all twenty requested speeds. The
actual wing is not test-calibrated, and no flight envelope is established. See
[current status](docs/CURRENT_STATUS.md) and the
[three estimating milestones](docs/THREE_MILESTONE_CONTRACT.md).

GitHub issues are authoritative for work status. Plans describe intended behavior,
not completed capability. Private aircraft evidence stays private; a later public
demonstration must use separately selected shareable inputs.

Physical-time diagnostic data can be viewed with the offline [flow playback builder](docs/FLOW_PLAYBACK.md). This is visualization, not flow qualification.
