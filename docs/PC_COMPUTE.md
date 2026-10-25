# PC compute integration

The owner authorizes porting generated work to the PC or building/running it
there, including a checkout at `G:\projects\openfoam`. Use the same GitHub repo
and retain source revision, inputs, runtime identity and output hashes per run.

On 2026-10-25, SSH alias `windows-pc` timed out before authentication. CPU/RAM,
GPU availability, WSL and Docker have therefore not been inventoried in this
project. No directory, checkout or runtime has been installed on the PC yet.

Once reachable: inspect hardware and installed runtimes read-only; create the
checkout if absent; select and pin the official x86_64 image (the Spark's
ARM64-specific digest is not portable); run the same cavity qualification and
compare numerical results before assigning wing cases. Do not assume bitwise
identity across architectures. Define cross-machine tolerances before comparison.
Use Linux storage inside WSL for active CFD files if available and measured to
be preferable; the G: checkout can hold source and exported reports. Record the
actual paths rather than assuming a WSL layout exists.

Initial compute work uses CPU OpenFOAM. Benchmark a representative case before
choosing the PC or Spark for larger meshes; RAM and available cores matter.
Prefer independent cases per host before attempting distributed MPI across the
PC/Spark link. The RTX3090 can be assessed separately for supported GPU solvers
or other workloads; the current pinned OpenFOAM path does not use it. A firmware
patch is not an established acceleration path for this pipeline.
