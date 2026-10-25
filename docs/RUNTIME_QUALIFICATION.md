# OpenFOAM Runtime Qualification

## Overview

This module provides a headless runtime qualification launcher for the OpenFOAM solver.
It uses Docker to run the official OpenCFD image and executes the cavity tutorial case
to verify numerical acceptance criteria.

## Pinned Runtime Identity

**Image:** `opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4`  
**Version:** v2412 (OpenFOAM 24.12)  
**Architecture:** native linux/arm64

## Usage

```bash
python3 scripts/qualify_runtime.py --output runs/unique-name
```

### Requirements

- Docker daemon running and accessible
- Host architecture must be aarch64/arm64
- Python 3.11+ (stdlib only, no external dependencies)

### Output Directory

The output directory must not exist or must be empty. The launcher will:

1. Create the output directory
2. Pull the pinned Docker image
3. Copy `$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity` into `cavity-a` and `cavity-b`
4. Run `blockMesh`, `checkMesh`, and `icoFoam` for both cases
5. Save logs and verification results

### Acceptance Criteria

Both runs must satisfy:

- **Mesh OK**: checkMesh reports successful validation
- **End marker**: Solver completes successfully
- **Final time = 0.5**: Steady-state simulation complete
- **400 field files**: Velocity (U) and pressure (p) fields at 400 time steps
- **Speed bounded 0..1.1 m/s**: Physical velocity range
- **Recirculation present**: Both positive and negative Ux values (flow pattern sanity)
- **Max Courant <= 1**: Numerical stability
- **Final local continuity <= 1e-6**: Mass conservation
- **Final cumulative abs continuity <= 1e-10**: Global mass conservation
- **Byte-identical U and p**: Same image/run settings produce identical results (repeatability)

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - all acceptance criteria passed |
| 1 | Argument error or precondition failure |
| 2 | Docker command failure |
| 3 | Acceptance check failure |

## Output Artifacts

Each run produces:

| File | Description |
|------|-------------|
| `qualify_report.json` | Full JSON report with status, metadata, and acceptance results |
| `container_stdout.log` | Full container stdout capture |
| `container_stderr.log` | Full container stderr capture |
| `cavity-a/` | First tutorial case directory |
| `cavity-b/` | Second tutorial case directory (byte-identical verification) |

### Report JSON Structure

```json
{
  "status": "passed|failed",
  "image": {
    "reference": "opencfd/openfoam-default@sha256:...",
    "version": "v2412",
    "identity": {
      "id": "sha256:...",
      "created": "ISO-8601 timestamp",
      "architecture": "arm64",
      "os": "linux"
    }
  },
  "git": {
    "revision": "commit hash",
    "dirty": boolean
  },
  "utc": "ISO-8601 timestamp",
  "platform": {
    "system": "Linux",
    "release": "kernel version",
    "machine": "aarch64"
  },
  "resource_limits": {
    "memory": "2g",
    "cpus": "2",
    "user": "UID:GID"
  },
  "inputs": {
    "output_path": "absolute path",
    "shell_script": "run.sh"
  },
  "acceptance": { ... },
  "artifacts_sha256": { ... }
}
```

## Uninstall

Remove only the selected image (never prune globally):

```bash
docker rmi opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4
```

## Container Execution Details

The launcher uses Docker with these flags:

- `--rm`: Auto-remove container after exit
- `--network none`: Isolated network (no external access)
- `--memory 2g`: Memory limit
- `--cpus 2`: CPU limit
- `--user UID:GID`: Run as host user (no root)
- Volume mounts:
  - `run.sh`: readonly (execution script)
  - `output/`: readwrite (results)

**No privileged mode, GPU, docker socket, credential mounts, or system config changes.**

## Shell Payload

The container executes this payload:

```bash
set +u
source /usr/lib/openfoam/openfoam2412/etc/bashrc
set -u

blockMesh -case cavity-a
blockMesh -case cavity-b

checkMesh -case cavity-a -time 0
checkMesh -case cavity-b -time 0

icoFoam -case cavity-a
icoFoam -case cavity-b
```

Note: `set +u` before sourcing, then `set -u` after to avoid undefined variable errors
during bashrc evaluation.

## Testing

Run unit tests (no Docker required):

```bash
python3 -m unittest tests.test_qualify_runtime -v
```

Tests verify:

- Mesh log parser (Mesh OK detection, cell/face counts)
- Solver log parser (End marker, final time, Courant, continuity)
- File hashing (SHA256 consistency)
- Output path validation (empty directory required)
- Shell payload structure (correct source order)

## Architecture Notes

### Why Docker?

- Official OpenCFD releases provide pre-built container images
- No system-wide installation or PATH manipulation required
- Consistent environment across host systems
- Resource limits enforced by Docker daemon

### Why v2412?

- Current stable OpenCFD release
- Native ARM64 support (required for DGX Spark)
- preCICE adapter compatibility (future work)
- Published SHA256 digest for reproducibility

### Limitations

- Docker daemon required on host
- No GPU acceleration (solver not GPU-enabled in this configuration)
- No multi-node MPI (single-container execution)
- Runtime execution verified on aarch64 only (PC support deferred)

### Not Validation

This tool verifies:

- Docker image pull and container execution
- Shell payload execution
- Numerical acceptance criteria

This tool does **not** validate:

- Physical accuracy of solver results
- Convergence to exact solution
- Applicability to specific wing configurations
- Flutter stability or aeroelastic behavior

## Related Documentation

- [Engineering roadmap](ENGINEERING_PLAN.md): stages and evidence gates
- [Rigid-wing MVP](RIGID_WING_MVP.md): analysis contract
- [Environment](ENVIRONMENT.md): setup status
