#!/usr/bin/env python3
"""Build an offline synchronized equilibrium comparison viewer from JSON payload."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def number(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{name}: expected finite number')
    return x


def sequence(x, name, nonempty=True):
    if not isinstance(x, list) or (nonempty and not x):
        raise ValueError(f'{name}: expected {"nonempty " if nonempty else ""}array')
    return x


def finite_array(values, name):
    """Validate array contains only finite numbers."""
    for i, v in enumerate(sequence(values, name)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f'{name}[{i}]: expected finite number')


def finite_3d_array(values, name):
    """Validate 3D array [[x,y,z], ...] contains only finite numbers."""
    for i, v in enumerate(sequence(values, name)):
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError(f'{name}[{i}]: expected [x,y,z]')
        for k, x in enumerate(v):
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                raise ValueError(f'{name}[{i}][{k}]: expected finite number')


def validate(data):
    """Validate the complete input schema."""
    try:
        if not isinstance(data, dict):
            raise ValueError('payload must be object')

        # Top-level fields
        if not isinstance(data.get('title'), str) or not data['title'].strip():
            raise ValueError('title must be nonempty string')
        if not isinstance(data.get('scope'), str) or not data['scope'].strip():
            raise ValueError('scope must be nonempty string')
        if not isinstance(data.get('source'), str) or not data['source'].strip():
            raise ValueError('source must be nonempty string')

        # Mesh
        mesh = data.get('mesh')
        if not isinstance(mesh, dict):
            raise ValueError('mesh must be object')
        nodes = mesh.get('nodes')
        if not isinstance(nodes, list) or len(nodes) == 0:
            raise ValueError('mesh.nodes must be nonempty array')
        finite_3d_array(nodes, 'mesh.nodes')

        quads = mesh.get('quads')
        if not isinstance(quads, list) or len(quads) == 0:
            raise ValueError('mesh.quads must be nonempty array')
        n_nodes = len(nodes)
        for i, q in enumerate(quads):
            if not isinstance(q, list) or len(q) != 4:
                raise ValueError(f'mesh.quads[{i}]: expected 4 node indices')
            for j, idx in enumerate(q):
                if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx >= n_nodes:
                    raise ValueError(f'mesh.quads[{i}][{j}]: node index out of range')

        # Models mapping
        models = data.get('models')
        if not isinstance(models, dict) or not models:
            raise ValueError('models must be nonempty object')
        model_names = list(models.keys())
        if 'baseline' not in model_names or 'thicker' not in model_names:
            raise ValueError("models must contain 'baseline' and 'thicker' keys")

        n_modes_baseline = None
        n_modes_thicker = None
        for tag, model in models.items():
            if not isinstance(model, dict):
                raise ValueError(f'models.{tag}: must be object')
            modes = model.get('modes')
            if not isinstance(modes, list) or len(modes) == 0:
                raise ValueError(f'models.{tag}.modes: must be nonempty array')
            for i, mode in enumerate(modes):
                if not isinstance(mode, list) or len(mode) != n_nodes:
                    raise ValueError(f'models.{tag}.modes[{i}]: must have {n_nodes} node displacements')
                finite_3d_array(mode, f'models.{tag}.modes[{i}]')

            mass_kg = number(model.get('mass_kg'), 'mass_kg')
            if isinstance(mass_kg, bool) or not isinstance(mass_kg, (int, float)) or mass_kg <= 0:
                raise ValueError(f'models.{tag}.mass_kg must be positive number')

            thickness_m = number(model.get('thickness_m'), 'thickness_m')
            if isinstance(thickness_m, bool) or not isinstance(thickness_m, (int, float)) or thickness_m <= 0:
                raise ValueError(f'models.{tag}.thickness_m must be positive number')

            # Track mode counts
            if tag == 'baseline':
                n_modes_baseline = len(modes)
            else:
                n_modes_thicker = len(modes)

        # Cases array
        cases = data.get('cases')
        if not isinstance(cases, list) or len(cases) == 0:
            raise ValueError('cases must be nonempty array')

        # Track which models are used
        used_models = set()
        has_baseline_frozen = False
        has_baseline_perturbation = False

        for i, c in enumerate(cases):
            if not isinstance(c, dict):
                raise ValueError(f'cases[{i}] must be object')
            if not isinstance(c.get('name'), str) or not c['name'].strip():
                raise ValueError(f'cases[{i}].name must be nonempty string')

            model_ref = c.get('model')
            if model_ref not in ('baseline', 'thicker'):
                raise ValueError(f'cases[{i}].model must be "baseline" or "thicker"')
            used_models.add(model_ref)

            reference_q = c.get('reference_q')
            if not isinstance(reference_q, list):
                raise ValueError(f'cases[{i}].reference_q must be array')
            n_modes_expected = len(models[model_ref]['modes'])
            if len(reference_q) != n_modes_expected:
                raise ValueError(f'cases[{i}].reference_q has {len(reference_q)} values, expected {n_modes_expected} for {model_ref}')
            finite_array(reference_q, f'cases[{i}].reference_q')

            frames = c.get('frames')
            if not isinstance(frames, list) or len(frames) < 2:
                raise ValueError(f'cases[{i}].frames must have >= 2 entries')

            # Validate frame structure: [time_seconds, q0, q1, ...]
            last_time = -1.0
            for j, f in enumerate(frames):
                if not isinstance(f, list) or len(f) < 2:
                    raise ValueError(f'cases[{i}].frames[{j}]: must have time and q values')
                t = number(f[0], 'frame time')
                if isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0:
                    raise ValueError(f'cases[{i}].frames[{j}].time_seconds must be nonnegative number')
                if t <= last_time:
                    raise ValueError(f'cases[{i}].frames: times must be strictly increasing')
                last_time = t

                q = f[1:]
                if len(q) != n_modes_expected:
                    raise ValueError(f'cases[{i}].frames[{j}]: q has {len(q)} values, expected {n_modes_expected}')
                finite_array(q, f'cases[{i}].frames[{j}].q')

            note = c.get('note')
            if note is not None and not isinstance(note, str):
                raise ValueError(f'cases[{i}].note must be string or null')

            stopped = c.get('stopped_at_50mm_guard')
            if not isinstance(stopped, bool):
                raise ValueError(f'cases[{i}].stopped_at_50mm_guard must be boolean')

            # Track specific case types for ordering check
            if model_ref == 'baseline':
                if note and 'frozen' in note.lower():
                    has_baseline_frozen = True
                if note and 'loaded' in note.lower():
                    has_baseline_perturbation = True

        if max(c['frames'][0][0] for c in cases) >= min(c['frames'][-1][0] for c in cases):
            raise ValueError('case histories must have a common positive time interval')

        # Verify at least one baseline case exists
        if 'baseline' not in used_models:
            raise ValueError('At least one baseline model case is required')

        # Verify at least one thicker model case exists
        if 'thicker' not in used_models:
            raise ValueError('At least one thicker model case is required')

    except (KeyError, TypeError) as exc:
        raise ValueError(f'malformed equilibrium comparison data: {exc}') from exc
    return data


def build_html(data):
    """Build HTML with embedded data and viewer script."""
    validate(data)
    # Escape JSON for safe embedding in <script> tag
    encoded = json.dumps(data, separators=(',', ':'), allow_nan=False)
    # Escape special characters that could break script tags
    for a, b in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        encoded = encoded.replace(a, b)

    assets = Path(__file__).with_name('equilibrium_comparison')
    page = (assets / 'viewer.html').read_text()
    script = (assets / 'viewer.js').read_text()
    return page.replace('/*__VIEWER__*/', script).replace('/*__DATA__*/', encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='Input JSON data path')
    parser.add_argument('--output', type=Path, required=True, help='Output HTML path')
    args = parser.parse_args()

    try:
        raw = args.data.read_bytes()
        def reject(value):
            raise ValueError(f'nonfinite JSON constant: {value}')
        data = json.loads(raw, parse_constant=reject)
        page = build_html(data)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(page)
        print(json.dumps({
            'output': str(args.output),
            'input_sha256': hashlib.sha256(raw).hexdigest(),
            'cases': len(data['cases']),
            'nodes': len(data['mesh']['nodes']),
            'models': list(data['models'].keys())
        }))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Equilibrium comparison build failed: {exc}\n')


if __name__ == '__main__':
    main()
