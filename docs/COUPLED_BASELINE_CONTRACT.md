# Native modal feedback pilot contract

Issue #38 owner scope update permits the current nearest-shell map as an estimating
approximation. The previous exact-moment no-go remains historical evidence; it no
longer blocks this bounded experiment. It does not become a claim of conservative
full-shell transfer or physical qualification.

The primary-owned participant uses one symmetric native bending mode, q in metres
of mean tip z. The source half-wing generalized mass is 1 kg with raw mean tip
shape -2.098338359375. Scaling the shape to unit tip displacement and mirroring both
half-wings gives M=2/mean_tip_shape²=0.45423328577302213 kg; frequency 8.810675 Hz,
K=1392.057119541888 N/m. Zero damping is an explicit diagnostic assumption. Initial
q=v=0 is an untrimmed startup; gravity is excluded. It is not a loaded-equilibrium
flutter test. Source NPZ SHA256:
8f5870bafb5f77b48f423102b5ab4451d710054e4f89bb15da76317da6cb0236.

Two separate structural interface meshes reproduce the native reference coordinates:
face centres receive integrated forces in N; points transmit displacement in m.
The pinned OpenFOAM adapter supplies pressure plus viscous forces with rho
1.2250532683653954 kg/m³ and gauge kinematic p. No second density/area conversion.
preCICE nearest-neighbor conservative/consistent maps between coincident copies
must be checked against native loads and saved point motion, not assumed identity.
H_face=W H_point uses the already verified fixed-reference area-fan operator.
Q=sum(H_face*F); point displacement=H_point*q. No extra shell-offset correction.
Axes x downstream, y spanwise, z up; origin (.0254,0,0)m; full area .24774144m²,
span2.4384m/chord.1016m;30m/s TAS,zero incidence,k-omega SST,no layers/transition.

Reuse the existing native OpenCFD2412/preCICE runtime, image
sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853.
Original upstream pins: preCICE3.4.1 f5e4c2c1837ced7a6b60c4e5fb5a1ecab1cf6ab1;
OpenFOAM adapter1.4.0 0801887b958f3101389cb719838dc8fc864d5369;
Python bindings3.4.0 1a469788eec0a3de1a00691bdf5e5b0b25a2ae97.
No upstream source is relicensed or copied into product code. Existing synthetic
participant informed the primary-owned native participant; main's verified
ModalSystem owns Newmark integration and immutable checkpoint/restore.

Serial-explicit Fluid-first runs once per window, with staggered geometry/load
feedback. The solid reads force at window end and integrates Newmark with accepted
start force and new endpoint force; it does not claim an implicit solution or
zero-order force hold. Implicit uses the same equations with repeated fluid/solid
trials and complete state rollback. Never accept a configured iteration cap as
convergence. Reference:
https://precice.org/configuration-coupling
https://precice.org/couple-your-code-waveform

Write every trial before acceptance; preserve rejected trials and failure state.
Check structural discrete energy against trapezoidal endpoint load work plus
midpoint damping loss. This is a structural integration identity, not full fluid
energy conservation. Native wall power and exchanged forces are audited separately.
A fixed displacement bound stops runaway pilots. Short runs and force agreement
establish plumbing only; periodic decay/growth and timestep independence remain
separate milestones. No actual-wing flutter or flight-limit claim follows.
