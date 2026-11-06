"""Small-rotation, work-conjugate transfer of point forces to a structural line.

All positions/forces/translations/rotations use one right-handed global frame and
SI units. Surface points are XYZ positions (e.g. CFD face centres). Caller supplies
structural node positions; no elastic axis or structural properties are inferred.
"""
from bisect import bisect_right
from dataclasses import dataclass
import math
from numbers import Real


def _real(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _vectors(values, name, count=None):
    try:
        rows = tuple(tuple(row) for row in values)
    except TypeError as exc:
        raise ValueError(f'{name} must contain three-vectors') from exc
    if count is not None and len(rows) != count:
        raise ValueError(f'{name} count must be {count}')
    if any(len(row) != 3 for row in rows):
        raise ValueError(f'{name} must contain three-vectors')
    return tuple(tuple(_real(v, name) for v in row) for row in rows)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


@dataclass(frozen=True)
class Mapping:
    nodes_m: tuple
    surface_points_m: tuple
    contributions: tuple
    tip_tolerance_m: float
    max_projection_m: float


def build_mapping(nodes_m, surface_points_m, tip_tolerance_m=0.0):
    """Bracket XYZ surface sample positions by structural-node global y stations.

    Each sample uses two adjacent nodes. Allowed tip projection clamps only the
    interpolation station; the physical force/displacement lever arm is retained.
    Empty surface samples are allowed. Caller inputs are copied into tuples.
    """
    nodes = _vectors(nodes_m, 'nodes_m')
    points = _vectors(surface_points_m, 'surface_points_m')
    tolerance = _real(tip_tolerance_m, 'tip_tolerance_m')
    if tolerance < 0 or len(nodes) < 2:
        raise ValueError('Require nonnegative tolerance and at least two nodes')
    stations = tuple(n[1] for n in nodes)
    if any(not math.isfinite(b-a) or b <= a for a, b in zip(stations, stations[1:])):
        raise ValueError('Node y stations must be finite and strictly increasing')
    entries = []
    max_projection = 0.0
    for point in points:
        station = min(max(point[1], stations[0]), stations[-1])
        projection = abs(point[1]-station)
        if projection > tolerance:
            raise ValueError('Surface point lies outside structural span tolerance')
        max_projection = max(max_projection, projection)
        left = min(max(bisect_right(stations, station)-1, 0), len(nodes)-2)
        t = (station-stations[left])/(stations[left+1]-stations[left])
        pair = []
        for node, weight in ((left, 1-t), (left+1, t)):
            arm = tuple(_real(point[k]-nodes[node][k], 'lever arm') for k in range(3))
            pair.append((node, weight, arm))
        entries.append(tuple(pair))
    return Mapping(nodes, points, tuple(entries), tolerance, max_projection)


def map_forces(mapping, surface_forces_N):
    """Return (nodal forces in N, nodal couples in N m), all three components."""
    forces = _vectors(surface_forces_N, 'surface_forces_N', len(mapping.surface_points_m))
    nodal = [[0.0]*3 for _ in mapping.nodes_m]
    couples = [[0.0]*3 for _ in mapping.nodes_m]
    for force, pair in zip(forces, mapping.contributions):
        for node, weight, arm in pair:
            moment = _cross(arm, force)
            for k in range(3):
                nodal[node][k] += weight*force[k]
                couples[node][k] += weight*moment[k]
    return _vectors(nodal, 'nodal force'), _vectors(couples, 'nodal couple')


def map_displacements(mapping, node_translations_m, node_rotations_rad):
    """Map small nodal motions using u_sample = sum N*(u_node + theta cross arm)."""
    translations = _vectors(node_translations_m, 'node_translations_m', len(mapping.nodes_m))
    rotations = _vectors(node_rotations_rad, 'node_rotations_rad', len(mapping.nodes_m))
    result = []
    for pair in mapping.contributions:
        value = [0.0]*3
        for node, weight, arm in pair:
            rotation = _cross(rotations[node], arm)
            for k in range(3):
                value[k] += weight*(translations[node][k]+rotation[k])
        result.append(value)
    return _vectors(result, 'surface displacement')
