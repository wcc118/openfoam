# Wing aerodynamics and aeroelastic engineering

Headless, evidence-driven aircraft analysis on DGX Spark and a PC.

Initial focus: generate a rigid wing, qualify an OpenFOAM runtime, and inspect
individual angle-of-attack cases before building a sweep or optimization loop.

## Start here

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

## Status

The pinned ARM64 runtime has completed repeatable cavity tutorial runs. Generated 4412/0012 wing surfaces pass the documented geometry checks.
Volume meshing and flow qualification are next; no flutter prediction or flight capability
has been demonstrated. See GitHub for independent review and acceptance state.

GitHub issues are authoritative for work status. Plans describe intended behavior,
not completed capability. Private aircraft evidence stays private; a later public
demonstration must use separately selected shareable inputs.
