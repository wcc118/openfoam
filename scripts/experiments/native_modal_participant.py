"""Bounded native-wing preCICE experiment, not a general structural adapter.

Separate coincident face/point meshes avoid additional interpolation. H_face=W H_point
and Q=H_face.T F use the same reference kinematics. Shell offsets are approximated.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scripts.modal_dynamics import ModalSystem


def run(participant, assets, settings, output):
    points, centers = assets['points'], assets['centers']
    hp, hf = assets['point_mode'], assets['face_mode']
    for value, shape in ((points, hp.shape), (centers, hf.shape)):
        if value.shape != shape or value.ndim != 2 or value.shape[1] != 3:
            raise ValueError('geometry and one-mode shapes must be [point/face,3]')
    if not all(np.isfinite(a).all() for a in (points, centers, hp, hf)):
        raise ValueError('nonfinite interface')
    mass, stiffness, damping = [settings[k] for k in ('mass_kg', 'stiffness_N_m', 'damping_N_s_m')]
    system = ModalSystem([mass], [damping], [stiffness])
    reference_q = float(settings.get('reference_q_m', 0.))
    initial_q = float(settings.get('initial_q_m', 0.))
    initial_v = float(settings.get('initial_v_m_s', 0.))
    initial_force = float(settings.get('initial_force_N', 0.))
    if not np.isfinite([reference_q, initial_q, initial_v, initial_force]).all():
        raise ValueError('nonfinite initial state or mesh reference')
    if abs(initial_q) > settings['displacement_limit_m']:
        raise ValueError('initial state exceeds displacement limit')
    # Structural restoring force uses the undeformed coordinate. The CFD mesh
    # may already represent a loaded pose, so only its increment is written.
    state = system.initial_state([initial_q], [initial_v], [initial_force])
    force_ids = participant.set_mesh_vertices('Solid-Forces', centers)
    motion_ids = participant.set_mesh_vertices('Solid-Motion', points)
    if participant.requires_initial_data():
        participant.write_data('Solid-Motion', 'Displacement', motion_ids, hp*(state.q[0]-reference_q))
    participant.initialize()
    rows, rollbacks, iteration, checkpoint = [], 0, 0, None
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    # Exclusive trace creation prevents accidental reuse of a prior experiment.
    trace = (output/'trials.jsonl').open('x')
    completed = False
    try:
        while participant.is_coupling_ongoing():
            if participant.requires_writing_checkpoint():
                checkpoint = system.checkpoint(state)
            dt = participant.get_max_time_step_size()
            forces = np.asarray(participant.read_data('Solid-Forces', 'Force', force_ids, dt))
            if forces.shape != hf.shape or not np.isfinite(forces).all():
                raise ValueError('invalid native face loads')
            qforce = float(np.sum(hf*forces))
            start = state
            end = system.step(start, [qforce], dt)
            if abs(end.q[0]) > settings['displacement_limit_m']:
                raise RuntimeError('bounded-pilot displacement limit exceeded')
            energy = lambda s: .5*mass*s.v[0]**2 + .5*stiffness*s.q[0]**2
            dq = end.q[0]-start.q[0]
            work = .5*(start.force[0]+qforce)*dq
            loss = damping*(.5*(start.v[0]+end.v[0]))**2*dt
            defect = energy(end)-energy(start)-work+loss
            if abs(defect) > 1e-12+1e-9*(abs(work)+abs(loss)+energy(end)):
                raise RuntimeError('structural discrete energy check failed')
            participant.write_data('Solid-Motion', 'Displacement', motion_ids, hp*(end.q[0]-reference_q))
            participant.advance(dt)
            iteration += 1
            rejected = participant.requires_reading_checkpoint()
            row = dict(time_s=end.time, dt_s=dt, q_m=end.q[0], v_m_s=end.v[0],
                       mesh_increment_m=end.q[0]-reference_q,
                       Q_N=qforce, force_N=forces.sum(axis=0).tolist(),
                       energy_J=energy(end), structural_load_work_J=work,
                       damping_loss_J=loss, structural_energy_defect_J=defect,
                       iteration=iteration, rejected=rejected)
            trace.write(json.dumps(row, allow_nan=False)+'\n'); trace.flush()
            if rejected:
                if checkpoint is None:
                    raise RuntimeError('rollback requested without checkpoint')
                state = system.restore(checkpoint)
                if state != checkpoint:
                    raise RuntimeError('incomplete checkpoint restore')
                rollbacks += 1
            else:
                # preCICE may accept at its configured cap: reject such a result.
                if settings['coupling']=='implicit' and iteration >= settings['max_iterations']:
                    raise RuntimeError('coupling iteration cap reached')
                rows.append(row); state=end; iteration=0
            if iteration >= settings['max_iterations']:
                raise RuntimeError('coupling iteration cap reached')
        if not rows or abs(state.time-settings['end_time_s']) > 1e-10:
            raise RuntimeError('missing expected end time')
        completed = True
    finally:
        trace.close()
        (output/'modal-history.json').write_text(json.dumps(dict(
            scope='Native one-bending-mode live feedback pilot; not damping or flutter qualification',
            completed=completed, settings=settings, rows=rows, rollbacks=rollbacks), indent=2)+'\n')
        participant.finalize()
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True); parser.add_argument('--settings', required=True)
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    args=parser.parse_args()
    settings=json.loads(Path(args.settings).read_text())
    raw=Path(args.assets).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=settings['assets_sha256']:
        raise ValueError('assets hash mismatch')
    import precice
    with np.load(args.assets, allow_pickle=False) as assets:
        run(precice.Participant('Solid',args.config,0,1),assets,settings,args.output)


if __name__=='__main__':
    main()
