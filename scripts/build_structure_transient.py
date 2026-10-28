#!/usr/bin/env python3
"""Build an offline computed-transient structural viewer from JSON payload."""
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


def vectors(values, name):
    for i, v in enumerate(sequence(values, name)):
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError(f'{name}[{i}]: expected three components')
        for x in v:
            number(x, name)


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
        # Top-level fields
        if not isinstance(data.get('title'), str) or not data['title'].strip():
            raise ValueError('title must be nonempty string')
        if not isinstance(data.get('scope'), str) or not data['scope'].strip():
            raise ValueError('scope must be nonempty string')
        if not isinstance(data.get('source'), str) or not data['source'].strip():
            raise ValueError('source must be nonempty string')
        if not isinstance(data.get('source_sha256'), dict) or not data['source_sha256']:
            raise ValueError('source_sha256 must be nonempty object')

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
        for i, q in enumerate(quads):
            if not isinstance(q, list) or len(q) != 4:
                raise ValueError(f'mesh.quads[{i}]: expected 4 node indices')
            for j, idx in enumerate(q):
                if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx >= len(nodes):
                    raise ValueError(f'mesh.quads[{i}][{j}]: node index out of range')

        if 'perimeter_nodes' not in mesh:
            raise ValueError('mesh.perimeter_nodes is required')
        n_perim = mesh['perimeter_nodes']
        if isinstance(n_perim, bool) or not isinstance(n_perim, int) or n_perim <= 0:
            raise ValueError('mesh.perimeter_nodes must be positive integer')

        # Modes
        modes = data.get('modes')
        if not isinstance(modes, list) or len(modes) == 0:
            raise ValueError('modes must be nonempty array')
        for i, mode in enumerate(modes):
            if not isinstance(mode, list) or len(mode) != len(nodes):
                raise ValueError(f'modes[{i}]: must have {len(nodes)} node displacements')
            finite_3d_array(mode, f'modes[{i}]')

        if 'modal_scale' not in data:
            raise ValueError('modal_scale is required')
        modal_scale = data['modal_scale']
        if isinstance(modal_scale, bool) or not isinstance(modal_scale, (int, float)) or modal_scale <= 0:
            raise ValueError('modal_scale must be positive number')

        # Cases
        cases = data.get('cases')
        if not isinstance(cases, list) or len(cases) == 0:
            raise ValueError('cases must be nonempty array')

        for i, c in enumerate(cases):
            if not isinstance(c.get('name'), str) or not c['name'].strip():
                raise ValueError(f'cases[{i}].name must be nonempty string')
            speed = c.get('speed_m_s')
            if isinstance(speed, bool) or not isinstance(speed, (int, float)) or speed <= 0:
                raise ValueError(f'cases[{i}].speed_m_s must be positive number')

            if not isinstance(c.get('baseline_force_applied'), bool):
                raise ValueError(f'cases[{i}].baseline_force_applied must be boolean')

            def_scale = c.get('default_deformation_scale')
            if isinstance(def_scale, bool) or not isinstance(def_scale, (int, float)) or def_scale <= 0:
                raise ValueError(f'cases[{i}].default_deformation_scale must be positive number')

            note = c.get('note')
            if note is not None and not isinstance(note, str):
                raise ValueError(f'cases[{i}].note must be string or null')

            frames = c.get('frames')
            if not isinstance(frames, list) or len(frames) < 2:
                raise ValueError(f'cases[{i}].frames must have >= 2 entries')

            # Validate frame structure: [time_seconds, q0, q1, ...]
            last_time = -1.0
            n_modes_expected = len(modes)
            for j, f in enumerate(frames):
                if not isinstance(f, list) or len(f) < 2:
                    raise ValueError(f'cases[{i}].frames[{j}]: must have time and q values')
                t = f[0]
                if isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0:
                    raise ValueError(f'cases[{i}].frames[{j}].time_seconds must be nonnegative number')
                if t <= last_time:
                    raise ValueError(f'cases[{i}].frames: times must be strictly increasing')
                last_time = t

                q = f[1:]
                if len(q) != n_modes_expected:
                    raise ValueError(f'cases[{i}].frames[{j}]: q has {len(q)} values, expected {n_modes_expected}')
                finite_array(q, f'cases[{i}].frames[{j}].q')

            if 'peak_vertex_component_m' not in c:
                raise ValueError(f'cases[{i}].peak_vertex_component_m is required')
            peak = c['peak_vertex_component_m']
            if isinstance(peak, bool) or not isinstance(peak, (int, float)) or not math.isfinite(peak):
                raise ValueError(f'cases[{i}].peak_vertex_component_m must be finite number')

            if not isinstance(c.get('stopped_at_20mm_motion_guard'), bool):
                raise ValueError(f'cases[{i}].stopped_at_20mm_motion_guard must be boolean')

    except (KeyError, TypeError) as exc:
        raise ValueError(f'malformed structure transient data: {exc}') from exc
    return data


def build_html(data):
    """Build HTML with embedded data and viewer script."""
    validate(data)
    # Escape JSON for safe embedding in <script> tag
    encoded = json.dumps(data, separators=(',', ':'), allow_nan=False)
    # Escape special characters that could break script tags
    for a, b in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        encoded = encoded.replace(a, b)

    assets = Path(__file__).with_name('structure_transient')
    page = (assets / 'viewer.html').read_text()
    script = (assets / 'viewer.js').read_text()
    return page.replace('/*__DATA__*/', encoded).replace('/*__VIEWER__*/', script)


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
            'modes': len(data['modes'])
        }))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Structure transient build failed: {exc}\n')


if __name__ == '__main__':
    main()
