"""Export loaded-equilibrium speed sweep results for offline comparison and plotting.

Reads native-modal.npz and sweep/summary.json from RESULTS_DIR, then generates
speed-comparison-data.json and speed-sweep.png.

Eligible histories: RESULTS_DIR/sweep/n{modes}-V{speed:g}/motion.json
Valid statuses: executed_exploratory, transient_guard_stop (only if motion >= 2 frames)
Excluded: failed_equilibrium, outside_displacement_experiment_guard, unstable_aero_rom,
          failed_numerical, or transient_guard_stop without sufficient motion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def load_native(base):
    """Load native-modal.npz and return arrays with SHA256 hash."""
    native_path = base / 'native-modal.npz'
    if not native_path.exists():
        raise FileNotFoundError(f'Missing required file: {native_path}')
    native = np.load(native_path)
    return dict(
        xyz=native['xyz'],
        quads=native['quads'],
        phi=native['phi'],
        mass=native['mass'],
        frequencies_Hz=native['frequencies_Hz'],
        generalized_mass=native['generalized_mass']
    ), hashlib.sha256(native_path.read_bytes()).hexdigest()


def load_summary(base):
    """Load sweep/summary.json and return list of reports."""
    summary_path = base / 'sweep' / 'summary.json'
    if not summary_path.exists():
        raise FileNotFoundError(f'Missing required file: {summary_path}')
    return json.loads(summary_path.read_text())


def load_motion(base, modes, speed):
    """Load motion.json for a specific modes/speed combination.

    Returns (history_dict, sha256) or (None, None) if not eligible.
    """
    folder = base / 'sweep' / f'n{modes}-V{speed:g}'
    motion_path = folder / 'motion.json'

    if not motion_path.exists():
        return None, None

    try:
        history = json.loads(motion_path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON in {motion_path}: {e}')

    # Check if motion has >= 2 frames
    frames = history.get('frames_time_and_q', [])
    if not isinstance(frames, list) or len(frames) < 2:
        return None, None

    sha256 = hashlib.sha256(motion_path.read_bytes()).hexdigest()
    return history, sha256


def is_eligible(report, history):
    """Determine if a case is eligible for inclusion.

    Valid: executed_exploratory, transient_guard_stop (with valid motion)
    Invalid: failed_equilibrium, outside_displacement_experiment_guard,
             unstable_aero_rom, failed_numerical, or transient_guard_stop without motion
    """
    status = report.get('status', '')

    # Valid statuses
    if status == 'executed_exploratory':
        return True

    if status == 'transient_guard_stop':
        # Must have valid motion with >= 2 frames (already validated in load_motion)
        # and stopped_at_50mm_guard must be True
        if history and history.get('stopped_at_50mm_guard', False):
            return True
        return False

    # All other statuses are invalid
    return False


def build_payload(base, native_data, native_sha256, summary):
    """Build the payload dict with cases sorted by speed then modes."""
    xyz = native_data['xyz']
    quads = native_data['quads']
    phi = native_data['phi']
    mass = native_data['mass']
    if phi.ndim != 3 or phi.shape[0] < 20 or phi.shape[1:] != (len(xyz), 3):
        raise ValueError('native source requires at least 20 modes with one xyz vector per node')

    # Build models: modes10 and modes20 share same physical mass/thickness
    models = {
        'modes10': {
            'modes': phi[:10].tolist(),
            'mass_kg': float(np.sum(mass)),
            'thickness_m': 0.00127
        },
        'modes20': {
            'modes': phi[:20].tolist(),
            'mass_kg': float(np.sum(mass)),
            'thickness_m': 0.00127
        }
    }

    # Group reports by modes and speed
    case_reports = []
    for report in summary:
        modes = report.get('modes')
        speed = report.get('speed_m_s')
        status = report.get('status', '')

        if modes not in (10, 20) or speed is None:
            continue

        # Check if this case has a valid motion file
        history, motion_sha256 = load_motion(base, modes, speed)
        if status == 'executed_exploratory' and history is None:
            raise ValueError(f'Completed case n{modes}-V{speed:g} lacks a replayable motion history')

        # Determine eligibility
        # If history is None (no motion file), case is not eligible
        eligible = history is not None and is_eligible(report, history)

        case_reports.append({
            'report': report,
            'history': history,
            'motion_sha256': motion_sha256,
            'eligible': eligible,
            'modes': modes,
            'speed': speed,
            'status': status
        })

    # Sort by speed then modes for default comparison order
    case_reports.sort(key=lambda x: (x['speed'], x['modes']))

    # Build cases list (only eligible ones)
    cases = []
    omitted = []

    for case_data in case_reports:
        report = case_data['report']
        history = case_data['history']
        modes = case_data['modes']
        speed = case_data['speed']
        status = case_data['status']
        eligible = case_data['eligible']

        model_key = f'modes{modes}'

        if not eligible:
            omitted.append({
                'modes': modes,
                'speed_m_s': speed,
                'status': status
            })
            continue

        # Extract required history fields
        frames_time_and_q = history.get('frames_time_and_q', [])
        equilibrium_q = history.get('equilibrium_q', [])
        stopped_at_50mm_guard = history.get('stopped_at_50mm_guard', False)

        # Determine note based on status
        if status == 'transient_guard_stop':
            note = f'Transient reached displacement guard. Experimental stop: 50 mm absolute native-node displacement component, not a physical allowable. {modes} modes / {speed:g} m/s / loaded perturbation'
        else:
            note = f'{modes} modes / {speed:g} m/s / loaded perturbation'

        cases.append({
            'name': note,
            'model': model_key,
            'reference_q': equilibrium_q,
            'frames': frames_time_and_q,
            'note': note,
            'stopped_at_50mm_guard': stopped_at_50mm_guard
        })

    payload = {
        'title': 'Loaded shell speed sweep · exploratory linear shell + UVLM',
        'scope': 'Exploratory linear shell + UVLM. Clamped loaded shape, not free-flight trim; no prestress, structural damping, flutter qualification or flight claim. Every case begins with +1 mm tip displacement and zero physical velocity relative to its reference. Magnification affects only the picture.',
        'source': f'wcc118/openfoam issue #36; {base.name}; pinned SHARPy and MYSTRAN',
        'mesh': {
            'nodes': xyz.tolist(),
            'quads': quads.tolist()
        },
        'models': models,
        'cases': cases,
        'source_sha256': {
            'native-modal.npz': native_sha256,
            'sweep/summary.json': hashlib.sha256((base / 'sweep' / 'summary.json').read_bytes()).hexdigest()
        },
        'omitted_cases': omitted
    }

    payload['scope'] += ' Baseline .050-inch skin; mode-count change only. Fixed CFL .5 is not timestep convergence. The 50 mm native-node component guard is an experimental stop, not an allowable.'
    if omitted:
        speeds = sorted({o['speed_m_s'] for o in omitted})
        payload['scope'] += ' No completed dynamic verdict at ' + ', '.join(f'{v:g}' for v in speeds) + ' m/s; those cases are omitted from playback, not classified as stable.'

    # Add motion hashes for included cases
    for case_data in case_reports:
        if case_data['eligible'] and case_data['motion_sha256']:
            path = f'sweep/n{case_data["modes"]}-V{case_data["speed"]:g}/motion.json'
            payload['source_sha256'][path] = case_data['motion_sha256']

    return payload


def validate_payload(payload):
    """Validate payload structure matches expected contract."""
    # Validate required top-level fields
    required_fields = ['title', 'scope', 'source', 'mesh', 'models', 'cases', 'source_sha256']
    for field in required_fields:
        if field not in payload:
            raise ValueError(f'Missing required field: {field}')

    # Validate mesh
    mesh = payload['mesh']
    if 'nodes' not in mesh or 'quads' not in mesh:
        raise ValueError('mesh must contain nodes and quads')
    if not mesh['nodes'] or not mesh['quads']:
        raise ValueError('mesh.nodes and mesh.quads must be nonempty')

    n_nodes = len(mesh['nodes'])
    nodes = np.asarray(mesh['nodes'], dtype=float)
    if nodes.shape != (n_nodes, 3) or not np.all(np.isfinite(nodes)):
        raise ValueError('mesh.nodes must be finite xyz vectors')
    for quad in mesh['quads']:
        if len(quad) != 4 or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= n_nodes for i in quad):
            raise ValueError('mesh.quads contains invalid node indices')

    # Validate models
    models = payload['models']
    if not models:
        raise ValueError('models must be nonempty')

    for model_key, model in models.items():
        if 'modes' not in model or 'mass_kg' not in model or 'thickness_m' not in model:
            raise ValueError(f'models.{model_key} must have modes, mass_kg, thickness_m')

        n_modes = len(model['modes'])
        for i, mode in enumerate(model['modes']):
            if len(mode) != n_nodes:
                raise ValueError(f'models.{model_key}.modes[{i}] has {len(mode)} nodes, expected {n_nodes}')

        array = np.asarray(model['modes'], dtype=float)
        if array.shape != (n_modes, n_nodes, 3) or not np.all(np.isfinite(array)):
            raise ValueError(f'models.{model_key}: invalid mode vectors')
        if not np.isfinite(model['mass_kg']) or model['mass_kg'] <= 0:
            raise ValueError(f'models.{model_key}.mass_kg must be positive')
        if not np.isfinite(model['thickness_m']) or model['thickness_m'] <= 0:
            raise ValueError(f'models.{model_key}.thickness_m must be positive')

    # Validate cases
    cases = payload['cases']
    if not cases:
        raise ValueError('cases must be nonempty')

    for i, case in enumerate(cases):
        if 'name' not in case or 'model' not in case:
            raise ValueError(f'cases[{i}] must have name and model')
        if case['model'] not in models:
            raise ValueError(f'cases[{i}].model references unknown model: {case["model"]}')
        if 'reference_q' not in case or 'frames' not in case:
            raise ValueError(f'cases[{i}] must have reference_q and frames')
        if 'stopped_at_50mm_guard' not in case:
            raise ValueError(f'cases[{i}] must have stopped_at_50mm_guard')

        n_modes = len(models[case['model']]['modes'])
        if len(case['reference_q']) != n_modes:
            raise ValueError(f'cases[{i}].reference_q has {len(case["reference_q"])} values, expected {n_modes}')
        if len(case['frames']) < 2:
            raise ValueError(f'cases[{i}].frames must have >= 2 entries')
        frames = np.asarray(case['frames'], dtype=float)
        if frames.shape != (len(case['frames']), n_modes + 1) or not np.all(np.isfinite(frames)):
            raise ValueError(f'cases[{i}].frames has invalid dimensions or nonfinite coordinates')
        if frames[0, 0] < 0 or not np.all(np.diff(frames[:, 0]) > 0):
            raise ValueError(f'cases[{i}].frames must have increasing nonnegative times')
        if not np.all(np.isfinite(case['reference_q'])) or not isinstance(case['stopped_at_50mm_guard'], bool):
            raise ValueError(f'cases[{i}]: invalid reference coordinates or guard flag')


def export(base, output_path):
    """Export speed comparison data to JSON."""
    # Load data
    native_data, native_sha256 = load_native(base)
    summary = load_summary(base)

    # Build payload
    payload = build_payload(base, native_data, native_sha256, summary)

    # Validate
    validate_payload(payload)

    # Write output
    output_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')

    return payload


def plot(base, payload):
    """Plot report fields directly; missing/guarded dynamics remain NaN gaps."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary = load_summary(base)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for n, color, style, marker in [(10, '#2878b5', '-', 'o'), (20, '#e1812c', '--', 's')]:
        reports = sorted((r for r in summary if r['modes'] == n), key=lambda r: r['speed_m_s'])
        speeds = [r['speed_m_s'] for r in reports]
        valid = [r['status'] == 'executed_exploratory' for r in reports]
        tip = [r.get('equilibrium_tip_z_m', np.nan)*1000 if ok else np.nan for r, ok in zip(reports, valid)]
        growth = [r.get('poles', {}).get('tracked_bending', {}).get('growth_per_s', np.nan) if ok else np.nan for r, ok in zip(reports, valid)]
        frequency = [r.get('poles', {}).get('tracked_bending', {}).get('frequency_hz', np.nan) if ok else np.nan for r, ok in zip(reports, valid)]
        dominant = [r.get('poles', {}).get('dominant_resolved_oscillatory', {}).get('growth_per_s', np.nan) if ok else np.nan for r, ok in zip(reports, valid)]
        for ax, values in [(axes[0, 0], tip), (axes[0, 1], frequency), (axes[1, 0], growth), (axes[1, 1], dominant)]:
            ax.plot(speeds, values, color=color, linestyle=style, marker=marker, markersize=5, label=f'{n} modes')
        guarded = [r for r in reports if r['status'] == 'outside_displacement_experiment_guard' and 'equilibrium_tip_z_m' in r]
        axes[0, 0].scatter([r['speed_m_s'] for r in guarded], [r['equilibrium_tip_z_m']*1000 for r in guarded], marker='x', color=color, s=65, label=f'{n} modes: guard, no dynamics')
        for r, ok in zip(reports, valid):
            fit = r.get('history_metrics', {}).get('first_modal_tip_peak_fit')
            if ok and fit:
                axes[1, 0].plot(r['speed_m_s'], fit['growth_per_s'], '.', color='black', markersize=3)
                axes[0, 1].plot(r['speed_m_s'], fit['frequency_hz'], '.', color='black', markersize=3)
    labels = ['Loaded mean tip z (mm)', 'Tracked first-bending frequency (Hz)', 'Tracked first-bending growth (1/s)', 'Least-damped resolved oscillatory growth (1/s)']
    for ax, label in zip(axes.flat, labels):
        ax.set_ylabel(label)
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    for ax in axes[1]:
        ax.axhline(0, color='black', linewidth=.8)
        ax.set_xlabel('Airspeed (m/s)')
    fig.suptitle('Loaded-reference airspeed sweep · same .050-inch shell · 10 versus 20 modes\nExploratory UVLM, zero structural damping, fixed CFL .5; negative growth means decay')
    omitted = payload.get('omitted_cases', [])
    omitted_speeds = sorted({r['speed_m_s'] for r in omitted})
    caption = 'Black dots: transient peak fits. Crosses: solved static shape outside the reference/initial displacement guard.'
    if omitted_speeds:
        caption += '\nNo completed dynamic verdict at ' + ', '.join(f'{v:g}' for v in omitted_speeds) + ' m/s; see report for explicit statuses. Guard is experimental, not an allowable.'
    fig.text(.5, .015, caption, ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, .95))
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, help='RESULTS_DIR containing native-modal.npz and sweep/')
    parser.add_argument('--output-json', type=Path, help='Output JSON path (default: RESULTS_DIR/speed-comparison-data.json)')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot generation')
    args = parser.parse_args()

    base = args.results

    # Check required files
    if not (base / 'native-modal.npz').exists():
        parser.exit(1, f'Missing required file: {base / "native-modal.npz"}\n')
    if not (base / 'sweep' / 'summary.json').exists():
        parser.exit(1, f'Missing required file: {base / "sweep" / "summary.json"}\n')

    # Export JSON
    output_json = args.output_json or (base / 'speed-comparison-data.json')
    payload = export(base, output_json)
    print(f'Exported: {output_json}')

    # Generate plot if requested
    if not args.no_plot:
        fig = plot(base, payload)
        output_png = base / 'speed-sweep.png'
        fig.savefig(output_png, dpi=160, bbox_inches='tight')
        import matplotlib.pyplot as plt
        plt.close(fig)
        print(f'Exported: {output_png}')


if __name__ == '__main__':
    main()
