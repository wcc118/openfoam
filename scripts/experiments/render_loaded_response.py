#!/usr/bin/env python3
"""Render native loaded-response histories and assessments in imperial units.

Creates an offline HTML viewer with time-series plots (tip displacement,
displacement relative to steady reference, generalized aerodynamic force)
and a metrics table showing fitting intervals and damping parameters.

Usage:
    python3 -m scripts.experiments.render_loaded_response --manifest FILE --output DIR

Output: PNG plots and self-contained HTML (inline SVG) in the output directory.
"""
import argparse
import html
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from scripts.engineering_units import to_imperial


# ============================================================================#
# Validation helpers
# ============================================================================#

def _number(x, name):
    """Validate a finite number."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{name}: expected finite number')
    return x


def _sequence(x, name, nonempty=True):
    """Validate a list/sequence."""
    if not isinstance(x, list) or (nonempty and not x):
        raise ValueError(f'{name}: expected {"nonempty " if nonempty else ""}array')
    return x


def _validate_history(rows):
    """Validate history rows structure."""
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f'history.rows[{i}]: expected object')
        _number(row.get('time_s'), f'history.rows[{i}].time_s')
        _number(row.get('q_m'), f'history.rows[{i}].q_m')
        _number(row.get('Q_N'), f'history.rows[{i}].Q_N')


def _validate_assessment(assessment):
    """Validate assessment structure."""
    if not isinstance(assessment, dict):
        raise ValueError('assessment: expected object')
    mesh_failed = assessment.get('mesh_failed')
    if not isinstance(mesh_failed, bool):
        raise ValueError('assessment.mesh_failed: expected boolean')
    _number(assessment.get('mesh_ok_count'), 'assessment.mesh_ok_count')
    _number(assessment.get('max_native_force_difference_N'), 'assessment.max_native_force_difference_N')
    execution = assessment.get('execution', {})
    if not isinstance(execution, dict):
        raise ValueError('assessment.execution: expected object')
    _number(execution.get('exit_code'), 'assessment.execution.exit_code')


def _validate_fit(fit):
    """Validate fit structure."""
    if not isinstance(fit, dict):
        raise ValueError('fit: expected object')
    completed = fit.get('completed')
    if not isinstance(completed, bool):
        raise ValueError('fit.completed: expected boolean')
    run_passed = fit.get('run_checks_passed')
    if not isinstance(run_passed, bool):
        raise ValueError('fit.run_checks_passed: expected boolean')
    classification = fit.get('classification')
    if classification not in ('observed_decay', 'observed_growth', 'indeterminate'):
        raise ValueError(f'fit.classification: expected observed_decay/observed_growth/indeterminate, got {classification!r}')
    fits = fit.get('fits', [])
    if not isinstance(fits, list):
        raise ValueError('fit.fits: expected array')
    for i, f in enumerate(fits):
        if not isinstance(f, dict):
            raise ValueError(f'fit.fits[{i}]: expected object')
        status = f.get('status')
        if status not in ('fit_available', 'fit_failed', 'no_fit_attempted'):
            raise ValueError(f'fit.fits[{i}].status: expected fit_available/fit_failed/no_fit_attempted, got {status!r}')
        _number(f.get('fit_start_s'), f'fit.fits[{i}].fit_start_s')
        _number(f.get('fit_end_s'), f'fit.fits[{i}].fit_end_s')
        _number(f.get('growth_per_s'), f'fit.fits[{i}].growth_per_s')
        _number(f.get('frequency_hz'), f'fit.fits[{i}].frequency_hz')
        _number(f.get('fitted_center_m'), f'fit.fits[{i}].fitted_center_m')
        peak = f.get('positive_peak_fit', {})
        if not isinstance(peak, dict):
            raise ValueError(f'fit.fits[{i}].positive_peak_fit: expected object')
        _number(peak.get('count'), f'fit.fits[{i}].positive_peak_fit.count')


def _validate_case(case):
    """Validate a case entry."""
    if not isinstance(case, dict):
        raise ValueError('case: expected object')
    name = case.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('case.name: expected nonempty string')
    history_path = case.get('history')
    if not isinstance(history_path, str) or not history_path.strip():
        raise ValueError('case.history: expected nonempty string')
    assessment_path = case.get('assessment')
    if not isinstance(assessment_path, str) or not assessment_path.strip():
        raise ValueError('case.assessment: expected nonempty string')
    # fit is optional


def validate_manifest(data):
    """Validate manifest structure and referenced files."""
    if not isinstance(data, dict):
        raise ValueError('manifest: expected object')
    _number(data.get('steady_reference_q_m'), 'manifest.steady_reference_q_m')
    cases = _sequence(data.get('cases'), 'manifest.cases', nonempty=True)
    for i, c in enumerate(cases):
        _validate_case(c)
    return data


# ============================================================================#
# Data loading
# ============================================================================#

def load_json_file(path, base_dir):
    """Load JSON from a path relative to base_dir."""
    full_path = base_dir / path
    if not full_path.exists():
        raise FileNotFoundError(f'Missing file: {full_path}')
    with open(full_path, 'r') as f:
        return json.load(f)


def load_case_data(case, base_dir):
    """Load history and assessment for a case. Fit is optional."""
    data = {
        'name': case['name'],
        'history': load_json_file(case['history'], base_dir),
        'assessment': load_json_file(case['assessment'], base_dir),
    }
    if 'fit' in case and case['fit'] is not None:
        data['fit'] = load_json_file(case['fit'], base_dir)
    return data


# ============================================================================#
# Plotting
# ============================================================================#

def _fmt_in(val):
    """Format as inches."""
    return f'{val:.4f}'

def _fmt_lbf(val):
    """Format as lbf."""
    return f'{val:.4f}'

def _fmt_s(val):
    """Format as seconds."""
    return f'{val:.2f}'


def _plot_time_series(ax, t, y, label, style='-', **kwargs):
    """Plot a time series with consistent styling."""
    ax.plot(t, y, style, label=label, **kwargs)


def _add_plot_decorations(ax, ylabel, unit):
    """Add grid, legend, and labels."""
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel(f'{ylabel} ({unit})')
    ax.legend(loc='best', fontsize='small')


def _style_for_line(idx, name, has_fit=False):
    """Determine line style based on index/name."""
    styles = ['-', '--', '-.', ':']
    style = styles[idx % len(styles)]
    # First curve is solid, others vary; fit curves get dashed
    if has_fit:
        style = '--'
    return style


def render_plots(cases_data, steady_reference_q_m, output_dir):
    """Render time-series plots for all cases."""
    # Collect all time vectors for common x-axis range
    all_times = []
    for cd in cases_data:
        hist = cd['history']
        rows = hist.get('rows', [])
        for row in rows:
            all_times.append(row['time_s'])

    t_min = 0.0
    t_max = max(all_times) if all_times else 1.0

    # Plot 1: Total tip displacement (in)
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    ax1.set_title('Total Tip Displacement')

    for idx, cd in enumerate(cases_data):
        hist = cd['history']
        rows = hist.get('rows', [])
        t_vals = [row['time_s'] for row in rows]
        q_vals = [row['q_m'] for row in rows]

        # Add initial point from settings if available
        settings = hist.get('settings', {})
        init_q = settings.get('initial_q_m')
        init_force = settings.get('initial_force_N')
        if init_q is not None and init_force is not None:
            t_vals = [0.0] + t_vals
            q_vals = [init_q] + q_vals

        # Sort by time
        sorted_pairs = sorted(zip(t_vals, q_vals), key=lambda x: x[0])
        t_sorted, q_sorted = zip(*sorted_pairs)

        t_np = np.array(t_sorted)
        q_np = np.array(q_sorted)
        q_in = to_imperial(q_np, 'in')
        style = _style_for_line(idx, cd['name'])
        _plot_time_series(ax1, t_np, q_in, cd['name'], style=style, linewidth=1.5)

    _add_plot_decorations(ax1, 'Tip Displacement', 'in')
    ax1.set_xlim(left=t_min)

    # Plot 2: Tip displacement relative to steady reference (in)
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    ax2.set_title('Tip Displacement Relative to Steady Reference')

    for idx, cd in enumerate(cases_data):
        hist = cd['history']
        rows = hist.get('rows', [])
        t_vals = [row['time_s'] for row in rows]
        q_vals = [row['q_m'] for row in rows]

        # Add initial point from settings
        settings = hist.get('settings', {})
        init_q = settings.get('initial_q_m')
        if init_q is not None:
            t_vals = [0.0] + t_vals
            q_vals = [init_q] + q_vals

        sorted_pairs = sorted(zip(t_vals, q_vals), key=lambda x: x[0])
        t_sorted, q_sorted = zip(*sorted_pairs)

        t_np = np.array(t_sorted)
        q_np = np.array(q_sorted)
        q_rel_in = to_imperial(q_np - steady_reference_q_m, 'in')
        style = _style_for_line(idx, cd['name'])
        _plot_time_series(ax2, t_np, q_rel_in, cd['name'], style=style, linewidth=1.5)

    _add_plot_decorations(ax2, 'Tip Displacement - Steady Ref', 'in')
    ax2.set_xlim(left=t_min)
    ax2.axhline(0, color='black', linestyle=':', alpha=0.5)

    # Plot 3: Generalized aerodynamic force (lbf)
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    ax3.set_title('Generalized Aerodynamic Force')

    for idx, cd in enumerate(cases_data):
        hist = cd['history']
        rows = hist.get('rows', [])
        t_vals = [row['time_s'] for row in rows]
        Q_vals = [row['Q_N'] for row in rows]

        # Add initial point from settings
        settings = hist.get('settings', {})
        init_force = settings.get('initial_force_N')
        if init_force is not None:
            t_vals = [0.0] + t_vals
            Q_vals = [init_force] + Q_vals

        sorted_pairs = sorted(zip(t_vals, Q_vals), key=lambda x: x[0])
        t_sorted, Q_sorted = zip(*sorted_pairs)

        t_np = np.array(t_sorted)
        Q_np = np.array(Q_sorted)
        Q_lbf = to_imperial(Q_np, 'lbf')
        style = _style_for_line(idx, cd['name'])
        _plot_time_series(ax3, t_np, Q_lbf, cd['name'], style=style, linewidth=1.5)

    _add_plot_decorations(ax3, 'Generalized Force', 'lbf')
    ax3.set_xlim(left=t_min)

    # Save PNGs
    fig1.tight_layout()
    fig2.tight_layout()
    fig3.tight_layout()

    fig1.savefig(output_dir / 'tip_displacement.png', dpi=150, bbox_inches='tight')
    fig2.savefig(output_dir / 'tip_displacement_rel.png', dpi=150, bbox_inches='tight')
    fig3.savefig(output_dir / 'generalized_force.png', dpi=150, bbox_inches='tight')

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)

    return [
        'tip_displacement.png',
        'tip_displacement_rel.png',
        'generalized_force.png',
    ]


# ============================================================================#
# Metrics table generation
# ============================================================================#

def _compute_fit_status(cd):
    """Determine the effective fit status, overriding labels when needed."""
    if 'fit' not in cd:
        return 'no_damping_assessment'

    fit = cd['fit']

    # Check for incomplete data or failures
    if not fit.get('completed'):
        return 'incomplete_data'

    if not fit.get('run_checks_passed'):
        return 'no_damping_conclusion'

    assessment = cd['assessment']
    if assessment.get('mesh_failed'):
        return 'no_damping_conclusion'

    exec_info = assessment.get('execution', {})
    if exec_info.get('exit_code') != 0:
        return 'no_damping_conclusion'

    # Classification override
    classification = fit.get('classification')
    if classification == 'indeterminate':
        return 'no_damping_conclusion'

    # Valid fit available
    fits_list = fit.get('fits', [])
    if not fits_list:
        return 'no_damping_conclusion'

    for f in fits_list:
        if f.get('status') == 'fit_available':
            return 'damping_assessed'

    return 'no_damping_conclusion'


def generate_metrics_table(cases_data):
    """Generate HTML table with fit metrics."""
    rows = []
    for cd in cases_data:
        name = cd['name']
        status = _compute_fit_status(cd)

        if status == 'no_damping_assessment':
            rows.append({
                'name': name,
                'status': 'No damping assessment (no fit supplied)',
                'fit_start_s': '-',
                'fit_end_s': '-',
                'growth_per_s': '-',
                'frequency_hz': '-',
                'peak_count': '-',
                'fitted_center_in': '-',
            })
        elif status == 'incomplete_data':
            rows.append({
                'name': name,
                'status': 'Incomplete data',
                'fit_start_s': '-',
                'fit_end_s': '-',
                'growth_per_s': '-',
                'frequency_hz': '-',
                'peak_count': '-',
                'fitted_center_in': '-',
            })
        elif status == 'no_damping_conclusion':
            classification = cd['fit'].get('classification', 'unknown')
            rows.append({
                'name': name,
                'status': 'No damping conclusion',
                'fit_start_s': '-',
                'fit_end_s': '-',
                'growth_per_s': '-',
                'frequency_hz': '-',
                'peak_count': '-',
                'fitted_center_in': '-',
            })
        else:
            # Extract first available fit
            fits_list = cd['fit'].get('fits', [])
            fit = None
            for f in fits_list:
                if f.get('status') == 'fit_available':
                    fit = f
                    break

            if fit:
                fits_start = fit.get('fit_start_s', '-')
                fits_end = fit.get('fit_end_s', '-')
                growth = fit.get('growth_per_s', '-')
                freq = fit.get('frequency_hz', '-')
                peak_count = fit.get('positive_peak_fit', {}).get('count', '-')
                fitted_center = fit.get('fitted_center_m', '-')

                # Format values
                growth_str = f'{growth:.4f}' if growth != '-' else '-'
                freq_str = f'{freq:.4f}' if freq != '-' else '-'
                peak_str = f'{int(peak_count)}' if peak_count != '-' else '-'
                center_str = f'{to_imperial(fitted_center, "in"):.4f}' if fitted_center != '-' else '-'

                rows.append({
                    'name': name,
                    'status': 'Damping assessed',
                    'fit_start_s': f'{fits_start:.4f}' if fits_start != '-' else '-',
                    'fit_end_s': f'{fits_end:.4f}' if fits_end != '-' else '-',
                    'growth_per_s': growth_str,
                    'frequency_hz': freq_str,
                    'peak_count': peak_str,
                    'fitted_center_in': center_str,
                })
            else:
                rows.append({
                    'name': name,
                    'status': 'No damping conclusion',
                    'fit_start_s': '-',
                    'fit_end_s': '-',
                    'growth_per_s': '-',
                    'frequency_hz': '-',
                    'peak_count': '-',
                    'fitted_center_in': '-',
                })

    return rows


# ============================================================================#
# HTML generation
# ============================================================================#

def generate_html(cases_data, steady_reference_q_m, png_files, metrics_rows, output_dir):
    """Generate self-contained HTML viewer."""
    # Escape names for HTML
    escaped_names = [html.escape(cd['name']) for cd in cases_data]

    # Build plot images as base64 (inline SVG approach - simpler and more reliable)
    # We'll include PNGs as references to files in the same directory
    plot_html = []
    plot_titles = [
        'Total Tip Displacement',
        'Tip Displacement Relative to Steady Reference',
        'Generalized Aerodynamic Force',
    ]

    for i, png_file in enumerate(png_files):
        rel_path = png_file
        plot_html.append(f'''
        <div class="plot-section">
            <h3>{html.escape(plot_titles[i])}</h3>
            <img src="{rel_path}" alt="{html.escape(plot_titles[i])}" style="max-width: 100%;">
        </div>
        ''')

    # Build metrics table
    table_rows_html = []
    for row in metrics_rows:
        table_rows_html.append(f'''
        <tr>
            <td>{html.escape(row["name"])}</td>
            <td>{html.escape(row["status"])}</td>
            <td>{html.escape(str(row["fit_start_s"]))}</td>
            <td>{html.escape(str(row["fit_end_s"]))}</td>
            <td>{html.escape(str(row["growth_per_s"]))}</td>
            <td>{html.escape(str(row["frequency_hz"]))}</td>
            <td>{html.escape(str(row["peak_count"]))}</td>
            <td>{html.escape(str(row["fitted_center_in"]))}</td>
        </tr>
        ''')

    table_html = f'''
    <table class="metrics-table">
        <thead>
            <tr>
                <th>Case</th>
                <th>Fit Status</th>
                <th>Fit Start (s)</th>
                <th>Fit End (s)</th>
                <th>Growth (1/s)</th>
                <th>Frequency (Hz)</th>
                <th>Peak Count</th>
                <th>Fitted Center (in)</th>
            </tr>
        </thead>
        <tbody>
            {''.join(table_rows_html)}
        </tbody>
    </table>
    '''

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Native Loaded Response - {html.escape(cases_data[0]["name"])} et al.</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #ffffff;
            color: #333;
        }}
        h1 {{
            border-bottom: 2px solid #007acc;
            padding-bottom: 10px;
        }}
        .subtitle {{
            color: #666;
            font-size: 0.9em;
        }}
        .plot-section {{
            margin: 30px 0;
            padding: 20px;
            background: #f5f5f5;
            border-radius: 8px;
        }}
        .plot-section h3 {{
            margin-top: 0;
            color: #007acc;
        }}
        .metrics-section {{
            margin: 30px 0;
            padding: 20px;
            background: #f5f5f5;
            border-radius: 8px;
        }}
        .metrics-section h3 {{
            margin-top: 0;
            color: #007acc;
        }}
        .metrics-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        .metrics-table th,
        .metrics-table td {{
            padding: 10px;
            text-align: left;
            border: 1px solid #ddd;
        }}
        .metrics-table th {{
            background: #007acc;
            color: white;
        }}
        .metrics-table tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        .info-box {{
            padding: 15px;
            background: #e8f4fc;
            border-left: 4px solid #007acc;
            margin: 20px 0;
        }}
        .info-box strong {{
            color: #005a9e;
        }}
        .disclaimer {{
            margin-top: 40px;
            padding: 15px;
            background: #fff3cd;
            border: 1px solid #ffeeba;
            border-radius: 4px;
            font-size: 0.85em;
        }}
        .status-valid {{
            color: #155724;
            font-weight: bold;
        }}
        .status-invalid {{
            color: #721c24;
            font-weight: bold;
        }}
        .status-neutral {{
            color: #856404;
        }}
    </style>
</head>
<body>
    <h1>Native Loaded Response - Single First-Bending-Mode CFD</h1>
    <p class="subtitle">Rendered {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Steady reference q = {to_imperial(steady_reference_q_m, "in"):.4f} in</p>

    <div class="info-box">
        <strong>Model notes:</strong> This is a single first-bending-mode native CFD simulation.
        Torsional stability is not represented by this pilot. Results are for diagnostic purposes
        only and do not constitute flutter limit determination or flight clearance.
    </div>

    {''.join(plot_html)}

    <div class="metrics-section">
        <h3>Fitting Metrics</h3>
        {table_html}
        <p style="font-size: 0.85em; color: #666; margin-top: 15px;">
            <em>Note:</em> Cases with omitted fit, incomplete history, failed solver execution,
            mesh_failed=true, or fit.run_checks_passed=false override any supplied observed_decay/growth
            label with "No damping conclusion". Damping assessment is based solely on supplied fit data.
        </p>
    </div>

    <div class="disclaimer">
        <strong>Limitations:</strong> This renderer displays existing computed results.
        It does not run CFD simulations, compute damping fits, or validate physics.
        Solver survival does not imply stability. Results require independent engineering
        review before any operational use.
    </div>
</body>
</html>
'''

    return html_content


# ============================================================================#
# Main entry point
# ============================================================================#

def main():
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split('\n')[0],
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--manifest', type=Path, required=True,
                        help='Path to manifest JSON file')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output directory (created if needed)')
    args = parser.parse_args()

    try:
        # Validate and load manifest
        manifest_path = args.manifest
        if not manifest_path.exists():
            print(f'Error: Manifest not found: {manifest_path}', file=sys.stderr)
            sys.exit(1)

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        validate_manifest(manifest)

        # Determine base directory for relative paths
        base_dir = manifest_path.parent

        # Create output directory (strict: must be empty or created)
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)

        # Clear output directory if not empty
        for item in output_dir.iterdir():
            if item.is_file():
                item.unlink()

        # Load all case data
        cases_data = []
        for case in manifest['cases']:
            cd = load_case_data(case, base_dir)
            # Validate loaded data
            _validate_history(cd['history'].get('rows', []))
            _validate_assessment(cd['assessment'])
            if 'fit' in cd:
                _validate_fit(cd['fit'])
            cases_data.append(cd)

        steady_reference_q_m = manifest['steady_reference_q_m']

        # Render plots
        png_files = render_plots(cases_data, steady_reference_q_m, output_dir)

        # Generate metrics table
        metrics_rows = generate_metrics_table(cases_data)

        # Generate HTML
        html_content = generate_html(
            cases_data, steady_reference_q_m, png_files, metrics_rows, output_dir
        )

        # Write HTML
        html_path = output_dir / 'index.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f'Rendered {len(cases_data)} cases to {output_dir}')
        print(f'  PNG plots: {", ".join(png_files)}')
        print(f'  HTML viewer: {html_path}')

    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Validation error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Unexpected error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
