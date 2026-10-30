"""Modal surface interface: displacement and force projection between physical and modal spaces.

Basis shape: [mode][point][xyz] -> H[i][p][k] where i=mode, p=point, k=xyz.
Physical vectors use SI conventions: displacements in meters, forces in Newtons.

Functions:
  displacements(basis, q): Compute physical displacements u = H q
  generalized_forces(basis, forces): Compute modal forces Q = H^T f
  mass_gram(basis, point_masses): Compute modal mass matrix M = sum_p m_p phi_i,p phi_j,p
"""

import math


def _validate_basis(basis):
    """Validate basis structure and contents. Returns (nmodes, npts)."""
    if not isinstance(basis, list) or not basis:
        raise ValueError("basis must be a nonempty list of modes")
    if not isinstance(basis[0], list) or not basis[0]:
        raise ValueError("basis must contain nonempty mode arrays")
    nmodes = len(basis)
    npts = len(basis[0])
    if npts == 0:
        raise ValueError("basis must have at least one point per mode")
    for i, mode in enumerate(basis):
        if not isinstance(mode, list):
            raise ValueError(f"mode {i} must be a list")
        if len(mode) != npts:
            raise ValueError(f"mode {i} has {len(mode)} points, expected {npts}")
        for j, pt in enumerate(mode):
            if not isinstance(pt, list) or len(pt) != 3:
                raise ValueError(f"basis[{i}][{j}] must be [x,y,z] with 3 components")
            for k, val in enumerate(pt):
                if not isinstance(val, (int, float)) or not math.isfinite(val):
                    raise ValueError(f"basis[{i}][{j}][{k}] must be finite numeric")
    return nmodes, npts


def _validate_q(basis, q):
    """Validate modal coordinates match basis modes."""
    nmodes, _ = _validate_basis(basis)
    if not isinstance(q, list) or len(q) != nmodes:
        raise ValueError(f"q must have {nmodes} modal coordinates")
    for i, val in enumerate(q):
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            raise ValueError(f"q[{i}] must be finite numeric")


def _validate_forces(basis, forces):
    """Validate physical forces match basis points."""
    _, npts = _validate_basis(basis)
    if not isinstance(forces, list) or len(forces) != npts:
        raise ValueError(f"forces must have {npts} point forces")
    for i, pt in enumerate(forces):
        if not isinstance(pt, list) or len(pt) != 3:
            raise ValueError(f"forces[{i}] must be [fx,fy,fz] with 3 components")
        for k, val in enumerate(pt):
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"forces[{i}][{k}] must be finite numeric")


def _validate_masses(basis, point_masses):
    """Validate point masses match basis points and are positive."""
    _, npts = _validate_basis(basis)
    if not isinstance(point_masses, list) or len(point_masses) != npts:
        raise ValueError(f"point_masses must have {npts} masses")
    for i, m in enumerate(point_masses):
        if not isinstance(m, (int, float)) or not math.isfinite(m) or m <= 0:
            raise ValueError(f"point_masses[{i}] must be finite positive")


def displacements(basis, q):
    """Return owned point translations Hq; basis scaling determines q units."""
    _validate_q(basis, q)
    return [[math.fsum(basis[i][p][k] * q[i] for i in range(len(basis)))
             for k in range(3)] for p in range(len(basis[0]))]


def generalized_forces(basis, forces):
    """Return H-transpose f, conjugate to q: Q dot dq = f dot du (joules)."""
    _validate_forces(basis, forces)
    return [math.fsum(mode[p][k] * forces[p][k]
                     for p in range(len(forces)) for k in range(3))
            for mode in basis]


def mass_gram(basis, point_masses):
    """Return Phi-transpose M Phi for scalar point masses in kilograms.

    Modal mass units depend on the supplied mode normalization. No normalization
    or mass conversion is performed. Only translational point masses are modeled.
    """
    _validate_masses(basis, point_masses)
    return [[math.fsum(point_masses[p] * a[p][k] * b[p][k]
                       for p in range(len(point_masses)) for k in range(3))
             for b in basis] for a in basis]
