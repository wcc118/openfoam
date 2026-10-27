# Aluminum hollow-wing surrogate

Owner definition (issue 30): 48 in root to tip, rigid root, 0.050 in homogeneous
7075-T6 aluminum wall around section A-A. This is a structural pipeline model,
not the actual carbon wing. The eight-inch telescoping overlap is metadata only;
no double skin, internal spars, contact, lock, endcaps, damping or prestress.

The mesh consists exclusively of **2D CQUAD4 shell elements**, located in 3D,
with PSHELL thickness and MAT1 elastic material. It contains no solid elements.
The provisional four-inch chord and NACA4412 are not measured production geometry.
The airfoil describes the shell midsurface. Closed-TE coefficient -0.1036 joins
upper and lower skins at one node, unlike the existing finite-TE CFD geometry
(-0.1015). The sharp trailing edge/thickness offset is an idealization.

SI units throughout: x downstream, y root to tip, z up. Root y=0 is clamped in
all six DOFs around the perimeter; uncapped tip y=1.2192 m is free. Moment origin
is the perimeter-node mean x,z at the root (recorded per mesh). The bending load
is +1 N in z distributed equally to tip nodes. Torsion uses a tip force couple
with zero net force and +1 Nm about y; no artificial rigid tip diaphragm.

E=71.7 GPa, nu=.33, rho=2810 kg/m3; G=E/[2(1+nu)]. These are typical elastic
surrogate inputs, not strength allowables. Property reference:
https://asm.matweb.com/search/SpecificMaterial.asp?bassnum=MA7075T6&lang=en
Shell mass is midsurface area times thickness times density, with no added mass.

```
python3 scripts/generate_aluminum_shell.py --output runs/shell-new
python3 scripts/generate_aluminum_shell.py --points 33 --sections 49 --output runs/shell-fine-new
python3 -m unittest discover -s tests
# From each generated directory, with pinned MYSTRAN on PATH:
mystran bending.bdf
mystran torsion.bdf
mystran modal.bdf
```

## Native verification, 2026-10-27

MYSTRAN 19.0.0 source 3a5913a904ee1adbda9fbcaf9c0a6af8e10f0f9f;
binary SHA256 e2980a1fb40fd3d4a0d48ad54f4829dfe052db631896d2be765429d1f9818c8d.
Artifacts on host: runs/aluminum-shell-20261027/{coarse,fine,fine-no-autospc}.
All nine native solves terminated normally, with no *FATAL messages.
Each modal run warns that the mass matrix has only 2304 (coarse) or 9216
(fine) nonzero diagonal entries, limiting the number of finite eigenvalues.
These equal the free translational DOFs; massless shell rotational DOFs do not
prevent extraction of the requested ten modes. No extra inertia was invented.
The six static solves have no *WARNING messages.
ERR contains internal memory-accounting INFORMATION and OP2 DEBUG messages;
these are retained, not suppressed. 79 repository tests pass.

| Quantity | 768 quads | 3072 quads |
| --- | ---: | ---: |
| Mass kg | .904521 | .905143 |
| Mean tip z per 1 N, mm | 1.49339 | 1.48327 |
| Fitted tip rotation per 1 Nm, rad | .00361472 | .00359085 |
| First frequency Hz | 8.78068 | 8.81068 |

All ten frequencies are positive. The first-mode shift is .34%; bending and
torsional compliance shift under .7%. Higher ordered frequencies shift up to
4.8%; modes have not been correlated by shape, so full-spectrum convergence is
NOT claimed. Root force/moment sums, including force lever arms, balance within
1e-5 N/Nm at printed-output precision. Summing nodal moments alone is incorrect.

Coarse mesh: no AUTOSPC. Fine mesh: 96 component-6 rotational DOFs automatically
constrained, zero translational AUTOSPC. A diagnostic repeat with PARAM,AUTOSPC,N
also normally terminated with ten positive modes: bending changes .000153%,
torsional compliance .181%, and first frequency .000023%. This bounds the
observed effect for this model; it does not prove all local rotations trustworthy.
No silent change to solver AUTOSPC defaults was made. The diagnostic modified
its decks; copied original model.json hashes describe the source decks only.

These checks support using the model for the next structural/FSI integration
step. They do not establish physical validation, carbon equivalence, strength,
flight capability or flutter onset. Steady CFD cannot establish flutter. New
CFD remains on hold. Before quantitative redesign comparison, add the actual
section, overlap load path, mass and carbon stiffness and compare modal data.
