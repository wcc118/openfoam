# Retained primary experiment sources

These files archive the actual bounded PC/WSL experiment drivers for issue38,
including failed snap/export attempts. They are provenance, not a general portable
case interface. They name retained PC cases under `/home/foam/projects/openfoam/runs`
and staged files under `/mnt/g/projects/openfoam/build`; do not run them blindly.
Each new run directory is exclusive; native runtime commands have walltime bounds,
stop their named container on timeout and retain exit/check results. Main product
code is `scripts/cfd_interface_transfer.py` and `tools/wingInterfaceExport`.

Pinned moving/force runtime image:
`sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853`.
Rigid initialization uses the retained OpenCFD2412 image
`opencfd/openfoam-default@sha256:adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b`.
Both are distinct recorded images; do not assume a floating tag.

Reuse: the nearest-cap map is verbatim archived from PR37 at28d70e8, source SHA256
c84ea5efb30d3e7ccf43c474f3d81c1e0093a34dd4af2dd5be75c03eb3f5ce4a. Its external
native-modal.npz SHA256 is8f5870bafb5f77b48f423102b5ab4451d710054e4f89bb15da76317da6cb0236.
The read-only coordinate-reproduction audit evaluates the same interpolation on
native reference coordinates; it does not modify the mode or CFD results. The
rigid-flow driver adapts the retained PR37 generator workflow, whose actual staged
generator hash is recorded in the native run manifest. Historical templates remain
retained inputs, not mutable sibling imports in the product code.

`manifest.json` hashes the archived executable sources. Large meshes, native mode
arrays, complete interfaces, flow fields and worker logs are intentionally not in
Git. The evidence archive and summary report preserve their relevant hashes and
locations. No raw work-machine measurements or commercial solver integration is
claimed by these synthetic-wing experiments.
