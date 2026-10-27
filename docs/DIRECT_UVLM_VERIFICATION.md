# Direct modal–UVLM benchmark checkpoint

Issue #36, 2026-10-27. **The direct interface now reproduces the earlier Goland
benchmark convention, but the causal coupling gives a different finite-time-step
crossing. No aluminum-shell flutter speed or new CFD result is claimed.**

## What changed

The previous pilot omitted SHARPy's quarter-panel downstream shift of a uniform
vortex lattice. The pinned `sharpy/aero/models/aerogrid.py:506` applies this shift
after placing each strip. The direct map now places each vertex at
`x = chord*((i+0.25)/M - elastic_axis)` and evaluates rotational displacement at
that same position. Moving the lattice without moving the structural moment arm
would not reproduce the reference. This is a vortex-lattice discretization
convention, not a change to the physical chord or elastic axis.

The experiments reuse SHARPy 2.4 source commit
`a4154d471c30f15db9af6524763ea250bb46c7b8` and existing image
`sha256:53f45db26c471d5d35b1aac8b77826f642f2b4dd74b8a1311838a3bb31e8de9a`.
No dependency was installed or sibling repository modified. Native MYSTRAN Goland
modes are the prior `goland-native.npz` export, hashed in the evidence.

## Model and controlled comparison

Use chord 1.8288 m, semispan 6.096 m, elastic axis 0.33 chord, air density
1.02 kg/m³, zero incidence, no gravity and zero physical structural damping.
Axes are x downstream, y spanwise, z up. The native beam frame is rotated into
this frame; translations and rotation cross vertex-offset define point motion.
One full-span lattice represents mirrored semispans with symmetric motion and
mode amplitude divided by sqrt(2), so total generalized mass is one. Frequencies
are 7.63739 and 15.21947 Hz. Root displacement is zero. Antisymmetric mechanisms,
fuselage interference and a physical wall are outside this benchmark.

Physical vertex forces are projected with the transpose of the point-motion
matrix. Arrays are flattened in SHARPy surface/xyz/chord/span C order. The same
map supplies point velocity. At reference speed 1 m/s, the aerodynamic system
uses circulation scaled by speed: displacement input is unchanged, velocity input
is divided by V and force output multiplied by V². Physical step is chord/(M V).
The zero-incidence reference force assertion passes; no deformed trim is involved.

Matching resolution is 16 chord panels, 16 span panels per half and a 10-chord
wake. The reference uses two aerodynamic surfaces; the direct experiment uses
one continuous full-span surface. Both retain two symmetric structural modes.

| Lattice and coupling convention | Oscillatory growth sign bracket (m/s) |
| --- | ---: |
| Prior native-MYSTRAN/upstream reference | 166.4211–166.5263 |
| Unshifted, raw predictor matrices used as standard feedback, ROM | 161.0–161.5 |
| Unshifted, causally converted predictor, ROM | 158.0–158.5 |
| Quarter-panel shift, raw predictor matrices used as standard feedback, ROM | 166.0–166.5 |
| Quarter-panel shift, causally converted predictor, ROM | 163.5–164.0 |

The shifted raw-reference run has growth -0.13697 /s at 166 m/s and +0.00886 /s
at 166.5 m/s; its upper-bracket frequency is 11.00265 Hz. This reproduces the
reference convention without tuning stiffness, mass, damping or frequencies.
It does **not** establish which finite-step result is physically converged.

All four controlled brackets above are unchanged at 0.5 m/s sampling when using
bilinear structural integration, zero-algorithmic-damping Newmark, or reference
Newmark algorithmic damping 5e-5. Physical damping remains zero. This bounds the
observed integration-choice effect only at that sampling resolution.

## Why the predictor distinction matters

Pinned `linuvlm.Dynamic` documents its unconverted equations as
`x[n+1] = A*x[n] + Bp*u[n+1]`, `y[n] = C*x[n] + D*u[n]`.
`libss.SSconv` substitutes `h[n] = x[n] - Bp*u[n]`, producing
`Bh = A*Bp`, `Dh = D + C*Bp`. The converted form is a standard causal state-space
system. The reference selects `remove_predictor=False` and feeds its matrices to
`libss.couple`, whose contract is standard state-space feedback; the controlled
raw cases intentionally reproduce that convention, not an exact predictor solve.

