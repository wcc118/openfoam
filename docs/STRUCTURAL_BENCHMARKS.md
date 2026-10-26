# Structural benchmarks

**Status:** In development for issue #24. No native execution or physical validation.

## Overview

This directory contains deterministic SI cantilever benchmark Nastran decks for MYSTRAN 19.0.0.
The benchmarks target SOL101 (linear static) and SOL103 (modal) analysis with three cases:

1. **Static transverse bending:** Tip load in global z direction
2. **Static torsion:** Tip moment about global x axis
3. **Normal bending modes:** Six eigenmodes via EIGRL

## Usage

```bash
python3 scripts/generate_structure_benchmarks.py --output-directory PATH
```

**CLI arguments:**
- `--output-directory PATH` (required): Output directory for decks and reference JSON
- `--element-count N` (default: 20): Number of equal-length elements
- `--radius R` (default: 0.005): Circular section radius in meters
- `--length L` (default: 1.0): Beam length in meters
- `--young-modulus E` (default: 70e9): Young's modulus in Pa
- `--poisson NU` (default: 0.3): Poisson's ratio
- `--density rho` (default: 2700): Density in kg/m³

**Output:**
- `bend_static.bdf`: SOL101 deck for transverse bending
- `torsion_static.bdf`: SOL101 deck for torsion
- `modal_bend.bdf`: SOL103 deck for eigenmodes
- `reference.json`: SI reference values and tolerances

## Model definition

**Geometry:**
- Circular cross-section, radius 0.005 m
- Length 1.0 m
- 20 equal elements, 21 nodes
- Beam lies along global x-axis (root at x=0, tip at x=1)
- CBAR orientation vector: global y-direction (0, 1, 0)

**Material (aluminum):**
- Young's modulus: 70 GPa
- Poisson's ratio: 0.3
- Density: 2700 kg/m³
- Shear modulus: G = E/(2(1+ν)) ≈ 26.92 GPa

**Section properties:**
- Area: A = πr² ≈ 7.854e-5 m²
- Moment of inertia (both planes): I = πr⁴/4 ≈ 4.909e-10 m⁴
- Torsional constant: J = πr⁴/2 ≈ 9.817e-10 m⁴

**Boundary conditions:**
- SPC1 ID=1: Root node (GRID 1) all DOFs fixed (123456)

**Loads:**
- Bending: FORCE2, tip node, Fz=1 N
- Torsion: MOMENT2, tip node, Mx=1 Nm

## Analytic references

**Static bending (tip deflection, Euler-Bernoulli):**
- Deflection: δ = FL³/(3EI) ≈ 0.00763 m
- Rotation: θ = FL²/(2EI) ≈ 0.01526 rad

**Static torsion (tip angle, Euler-Bernoulli):**
- Angle: φ = TL/(GJ) ≈ 0.04775 rad

**Modal frequencies (Euler-Bernoulli):**
- f = β²/(2π) × √(EI/(ρAL⁴))

| Mode | β value | Frequency (Hz) |
|------|---------|----------------|
| 1 | 1.875104068711961 | ~1.48 |
| 2 | 4.694091132974174 | ~9.43 |
| 3 | 7.854757438237612 | ~26.03 |

**Total mass:** m = ρAL ≈ 0.0785 kg

## JSON reference

The generated `reference.json` contains:

- Model parameters (geometry, material, section)
- Static bending: load, analytic δ, analytic θ, tolerance (1% relative)
- Static torsion: load, analytic φ, tolerance (1% relative)
- Modal bending: eigenvalue method, requested modes, β values, analytic frequencies, tolerance (2% for first bending)
- Output file SHA256 hashes
- Assumptions and limitations

**Tolerances are prospective**—not observed values.

## Assumptions and limitations

1. **Beam theory:** Euler-Bernoulli (slender beam, neglects shear deformation and rotary inertia)
2. **Material:** Isotropic linear elastic
3. **Cross-section:** Perfect circular geometry
4. **Boundary:** Root node all DOFs fixed (SPC1 123456)
5. **Solver differences:** MYSTRAN may differ in shear/rotary inertia/mass formulations
6. **Verification:** Native execution with MYSTRAN required for physical validation
7. **Degeneracy:** Circular beam has duplicate bending planes; first six solver modes include torsional/axial modes

**No claim of physical verification before actual MYSTRAN execution.** This is a deterministic
benchmark generator for engineering comparison, not an oracle.

## Provenance

**Source:** MYSTRAN 19.0.0
- Repository: https://github.com/MystranSolver/MYSTRANSolver
- Commit: 3a5913a904ee1adbda9fbcaf9c0a6af8e10f0f9f
- License: MIT

**Deck format:** Nastran free-field (NASTRAN compatibility mode)
- Supported cards: GRID, CBAR, PBAR, MAT1, SPC1, FORCE2, MOMENT2, LOAD, EIGRL
- See `dev_docs/bdf_card_compatibility.md` in MYSTRAN repository

**Distinction:** Static (SOL101) and modal (SOL103) analysis only.
No flutter prediction capability.

## Test coverage

Run tests with:
```bash
python3 -m pytest tests/test_generate_structure_benchmarks.py -v
```

Tests verify:
- Deck content (required cards, solution type, SPC1, load direction)
- Geometry (node count, coordinates, element count)
- Material properties (E, G, ν, ρ)
- Section properties (A, I, J)
- Reference JSON (analytic values, tolerances, provenance, SHA256)
- CLI behavior (output directory validation, determinism)
- Input validation (element count, nonnegative values)

## See also

- [Engineering plan](ENGINEERING_PLAN.md)
- [Reuse inventory](REUSE_INVENTORY.md)
- [First flow case](FIRST_FLOW_CASE.md)
