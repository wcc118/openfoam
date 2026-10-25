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

**Pinned runtime:** `opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4` (v2412, native linux/arm64)

- [Runtime qualification documentation](docs/RUNTIME_QUALIFICATION.md): usage, acceptance criteria, and output artifacts.

This module verifies the Docker-based OpenFOAM runtime with the cavity tutorial.
Passing acceptance criteria confirms the runtime is operational but does not
validate physical accuracy or flight capability.

## Status

This repository is being initialized. No solver installation, CFD result, flutter
prediction, or flight capability has yet been demonstrated here.

GitHub issues are authoritative for work status. Plans describe intended behavior,
not completed capability. Private aircraft evidence stays private; a later public
demonstration must use separately selected shareable inputs.
