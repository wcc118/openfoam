# Environment and runtime qualification

Observed 2026-10-24 in /home/connellwc83/projects/openfoam:

- Directory initially empty, not a Git repository; private wcc118/openfoam created.
- Ubuntu 24.04.4 LTS, aarch64 (DGX Spark environment).
- Docker executable/daemon available; daemon reports aarch64.
- foamVersion not on PATH; dpkg query showed no installed OpenFOAM package.
- Ubuntu configured archive candidate: openfoam 1912.200626-2build3 (arm64).
- No runtime installed or solver executed by planning issue #1.
- PC CPU/RAM/OS and remote execution details have not been inspected in this project.
  Owner reports an RTX 3090; do not infer benchmark performance from that alone.

## OpenFOAM Runtime Qualification (issue #2)

**Selected runtime:** `opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4` (v2412)

**Architecture:** native linux/arm64

**Verification method:** Docker-based headless runtime qualification launcher.

### Implementation

- **Launcher:** `scripts/qualify_runtime.py`
- **Tests:** `tests/test_qualify_runtime.py` (unit tests, no Docker required)
- **Documentation:** `docs/RUNTIME_QUALIFICATION.md`

### Usage

```bash
python3 scripts/qualify_runtime.py --output runs/unique-name
```

### Acceptance criteria

Both cavity tutorial runs must satisfy:

- Mesh OK (checkMesh validation)
- Solver ends successfully (Exit marker)
- Final time = 0.5
- 400 time steps for U and p fields
- Speed bounded 0..1.1 m/s
- Recirculation present (both Ux signs)
- Max Courant <= 1
- Final local continuity <= 1e-6
- Final cumulative abs continuity <= 1e-10
- Byte-identical U and p between runs

### Container execution

- Image: `opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4`
- Flags: `--rm --network none --memory 2g --cpus 2 --user UID:GID`
- Shell payload: sources `/usr/lib/openfoam/openfoam2412/etc/bashrc`, runs blockMesh/checkMesh/icoFoam

### Uninstall

Remove only the selected image:

```bash
docker rmi opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4
```

### Observed results (primary exploratory run)

The following observations were recorded during primary exploratory execution
(outside this isolated worker):

- **Max Courant:** 0.852134
- **Final local continuity:** 9.66354e-09
- **Final cumulative continuity:** -4.19231e-18
- **Final fields:** byte-identical between runs
- **Solver banner:** _45e7c4a0-20241224 / scalar64 label32

These observations are context only; do not fabricate a committed run result.
Primary will populate observed evidence.

### Next detailed task

Select and pin one OpenFOAM distribution/version with a reproducible native ARM64
installation or isolated source/container build. Investigate current OpenCFD releases
first because of intended future preCICE use, but verify actual ARM64 availability,
solver support, licensing and resource cost before selecting. The old Ubuntu package
is an available fallback, not the automatic choice. Do not confuse Foundation 14
with OpenCFD v2606 or assume matching case files.

Record exact source/image checksum, dependencies/build options, environment activation,
memory/disk budget, and uninstall/rebuild instructions. Avoid mutable latest tags,
system-wide shell changes, and remote scripts piped to privileged shells. Use explicit
per-command activation. Run an official reference case appropriate to that release,
check observed outputs, and reproduce it from a fresh case directory.

Gate: version and native architecture evidence plus a complete successful reference
run with numerical sanity checks. An installed executable alone does not pass.
GPU acceleration, multi-machine MPI, preCICE and structural solvers are deferred.

Source: https://precice.org/adapter-openfoam-support (consulted 2026-10-24).
It describes distribution/version differences and notes mesh-motion result changes
for v2606; this is a reason to qualify the chosen version, not assume compatibility.
