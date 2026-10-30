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
            note = f'Guard-exceeded equilibrium. Experimental stop: 50 mm absolute native-node displacement component, not a physical allowable. {modes} modes / {speed:g} m/s / loaded perturbation'
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
        'source': 'wcc118/openfoam issue #36; pinned SHARPy and MYSTRAN',
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

        if model['mass_kg'] <= 0:
            raise ValueError(f'models.{model_key}.mass_kg must be positive')
        if model['thickness_m'] <= 0:
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
    """Create 2x2 plot of speed sweep results."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    xyz = np.array(payload['mesh']['nodes'])
    tip = np.isclose(xyz[:, 1], xyz[:, 1].max())

    # Load summary to get metrics
    summary = load_summary(base)

    # Build lookup for reports by (modes, speed)
    report_lookup = {}
    for report in summary:
        key = (report.get('modes'), report.get('speed_m_s'))
        if key[0] is not None and key[1] is not None:
            report_lookup[key] = report

    # Collect data by model
    modes10_data = {'speeds': [], 'equilibrium_tip_z': [], 'tracked_growth': [],
                    'tracked_freq': [], 'dominant_growth': []}
    modes20_data = {'speeds': [], 'equilibrium_tip_z': [], 'tracked_growth': [],
                    'tracked_freq': [], 'dominant_growth': []}
    omitted = payload.get('omitted_cases', [])

    for case in payload['cases']:
        model = case['model']

        # Parse modes and speed from case name
        name_parts = case['name'].split('/')
        if len(name_parts) < 2:
            continue

        # Extract modes (10 or 20) and speed
        modes_part = name_parts[0].strip().replace('modes', '')
        speed_part = name_parts[1].strip().replace('m/s', '').strip()
        try:
            modes = int(modes_part)
            speed = float(speed_part)
        except (ValueError, IndexError):
            continue

        data = modes10_data if modes == 10 else modes20_data

        # Calculate equilibrium mean tip z from reference_q
        phi = np.array(payload['models'][model]['modes'])
        tip_map = phi[:, tip, 2].mean(axis=1) / np.sqrt(2)
        eq_tip_z = np.array(case['reference_q']) @ tip_map * 1000  # mm

        # Look up metrics from original report
        report = report_lookup.get((modes, speed), {})

        # Get tracked bending growth/freq
        tracked_bending = report.get('poles', {}).get('tracked_bending', {})
        growth_per_s = tracked_bending.get('growth_per_s')
        frequency_hz = tracked_bending.get('frequency_hz')

        # Get dominant resolved oscillatory growth
        dominant = report.get('poles', {}).get('dominant_resolved_oscillatory', {})
        dominant_growth = dominant.get('growth_per_s')

        data['speeds'].append(speed)
        data['equilibrium_tip_z'].append(eq_tip_z)
        data['tracked_growth'].append(growth_per_s if growth_per_s is not None else np.nan)
        data['tracked_freq'].append(frequency_hz if frequency_hz is not None else np.nan)
        data['dominant_growth'].append(dominant_growth if dominant_growth is not None else np.nan)

    # Create 2x2 subplot
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)

    # Plot 1: equilibrium mean tip z vs speed
    ax = axes[0, 0]
    ax.plot(modes10_data['speeds'], modes10_data['equilibrium_tip_z'],
            'o-', label='modes10', markersize=5)
    ax.plot(modes20_data['speeds'], modes20_data['equilibrium_tip_z'],
            's-', label='modes20', markersize=5)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    ax.set_ylabel('Equilibrium mean tip z (mm)')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # Plot 2: tracked bending growth vs speed
    ax = axes[1, 0]
    ax.plot(modes10_data['speeds'], modes10_data['tracked_growth'],
            'o-', label='modes10', markersize=5)
    ax.plot(modes20_data['speeds'], modes20_data['tracked_growth'],
            's-', label='modes20', markersize=5)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    ax.set_ylabel('Tracked bending growth (1/s)')
    ax.set_xlabel('Speed (m/s)')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # Plot 3: tracked bending frequency vs speed
    ax = axes[0, 1]
    ax.plot(modes10_data['speeds'], modes10_data['tracked_freq'],
            'o-', label='modes10', markersize=5)
    ax.plot(modes20_data['speeds'], modes20_data['tracked_freq'],
            's-', label='modes20', markersize=5)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    ax.set_ylabel('Tracked bending frequency (Hz)')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # Plot 4: dominant resolved oscillatory growth vs speed
    ax = axes[1, 1]
    ax.plot(modes10_data['speeds'], modes10_data['dominant_growth'],
            'o-', label='modes10', markersize=5)
    ax.plot(modes20_data['speeds'], modes20_data['dominant_growth'],
            's-', label='modes20', markersize=5)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    ax.set_ylabel('Dominant oscillatory growth (1/s)')
    ax.set_xlabel('Speed (m/s)')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # Title
    fig.suptitle('Exploratory loaded-equilibrium speed sweep\nClamped shell, 1mm tip kick, zero structural damping, UVLM, fixed-CFL')
    fig.tight_layout()

    # Add caption about omitted cases
    if omitted:
        caption = f'Omitted cases ({len(omitted)}): '
        caption += ', '.join([f'{o["modes"]} modes @ {o["speed_m_s"]} m/s ({o["status"]})' for o in omitted])
        fig.text(0.5, 0.01, caption, ha='center', fontsize=8, style='italic')

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
        plt.close(fig)
        print(f'Exported: {output_png}')


if __name__ == '__main__':
    main()
