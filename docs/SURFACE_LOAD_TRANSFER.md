# Surface Load Transfer

This module implements a small-rotation, work-conjugate transfer of point forces to a structural line model. It maps surface samples (e.g., CFD face centres) to structural nodal forces and couples, and provides the work-conjugate displacement mapping.

## Overview

The transfer operator handles:
- Point forces → nodal forces and couples (moment calculation)
- Nodal displacements and rotations → surface displacements (work-conjugate transpose)

**Physical domain**: Linear interpolation in structural y-coordinate, full 3D lever arm for moments.
**Kinematic domain**: Small rotations (first-order approximation), linear interpolation of nodal motions.

## Coordinate System

**Global frame**: Right-handed Cartesian system with SI units (metres, newtons, radians).

```
z
|   y
|  /
| /
o------ x
```

- **x**: Downstream, along the undeformed wing chord
- **y**: Wing span; structural interpolation stations must increase along this axis
- **z**: Up. Wind-axis lift and drag directions depend on angle of attack.

All positions, forces, displacements, and rotations use this single global frame.

## API

### Mapping Dataclass

```python
@dataclass(frozen=True)
class Mapping:
    nodes_m: tuple        # Structural node positions (XYZ, metres)
    surface_points_m: tuple  # Sample positions (XYZ, metres)
    contributions: tuple  # Interpolation weights and lever arms
    tip_tolerance_m: float  # Allowed out-of-span projection (metres)
    max_projection_m: float # Maximum observed projection in this mapping
```

Create a mapping using `build_mapping()`. The mapping is immutable and stores tuples.

### Build Mapping

```python
def build_mapping(nodes_m, surface_points_m, tip_tolerance_m=0.0):
    """Bracket XYZ surface sample positions by structural-node global y stations.

    Args:
        nodes_m: Sequence of 3D node positions [(x,y,z), ...] in metres.
                Node y coordinates must be finite and strictly increasing.
        surface_points_m: Sequence of 3D sample positions in metres.
        tip_tolerance_m: Allowed projection beyond node span (metres).
                        Clamps interpolation station; physical lever arm retained.

    Returns:
        Mapping dataclass with interpolation data.

    Raises:
        ValueError: Invalid inputs, unordered nodes, negative tolerance,
                   point outside span tolerance, or fewer than 2 nodes.
    """
```

### Map Forces

```python
def map_forces(mapping, surface_forces_N):
    """Return (nodal forces in N, nodal couples in N m), all three components.

    Args:
        mapping: Mapping from build_mapping().
        surface_forces_N: Force vectors at each surface point [(Fx,Fy,Fz), ...] in newtons.
                         Count must match mapping.surface_points_m.

    Returns:
        (nodal_forces, nodal_couples) where:
        - nodal_forces: Force vectors at each node [(Fx,Fy,Fz), ...] in newtons
        - nodal_couples: Moment vectors at each node [(Mx,My,Mz), ...] in newton-metres

    Moment calculation: For each surface point with lever arm r and force F,
    the moment about the node is M = r × F (cross product).
    """
```

### Map Displacements

```python
def map_displacements(mapping, node_translations_m, node_rotations_rad):
    """Map small nodal motions using u_sample = Σ N·(u_node + θ × r).

    Args:
        mapping: Mapping from build_mapping().
        node_translations_m: Node displacement vectors [(ux,uy,uz), ...] in metres.
                            Count must match number of nodes.
        node_rotations_rad: Node rotation vectors [(θx,θy,θz), ...] in radians.
                          Count must match number of nodes.
                          Small rotation approximation (first-order).

    Returns:
        surface_displacements: Displacement vectors at each surface point
                              [(ux,uy,uz), ...] in metres.

    The displacement at a surface point is interpolated from surrounding nodes,
    with rotation contribution θ × r (rotation vector cross lever arm).
    """
```

## Formulas

### Force Transfer

For a surface point at position **p** with force **F**:

1. Reject points beyond the explicit tip tolerance, then clamp the admitted y-station to `[y₀, yₙ]`
2. Find bracketing nodes `i, i+1` such that `yᵢ ≤ y ≤ yᵢ₊₁`
3. Interpolation station: `t = (y - yᵢ) / (yᵢ₊₁ - yᵢ)`
4. Lever arms: `r₀ = p - node₀`, `r₁ = p - node₁`
5. Weighted contributions:
   - Node `i`: weight `1-t`, force `(1-t)·F`, couple `(1-t)·(rᵢ × F)`
   - Node `i+1`: weight `t`, force `t·F`, couple `t·(rᵢ₊₁ × F)`

