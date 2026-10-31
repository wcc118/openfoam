"""Experimental native mass-normalized multimode preCICE participant.

H_face = W H_point and Q = H_face.T F preserve virtual work for the supplied
reference kinematics. Geometry and loads cross preCICE in metres and newtons.
Original frequencies are required; no stiffness scaling is applied here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from scripts.modal_dynamics import ModalSystem


def _array(value, name, shape):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'{name} must be finite with shape {shape}')
    return a


def _sha(value, name):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind != 'U' or not re.fullmatch('[0-9a-f]{64}', str(a)):
        raise ValueError(f'{name} must be a SHA256 scalar string')
    return str(a)


def run(participant, assets, settings, output):
    points, centers = [np.asarray(assets[k], dtype=float) for k in ('points', 'centers')]
    for name, a in (('points', points), ('centers', centers)):
        if a.ndim != 2 or a.shape[1] != 3 or not len(a) or not np.isfinite(a).all():
            raise ValueError(f'{name} must be nonempty finite [N,3]')
    indices = np.asarray(assets['mode_indices'])
    if (indices.ndim != 1 or not len(indices) or indices.dtype.kind not in 'iu'
            or min(indices) < 0 or len(set(indices.tolist())) != len(indices)):
        raise ValueError('mode_indices must be unique nonnegative integers')
    n = len(indices)
    requested_indices = np.asarray(settings['mode_indices'])
    if requested_indices.dtype.kind not in 'iu' or not np.array_equal(indices, requested_indices):
        raise ValueError('mode_indices mismatch')
    hp = _array(assets['point_modes'], 'point_modes', (len(points), 3, n))
    hf = _array(assets['face_modes'], 'face_modes', (len(centers), 3, n))
    frequencies = _array(assets['frequencies_hz'], 'frequencies_hz', (n,))
    requested = _array(settings['modal_frequencies_hz'], 'modal_frequencies_hz', (n,))
    if min(frequencies) <= 0 or not np.array_equal(frequencies, requested):
        raise ValueError('positive original modal frequencies must match assets')
    native_sha = _sha(assets['native_modal_sha256'], 'native_modal_sha256')
    if native_sha != _sha(settings['native_modal_sha256'], 'native_modal_sha256'):
        raise ValueError('native modal hash mismatch')
    _sha(settings['assets_sha256'], 'assets_sha256')
    damping = _array(settings['damping_ratio'], 'damping_ratio', (n,))
    if min(damping) < 0:
        raise ValueError('damping_ratio must be nonnegative')
    reference, q, v, force = [_array(settings[k], k, (n,)) for k in
                              ('reference_q', 'initial_q', 'initial_v', 'initial_force')]
    limits = _array([settings['absolute_displacement_limit_m'],
                     settings['mesh_increment_limit_m']], 'physical displacement limits', (2,))
    if min(limits) <= 0:
        raise ValueError('physical displacement limits must be positive')
    cap = settings['max_iterations']
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError('max_iterations must be a positive integer')
    if settings['coupling'] not in ('explicit', 'implicit'):
        raise ValueError('coupling must be explicit or implicit')
    end_time = np.asarray(settings['end_time_s'], dtype=float)
    if end_time.shape != () or not np.isfinite(end_time) or end_time <= 0:
        raise ValueError('end_time_s must be positive finite scalar')
    omega = 2*np.pi*frequencies
    stiffness, damping_coefficient = omega**2, 2*damping*omega
    system = ModalSystem(np.ones(n), damping_coefficient, stiffness)
    state = system.initial_state(q, v, force)

    def motion(coordinates):
        absolute = np.einsum('ncm,m->nc', hp, coordinates)
        increment = np.einsum('ncm,m->nc', hp, np.asarray(coordinates)-reference)
        maxima = np.array([np.max(abs(absolute)), np.max(abs(increment))])
        if not np.isfinite(maxima).all() or np.any(maxima > limits):
            raise RuntimeError('physical displacement limit exceeded')
        return increment, maxima

    initial_displacement, _ = motion(q)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Claim the output before entering preCICE, so a collision cannot leave a live participant.
    trace = (output/'trials.jsonl').open('x')
    rows, rollbacks, iteration, checkpoint = [], 0, 0, None
    completed, initialized, failure = False, False, None
    try:
        force_ids = participant.set_mesh_vertices('Solid-Forces', centers)
        motion_ids = participant.set_mesh_vertices('Solid-Motion', points)
        if participant.requires_initial_data():
            participant.write_data('Solid-Motion', 'Displacement', motion_ids, initial_displacement)
        participant.initialize()
        initialized = True
        while participant.is_coupling_ongoing():
            if participant.requires_writing_checkpoint():
                checkpoint = system.checkpoint(state)
            dt = participant.get_max_time_step_size()
            forces = _array(participant.read_data('Solid-Forces', 'Force', force_ids, dt),
                            'native face loads', (len(centers), 3))
            qforce = np.einsum('fcm,fc->m', hf, forces)
            start = state
            end = system.step(start, qforce, dt)
            displacement, maxima = motion(end.q)
            energy = lambda s: .5*(np.dot(s.v, s.v)+np.dot(stiffness, np.square(s.q)))
            dq = np.asarray(end.q)-start.q
            work = .5*np.dot(np.asarray(start.force)+qforce, dq)
            vmid = .5*(np.asarray(start.v)+end.v)
            loss = np.dot(damping_coefficient, vmid**2)*dt
            defect = energy(end)-energy(start)-work+loss
            if abs(defect) > 1e-12+1e-9*(abs(work)+abs(loss)+energy(end)):
                raise RuntimeError('structural discrete energy check failed')
            participant.write_data('Solid-Motion', 'Displacement', motion_ids, displacement)
            participant.advance(dt)
            iteration += 1
            rejected = participant.requires_reading_checkpoint()
            row = dict(time_s=end.time, dt_s=dt, q=list(end.q), v=list(end.v),
                       Q_generalized=qforce.tolist(), force_N=forces.sum(axis=0).tolist(),
                       energy_J=energy(end), structural_load_work_J=work,
                       damping_loss_J=loss, structural_energy_defect_J=defect,
                       max_absolute_point_displacement_m=float(maxima[0]),
                       max_mesh_increment_m=float(maxima[1]), iteration=iteration,
                       rejected=bool(rejected))
            trace.write(json.dumps(row, allow_nan=False)+'\n')
            trace.flush()
            if rejected:
                if checkpoint is None:
                    raise RuntimeError('rollback requested without checkpoint')
                state = system.restore(checkpoint)
                if state != checkpoint:
                    raise RuntimeError('incomplete checkpoint restore')
                rollbacks += 1
            else:
                if settings['coupling'] == 'implicit' and iteration >= cap:
                    raise RuntimeError('coupling iteration cap reached')
                rows.append(row)
                state, iteration = end, 0
            if iteration >= cap:
                raise RuntimeError('coupling iteration cap reached')
        if not rows or abs(state.time-float(end_time)) > 1e-10:
            raise RuntimeError('missing expected end time')
        completed = True
    except BaseException as error:
        failure = f'{type(error).__name__}: {error}'
        raise
    finally:
        trace.close()
        try:
            (output/'multimodal-history.json').write_text(json.dumps(dict(
                scope='Experimental original-mode CFD coupling; execution is not flutter qualification',
                completed=completed, failure=failure, settings=settings, rows=rows,
                rollbacks=rollbacks, units=dict(shape='1/sqrt(kg)', q='sqrt(kg)*m',
                v='sqrt(kg)*m/s', Q_generalized='sqrt(kg)*m/s^2', energy='J',
                boundary_displacement='m', boundary_force='N')), indent=2, allow_nan=False)+'\n')
        finally:
            if initialized:
                participant.finalize()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('assets', 'settings', 'config', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    settings = json.loads(Path(args.settings).read_text())
    if hashlib.sha256(Path(args.assets).read_bytes()).hexdigest() != settings['assets_sha256']:
        raise ValueError('assets hash mismatch')
    import precice
    with np.load(args.assets, allow_pickle=False) as assets:
        run(precice.Participant('Solid', args.config, 0, 1), assets, settings, args.output)


if __name__ == '__main__':
    main()
