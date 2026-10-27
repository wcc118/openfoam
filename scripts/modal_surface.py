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
    """Compute physical displacements u = H q.
    
    Args:
        basis: [mode][point][xyz] shape matrix H
        q: [mode] modal coordinates
    
    Returns:
        [point][xyz] physical displacements as new list
    """
    _validate_basis(basis)
    _validate_q(basis, q)
    nmodes, npts = len(basis), len(basis[0])
    result = []
    for p in range(npts):
        xyz = [0.0, 0.0, 0.0]
        for i in range(nmodes):
            hi = basis[i][p]
            qi = q[i]
            for k in range(3):
                xyz[k] += hi[k] * qi
        result.append(xyz)
    return result


def generalized_forces(basis, forces):
    """Compute modal forces Q = H^T f.
    
    Args:
        basis: [mode][point][xyz] shape matrix H
        forces: [point][xyz] physical forces
    
    Returns:
        [mode] generalized forces as new list
    """
    _validate_basis(basis)
    _validate_forces(basis, forces)
    nmodes, npts = len(basis), len(basis[0])
    result = []
    for i in range(nmodes):
        qi = 0.0
        for p in range(npts):
            hi = basis[i][p]
            fp = forces[p]
            for k in range(3):
                qi += hi[k] * fp[k]
        result.append(qi)
    return result


def mass_gram(basis, point_masses):
    """Compute modal mass matrix M_{ij} = sum_p m_p phi_i,p phi_j,p.
    
    Args:
        basis: [mode][point][xyz] shape matrix H
        point_masses: [point] scalar masses in grams
    
    Returns:
        [mode][mode] symmetric modal mass matrix as new list
    """
    _validate_basis(basis)
    _validate_masses(basis, point_masses)
    nmodes, npts = len(basis), len(basis[0])
    result = [[0.0] * nmodes for _ in range(nmodes)]
    for p in range(npts):
        mp = point_masses[p]
        for i in range(nmodes):
            phi_i = basis[i][p]
            for k in range(3):
                phi_ik = phi_i[k]
                for j in range(i, nmodes):
                    phi_j = basis[j][p]
                    phi_jk = phi_j[k]
                    result[i][j] += mp * phi_ik * phi_jk
                    if i != j:
                        result[j][i] = result[i][j]
    return result
