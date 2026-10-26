# Structural beam benchmarks

Partial implementation for #24. Generate SI Nastran-compatible static bending,
static torsion and bending-modal decks with:

```bash
python3 scripts/generate_structure_benchmarks.py --output-directory runs/beam-check
```

The directory must be empty. The CLI supports length, radius, element count,
Young's modulus, Poisson ratio and density. Length/radius/modulus/density must be
positive; the supported Poisson range is 0 <= nu < 0.5. These are analytical
benchmark properties, not measured wing inputs.

Default circular cantilever: L=1m, r=.005m, E=70GPa, nu=.3, rho=2700kg/m³,
20 CBAR elements, global x along the beam and orientation vector global y.
SPC1 fixes only node1, all six DOFs. A unit tip force acts along +z for bending;
a unit tip moment acts about +x for torsion. Positive z deflection produces
negative rotation about y; the JSON bending rotation is a magnitude.

With A=pi*r², I=pi*r⁴/4, J=2I and G=E/[2(1+nu)], references are:

| Quantity | Formula | Default value |
|---|---|---|
| Tip bending displacement | F L³/(3 E I) | .00970087272 m |
| Tip bending rotation magnitude | F L²/(2 E I) | .01455130908 rad |
| Tip twist | T L/(G J) | .03783340361 rad |
| Total mass | rho A L | .2120575041 kg |
| First three distinct bending frequencies | beta²/(2pi) sqrt(EI/(rho A L⁴)) | 7.12324744,44.64062969,124.99505576 Hz |

Beta values are 1.875104068711961,4.694091132974174,7.854757438237612.
Euler–Bernoulli assumptions are a uniform slender beam, small deformation and
linear isotropic elasticity. The circular section has paired bending planes.
The default six requested modes are three bending pairs, not six distinct
analytical frequencies. Compare mode character as well as frequency.

MYSTRAN19's `Source/EMG/EMG3/BREL1.f90` supplies translational lumped beam mass
only. MAT1 density does **not** supply physical torsional rotary inertia in this
model. Explicit mass/CG/inertia modeling and separate torsional modal checks are
required before wing flutter analysis. Do not add artificial mass to hide this.

`reference.json` includes input values, analytical references, prospective
1% static and 2% first-bending-frequency tolerances, and SHA256 hashes of actual
written deck bytes. Solver process exit is not acceptance: MYSTRAN has returned
exit0 for malformed decks containing fatal errors. Require normal termination,
no fatal errors, expected finite displacements/eigenvalues, and reference checks.
Numerical verification is distinct from physical wing validation.

The independently executed [native fixtures](../tests/fixtures/structure-native/README.md)
establish valid card syntax and baseline results. Free-field real values must
have decimal points and fit MYSTRAN's16-character fields. Supported cards here:
GRID,CBAR,PBAR,MAT1,SPC1,FORCE,MOMENT,EIGRL; SOL101/103 only. No flutter solver or
actual-wing model is included.

Pinned solver: [MYSTRAN19.0.0](https://github.com/MystranSolver/MYSTRANSolver),
commit `3a5913a904ee1adbda9fbcaf9c0a6af8e10f0f9f`, MIT license. Preserve dependency
licenses separately. See [reuse inventory](REUSE_INVENTORY.md).

Run `python3 -m unittest discover -s tests` for repository tests; native execution
is additional evidence and is not silently substituted by text-format tests.
