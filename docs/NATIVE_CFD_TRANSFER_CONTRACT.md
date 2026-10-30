# Native CFD interface diagnostic — issue 38

Primary design, first bounded component. This diagnostic is not a coupled solver.
Reuse main's modal_surface for Hq/H-transpose f and PR37 native point exporter
(28d70e871d57a62c91ea19e268db3909f8997bd0) for native ordering conventions.
PR27's transfer_surface_loads.py (2c01d84) was inspected: its structural-line
translations/rotations do not directly represent the native shell surface, so do
not import it as a shell mapping. No mutable sibling imports or new dependencies.

## Native export

Add tools/wingInterfaceExport/wingInterfaceExport.C and Make files for pinned
OpenCFD2412. Use native pointMesh wing patch meshPoints ordering and fvMesh faces,
Cf and Sf. Export JSON interface.json to the case/rank path. Serial point/face IDs
are mesh IDs; in parallel read pointProcAddressing and faceProcAddressing and
convert signed face addressing using abs(address)-1. Fail missing/inconsistent
addressing; never guess global IDs. On the wing boundary require outward face
orientation (positive face addressing). C++ should use ordinary Foam APIs,
17-digit numeric precision, valid JSON, no custom pressure computation.

Schema: schema_version=1, axes=[x_downstream,y_spanwise,z_up], length_unit=m,
area_unit=m2, reference_state=exported_mesh, rank integer, patch=wing,
point_ids=[global integer IDs], points_m=[[x,y,z]], faces=[{id:global face ID,
point_indices:[indices into THIS point array in native face order],
center_m:[x,y,z], area_vector_m2:[Sx,Sy,Sz]}]. Include time_s and native_runtime.
Exporter may operate on the mesh selected by standard createTime/createMesh;
explicitly report selected time. Initial implementation need not loop times.

## Python operator and diagnostics

scripts/cfd_interface_transfer.py exposes build_interface(export),
face_displacements(mapping, point_displacements), point_forces(mapping, face_forces),
and verify_interface(export, face_forces=None, modes=None). Ordinary package imports.
Use immutable/owned mapping arrays. Reject bool/nonfinite values, wrong units/frame,
IDs/order/dimensions, duplicate face vertices, degenerate faces, unknown references.

For a polygon, average its vertices to a fan center. For each adjacent pair form a
triangle to that fan center. Weight triangle centroids by positive triangle area.
Accumulate the resulting vertex weights (each triangle gives 1/3 to each endpoint
and 1/(3*n) to all vertices through the fan center). They must sum to one and
reproduce the NATIVE supplied face center within1e-10m. The triangulated area vector
must agree with supplied Sf (absolute1e-12m2 plus relative1e-10); otherwise fail.
Treat this as a specified fixed-geometry interpolation, not an assertion that it
is the exact derivative of OpenFOAM's movingWallVelocity. Do not silently correct
native centers, renormalize bad geometry or loosen tolerances.

D_face = W D_point; F_point = W-transpose F_face. F_face are dimensional integrated
fluid-on-wall point forces at Cf in N (not pressure, Cp or traction). No density or
area multiplication. The caller owns native pressure/viscous force extraction.
Check conservation of summed forces, moments about origin and an independently
shifted origin, and virtual work with nontrivial deterministic point displacements.
Also check rigid translation and infinitesimal rigid rotation reproduction. If
modes [mode][point][xyz] are supplied, use main modal_surface at POINTS and project
W-transpose forces with the same basis; verify modal/point/face virtual work. Do not
assume mass normalization or invent a half/full-span factor.

Report geometry/input hashes, scope, counts, reference positions, units, observed
errors and tolerances, and which loads/modes are synthetic versus supplied. A
synthetic load check must explicitly say it is not measured CFD force evidence.
No flutter/damping classifier. A successful geometry diagnostic does not qualify
native shell interpolation, fluid time history, moving-wall flux velocity, periodic
response, or implicit feedback. Keep those remaining gates explicit.

CLI: python3 -m scripts.cfd_interface_transfer EXPORT --output REPORT
Optional --loads JSON requires {quantity:integrated_point_force,force_unit:N,
face_ids:[exact exported order],forces_N:[[x,y,z]]}; optional --modes JSON requires
{point_ids:[exact exported order],basis_units:dimensionless,coordinate_units:m,
shapes:[mode][point][xyz]}. Unknown/ambiguous units fail. Hash exact input bytes.
No report written on invalid input; finite JSON only.

Meaningful tests: triangulated/quad/nonplanar geometry whose native centroid follows
the stated area fan; nonuniform loads; totalF/M about two origins; virtual work;
rigid motion; signed/scaled two-mode projection; permuted global IDs/order; negative
unit/frame/bool/nonfinite/degenerate/center/Sf/load-order cases; clean-copy CLI.
Compile and exercise the exporter on actual retained serial/parallel CFD cases as
primary-run evidence. Keep large meshes/results out of Git. Actual transient CFD
flow and native shell projection are primary follow-ons, not worker deliverables.
