# Native CFD face/point transfer

`wingInterfaceExport` exports native OpenCFD2412 wing point/face ordering, global
processor addressing, coordinates, face centres and oriented area vectors. The
Python diagnostic uses those actual coordinates to construct a sparse,
area-weighted face interpolation W and its force transpose. It checks forces,
moments about two origins, rigid motion and virtual work, including modal work.
It does not implement a structural feedback solver.

## Run

Use an OpenCFD2412 environment to build the exporter:

```sh
source /usr/lib/openfoam/openfoam2412/etc/bashrc
wmake tools/wingInterfaceExport
wingInterfaceExport -case CASE
mpirun -np 4 wingInterfaceExport -case CASE -parallel
```

The executable is written to `FOAM_USER_APPBIN`. Export follows the case's
`controlDict` start selection; the selected time is recorded in the JSON. A serial
case writes `CASE/interface.json`; a decomposed case writes one file per processor.
Do not concatenate processor point arrays: shared point IDs must be assembled.
Faces must occur once globally. Reversed wing face addressing is rejected.
This first diagnostic expects nonempty wing geometry in each processed export.

With Python3 and NumPy, from the repository root:

```sh
python3 -m scripts.cfd_interface_transfer CASE/interface.json --output report.json
python3 -m unittest discover -s tests -p test_cfd_interface_transfer.py
```

The default uses explicitly synthetic nonuniform forces and two synthetic shapes.
To supply loads, use `--loads loads.json` with `quantity: integrated_point_force`,
`force_unit: N`, `face_ids` in exact export order and `forces_N: [face][xyz]`.
To supply modes, use `--modes modes.json` with `point_ids` in exact export order,
`basis_units: dimensionless`, `coordinate_units: m` and `shapes: [mode][point][xyz]`.
The CLI hashes exact input bytes and distinguishes supplied/synthetic inputs.
The API accepts JSON-style numeric lists; boolean/nonfinite numbers are rejected.
Unknown units, geometry disagreement and wrong ordering fail before report creation.
A completed diagnostic with a failed conservation check writes `passed:false` and
returns exit2; an invalid input returns exit1. Only all passing checks return exit0.

## Meaning of the operator

A face is triangulated about the arithmetic mean of its vertices. Positive triangle
areas weight triangle centroids; their contributions define vertex weights. These
must reproduce the exported native centre within1e-10m, and the oriented triangle
area sum must match native Sf within1e-12m2 plus1e-10 relative. No native geometry is
silently corrected. An irregular polygon generally does not have equal weights.
Only face-vertex entries are stored, avoiding a dense faces-by-points matrix.

For displacements, `u_face = W u_point`; for forces, `f_point = W^T f_face`.
The same stored weights appear in both directions. Partition of unity preserves
force, linear coordinate reproduction preserves moment, and transposition preserves
work. `modal_surface` then uses the same point basis for `u_point = H q` and
`Q = H^T f_point`; no unit modal mass or half-wing scale factor is assumed.
Input forces are integrated dimensional forces, not pressure or force coefficients.

This is a fixed-geometry kinematic interpolation. It is not automatically the exact
derivative of a changing polygon centroid or OpenFOAM's flux-corrected
`movingWallVelocity`. Those distinctions matter when comparing actual wall power
with modal power. Native shell-to-CFD interpolation and its transpose are separate
from the face-to-point stage; passing this diagnostic cannot qualify that stage.
Use [the design contract](NATIVE_CFD_TRANSFER_CONTRACT.md) and native experiment
reports for remaining mesh, force-provenance, startup, periodic, timestep and
implicit-feedback gates. No damping, flutter or flight limit follows from this tool.
