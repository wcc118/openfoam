"""Portable case runner for modal free-decay verification.

Reads a portable case JSON fixture, validates it against the contract,
runs the modal dynamics simulation, and produces a JSON report.

CLI: python3 -m scripts.portable_case INPUT --output OUTPUT
"""

import argparse
import hashlib
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from scripts.modal_dynamics import ModalSystem
from scripts.modal_surface import displacements, generalized_forces


def _compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def _compute_sha256_str(text: str) -> str:
    """Compute SHA256 hash of UTF-8 string."""
    return _compute_sha256_bytes(text.encode('utf-8'))


def _validateFinite(value: Any, name: str) -> None:
    """Validate that value is finite and not a boolean."""
    if isinstance(value, bool):
        raise ValueError(f'{name} must be numeric, not boolean')
    if not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be numeric')
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')


def _validateFiniteArray(arr: Any, name: str) -> None:
    """Validate array contains only finite numeric values."""
    if not isinstance(arr, list):
        raise ValueError(f'{name} must be a list')
    if not arr:
        raise ValueError(f'{name} must be nonempty')
    flat = [v for sub in arr for v in (sub if isinstance(sub, list) else [sub])]
    for v in flat:
        _validateFinite(v, f'{name} element')


def _validateNonemptyList(arr: Any, name: str) -> None:
    """Validate that arr is a nonempty list."""
    if not isinstance(arr, list) or not arr:
        raise ValueError(f'{name} must be a nonempty list')


def _validateFiniteNonnegative(value: Any, name: str) -> None:
    """Validate finite nonnegative value."""
    _validateFinite(value, name)
    if value < 0:
        raise ValueError(f'{name} must be nonnegative')


def _validateFinitePositive(value: Any, name: str) -> None:
    """Validate finite positive value."""
    _validateFinite(value, name)
    if value <= 0:
        raise ValueError(f'{name} must be positive')


def _validateFiniteNonnegativeArray(arr: Any, name: str) -> None:
    """Validate array contains only finite nonnegative values."""
    if not isinstance(arr, list) or not arr:
        raise ValueError(f'{name} must be a nonempty list')
    for v in arr:
        _validateFiniteNonnegative(v, f'{name} element')


def _validateFinitePositiveArray(arr: Any, name: str) -> None:
    """Validate array contains only finite positive values."""
    if not isinstance(arr, list) or not arr:
        raise ValueError(f'{name} must be a nonempty list')
    for v in arr:
        _validateFinitePositive(v, f'{name} element')


def _validateArrayShape(arr: Any, expected_shape: Tuple[int, ...], name: str) -> None:
    if not isinstance(arr, list) or len(arr) != expected_shape[0]:
        raise ValueError(f'{name} must have shape {expected_shape}')
    for i, value in enumerate(arr):
        if len(expected_shape) == 1:
            _validateFinite(value, f'{name}[{i}]')
        else:
            _validateArrayShape(value, expected_shape[1:], f'{name}[{i}]')


def _validateUniqueIds(ids: List[Any], name: str) -> None:
    """Validate list contains unique nonempty IDs (string or numeric)."""
    _validateNonemptyList(ids, name)
    seen = set()
    for i, id_ in enumerate(ids):
        # Allow strings or numbers
        is_valid_id = (
            (isinstance(id_, str) and id_) or
            (isinstance(id_, (int, float)) and not isinstance(id_, bool))
        )
        if not is_valid_id:
            raise ValueError(f'{name}[{i}] must be a nonempty ID')
        if isinstance(id_, (int, float)):
            _validateFinite(id_, name)
        if id_ in seen:
            raise ValueError(f'{name}[{i}] is a duplicate ID')
        seen.add(id_)


def _validateNonemptyString(value: Any, name: str) -> None:
    """Validate nonempty string."""
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a nonempty string')


def _validateDirection(arr: Any, name: str) -> None:
    """Validate that arr is a unit vector within 1e-10 tolerance."""
    _validateArrayShape(arr, (3,), name)
    if len(arr) != 3:
        raise ValueError(f'{name} must have 3 components')
    norm = math.sqrt(sum(x*x for x in arr))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError(f'{name} must be a finite nonzero vector')
    if abs(norm - 1.0) > 1e-10:
        raise ValueError(f'{name} must be a unit vector within 1e-10 tolerance')


