# Environment and runtime qualification

Initial observations (2026-10-24): Ubuntu 24.04.4 LTS, aarch64 DGX Spark,
Docker available, no host OpenFOAM installation. Ubuntu's package candidate was
1912.200626-2build3; it was not installed. PC CPU/RAM/OS and remote execution
remain uninspected; owner reports an RTX 3090.

## Selected runtime (issue #2)

Official OpenCFD v2412, native linux/arm64:
`opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4`.
The primary inspected the multi-platform manifest and pulled this exact ARM64 digest.
Image size: 1,292,001,858 bytes. Solver build: `_45e7c4a0-20241224`, scalar64/label32.
This selection avoids host package/global-shell changes and supports the required
meshing and steady/transient executables. It predates v2606 mesh-motion changes;
future preCICE compatibility still needs its own qualification.

[Runtime instructions](RUNTIME_QUALIFICATION.md) describe explicit installation,
per-command activation, removal, limits, tests, and evidence. The launcher runs as
host UID/GID with no network, two CPU equivalents and a 2 GB memory limit.
The cavity tutorial is copied twice and run independently through t=0.5.
There are 400 field values/cells, NOT 400 time directories.

Primary native exploratory and corrected-launcher runs on 2026-10-25 completed:
checkMesh reported Mesh OK; final U/p were byte-identical; max Courant 0.852134,
final local continuity 9.66354e-09, cumulative -4.19231e-18. These are runtime
sanity/repeatability observations, not experimental CFD validation.
Reviewed run summaries will be retained in docs/evidence with hashes and raw artifact
locations; GitHub #2/PR #7 determine acceptance state.

## Next gates

Generated wing geometry (#3), one flow case (#4), and mesh/domain/AoA evidence (#5).
No wing flow, compressible-flow, structural or flutter capability follows from
successfully running the cavity. GPU acceleration, MPI and FSI remain deferred.

Reference consulted 2026-10-24: https://precice.org/adapter-openfoam-support
(distribution/version differences and v2606 mesh-motion changes).
