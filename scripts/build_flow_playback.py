#!/usr/bin/env python3
"""Build an offline diagnostic viewer from sampled physical-time CFD JSON."""
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


def increasing(rows, name):
    last = -1.0
    for r in rows:
        t = number(r['time_s'], name + '.time_s')
        if t < 0 or t <= last:
            raise ValueError(f'{name}: times must be nonnegative and strictly increasing')
        last = t


def validate(data):
    try:
        if data['schema_version'] != 1 or isinstance(data['schema_version'], bool):
            raise ValueError('unsupported schema_version')
        if data['time_kind'] != 'physical_seconds':
            raise ValueError('only physical_seconds is supported; steady iterations are not time')
        run = data['run']
        for k in ['id', 'solver', 'source_revision']:
            if not isinstance(run[k], str) or not run[k]:
                raise ValueError(f'run.{k}: expected nonempty text')
        if run['status'] != 'diagnostic_only':
            raise ValueError('run.status must be diagnostic_only')
        for k in ['speed_m_s', 'chord_m', 'dynamic_pressure_kinematic']:
            if number(run[k], k) <= 0:
                raise ValueError(f'{k}: must be positive')
        number(run['reference_pressure_kinematic'], 'reference pressure')
        for v in sequence(run['limitations'], 'limitations'):
            if not isinstance(v, str) or not v.strip():
                raise ValueError('limitations must contain nonempty text')
        wing, samples = data['wing'], data['samples']
        vectors(wing['points'], 'wing.points')
        for tri in sequence(wing['triangles'], 'triangles'):
            if not isinstance(tri, list) or len(tri) != 3 or len(set(tri)) != 3:
                raise ValueError('triangle must contain three distinct indices')
            if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(wing['points']) for i in tri):
                raise ValueError('triangle index out of bounds or not an integer')
        vectors(samples['points'], 'samples.points')
        n = len(samples['points'])
        if len(sequence(samples['groups'], 'groups')) != n or any(g not in ['midspan', 'tip', 'wake'] for g in samples['groups']):
            raise ValueError('sample groups must match points and be midspan/tip/wake')
        frames = sequence(data['frames'], 'frames')
        if len(frames) < 2:
            raise ValueError('at least two physical-time frames are required')
        increasing(frames, 'frames')
        for f in frames:
            vectors(f['U'], 'frame.U')
            if len(f['U']) != n or len(sequence(f['p'], 'frame.p')) != n:
                raise ValueError('frame field lengths must match sample points')
            for u, p in zip(f['U'], f['p']):
                number(math.hypot(*u), 'derived speed')
                number((number(p, 'p') - run['reference_pressure_kinematic']) / run['dynamic_pressure_kinematic'], 'derived Cp')
            number(f['time_s'] * run['speed_m_s'] / run['chord_m'], 'dimensionless time')
        loads = sequence(data['loads'], 'loads', nonempty=False)
        increasing(loads, 'loads')
        for r in loads:
            for k in ['CL', 'CD', 'Cm']:
                number(r[k], k)
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError(f'malformed playback data: {exc}') from exc
    return data


def derived_ranges(data):
    run = data['run']
    speeds = [math.hypot(*u) for f in data['frames'] for u in f['U']]
    cp = [(p-run['reference_pressure_kinematic'])/run['dynamic_pressure_kinematic'] for f in data['frames'] for p in f['p']]
    return {'speed': [min(speeds), max(speeds)], 'cp': [min(cp), max(cp)]}


def build_html(data):
    validate(data)
    payload = dict(data, color_ranges=derived_ranges(data))
    encoded = json.dumps(payload, separators=(',', ':'), allow_nan=False)
    for a, b in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        encoded = encoded.replace(a, b)
    assets = Path(__file__).with_name('playback')
    page = (assets/'viewer.html').read_text()
    script = (assets/'viewer.js').read_text()
    return page.replace('/*__VIEWER__*/', script).replace('/*__DATA__*/', encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        def reject(value):
            raise ValueError(f'nonfinite JSON constant: {value}')
        data = json.loads(raw, parse_constant=reject)
        page = build_html(data)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(page)
        print(json.dumps({'output': str(args.output), 'input_sha256': hashlib.sha256(raw).hexdigest(), 'frames': len(data['frames']), 'time_kind': 'physical_seconds'}))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Playback build failed: {exc}\n')


if __name__ == '__main__':
    main()