def _validateIdsMatch(actual: List[Any], expected: List[Any], name: str) -> None:
    """Validate that actual IDs match expected IDs exactly."""
    if isinstance(expected, list):
        _validateUniqueIds(actual, name)
    if actual != expected:
        raise ValueError(f'{name} IDs must match reference')


def _validateTimeHistory(times: List[float], name: str) -> None:
    """Validate time history: starts at zero, at least two samples, strictly increasing."""
    if not isinstance(times, list) or len(times) < 2:
        raise ValueError(f'{name} must have at least two samples')
    if times[0] != 0.0:
        raise ValueError(f'{name} must start at zero')
    for i in range(1, len(times)):
        if not isinstance(times[i], (int, float)) or not math.isfinite(times[i]):
            raise ValueError(f'{name}[{i}] must be finite')
        if times[i] <= times[i-1]:
            raise ValueError(f'{name} must be strictly increasing')


def _validateModalMassFrequency(mass: float, stiffness: float, damping: float, freq_hz: float) -> None:
    """Validate frequency matches sqrt(k/m)/(2*pi) within tolerance."""
    if mass <= 0 or stiffness < 0:
        return  # Skip frequency check if invalid
    expected_freq = math.sqrt(stiffness / mass) / (2 * math.pi)
    # Relative 1e-10 plus absolute 1e-12 Hz tolerance
    diff = abs(freq_hz - expected_freq)
    tolerance = 1e-10 * expected_freq + 1e-12
    if diff > tolerance:
        raise ValueError(f'frequency_hz {freq_hz} does not match sqrt(k/m)/(2*pi)={expected_freq}')


def _validateDampingKind(damping: Dict[str, Any]) -> Tuple[str, Optional[float]]:
    """Validate damping configuration and return (kind, c_value or None)."""
    if not isinstance(damping, dict):
        raise ValueError('damping must be a dictionary')
    if 'kind' not in damping:
        raise ValueError('damping must have a kind field')
    kind = damping.get('kind')
    if kind not in ('assumed', 'measured', 'unknown'):
        raise ValueError(f'Unsupported damping kind: {kind}')

    if kind == 'unknown':
        if 'c_kg_per_s' not in damping:
            raise ValueError('unknown damping must have explicit null c_kg_per_s')
        if 'c_kg_per_s' in damping:
            if damping['c_kg_per_s'] is not None:
                raise ValueError('unknown damping must have null c_kg_per_s')
        return kind, None
    else:
        if 'c_kg_per_s' not in damping:
            raise ValueError(f'{kind} damping must have c_kg_per_s')
        c_val = damping['c_kg_per_s']
        if c_val is None:
            raise ValueError(f'{kind} damping must have nonnull c_kg_per_s')
        _validateFiniteNonnegative(c_val, 'damping coefficient')
        return kind, c_val


