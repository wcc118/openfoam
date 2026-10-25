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

## Next detailed task

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