An independent generalized eigenproblem retains the original `u[n+1]` term and
closes the structural output/feedthrough equations directly. Its eigenvalues
agree with the causally converted coupled system to 5.00e-14 at 166.5 m/s.
This checks the algebra and feedthrough treatment, not aerodynamic model validity.
Do not remove the conversion merely to recover a familiar reference number.

## Checks and limitations

- Existing 86 repository tests pass; both experimental scripts compile.
- Native-map root motion is zero; random virtual-work absolute discrepancy is
  below 1e-10 in the shifted benchmark.
- Zero-load structural frequencies recovered by inverse bilinear mapping agree
  with native frequencies to 4.31e-15 relative error; maximum spurious growth
  is 3.25e-13 /s. This checks the unloaded structural block, not a V=0 UVLM solve.
- The 12-state observability Krylov reduction uses the pinned reference algorithm
  and order (r=6). The shifted ROM spectral radius is 0.97144194671, stable.
- For the **unshifted** system, full-versus-reduced transfer relative Frobenius
  error is 0.0108%, 0.0352%, 0.0754% at 50, 70, 100 rad/s, respectively, evaluated
  with the 166.5 m/s physical step. This does not certify the shifted ROM.
- Unshifted full-order causal growth is negative at 155 and positive at 160 m/s;
  unconverted full-order reference-convention growth is negative at 160 and
  positive at 165 m/s, consistent with the narrower ROM brackets.
- Growth envelopes are sampled, not mode-continuation tracks. Divergence is not
  independently classified. No time/wake/mesh convergence or shell-basis study
  is asserted. The benchmark is linear, incompressible and small-motion.

## Reproduction and retained artifacts

Scripts: `scripts/experiments/goland_modal_uvlm.py` assembles the direct interface;
`goland_coupling_controls.py` reuses projected matrices to isolate the conventions
and checks descriptor eigenvalues and the unloaded structural block. They are
bounded engineering experiments, not a production solver CLI. Run in the pinned
image with `/src` the read-only pinned SHARPy tree, `PYTHONPATH=/src`, `/results`
a writable artifact directory containing `goland-native.npz`, and `/experiment`
the read-only script directory. Disable container networking; retain logs.

For the shifted reference run, set `PANELS_M=16 PANELS_N=16 WAKE_FACTOR=10
SPEEDS=160,165,166,166.5,167,170 REMOVE_PREDICTOR=0 CASE_TAG=shifted-raw-rom`.
`PANEL_SHIFT=0.25 USE_ROM=1 STRUCTURAL_METHOD=newmark` are defaults. Run
`python /experiment/goland_modal_uvlm.py`. Output directories must not exist.
For controls on that reduced export, set
`MATRIX_CASE=shifted-raw-rom-M16-N16-W10 OUTPUT_CASE=shifted-coupling-controls
REDUCE_INPUT=0` and run `python /experiment/goland_coupling_controls.py`.
With reduction disabled, empty transfer-check results mean no new full-order
comparison was performed. Historical unshifted controls used the retained
full-order unconverted export and the default input case.

Large matrices, logs and earlier executed script versions remain under host
`runs/shell-uvlm-20261027/`. The committed
[evidence JSON](evidence/direct-uvlm-controls-20261027.json) includes numerical
reports, input/script hashes, execution warnings and the failed first reduction
attempt (missing SHARPy variable metadata), followed by the successful correction.
Final scripts were formatted after execution; the modal script's AST was checked
against its executed copy. The source mount's Git ownership warning did not stop
solves; host source commit was recorded without changing global Git trust.

## Next engineering gate

Keep #36 in progress. Isolate time-step convergence from chord refinement,
confirm the shifted full-order/reduced response and track the actual oscillatory
mode. Check a time-domain response against the causal eigenvalues. Only then
apply the direct paired-skin shell map with the same lattice convention,
explicit root symmetry, deformed-reference equilibrium, and 10/20/30-mode plus
wake/mesh/damping sensitivities. The existing hold on new CFD remains in force.
