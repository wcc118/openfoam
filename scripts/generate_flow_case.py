"""Generate an UNQUALIFIED OpenCFD v2412 rigid-wing case; never run the solver."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

V_INF, RHO, NU = 30.0, 1.2250532683653954, 1.4605775310347254e-5
CHORD, SPAN = .1016, 1.2192
AREA = CHORD * SPAN
COFR = (.0254, 0., 0.)
REQUIRED = ('points', 'faces', 'owner', 'neighbour', 'boundary')
OPTIONAL = ('cellZones', 'faceZones', 'pointZones')
PATCHES = {'inlet': 'patch', 'outlet': 'patch', 'farfield': 'patch', 'wing': 'wall'}


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def vector(values):
    return '(' + ' '.join(format(v, '.16g') for v in values) + ')'


def flow_quantities(alpha):
    if not math.isfinite(alpha) or not -15 <= alpha <= 15:
        raise ValueError('alpha must be finite and in [-15, 15] degrees')
    a = math.radians(alpha)
    drag = (math.cos(a), 0., math.sin(a))
    lift = (-math.sin(a), 0., math.cos(a))
    k = 1.5 * (V_INF * .001) ** 2
    return dict(alpha_deg=alpha, velocity_m_s=[V_INF*x for x in drag],
                drag_direction=drag, lift_direction=lift, pitch_axis=(0., 1., 0.),
                dynamic_pressure_Pa=.5*RHO*V_INF**2, k_m2_s2=k,
                omega_per_s=math.sqrt(k)/(.09**.25 * .07*CHORD))


def mesh_files(mesh):
    """Accept a small native ASCII boundary subset, not a general Foam parser."""
    if mesh.is_symlink() or not mesh.is_dir():
        raise ValueError('mesh-dir must be a real directory')
    files = []
    for name in REQUIRED + OPTIONAL:
        p = mesh/name
        if p.is_symlink():
            raise ValueError(f'mesh symlink is not supported: {name}')
        if p.exists():
            if not p.is_file():
                raise ValueError(f'mesh entry is not a regular file: {name}')
            files.append(name)
        elif name in REQUIRED:
            raise ValueError(f'missing mesh file: {name}')
    text = (mesh/'boundary').read_text(encoding='ascii')
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    text = re.sub(r'\bFoamFile\s*\{[^{}]*\}', '', text, count=1)
    match = re.fullmatch(r'\s*(\d+)\s*\((.*)\)\s*;?\s*', text, re.S)
    if not match:
        raise ValueError('unsupported boundary format; require native counted ASCII patch list')
    entries = re.findall(r'([A-Za-z_]\w*)\s*\{([^{}]*)\}', match[2])
    remainder = re.sub(r'[A-Za-z_]\w*\s*\{[^{}]*\}', '', match[2]).strip()
    names = [n for n, _ in entries]
    if remainder or int(match[1]) != len(entries) or len(names) != len(set(names)):
        raise ValueError('malformed or duplicate boundary patches')
    if set(names) != set(PATCHES):
        raise ValueError(f'expected patches {sorted(PATCHES)}; found {names}')
    for name, body in entries:
        kind = re.search(r'\btype\s+(\w+)\s*;', body)
        if not kind or kind[1] != PATCHES[name]:
            raise ValueError(f'wrong boundary type for {name}')
        for key in ('nFaces', 'startFace'):
            value = re.search(r'\b'+key+r'\s+(\d+)\s*;', body)
            if not value or (key == 'nFaces' and int(value[1]) == 0):
                raise ValueError(f'invalid {key} for {name}')
    return files, names


def foam_header(name, kind='dictionary'):
    return f'FoamFile {{ version 2.0; format ascii; class {kind}; object {name}; }}\n'


def field(name, dimensions, initial, boundaries, kind='volScalarField'):
    return (foam_header(name, kind) + f'dimensions [{dimensions}];\n'
            + f'internalField uniform {initial};\nboundaryField\n{{\n'
            + ''.join(f'    {p} {{ {body} }}\n' for p, body in boundaries.items()) + '}\n')


def dictionaries(flow, iterations):
    u = vector(flow['velocity_m_s'])
    k, omega = flow['k_m2_s2'], flow['omega_per_s']
    def inlet_outlet(value):
        return {'inlet': f'type fixedValue; value uniform {value};',
                'outlet': f'type inletOutlet; inletValue uniform {value}; value uniform {value};',
                'farfield': f'type freestream; freestreamValue uniform {value}; value uniform {value};'}
    ub = inlet_outlet(u); ub['wing'] = 'type noSlip;'
    kb = inlet_outlet(k); kb['wing'] = 'type fixedValue; value uniform 0;'
    ob = inlet_outlet(omega)
    ob['wing'] = f'type omegaWallFunction; blending binomial; n 2; value uniform {omega};'
    pb = {'inlet': 'type zeroGradient;', 'outlet': 'type fixedValue; value uniform 0;',
          'farfield': 'type freestreamPressure; value uniform 0;', 'wing': 'type zeroGradient;'}
    nb = {p: 'type calculated; value uniform 0;' for p in PATCHES}
    nb['wing'] = 'type nutLowReWallFunction; value uniform 0;'
    result = {'0/U': field('U', '0 1 -1 0 0 0 0', u, ub, 'volVectorField'),
              '0/p': field('p', '0 2 -2 0 0 0 0', 0, pb),
              '0/k': field('k', '0 2 -2 0 0 0 0', k, kb),
              '0/omega': field('omega', '0 0 -1 0 0 0 0', omega, ob),
              '0/nut': field('nut', '0 2 -1 0 0 0 0', 0, nb)}
    result['constant/transportProperties'] = foam_header('transportProperties') + f'transportModel Newtonian;\nnu [0 2 -1 0 0 0 0] {NU};\n'
    result['constant/turbulenceProperties'] = foam_header('turbulenceProperties') + 'simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n'
    force_common = f'libs (forces); patches (wing); rho rhoInf; rhoInf {RHO}; CofR {vector(COFR)}; p p; U U; writeControl timeStep; writeInterval 1;'
    result['system/controlDict'] = foam_header('controlDict') + f'''application simpleFoam;
startFrom startTime; startTime 0; stopAt endTime; endTime {iterations}; deltaT 1;
writeControl timeStep; writeInterval 100; purgeWrite 0;
writeFormat ascii; writePrecision 12; timeFormat general; timePrecision 12;
runTimeModifiable false;
functions
{{
    forces {{ type forces; {force_common} }}
    forceCoeffs
    {{
        type forceCoeffs; {force_common}
        liftDir {vector(flow['lift_direction'])}; dragDir {vector(flow['drag_direction'])};
        pitchAxis (0 1 0); magUInf {V_INF}; lRef {CHORD}; Aref {AREA};
    }}
    solverInfo {{ type solverInfo; libs (utilityFunctionObjects); fields (p U k omega); writeControl timeStep; writeInterval 1; }}
    yPlus {{ type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }}
    wallShearStress {{ type wallShearStress; libs (fieldFunctionObjects); patches (wing); writeControl writeTime; }}
}}
'''
    result['system/fvSchemes'] = foam_header('fvSchemes') + '''ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; grad(U) cellLimited Gauss linear 1; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwindV grad(U);
    div(phi,k) bounded Gauss upwind;
    div(phi,omega) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited 0.5; }
wallDist { method meshWave; }
'''
    result['system/fvSolution'] = foam_header('fvSolution') + '''solvers
{
    p { solver GAMG; tolerance 1e-8; relTol 0.05; smoother GaussSeidel; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.1; }
}
SIMPLE { nNonOrthogonalCorrectors 1; consistent true; }
relaxationFactors { fields { p 0.3; } equations { U 0.7; k 0.7; omega 0.7; } }
'''
    return result


def source_metadata():
    root = Path(__file__).resolve().parents[1]
    data = {'generator_sha256': sha256_file(__file__), 'revision': None, 'dirty': None}
    try:
        rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, timeout=10)
        state = subprocess.run(['git', 'status', '--porcelain'], cwd=root, capture_output=True, text=True, timeout=10)
        if rev.returncode == 0: data['revision'] = rev.stdout.strip()
        if state.returncode == 0: data['dirty'] = bool(state.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return data


def generate_case(mesh_dir, output, alpha=4., iterations=500):
    flow = flow_quantities(alpha)
    if type(iterations) is not int or not 500 <= iterations <= 5000:
        raise ValueError('iterations must be an integer in [500, 5000]')
    mesh, out = Path(mesh_dir), Path(output)
    if out.exists() or out.is_symlink():
        raise ValueError('output must not already exist, including empty directories or symlinks')
    files, patches = mesh_files(mesh)
    if out.resolve().is_relative_to(mesh.resolve()):
        raise ValueError('output must not be inside the source mesh directory')
    source_hashes = {name: sha256_file(mesh/name) for name in files}
    report = {'schema_version': 1, 'status': 'setup_in_progress',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'source': source_metadata(),
              'mesh': {'source_path': str(mesh.resolve()), 'source_sha256': source_hashes,
                       'copied_sha256': {}, 'boundary_patches': patches},
              'flow': {**flow, 'speed_m_s': V_INF, 'density_kg_m3': RHO,
                       'kinematic_viscosity_m2_s': NU, 'chord_Re': V_INF*CHORD/NU,
                       'mach': V_INF/340.28686350385243, 'turbulence_intensity': .001,
                       'turbulence_length_scale_m': .07*CHORD},
              'geometry': {'span_m': SPAN, 'chord_m': CHORD, 'reference_area_m2': AREA,
                           'moment_origin_m': COFR},
              'axes': {'x': 'downstream', 'y': 'span', 'z': 'up', 'moment': 'positive y'},
              'atmosphere_source': {'repository': 'wcc118/flight-loads',
                  'revision': '7fe19f0761e00dd54238100461effa2533fc62c8',
                  'file': 'src/flightloads/atmosphere.py',
                  'sha256': 'a7ce6a74f152a713f5d02360580a1f94f9f91dd4e23f48ec07c629d00be0f5ca'},
              'model': {'solver': 'simpleFoam', 'turbulence': 'kOmegaSST',
                        'assumption': 'fully turbulent; transition uncertainty unresolved',
                        'wall_k': 'fixedValue 0', 'wall_omega': 'omegaWallFunction binomial n2',
                        'wall_nut': 'nutLowReWallFunction', 'pressure': 'kinematic m2/s2'},
              'iterations': iterations, 'time_meaning': 'SIMPLE iteration, not physical seconds',
              'generated_sha256': {}, 'scope': 'setup only; no mesh, flow or physical qualification'}
    # Once this succeeds, retain all partial artifacts on subsequent failures.
    out.mkdir(parents=True, exist_ok=False)
    stage = 'create_structure'
    try:
        (out/'constant/polyMesh').mkdir(parents=True)
        (out/'0').mkdir(); (out/'system').mkdir()
        stage = 'copy_mesh'
        for name in files:
            src, dst = mesh/name, out/'constant/polyMesh'/name
            if src.is_symlink() or not src.is_file():
                raise ValueError(f'source changed during copy: {name}')
            shutil.copyfile(src, dst, follow_symlinks=False)
            if dst.is_symlink():
                raise ValueError(f'source changed to symlink during copy: {name}')
            copied = sha256_file(dst)
            report['mesh']['copied_sha256'][name] = copied
            if copied != source_hashes[name] or sha256_file(src) != source_hashes[name]:
                raise ValueError(f'source/copy hash mismatch: {name}')
        stage = 'write_dictionaries'
        for name, text in dictionaries(flow, iterations).items():
            (out/name).write_text(text, encoding='ascii')
            report['generated_sha256'][name] = sha256_file(out/name)
        report['status'] = 'unqualified_setup'
        stage = 'write_manifest'
        (out/'manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    except (OSError, ValueError) as exc:
        report.update(status='setup_failed', failure={'stage': stage, 'error': str(exc)})
        try:
            (out/'manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        except OSError as manifest_error:
            print(f'Could not retain failure manifest: {manifest_error}', file=sys.stderr)
        raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--alpha-deg', type=float, default=4.)
    parser.add_argument('--iterations', type=int, default=500)
    args = parser.parse_args(argv)
    try:
        report = generate_case(args.mesh_dir, args.output, args.alpha_deg, args.iterations)
    except (OSError, ValueError) as exc:
        print(f'Case generation failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps({'output': str(args.output), 'status': report['status']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
