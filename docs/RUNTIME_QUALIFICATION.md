# OpenFOAM runtime qualification

The runtime is official OpenCFD v2412 on native linux/arm64, isolated in Docker.
The primary selected this dependency after inspecting the official multi-architecture
manifest. No host package or global shell configuration changes are required.

## Install and run

Prerequisites: an ARM64 Linux host, Docker daemon access, Python 3, Git, about 2 GB
free disk for the image/artifacts and at least 2 GB available runtime memory.
The image occupies 1,292,001,858 bytes locally. Other resident services need their
own memory budget. This launcher currently rejects non-ARM64 hosts; PC support is later.

Explicitly download the pinned image once:

```bash
docker pull --platform linux/arm64 opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4
python3 scripts/qualify_runtime.py --output runs/runtime-001
python3 -m unittest discover -s tests -v
```

The launcher never downloads an image. Existing output directories (even empty ones)
are rejected. Run again using a new name. No destructive cleanup is automatic.
Only the selected output directory is mounted; Docker runs non-root matching host
UID/GID, with no network, a 2 GB memory limit and two CPU equivalents. The image's
entrypoint is explicitly bypassed, and its bashrc is sourced only inside the container.
`foamVersion` is unavailable in this image; WM_PROJECT_VERSION and solver banners
identify the release/build instead.

## What runs and what passes

Two fresh copies of the image's official icoFoam/cavity/cavity tutorial each run
blockMesh, checkMesh, and icoFoam. Every command has a separate log and exit-code
entry. A failed command stops execution. Each run must have Mesh OK, 400 cells,
End at t=0.5, 400 finite velocity vectors and pressures, max speed <=1.1 m/s,
both signs of Ux, all recorded Courant maxima <=1, final local continuity <=1e-6,
and final absolute cumulative continuity <=1e-10. Final U and p files must be
byte-identical between runs. Missing evidence fails; it is never treated as zero.
These are fixed tutorial sanity/repeatability checks, not physical validation.

Artifacts include the exact shell payload, image identity, source revision/dirty
state, UTC timestamps, Docker command/exit codes, tutorial inputs and mesh/fields,
per-command logs, and qualify_report.json with actual measurements and file SHA256s.
The report does not hash itself. Hashes include the generated case inputs and outputs.
Failed executions retain logs and a failed report whenever the output directory can
be created/written. Preexisting-path errors leave that path untouched.

Tests use captured real tutorial fields/log excerpts plus deliberate corruptions and
mocked command failure; they require no Docker. Real qualification remains necessary.

## Removal and limitations

To remove the runtime image, explicitly run `docker image rm` with the exact image
reference above, after checking that other work does not need it. Do not use global
Docker prune commands. Remove only your selected run directories when no longer needed;
keep referenced engineering evidence. Reinstall by pulling the same digest.

No wing, turbulence, compressible-flow, MPI, GPU, structural, or FSI result is established
by this qualification. Those tools exist in the image but require separate case evidence.
