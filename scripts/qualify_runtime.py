#!/usr/bin/env python3
"""Qualify a pinned native Linux OpenFOAM runtime; not physical validation."""
import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Architecture to image digest mapping
ARCH_IMAGE_MAP = {
    'aarch64': 'b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4',
    'arm64': 'b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4',
    'x86_64': 'adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b',
    'amd64': 'adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b',
}


def get_openfoam_image():
    """Get the pinned OpenFOAM image reference based on host architecture."""
    host_arch = platform.machine().lower()
    if host_arch not in ARCH_IMAGE_MAP:
        raise ValueError(f'unsupported host architecture: {host_arch}')
    return 'opencfd/openfoam-default@sha256:' + ARCH_IMAGE_MAP[host_arch]
SHELL_PAYLOAD = '''#!/bin/bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
printf '%s\\n' "$WM_PROJECT_VERSION" > version.txt
printf '%s\\n' "$WM_OPTIONS" > build-options.txt
run_command() {
    case_name="$1"; command_name="$2"
    if "$command_name" -case "$case_name" > "$case_name/log.$command_name" 2>&1; then
        rc=0
    else
        rc=$?
    fi
    printf '%s %s %s\\n' "$case_name" "$command_name" "$rc" >> exit-codes.txt
    return "$rc"
}
for case_name in cavity-a cavity-b; do
    cp -r "$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity" "$case_name"
    for command_name in blockMesh checkMesh icoFoam; do
        run_command "$case_name" "$command_name"
    done
done
'''


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_field(path, kind):
    """Strict parser for the pinned tutorial's nonuniform ASCII internal field."""
    text = Path(path).read_text()
    require(re.search(r'format\s+ascii\s*;', text), f'{path}: expected ASCII')
    match = re.search(r'internalField\s+nonuniform\s+List<'+kind+r'>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    require(match is not None, f'{path}: missing nonuniform {kind} internalField')
    count, body = int(match[1]), match[2]
    if kind == 'vector':
        values = [[float(x) for x in row.split()] for row in re.findall(r'\(([^()]*)\)', body)]
        require(not re.sub(r'\([^()]*\)', '', body).strip(), f'{path}: unexpected vector data')
        require(all(len(row) == 3 for row in values), f'{path}: expected three vector components')
        flat = [x for row in values for x in row]
    else:
        values = [float(x) for x in body.split()]
        flat = values
    require(count == len(values) == 400, f'{path}: expected 400 values, got {len(values)}, declared {count}')
    require(all(math.isfinite(x) for x in flat), f'{path}: nonfinite field')
    return values


def parse_solver_log(text):
    require(re.search(r'^End\s*$', text, re.M), 'icoFoam missing End')
    times = re.findall(r'^Time = (\S+)\s*$', text, re.M)
    courant = re.findall(r'Courant Number mean:\s*\S+\s+max:\s*(\S+)', text)
    continuity = re.findall(r'time step continuity errors : sum local = (\S+), global = (\S+), cumulative = (\S+)', text)
    require(times and courant and continuity, 'missing time, Courant or continuity evidence')
    times = [float(x) for x in times]
    courant = [float(x) for x in courant]
    continuity = [[float(x) for x in row] for row in continuity]
    require(all(math.isfinite(x) for x in times+courant+[x for row in continuity for x in row]), 'nonfinite solver evidence')
    require(times[-1] == 0.5, 'expected final time 0.5')
    require(0 <= min(courant) <= max(courant) <= 1, 'Courant out of bounds')
    require(abs(continuity[-1][0]) <= 1e-6, 'local continuity exceeds 1e-6')
    require(abs(continuity[-1][2]) <= 1e-10, 'cumulative continuity exceeds 1e-10')
    build = re.search(r'^Build\s*:\s*(.+)$', text, re.M)
    require(build is not None and '2412' in build[1], 'unexpected/missing solver build')
    return dict(final_time=times[-1], max_courant=max(courant), final_local_continuity=continuity[-1][0],
                final_cumulative_continuity=continuity[-1][2], build=build[1])


def verify_acceptance(output):
    output = Path(output)
    require((output/'version.txt').read_text().strip() == 'v2412', 'unexpected OpenFOAM version')
    expected = [f'{case} {cmd} 0' for case in ('cavity-a','cavity-b') for cmd in ('blockMesh','checkMesh','icoFoam')]
    require((output/'exit-codes.txt').read_text().splitlines() == expected, 'incomplete/failed command ledger')
    evidence = {}
    for name in ('cavity-a', 'cavity-b'):
        case = output/name
        mesh = (case/'log.checkMesh').read_text()
        require(re.search(r'^Mesh OK\.\s*$', mesh, re.M), f'{name}: checkMesh failed')
        require(re.search(r'^\s*cells:\s+400\s*$', mesh, re.M), f'{name}: expected 400 cells')
        u = read_field(case/'0.5/U', 'vector')
        read_field(case/'0.5/p', 'scalar')
        speed = [math.sqrt(sum(v*v for v in row)) for row in u]
        require(max(speed) <= 1.1, f'{name}: velocity exceeds 1.1 m/s')
        require(min(row[0] for row in u) < 0 < max(row[0] for row in u), f'{name}: missing recirculation signs')
        evidence[name] = dict(mesh_ok=True, cells=400, velocity_vectors=400, pressure_values=400,
                              max_speed_mps=max(speed), **parse_solver_log((case/'log.icoFoam').read_text()))
    for field in ('U', 'p'):
        require((output/'cavity-a/0.5'/field).read_bytes() == (output/'cavity-b/0.5'/field).read_bytes(), f'{field}: repeated fields differ')
    evidence['byte_identical_fields'] = ['U','p']
    return evidence


def container_command(output):
    return ['docker','run','--rm','--pull','never','--network','none','--memory','2g','--cpus','2',
            '--user', f'{os.getuid()}:{os.getgid()}', '--mount',f'type=bind,src={output},dst=/work',
            '--workdir','/work','--entrypoint','/bin/bash',get_openfoam_image(),'/work/run.sh']


def qualify(output):
    output = Path(output).absolute()
    host_arch = platform.machine().lower()
    # Early rejection of unsupported architecture before directory creation
    if host_arch not in ARCH_IMAGE_MAP:
        report = dict(schema='openfoam-runtime-qualification-v1', run_id=output.name,
                      started_utc=datetime.now(timezone.utc).isoformat(), status='failed',
                      scope='runtime qualification and repeatability; not physical validation',
                      image_reference=None, platform=platform.platform(), architecture=host_arch,
                      limits=dict(memory='2g',cpus=2), commands=[],
                      error=f'unsupported host architecture: {host_arch}',
                      finished_utc=datetime.now(timezone.utc).isoformat(),
                      artifacts_sha256={})
        output.mkdir(parents=True, exist_ok=False)
        (output/'qualify_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        return report
    # mkdir is intentionally exclusive, including empty existing directories/symlinks.
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='openfoam-runtime-qualification-v1', run_id=output.name,
                  started_utc=datetime.now(timezone.utc).isoformat(), status='failed',
                  scope='runtime qualification and repeatability; not physical validation',
                  image_reference=get_openfoam_image(), platform=platform.platform(), architecture=host_arch,
                  limits=dict(memory='2g',cpus=2), commands=[])
    try:
        require(',' not in str(output), 'Docker mount path must not contain commas')
        revision = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        dirty = subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        report['source'] = dict(revision=revision, dirty=bool(dirty), launcher_sha256=sha256_file(__file__))
        inspect = ['docker','image','inspect',get_openfoam_image()]
        result = subprocess.run(inspect,capture_output=True,text=True)
        report['commands'].append(dict(argv=inspect,exit_code=result.returncode))
        (output/'image-inspect.log').write_text(result.stdout+result.stderr)
        require(result.returncode == 0, 'pinned image missing: use documented explicit docker pull')
        identity = json.loads(result.stdout)[0]
        expected_arch = 'arm64' if host_arch in ('aarch64', 'arm64') else 'amd64'
        require(identity['Architecture']==expected_arch and identity['Os']=='linux', f'image is not linux/{expected_arch}')
        report['image'] = {key:identity[key] for key in ('Id','Architecture','Os','Size','RepoDigests')}
        report['platform_match'] = dict(host=host_arch, image=identity['Architecture'], os=identity['Os'])
        (output/'run.sh').write_text(SHELL_PAYLOAD)
        command = container_command(output)
        result = subprocess.run(command,capture_output=True,text=True)
        report['commands'].append(dict(argv=command,exit_code=result.returncode))
        (output/'container_stdout.log').write_text(result.stdout)
        (output/'container_stderr.log').write_text(result.stderr)
        require(result.returncode == 0, f'container exited {result.returncode}; inspect retained logs')
        report['checks'] = verify_acceptance(output)
        report['status'] = 'passed'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report['error'] = str(exc)
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        report['artifacts_sha256'] = {str(p.relative_to(output)):sha256_file(p)
                                     for p in sorted(output.rglob('*')) if p.is_file() and p.name!='qualify_report.json'}
        (output/'qualify_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new artifact directory; existing paths rejected')
    args = parser.parse_args()
    try:
        report = qualify(args.output)
    except (OSError, ValueError) as exc:
        print(str(exc))
        return 1
    print(json.dumps({key:report[key] for key in ('status','run_id','scope')}))
    if 'error' in report:
        print(report['error'])
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