### Displacement Transfer (Work-Conjugate)

For nodal displacements **uᵢ** and rotations **θᵢ**:

At surface point with bracketing nodes `i, i+1`:
- Displacement from node `i`: `Nᵢ·(uᵢ + θᵢ × rᵢ)`
- Displacement from node `i+1`: `Nᵢ₊₁·(uᵢ₊₁ + θᵢ₊₁ × rᵢ₊₁)`

Total: `u = (1-t)·(uᵢ + θᵢ × rᵢ) + t·(uᵢ₊₁ + θᵢ₊₁ × rᵢ₊₁)`

### Conservation Properties

- **Force balance**: Σ nodal_forces = Σ surface_forces (up to roundoff)
- **Moment balance**: Σ (nodal_couples + nodeᵢ × nodal_forcesᵢ) = Σ (surface_pointᵢ × surface_forceᵢ) (up to roundoff, about any origin)
- **Virtual work**: Σ (surface_forceᵢ · surface_displacementᵢ) = Σ (nodal_forceᵢ · node_displacementᵢ) + Σ (nodal_coupleᵢ · node_rotationᵢ) (up to roundoff)

*Note: Conservation checks establish algebraic consistency; they do not establish spatial interpolation accuracy or physical validity.*

## Limitations

1. **Linear interpolation**: Only two adjacent nodes contribute per surface point. No higher-order shape functions.

2. **Small rotations**: Rotation contribution uses first-order approximation `u_rot = θ × r`. Large rotations require geometrically exact formulations.

3. **Structural line model**: Nodes are assumed colinear in y-direction for interpolation purposes. Actual node positions may be 3D; lever arms use full 3D positions.

4. **No physics inference**: This module performs interpolation only. It supplies:
   - No stiffness, mass, or damping matrices
   - No dynamic aerodynamics
   - No flutter analysis
   - No elastic axis definition

5. **Caller responsibilities**:
   - Supply actual structural node positions (no assumed axis)
   - Ensure y stations are strictly increasing
   - Provide consistent reference frames
   - Handle time-stepping and convergence externally

## Usage Example

```python
from transfer_surface_loads import build_mapping, map_forces, map_displacements

# Structural nodes (3D positions)
nodes = [
    (0.0, 0.0, 0.0),   # root
    (0.0, 5.0, 0.0),   # midspan
    (0.0, 10.0, 0.0),  # tip
]

# CFD surface points (e.g., face centres)
points = [
    (1.0, 2.5, 0.01),  # near midspan
    (1.0, 7.5, 0.01),  # near tip
]

# Build interpolation mapping
mapping = build_mapping(nodes, points, tip_tolerance_m=0.1)

# Map aerodynamic forces to structural loads
forces = [
    (100.0, 0.0, -500.0),  # x, y, z forces at point 0
    (80.0, 0.0, -400.0),   # x, y, z forces at point 1
]

nodal_forces, nodal_couples = map_forces(mapping, forces)

# Map structural motion to surface displacement (e.g., for virtual work)
translations = [
    (0.001, 0.0, 0.0),    # node 0 deflection
    (0.002, 0.0, 0.001),  # node 1 deflection
    (0.003, 0.0, 0.002),  # node 2 deflection
]

rotations = [
    (0.0, 0.0, 0.01),     # node 0 rotation (rad)
    (0.0, 0.0, 0.008),    # node 1 rotation
    (0.0, 0.0, 0.005),    # node 2 rotation
]

surface_displacements = map_displacements(mapping, translations, rotations)
```

## Testing

Run the unit test suite:
```bash
python -m unittest tests.test_transfer_surface_loads -v
```

Tests verify:
- Hand-calculated verification case
- Force and moment conservation
- Virtual work equality
- Rigid translation and rotation reproduction
- Endpoint handling and tolerance behavior
- Invalid input rejection
- Immutable input preservation

## References

- Work-conjugate pairing: forces with displacements, couples with rotations
- Small rotation approximation: `δu = θ × r` for first-order kinematics
- Linear Lagrange interpolation: two-node segment shape functions
