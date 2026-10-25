# PC compute integration

The PC is connected through direct LAN SSH: Spark `10.0.0.98` to PC
`10.0.0.92`. This project does not use Tailscale. The owner enabled Windows
OpenSSH and an inbound rule scoped to those local/remote addresses. The rule's
Private-only profile initially prevented connection; changing profile scope
while preserving address restrictions restored access. The owner-confirmed
ED25519 host fingerprint was verified and pinned in a dedicated known-hosts file.
No credentials or private keys belong in this repository.

Observed 2026-10-25: Intel i5-13600K (14 cores, 20 logical processors), about
64 GB RAM, RTX3090 24 GB. The GPU was in use by the owner. Initial OpenFOAM jobs
use two CPU slots and a 2 GB container memory limit; this solver path does not
use the GPU. No firmware changes were made.

## Workspaces and runtime

- Windows source/export checkout: `G:\projects\openfoam`, initialized without
  overwriting existing preview files; those artifacts remain locally excluded.
- Active Linux checkout: `/home/foam/projects/openfoam` in dedicated WSL2 distro
  `OpenFOAM-24.04`, user `foam`.
- WSL virtual disk: `G:\projects\openfoam\build\wsl\OpenFOAM-24.04`.
- Fresh portable preview: `G:\projects\openfoam\runs\wing-baseline-pc-20261025\preview.html`.

The existing Ubuntu-24.04 registration referenced a missing VHDX and was
preserved. The separate distro was imported from Canonical's versioned
`https://releases.ubuntu.com/noble/ubuntu-24.04.5-wsl-amd64.wsl`, verified against
SHA256SUMS: `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`.
Ubuntu's packaged Docker 29.1.3, Git, Python3, curl and CA certificates were
installed; systemd starts Docker. No desktop GUI or host reboot was needed.

The Windows checkout was populated from a verified Git bundle of main revision
`497c08fa8380aabc206059a36ef57aa8eeeec048`. Cloning its Windows-mounted `.git`
into Linux failed Git's ownership check. Cloning the transferred bundle avoids
changing trust settings. A bundle containing only main has no symbolic HEAD;
explicitly `git switch main` after cloning. Both checkouts retain the GitHub
origin; no GitHub credential was copied to the PC.

Pinned PC image:

```text
opencfd/openfoam-default@sha256:adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b
```

This is linux/amd64, distinct from the Spark's ARM64 digest. The repository's
original qualifier is still ARM-only. The retained
[one-off adapter](evidence/adapters/qualify-pc-20261025.py) documents the observed
x86 run using its unchanged payload, container constraints and acceptance
verifier. It is historical evidence with fixed paths and an exclusive output,
not a general launcher. Reusable architecture selection remains follow-up work.

## Observed qualification

[PC report](evidence/pc-runtime-20261025.json): both 400-cell cavity runs reached
0.5 s, maximum Courant 0.852134, maximum speed 0.8526671462436952 m/s,
final local continuity 9.66354e-9 and cumulative continuity 1.21735e-17.
Velocity and pressure files were identical between PC repeats.

Full-field [cross-platform comparison](evidence/pc-cross-platform-20261025.json)
used the previously declared per-component tolerance
`abs(a-b) <= 1e-10 + 1e-6*max(abs(a),abs(b))`, with identical cell ordering and
pressure reference. All 1,200 velocity components and 400 kinematic pressure
values matched exactly at written precision; final U/p file hashes also matched
Spark. This single tutorial does not establish general cross-platform identity.

Raw PC evidence is at `/home/foam/projects/openfoam/runs/pc-runtime-20261025`;
exported report at `G:\projects\openfoam\build\pc-runtime-report.json`.
The source verifier's SHA-256 is recorded, along with the adapter, image,
commands, limits and artifact hashes. Cross-host tolerances were declared in
issue #9 before comparing full fields.

This qualifies runtime sanity and repeatability, not wing aerodynamics or
physical accuracy. A representative mesh/RANS benchmark is still needed before
claiming acceleration. Prefer independent cases on each machine before exploring
MPI across hosts. Generated-wing trials remain rejected by mesh/layer checks.

A stock `simpleFoam/airFoil2D` control subsequently ran 500 iterations on both
hosts with identical input manifests, using Spalart–Allmaras and the bundled
10,720-cell mesh. Total one-shot elapsed times were 4.59 s Spark and 5.39 s PC,
including startup, file copying and output. This tiny run shows no PC speedup
and is not a representative scaling benchmark. Both retained mesh logs report
one failure (266 faces not in upper-triangular order); solver completion is not
mesh acceptance. No generated-wing result is inferred. Raw logs remain under
`runs/stock-airfoil-control-20261025` on each host. A representative, accepted
workload and repeated measurements remain outstanding.

The Windows preview now also embeds rejected trial3 mesh cross-sections and
layer coverage via sibling `mesh-preview.html`; the geometry-only original is
preserved as `preview.geometry-only.html`. The standalone mesh page embeds its
images and input hashes, with no network dependency. See issue #4's preview
checkpoint for provenance and limitations.
