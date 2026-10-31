"""Render supplied loaded-response histories and assessments in imperial units.

python3 -m scripts.experiments.render_loaded_response --manifest FILE --output DIR
Paths in the manifest are relative to its directory. DIR must not exist.
Writes PNG plots and a self-contained HTML preview; computes no damping fits.
"""
import argparse
import html
import hashlib
import io
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from scripts.engineering_units import to_imperial


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite real number')
    return value


def load_cases(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    reference = number(manifest['steady_reference_q_m'])
    entries = manifest['cases']
    if not isinstance(entries, list) or not entries:
        raise ValueError('Manifest must contain at least one case')
    cases = []
    for entry in entries:
        if not isinstance(entry['name'], str) or not entry['name'].strip():
            raise ValueError('Case name must be a nonempty string')
        data = {'name': entry['name']}
        hashes = {}
        for key in ('history', 'assessment', 'fit'):
            if key == 'fit' and entry.get(key) is None:
                continue
            raw = (manifest_path.parent / entry[key]).read_bytes()
            hashes[key] = hashlib.sha256(raw).hexdigest()
            data[key] = json.loads(raw)
            if not isinstance(data[key], dict):
                raise ValueError(f'{key} must be an object')
        history, audit = data['history'], data['assessment']
        for obj, key in ((history, 'completed'), (audit, 'completed'), (audit, 'mesh_failed')):
            if not isinstance(obj.get(key), bool):
                raise ValueError(f'{key} must be boolean')
        count = audit['mesh_ok_count']
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('Mesh check count must be a nonnegative integer')
        code = audit.get('execution', {}).get('exit_code')
        if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
            raise ValueError('Solver exit code must be an integer or absent')
        settings = history['settings']
        samples = [[0., number(settings['initial_q_m']), number(settings['initial_force_N'])]]
        for row in history['rows']:
            samples.append([number(row[k]) for k in ('time_s', 'q_m', 'Q_N')])
        data['samples'] = np.array(samples, dtype=float)
        if np.any(np.diff(data['samples'][:, 0]) <= 0):
            raise ValueError('Accepted history times must increase strictly after t=0')
        fit = data.get('fit')
        if fit is not None:
            for source, field in (('history', 'history_sha256'), ('assessment', 'audit_sha256')):
                if field in fit and fit[field] != hashes[source]:
                    raise ValueError(f'Fit does not match its {source} source')
            for key in ('completed', 'run_checks_passed'):
                if not isinstance(fit.get(key), bool):
                    raise ValueError(f'Fit {key} must be boolean')
            if fit.get('classification') not in ('observed_decay', 'observed_growth', 'indeterminate'):
                raise ValueError('Unknown supplied response classification')
            if not isinstance(fit.get('fits'), list):
                raise ValueError('Fit entries must be a list')
            for item in fit['fits']:
                if not isinstance(item, dict) or not isinstance(item.get('status'), str):
                    raise ValueError('Each fit entry must have a status')
                # Failed, indeterminate and insufficient histories need no invented metrics.
                if item['status'] == 'fit_available':
                    for key in ('fit_start_s', 'fit_end_s', 'growth_per_s', 'frequency_hz', 'fitted_center_m'):
                        number(item[key])
                    number(item['positive_peak_fit']['count'])
        cases.append(data)
    return reference, cases


def status(case):
    history, audit, fit = case['history'], case['assessment'], case.get('fit')
    if len(case['samples']) < 2 or not history['completed'] or not audit['completed']:
        return 'Incomplete run; no damping conclusion', False
    if audit.get('execution', {}).get('exit_code') != 0:
        return 'Solver failed or unverified; no damping conclusion', False
    if audit['mesh_failed']:
        return 'Mesh quality failed; no damping conclusion', False
    if audit['mesh_ok_count'] < 2:
        return 'Mesh checks incomplete; no damping conclusion', False
    if fit is None:
        return 'Damping not assessed (no fit supplied)', False
    if not fit['completed'] or not fit['run_checks_passed']:
        return 'Assessment incomplete or failed; no damping conclusion', False
    available = [item for item in fit['fits'] if item['status'] == 'fit_available']
    if not available or len(available) != len(fit['fits']):
        return 'Indeterminate response; no damping conclusion', False
    label = {'observed_decay': 'Observed decay', 'observed_growth': 'Observed growth',
             'indeterminate': 'Indeterminate response'}[fit['classification']]
    return label, True


def metrics(cases):
    rows = []
    for case in cases:
        label, show = status(case)
        entries = case['fit']['fits'] if show else [None]
        for item in entries:
            values = [case['name'], label, f"{case['samples'][-1, 0]:.4f}"]
            if item is None:
                values += ['—'] * 5
            else:
                values += [f"{item['fit_start_s']:.4f}–{item['fit_end_s']:.4f}",
                           f"{item['growth_per_s']:+.4f}", f"{item['frequency_hz']:.4f}",
                           str(item['positive_peak_fit']['count']),
                           f"{to_imperial(item['fitted_center_m'], 'in'):.5f}"]
            rows.append('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in values) + '</tr>')
    return ''.join(rows)


def render(manifest, output):
    reference, cases = load_cases(manifest)
    # Exclusive creation preserves existing files, even when inputs are invalid.
    output.mkdir(parents=True, exist_ok=False)
    specs = [('tip_displacement', 'Total tip displacement (in)', 'in', 1, 0.),
             ('tip_displacement_rel', 'Tip displacement from steady reference (in)', 'in', 1, reference),
             ('generalized_force', 'Generalized aerodynamic force (lbf)', 'lbf', 2, 0.)]
    svgs = []
    for panel, (name, ylabel, unit, column, offset) in enumerate(specs):
        fig, ax = plt.subplots(figsize=(10, 4), layout='constrained')
        for index, case in enumerate(cases):
            samples = case['samples']
            ax.plot(samples[:, 0], to_imperial(samples[:, column] - offset, unit),
                    label=case['name'], linestyle=('-', '--', '-.', ':')[index % 4],
                    gid=f'curve-{index}-{panel}', linewidth=1.5)
        ax.set(xlabel='Time (s)', ylabel=ylabel)
        ax.set_xlim(0, max(case['samples'][-1, 0] for case in cases) or 1.)
        if panel == 1:
            ax.axhline(0., color='gray', linewidth=.7)
        ax.grid(alpha=.25)
        ax.legend(fontsize='small')
        fig.savefig(output / (name + '.png'), dpi=150)
        buffer = io.StringIO()
        fig.savefig(buffer, format='svg')
        plt.close(fig)
        svg = buffer.getvalue()
        svgs.append(svg[svg.index('<svg'):])
    controls = ' '.join(f'<label><input type="checkbox" checked data-case="{i}">'
                        + html.escape(case['name']) + '</label>' for i, case in enumerate(cases))
    headers = ['Case', 'Run / response status', 'Recorded end (s)', 'Fit interval (s)',
               'Growth (1/s)', 'Frequency (Hz)', 'Positive peaks', 'Fitted center (in)']
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loaded native CFD response</title><style>
body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 20px;color:#172c40;background:#f7f9fb}
svg{width:100%;height:auto}table{border-collapse:collapse;font-size:14px}td,th{padding:9px;text-align:left;border-bottom:1px solid #ccd5df}
label{display:inline-block;margin:5px 14px 5px 0}.table{overflow-x:auto}
</style><h1>Loaded native CFD response</h1>
<p>Single first-bending-mode live CFD. These histories do not determine a wing flutter limit.
Generalized force weights the surface loads by the first bending mode.</p>'''
    page += f'<p>Steady starting reference: {to_imperial(reference, "in"):.5f} in. '
    page += 'The fitted oscillation center is reported separately in the table. Curves end at their recorded times.</p>'
    page += '<p>Toggle overlapping curves:</p>' + controls + ''.join(svgs)
    page += '<div class="table"><table><tr>' + ''.join('<th>' + x + '</th>' for x in headers)
    page += '</tr>' + metrics(cases) + '</table></div>'
    page += '''<p>Negative growth indicates decay; positive growth indicates increasing amplitude in the supplied fit.
Failed or incomplete runs receive no damping conclusion. This preview displays supplied assessments and computes no fits.</p>
<script>document.querySelectorAll('input[data-case]').forEach(input=>input.addEventListener('change',()=>{
[0,1,2].forEach(panel=>document.getElementById('curve-'+input.dataset.case+'-'+panel).style.display=input.checked?'':'none');
}));</script></html>'''
    (output / 'index.html').write_text(page)
    return output / 'index.html'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(render(args.manifest, args.output))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    main()
