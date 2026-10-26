# Point-force transfer verification

Primary verification used all181780 native wing-face centres and SI face-force
vectors from saved4deg iteration700. Input archive/analysis remains local under
`runs/wing-fsi-goal-20261026/checkpoint700`; its compressed NumPy input hash and the
exact transfer module hash are in `transfer-module700-verification.json`.
The module has not changed since the recorded commit5c5fc8c.

The caller supplied25 nodes spanning y=-.6096..+.6096m, x=.0254m,z=0.
This quarter-chord line is a verification scaffold, not a measured elastic axis.
An explicit1e-5m tip tolerance admitted the mesh's6.21693e-6m overhang, retaining
actual3D lever arms. Moment balance used origin(.013,.1,.02)m.

Independent NumPy sums compared source force/moment with transferred nodal forces
and couples. Seed26 normal random nodal translations scaled1e-4m and rotations
scaled1e-3rad checked virtual work against the mapped surface motions.
Maximum errors:4.974e-13N,4.441e-14Nm,2.656e-18J. This is numerical transfer
verification, not a structural solve, interpolation-accuracy study or flutter
prediction. The committed unit tests additionally exercise independent hand
calculations, general rigid rotations and explicit out-of-span projection.
