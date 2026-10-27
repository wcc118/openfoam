# Modal Surface Interface

## Overview

`scripts/modal_surface.py` provides utility functions for projecting between physical and modal spaces for shell structures. The interface follows the standard reduced-order approximation:

- Physical displacement: **u = H q**
- Generalized force: **Q = H^T f**
- Modal mass matrix: **M_ij = Σ_p m_p φ_i,p · φ_j,p**

Where:
- **H** is the shape matrix with shape `[mode][point][xyz]`
- **q** is the vector of modal coordinates
- **u** is the physical displacement vector
- **f** is the physical force vector
- **Q** is the generalized force vector
- **M** is the modal mass matrix
- **φ_i,p** is the i-th mode evaluated at point p

## Usage

```python
from scripts.modal_surface import displacements, generalized_forces, mass_gram

# Basis: [mode][point][xyz] - shape matrix H
basis = [
    [[1.0, 0.0, 0.0], [0.5, 0.0, 0.0]],  # Mode 0: bending in x
    [[0.0, 0.0, 1.0], [0.0, 0.0, 0.5]],  # Mode 1: bending in z
]

# Modal coordinates q (unit depends on modal normalization)
q = [0.01, -0.005]  # meters for physical translation modes

# Compute physical displacements at each point
u = displacements(basis, q)  # [point][xyz] in meters

# Physical forces at each point (Newtons)
forces = [[10.0, 0.0, 0.0], [5.0, 0.0, 0.0]]

# Compute generalized forces
Q = generalized_forces(basis, forces)  # [mode] in N·m (conjugate to q)

# Point masses in grams
point_masses = [100.0, 50.0]  # grams

# Compute modal mass matrix
M = mass_gram(basis, point_masses)  # [mode][mode] in grams
```

## Conventions

### SI Units

- **Displacements u**: meters (m)
- **Forces f**: Newtons (N)
- **Generalized forces Q**: Newton-meters (N·m) if q is in meters
- **Point masses**: grams (g)
- **Modal mass matrix M**: grams (g)

### Mode Normalization

The module does not assume any particular mode normalization. Common conventions:

- **Physical displacement normalization**: modes represent unit physical displacement
- **Mass normalization**: modes scaled so that M = I (identity)
- **Maximum displacement normalization**: max |φ| = 1

The choice of normalization affects the units of q and Q:
- If q is in meters (physical displacement), Q is in Newtons
- If q is dimensionless (normalized mode), Q is in Newton-meters

### Axes

The standard right-handed coordinate system is used:
- **x**: chord downstream
- **y**: root to tip (spanwise)
- **z**: up (lift direction)

### Shape Matrix Layout

```python
# H[i][p][k] where:
#   i = mode index (0..nmodes-1)
#   p = point index (0..npts-1)
#   k = component index (0=x, 1=y, 2=z)
```

Example for 2 modes, 3 points:

```python
H = [
    [[Hx0, Hy0, Hz0], [Hx1, Hy1, Hz1], [Hx2, Hy2, Hz2]],  # Mode 0
    [[Hx0, Hy0, Hz0], [Hx1, Hy1, Hz1], [Hx2, Hy2, Hz2]],  # Mode 1
]
```

## Functions

### `displacements(basis, q)`

Compute physical displacements **u = H q**.

**Arguments:**
- `basis`: `[mode][point][xyz]` shape matrix
- `q`: `[mode]` modal coordinates

**Returns:** `[point][xyz]` physical displacements in meters

### `generalized_forces(basis, forces)`

Compute generalized forces **Q = H^T f**.

**Arguments:**
- `basis`: `[mode][point][xyz]` shape matrix
- `forces`: `[point][xyz]` physical forces in Newtons

**Returns:** `[mode]` generalized forces

### `mass_gram(basis, point_masses)`

Compute modal mass matrix **M_ij = Σ_p m_p φ_i,p · φ_j,p**.

**Arguments:**
- `basis`: `[mode][point][xyz]` shape matrix
- `point_masses`: `[point]` scalar masses in grams

**Returns:** `[mode][mode]` symmetric modal mass matrix in grams

## Virtual Work Consistency

The implementation preserves virtual work:

```
u · f = q · Q
```

where:
- `u · f = Σ_p Σ_k u_p,k * f_p,k` (physical work)
- `q · Q = Σ_i q_i * Q_i` (modal work)

This equality is verified by tests and holds for any basis Q and force configuration.

## Error Handling

All functions validate inputs and raise `ValueError` for:

- Empty or ragged basis arrays
- Non-finite values (NaN, inf)
- Dimension mismatches between basis, q, forces, and masses
- Non-positive point masses
- Non-numeric values

## Limitations

- No automatic normalization or scaling of modes
- No rotation or lever arm inference
- Direct shell-node mapping only (no aerodynamic interpolation)
- Not a solver: does not compute modes or frequencies

## Testing

Run tests with:

```bash
python -m unittest tests.test_modal_surface -v
```

Tests include:
- Handcomputed displacement and force values
- Virtual work equality (u·f = q·Q)
- Column rescaling invariance
- Off-diagonal mass matrix terms
- Zero/root basis handling
- Input validation (ragged, nonfinite, mismatched)

## References

- Issue #34: Shell modal interface implementation
- `FSI_FLUTTER_PLAN.md`: Modal extraction and coupling strategy
- `test_aluminum_shell.py`: Shell geometry generation
