# Native setup checks, 2026-10-25

These are setup diagnostics, not accepted aerodynamic results. PC native amd64
OpenCFD v2412 image and all commands/source hashes are recorded in execution
reports. Original cases remain under `/home/foam/projects/openfoam/runs/` on the
PC. They use the 2,850,441-cell trial9 mesh, with source/copied mesh hashes in each
manifest. The original generated manifests describe the pre-override setup;
execution reports separately record diagnostic endTime changes and both hashes.

- `wing-flow-preflight-pc-20261025`: source82ce181, `simpleFoam -dry-run` aborted
  in simplified-mesh zone handling before reading flow fields. Retained as a
  failed diagnostic; it does not establish a defect in the actual wing mesh.
- `wing-flow-smoke-pc-20261025`: source82ce181, normal full-mesh one-iteration
  check failed because v2412 freestreamPressure requires freestreamValue.
- `wing-flow-smoke2-pc-20261025`: source48a6f9b supplies that entry and completes
  one normal iteration with fields, SST, forces and forceCoeffs loaded. Native
  force output includes the declared density, reference dimensions and load
  components. Startup loads/residuals are not converged performance results.

The one-iteration checks deliberately override endTime from500 to1 only in
separate disposable diagnostic cases; they do not weaken the minimum500-iteration
acceptance criterion. The fresh500-iteration case uses the unmodified generated
controlDict. At archival time that solve had started, not completed.

Primary Python verification at48a6f9b:61 tests passed, including47 existing tests.
They exercise real native boundary-list syntax, generated axes/classes/conditions,
exclusive outputs, source preservation, independent hashes, and failure reports.
Native execution remains distinct from these tests, numerical convergence,
physical validation and flight capability. Native raw logs retain their bytes;
Git whitespace exceptions apply only to those evidence logs.