def validate_case(case: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate a portable case against the v1 contract.

    Returns (is_valid, error_message). Does not execute any simulation.
    Does not modify the input case.
    """
    import copy
    # Deep copy to avoid modifying input
    case = copy.deepcopy(case)

    try:
        # Schema version and profile
        if not isinstance(case, dict):
            raise ValueError('case must be a dictionary')
        if type(case.get('schema_version')) is not int or case['schema_version'] != 1:
            raise ValueError('schema_version must be 1')
        if case.get('profile') != 'diagonal_modal_point_forces':
            raise ValueError('profile must be "diagonal_modal_point_forces"')

        # Basic identifiers
        if not isinstance(case.get('case_id'), str) or not case['case_id']:
            raise ValueError('case_id must be a nonempty string')

        # Configuration section
        config = case.get('configuration')
        if not isinstance(config, dict):
            raise ValueError('configuration must be a dictionary')

        _validateNonemptyString(config.get('id'), 'configuration.id')
        for field in ('support_conditions', 'joint_state'):
            _validateNonemptyString(config.get(field), 'configuration.' + field)
        axes = config.get('axes')
        if axes not in (['x_downstream', 'y_spanwise', 'z_up'],):
            raise ValueError('axes must be ["x_downstream", "y_spanwise", "z_up"]')
        if config.get('handedness') != 'right':
            raise ValueError('handedness must be "right"')
        if config.get('length_unit') != 'm':
            raise ValueError('length_unit must be "m"')
        if config.get('time_unit') != 's':
            raise ValueError('time_unit must be "s"')
        if config.get('reference_shape') != 'undeformed':
            raise ValueError('reference_shape must be "undeformed"')

        # Geometry section
        geom = case.get('geometry')
        if not isinstance(geom, dict):
            raise ValueError('geometry must be a dictionary')

        _validateIdsMatch(geom.get('configuration_id'), config.get('id'), 'geometry.configuration_id')
        node_ids = geom.get('node_ids')
        _validateUniqueIds(node_ids, 'geometry.node_ids')
        nodes = geom.get('nodes_m')
        _validateArrayShape(nodes, (len(node_ids), 3), 'geometry.nodes_m')
        _validateFiniteArray(nodes, 'geometry.nodes_m')

        tip_ids = geom.get('tip_node_ids')
        _validateUniqueIds(tip_ids, 'tip_node_ids')
        if not tip_ids:
            raise ValueError('tip_node_ids must be nonempty')
        if not all(tip in node_ids for tip in tip_ids):
            raise ValueError('tip_node_ids must be a subset of geometry.node_ids')

        # Structure section
        struct = case.get('structure')
        if not isinstance(struct, dict):
            raise ValueError('structure must be a dictionary')

        _validateIdsMatch(struct.get('configuration_id'), config.get('id'), 'structure.configuration_id')
        struct_node_ids = struct.get('node_ids')
        _validateIdsMatch(struct_node_ids, node_ids, 'structure.node_ids')

        components = struct.get('components')
        if components != ['ux', 'uy', 'uz']:
            raise ValueError('structure.components must be ["ux", "uy", "uz"]')

        if struct.get('basis_units') != 'dimensionless':
            raise ValueError('structure.basis_units must be "dimensionless"')
        if struct.get('coordinate_units') != 'm':
            raise ValueError('structure.coordinate_units must be "m"')
        if struct.get('normalization') != 'explicit_modal_mass':
            raise ValueError('structure.normalization must be "explicit_modal_mass"')

        modes = struct.get('modes')
        if not isinstance(modes, list) or not modes:
            raise ValueError('structure.modes must be a nonempty list')

        # Validate each mode
        for i, mode in enumerate(modes):
            if not isinstance(mode, dict):
                raise ValueError(f'modes[{i}] must be a dictionary')

            _validateNonemptyString(mode.get('id'), f'modes[{i}].id')

            shape = mode.get('shape')
            if not isinstance(shape, list) or len(shape) != len(node_ids):
                raise ValueError(f'modes[{i}].shape must have {len(node_ids)} nodes')
            _validateArrayShape(shape, (len(node_ids), 3), f'modes[{i}].shape')
            _validateFiniteArray(shape, f'modes[{i}].shape')

            mass = mode.get('mass_kg')
            _validateFinitePositive(mass, f'modes[{i}].mass_kg')

            stiffness = mode.get('stiffness_N_per_m')
            _validateFiniteNonnegative(stiffness, f'modes[{i}].stiffness_N_per_m')

            freq_hz = mode.get('frequency_hz')
            _validateFinite(freq_hz, f'modes[{i}].frequency_hz')
            if freq_hz < 0:
                raise ValueError(f'modes[{i}].frequency_hz must be positive')

            _validateModalMassFrequency(mass, stiffness, 0, freq_hz)

            damping = mode.get('damping')
            damping_kind, damping_val = _validateDampingKind(damping)
            mode['_damping_kind'] = damping_kind
            mode['_damping_val'] = damping_val

            # Check that unknown damping is properly marked
            if damping_kind == 'unknown' and damping_val is not None:
                raise ValueError(f'modes[{i}].damping unknown must have null coefficient')

        _validateUniqueIds([m['id'] for m in modes], 'mode IDs')
        # Initial conditions
        init_q = struct.get('initial_q_m')
        init_v = struct.get('initial_v_m_per_s')
        n_modes = len(modes)
        if not isinstance(init_q, list) or len(init_q) != n_modes:
            raise ValueError(f'initial_q_m must have {n_modes} elements')
        _validateArrayShape(init_q, (n_modes,), 'initial_q_m')
        if not isinstance(init_v, list) or len(init_v) != n_modes:
            raise ValueError(f'initial_v_m_per_s must have {n_modes} elements')
        _validateArrayShape(init_v, (n_modes,), 'initial_v_m_per_s')

        # Aerodynamics section
        aero = case.get('aerodynamics')
        if not isinstance(aero, dict):
            raise ValueError('aerodynamics must be a dictionary')

        _validateIdsMatch(aero.get('configuration_id'), config.get('id'), 'aerodynamics.configuration_id')
        aero_node_ids = aero.get('node_ids')
        _validateIdsMatch(aero_node_ids, node_ids, 'aerodynamics.node_ids')

        source_kind = aero.get('source_kind')
        if source_kind not in ('synthetic_prescribed', 'solver_export'):
            raise ValueError('aerodynamics.source_kind must be "synthetic_prescribed" or "solver_export"')

        history_kind = aero.get('history_kind')
        if history_kind not in ('time_history', 'steady'):
            raise ValueError('aerodynamics.history_kind must be "time_history"')

        if aero.get('quantity') != 'integrated_point_force':
            raise ValueError('aerodynamics.quantity must be "integrated_point_force"')
        if aero.get('force_unit') != 'N':
            raise ValueError('aerodynamics.force_unit must be "N"')

        pressure_meaning = aero.get('pressure_meaning')
        if pressure_meaning != 'not_applicable':
            raise ValueError('aerodynamics.pressure_meaning must be "not_applicable"')

        time_convention = aero.get('time_convention')
        if time_convention != 'seconds_from_start':
            raise ValueError('aerodynamics.time_convention must be "seconds_from_start"')

        if aero.get('load_reference') != 'fixed_reference_geometry':
            raise ValueError('load_reference must be fixed_reference_geometry')
        for field in ('density_kg_m3', 'reference_area_m2', 'reference_length_m', 'airspeed_m_s'):
            value = aero.get(field)
            if value is not None or source_kind == 'solver_export':
                check = _validateFiniteNonnegative if field == 'airspeed_m_s' else _validateFinitePositive
                check(value, 'aerodynamics.' + field)
        convention = aero.get('airspeed_convention')
        if convention is not None or source_kind == 'solver_export':
            if convention != 'TAS':
                raise ValueError('airspeed_convention must be TAS')
        times = aero.get('times_s')
        _validateFiniteArray(times, 'aerodynamics.times_s')
        _validateArrayShape(times, (len(times),), 'aerodynamics.times_s')
        if history_kind == 'steady':
            if times != [0]:
                raise ValueError('steady history must have one sample at zero')
        else:
            _validateTimeHistory(times, 'aerodynamics.times_s')

        # Forces: [time][node][xyz]
        forces = aero.get('forces_N')
        n_times = len(times)
        if not isinstance(forces, list) or len(forces) != n_times:
            raise ValueError('aerodynamics.forces_N must have {n_times} time samples')
        for t_idx, time_forces in enumerate(forces):
            if not isinstance(time_forces, list) or len(time_forces) != len(node_ids):
                raise ValueError(f'aerodynamics.forces_N[{t_idx}] must have {len(node_ids)} nodes')
            _validateArrayShape(time_forces, (len(node_ids), 3), f'aerodynamics.forces_N[{t_idx}]')
            _validateFiniteArray(time_forces, f'aerodynamics.forces_N[{t_idx}]')

        # Moment origin
        moment_origin = aero.get('moment_origin_m')
        if not isinstance(moment_origin, list) or len(moment_origin) != 3:
            raise ValueError('aerodynamics.moment_origin_m must have 3 components')
        _validateArrayShape(moment_origin, (3,), 'aerodynamics.moment_origin_m')

        # Extension and overlap (can be null or finite nonnegative)
        extension = config.get('extension_m')
        if extension is not None:
            _validateFiniteNonnegative(extension, 'configuration.extension_m')
        overlap = config.get('overlap_m')
        if overlap is not None:
            _validateFiniteNonnegative(overlap, 'configuration.overlap_m')

        # Measurements section (empty is valid)
        measurements = case.get('measurements', [])
        if not isinstance(measurements, list):
            raise ValueError('measurements must be a list')
        if measurements:
            _validateUniqueIds([m.get('id') if isinstance(m, dict) else None for m in measurements], 'measurement IDs')
        for i, meas in enumerate(measurements):
            if not isinstance(meas, dict):
                raise ValueError(f'measurements[{i}] must be a dictionary')
            _validateNonemptyString(meas.get('id'), f'measurements[{i}].id')
            _validateIdsMatch(meas.get('configuration_id'), config.get('id'), f'measurements[{i}].configuration_id')

            kind = meas.get('kind')
            if kind not in ('modal', 'steady_aero', 'dynamic_aero'):
                raise ValueError(f'measurements[{i}].kind must be modal/steady_aero/dynamic_aero')

            env = meas.get('environment')
            if env not in ('ground', 'in_flow'):
                raise ValueError(f'measurements[{i}].environment must be ground/in_flow')

            role = meas.get('role')
            if role not in ('calibration', 'validation'):
                raise ValueError(f'measurements[{i}].role must be calibration/validation')

            data_status = meas.get('data_status')
            if data_status != 'metadata_only':
                raise ValueError(f'measurements[{i}].data_status must be metadata_only')

            channels = meas.get('channels')
            if not isinstance(channels, list) or not channels:
                raise ValueError(f'measurements[{i}].channels must be nonempty')

            _validateUniqueIds([ch.get('id') if isinstance(ch, dict) else None for ch in channels], 'channel IDs')
            for j, ch in enumerate(channels):
                if not isinstance(ch, dict):
                    raise ValueError(f'measurements[{i}].channels[{j}] must be a dictionary')
                _validateNonemptyString(ch.get('id'), f'measurements[{i}].channels[{j}].id')

                pos = ch.get('position_m')
                _validateArrayShape(pos, (3,), f'measurements[{i}].channels[{j}].position_m')
                if len(pos) != 3:
                    raise ValueError(f'measurements[{i}].channels[{j}].position_m must have 3 components')

                direction = ch.get('direction')
                _validateDirection(direction, f'measurements[{i}].channels[{j}].direction')

                quantity = ch.get('quantity')
                unit = ch.get('unit')
                valid_pairs = [
                    ('displacement', 'm'),
                    ('acceleration', 'm/s^2'),
                    ('force', 'N'),
                    ('pressure', 'Pa'),
                ]
                if (quantity, unit) not in valid_pairs:
                    raise ValueError(f'measurements[{i}].channels[{j}] invalid quantity/unit pair')

                excitation = ch.get('excitation')
                if not isinstance(excitation, dict):
                    raise ValueError(f'measurements[{i}].channels[{j}].excitation must be a dictionary')
                if 'known' not in excitation or not isinstance(excitation['known'], bool):
                    raise ValueError(f'measurements[{i}].channels[{j}].excitation.known must be boolean')
                _validateNonemptyString(excitation.get('description'), f'measurements[{i}].channels[{j}].excitation.description')

                sample_axis = ch.get('sample_axis')
                if not isinstance(sample_axis, dict):
                    raise ValueError(f'measurements[{i}].channels[{j}].sample_axis must be a dictionary')
                axis_kind = sample_axis.get('kind')
                if axis_kind not in ('time_s', 'frequency_hz'):
                    raise ValueError(f'measurements[{i}].channels[{j}].sample_axis.kind must be time_s/frequency_hz')
                axis_values = sample_axis.get('values', [])
                if not isinstance(axis_values, list):
                    raise ValueError(f'measurements[{i}].channels[{j}].sample_axis.values must be a list')
                for v in axis_values:
                    _validateFiniteNonnegative(v, 'sample_axis.values')
                    if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                        raise ValueError(f'measurements[{i}].channels[{j}].sample_axis.values must be nonnegative')
                for k in range(1, len(axis_values)):
                    if axis_values[k] <= axis_values[k-1]:
                        raise ValueError(f'measurements[{i}].channels[{j}].sample_axis.values must be strictly increasing')

                phase_conv = ch.get('phase_convention')
                if phase_conv is not None and (not isinstance(phase_conv, str) or not phase_conv):
                    raise ValueError(f'measurements[{i}].channels[{j}].phase_convention must be nonempty or null')

                uncertainty = ch.get('uncertainty')
                if not isinstance(uncertainty, dict):
                    raise ValueError(f'measurements[{i}].channels[{j}].uncertainty must be a dictionary')
                unc_status = uncertainty.get('status')
                if unc_status not in ('unknown', 'specified'):
                    raise ValueError(f'measurements[{i}].channels[{j}].uncertainty.status must be unknown/specifies')
                _validateNonemptyString(uncertainty.get('description'), f'measurements[{i}].channels[{j}].uncertainty.description')

                provenance = ch.get('provenance')
                if not isinstance(provenance, dict):
                    raise ValueError(f'measurements[{i}].channels[{j}].provenance must be a dictionary')
                _validateNonemptyString(provenance.get('source'), f'measurements[{i}].channels[{j}].provenance.source')
                sha256 = provenance.get('sha256')
                if sha256 is not None:
                    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in '0123456789abcdefABCDEF' for c in sha256):
                        raise ValueError(f'measurements[{i}].channels[{j}].provenance.sha256 must be 64 hex chars or null')
                    try:
                        int(sha256, 16)
                    except ValueError:
                        raise ValueError(f'measurements[{i}].channels[{j}].provenance.sha256 must be hex')

        # Provenance section
        provenance = case.get('provenance')
        if not isinstance(provenance, dict):
            raise ValueError('provenance must be a dictionary')
        _validateNonemptyString(provenance.get('scope'), 'provenance.scope')
        _validateNonemptyString(provenance.get('source'), 'provenance.source')

        return True, ""

    except (ValueError, TypeError, OverflowError) as e:
        return False, str(e)


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and execute endpoint loads; API hashes canonical input JSON."""
    valid, error = validate_case(case)
    if not valid:
        raise ValueError(error)
    modes = case['structure']['modes']
    if any(m['damping']['kind'] == 'unknown' for m in modes):
        raise ValueError('unknown damping requires an explicit coefficient or assumption')
    aero = case['aerodynamics']
    if aero['history_kind'] != 'time_history':
        raise ValueError('steady loads cannot execute a transient case')
    system = ModalSystem([m['mass_kg'] for m in modes],
                         [m['damping']['c_kg_per_s'] for m in modes],
                         [m['stiffness_N_per_m'] for m in modes])
    basis = [m['shape'] for m in modes]
    times = aero['times_s']
    forces = np.array(aero['forces_N'])
    projected = [generalized_forces(basis, f) for f in aero['forces_N']]
    state = system.initial_state(case['structure']['initial_q_m'],
                                 case['structure']['initial_v_m_per_s'], projected[0])
    states = [state]
    for i in range(1, len(times)):
        state = system.step(state, projected[i], times[i] - times[i-1])
        states.append(state)
    q, v, acc = [np.array([getattr(st, name) for st in states]) for name in ('q', 'v', 'a')]
    Q = np.array(projected)
    u = np.array([displacements(basis, row.tolist()) for row in q])
    modal_work = np.sum(.5 * (Q[1:] + Q[:-1]) * np.diff(q, axis=0), axis=0)
    physical_work = np.sum(.5 * (forces[1:] + forces[:-1]) * np.diff(u, axis=0))
    vm = .5 * (v[1:] + v[:-1])
    damping_loss = np.sum(np.diff(times)[:, None] * vm**2 * system.damping)
    tips = [case['geometry']['node_ids'].index(n) for n in case['geometry']['tip_node_ids']]
    result = {
        'schema_version': 1, 'profile': case['profile'], 'case_id': case['case_id'],
        'scope': 'numerical verification only; prescribed loads, no aerodynamic feedback or flutter prediction',
        'configuration': copy.deepcopy(case['configuration']),
        'input_sha256': hashlib.sha256(json.dumps(case, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        'input_hash_kind': 'canonical_json',
        'retained_assumptions': {'damping': [dict(mode_id=m['id'], **m['damping']) for m in modes]},
        'provenance': copy.deepcopy(case['provenance']),
        'measurements': copy.deepcopy(case.get('measurements', [])),
        'numerical_results': {
            'time_samples': len(times), 'time_steps_s': np.diff(times).tolist(),
            'modal_work_j': modal_work.tolist(), 'total_modal_work_j': float(modal_work.sum()),
            'physical_work_j': float(physical_work), 'damping_loss_j': float(damping_loss),
            'time_history': {
                'times_s': list(times), 'modal_displacements_m': q.tolist(),
                'modal_velocities_m_per_s': v.tolist(), 'modal_accelerations_m_per_s2': acc.tolist(),
                'generalized_forces_N': Q.tolist(), 'physical_node_displacements_m': u.tolist(),
                'mean_tip_displacement_m': u[:, tips].mean(axis=1).tolist()
            }
        }
    }
    # Also guard aggregate overflow before returning an apparently valid report.
    json.dumps(result, allow_nan=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate and run portable modal case fixtures.')
    parser.add_argument('input', metavar='INPUT', help='Input JSON case file')
    parser.add_argument('--output', required=True, help='Output JSON report file')
    args = parser.parse_args()
    try:
        input_bytes = Path(args.input).read_bytes()
        case = json.loads(input_bytes)
        result = run_case(case)
        result['input_sha256'] = hashlib.sha256(input_bytes).hexdigest()
        result['input_hash_kind'] = 'exact_file_bytes'
        encoded = json.dumps(result, indent=2, allow_nan=False)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + '\n')
    except (ValueError, TypeError, OSError, OverflowError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    print(f'Output written to: {args.output}')
    print(f"Input SHA256: {result['input_sha256']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
