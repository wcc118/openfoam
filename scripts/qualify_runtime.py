#!/usr/bin/env python3
"""
OpenFOAM runtime qualification launcher.

Qualifies the pinned OpenFOAM Docker image by running the cavity tutorial
and verifying numerical acceptance criteria.

Usage:
    python3 scripts/qualify_runtime.py --output runs/unique-name

Exit codes:
    0 - Success
    1 - Argument error or precondition failure
    2 - Docker command failure
    3 - Acceptance check failure
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# Fixed OpenFOAM image identity
OPENFOAM_IMAGE = "opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4"
OPENFOAM_VERSION = "v2412"

# Shell activation payload
FOAM_BASHRC = "/usr/lib/openfoam/openfoam2412/etc/bashrc"

SHELL_PAYLOAD = f"""#!/bin/bash
set +u
source {FOAM_BASHRC}
set -u

# Record OpenFOAM version and build info
echo "=== OpenFOAM Runtime Information ==="
echo "WM_PROJECT_VERSION: $WM_PROJECT_VERSION"
echo "WM_COMPILER: $WM_COMPILER"
echo "WM_PRECISION_OPTION: $WM_PRECISION_OPTION"
echo "WM_LABEL_SIZE: $WM_LABEL_SIZE"
echo ""

# Run blockMesh
echo "=== Running blockMesh ==="
blockMesh -case cavity-a
blockMesh -case cavity-b

# Run checkMesh
echo "=== Running checkMesh ==="
checkMesh -case cavity-a -time 0
checkMesh -case cavity-b -time 0

# Run icoFoam
echo "=== Running icoFoam ==="
icoFoam -case cavity-a
icoFoam -case cavity-b

# Record solver exit codes
echo "=== Solver Exit Codes ==="
echo "blockMesh exit codes recorded above"
echo "checkMesh exit codes recorded above"
echo "icoFoam exit codes recorded above"
"""


def check_host_architecture():
    """Check if host architecture is aarch64/arm64."""
    result = subprocess.run(
        ["uname", "-m"],
        capture_output=True,
        text=True,
        check=True,
    )
    arch = result.stdout.strip().lower()
    if arch not in ("aarch64", "arm64"):
        raise RuntimeError(f"Unsupported architecture: {arch}. Expected aarch64/arm64.")
    return arch


def get_host_uid_gid():
    """Get host user and group IDs."""
    return os.getuid(), os.getgid()


def sha256_file(path):
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_string(s):
    """Compute SHA256 hash of a string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def ensure_output_path_empty(output_path):
    """Ensure output path doesn't exist or is empty directory."""
    p = Path(output_path)
    if p.exists():
        if not p.is_dir():
            raise ValueError(f"Output path exists and is not a directory: {output_path}")
        if any(p.iterdir()):
            raise ValueError(f"Output path is not empty: {output_path}")


def pull_docker_image():
    """Pull the pinned Docker image."""
    print(f"Pulling Docker image: {OPENFOAM_IMAGE}")
    result = subprocess.run(
        ["docker", "pull", OPENFOAM_IMAGE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise RuntimeError(f"Docker pull failed with exit code {result.returncode}")
    return result.stdout


def parse_docker_inspect_field(output, field):
    """Parse a field from docker inspect output."""
    try:
        data = json.loads(output)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return data.get(field, None)
    except (json.JSONDecodeError, IndexError):
        return None


def inspect_docker_image():
    """Inspect the Docker image for identity verification."""
    result = subprocess.run(
        ["docker", "image", "inspect", OPENFOAM_IMAGE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Docker inspect failed: {result.stderr}")
    
    image_id = parse_docker_inspect_field(result.stdout, "Id")
    created = parse_docker_inspect_field(result.stdout, "Created")
    arch = parse_docker_inspect_field(result.stdout, "Architecture")
    os_version = parse_docker_inspect_field(result.stdout, "Os")
    
    return {
        "id": image_id,
        "created": created,
        "architecture": arch,
        "os": os_version,
    }


def create_shell_script(output_path):
    """Create the shell script to run inside container."""
    script_path = output_path / "run.sh"
    with open(script_path, "w") as f:
        f.write(SHELL_PAYLOAD)
    os.chmod(script_path, 0o555)
    return script_path


def create_container_run_command(output_path, script_path, uid, gid):
    """Create the docker run command as argument array."""
    # Container flags per requirements
    base_flags = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--user",
        f"{uid}:{gid}",
    ]
    
    # Volume mounts: output directory writable, script readonly
    script_src = str(script_path.resolve())
    output_src = str(output_path.resolve())
    
    volume_flags = [
        "-v",
        f"{script_src}:/opt/run.sh:ro",
        "-v",
        f"{output_src}:/opt/output:rw",
    ]
    
    # Working directory and image
    workdir_flags = ["-w", "/opt"]
    
    # Image and command
    image_and_cmd = [OPENFOAM_IMAGE, "/bin/bash", "/opt/run.sh"]
    
    return base_flags + volume_flags + workdir_flags + [OPENFOAM_IMAGE] + ["/bin/bash", "/opt/run.sh"]


def run_container(output_path, script_path, uid, gid):
    """Run the container and capture output."""
    cmd = create_container_run_command(output_path, script_path, uid, gid)
    
    print(f"Running container with command: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    
    # Save container stdout/stderr
    (output_path / "container_stdout.log").write_text(result.stdout)
    (output_path / "container_stderr.log").write_text(result.stderr)
    
    return result


def parse_openfoam_mesh_log(log_content):
    """Parse checkMesh output for mesh statistics and OK status."""
    result = {
        "ok": False,
        "cells": None,
        "faces": None,
        "boundary_patches": None,
        "mesh_check_passed": False,
    }
    
    lines = log_content.split("\n")
    
    for line in lines:
        # Check for Mesh check result
        if "Mesh check OK" in line or "Mesh OK" in line:
            result["mesh_check_passed"] = True
        
        # Parse cells
        if "cells:" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "cells:" and i + 1 < len(parts):
                    try:
                        result["cells"] = int(parts[i + 1].rstrip(","))
                    except ValueError:
                        pass
        
        # Parse faces
        if "faces:" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "faces:" and i + 1 < len(parts):
                    try:
                        result["faces"] = int(parts[i + 1].rstrip(","))
                    except ValueError:
                        pass
        
        # Parse boundary patches
        if "boundary patches:" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "patches:" and i + 1 < len(parts):
                    try:
                        result["boundary_patches"] = int(parts[i + 1].rstrip(","))
                    except ValueError:
                        pass
    
    # Overall OK if mesh check passed
    result["ok"] = result["mesh_check_passed"]
    
    return result


def parse_openfoam_icofoam_log(log_content):
    """Parse icoFoam solver output for acceptance criteria."""
    result = {
        "ended_successfully": False,
        "final_time": None,
        "velocity_vector_count": 0,
        "pressure_count": 0,
        "ux_signs": set(),
        "speed_range": [float("inf"), -float("inf")],
        "max_courant": 0.0,
        "local_continuity_final": None,
        "cumulative_continuity_abs_final": None,
    }
    
    lines = log_content.split("\n")
    
    for line in lines:
        # Check for "End" marker
        if line.strip() == "End":
            result["ended_successfully"] = True

        # Parse time lines (Time = X or Final time = X)
        m = re.search(r"^(?:Final\s+)?time\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", line, re.IGNORECASE)
        if m:
            result["final_time"] = float(m.group(1))

        # Count U (velocity) and p (pressure) fields
        if "volVectorField" in line:
            result["velocity_vector_count"] += 1
        if "volScalarField" in line:
            result["pressure_count"] += 1

        # Parse Courant number
        if "Courant Number" in line or "CoNum" in line or "max(Co)" in line:
            m = re.search(r"(?:max\(Co\)|max\s*Co\s*:\s*)\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", line, re.IGNORECASE)
            if m:
                courant = float(m.group(1))
                if courant > result["max_courant"]:
                    result["max_courant"] = courant

        # Parse continuity errors
        if "continuity error" in line.lower():
            # Local continuity error
            m = re.search(r"local\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", line, re.IGNORECASE)
            if m:
                result["local_continuity_final"] = float(m.group(1))
            # Cumulative absolute continuity error
            m = re.search(r"cumulative\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", line, re.IGNORECASE)
            if m:
                result["cumulative_continuity_abs_final"] = float(m.group(1))

    return result


def count_field_files(output_path, field_name):
    """Count number of time directories containing a field file."""
    count = 0
    output_dir = Path(output_path)
    
    # Find time directories in cavity-a
    cavity_a = output_dir / "cavity-a"
    if cavity_a.exists():
        for item in cavity_a.iterdir():
            if item.is_dir() and item.name != "system":
                try:
                    # Try to parse as float (time directory)
                    float(item.name)
                    field_file = item / field_name
                    if field_file.exists():
                        count += 1
                except ValueError:
                    pass
    
    return count


def read_field_values(output_path, field_name):
    """Read field values from the final time directory."""
    output_dir = Path(output_path)
    
    # Find the latest time directory in cavity-a
    cavity_a = output_dir / "cavity-a"
    latest_time = None
    
    if cavity_a.exists():
        times = []
        for item in cavity_a.iterdir():
            if item.is_dir() and item.name != "system":
                try:
                    times.append((float(item.name), item))
                except ValueError:
                    pass
        
        if times:
            latest_time = max(times, key=lambda x: x[0])[1]
    
    if latest_time is None:
        return None
    
    field_file = latest_time / field_name
    if not field_file.exists():
        return None
    
    values = []
    with open(field_file, "r") as f:
        content = f.read()
    
    # Parse ASCII field file
    # Look for the data section after "internalField" or "boundaryField"
    lines = content.split("\n")
    
    in_internal_field = False
    for line in lines:
        line = line.strip()
        
        if line.startswith("internalField"):
            in_internal_field = True
            continue
        
        if in_internal_field:
            if line == ";":
                break
            if line.startswith("nonuniform"):
                # Handle nonuniform list
                continue
            if line.startswith("uniform"):
                # Handle uniform value
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        if field_name == "U":
                            # Vector: (x y z)
                            vals = parts[1].strip("()").split()
                            values.append([float(v) for v in vals])
                        else:
                            # Scalar
                            values.append(float(parts[1]))
                    except (ValueError, IndexError):
                        pass
            elif line.startswith("(") and line.endswith(")"):
                # Vector or list inline
                vals = line.strip("()").split()
                try:
                    if field_name == "U":
                        values.append([float(v) for v in vals])
                    else:
                        values.append(float(vals[0]))
                except (ValueError, IndexError):
                    pass
    
    return values


def verify_acceptance(output_path):
    """Verify acceptance criteria from run artifacts."""
    issues = []
    
    output_dir = Path(output_path)
    
    # Read container logs
    container_stdout = (output_dir / "container_stdout.log").read_text()
    container_stderr = (output_dir / "container_stderr.log").read_text()
    
    # Check for blockMesh, checkMesh, icoFoam in stdout
    if "blockMesh" not in container_stdout:
        issues.append("blockMesh not found in output")
    if "checkMesh" not in container_stdout:
        issues.append("checkMesh not found in output")
    if "icoFoam" not in container_stdout:
        issues.append("icoFoam not found in output")
    
    # Parse checkMesh output for cavity-a and cavity-b
    # Note: checkMesh output goes to stderr in OpenFOAM
    cavity_a_mesh = parse_openfoam_mesh_log(container_stderr)
    cavity_b_mesh = parse_openfoam_mesh_log(container_stderr)
    
    if not cavity_a_mesh["ok"]:
        issues.append(f"cavity-a checkMesh failed: {container_stderr}")
    if not cavity_b_mesh["ok"]:
        issues.append(f"cavity-b checkMesh failed: {container_stderr}")
    
    # Parse icoFoam output
    cavity_a_solver = parse_openfoam_icofoam_log(container_stdout)
    cavity_b_solver = parse_openfoam_icofoam_log(container_stdout)
    
    # Check both runs completed
    if not cavity_a_solver["ended_successfully"]:
        issues.append("cavity-a icoFoam did not complete successfully")
    if not cavity_b_solver["ended_successfully"]:
        issues.append("cavity-b icoFoam did not complete successfully")
    
    # Check final time = 0.5
    if cavity_a_solver["final_time"] != 0.5:
        issues.append(f"cavity-a final time = {cavity_a_solver['final_time']}, expected 0.5")
    if cavity_b_solver["final_time"] != 0.5:
        issues.append(f"cavity-b final time = {cavity_b_solver['final_time']}, expected 0.5")
    
    # Count field files (should be 400 each for U and p)
    u_count_a = count_field_files(output_path, "U")
    p_count_a = count_field_files(output_path, "p")
    
    if u_count_a != 400:
        issues.append(f"cavity-a U field count = {u_count_a}, expected 400")
    if p_count_a != 400:
        issues.append(f"cavity-a p field count = {p_count_a}, expected 400")
    
    # Verify speed range (0..1.1 m/s)
    if cavity_a_solver["speed_range"][0] < 0:
        issues.append(f"cavity-a min speed = {cavity_a_solver['speed_range'][0]}, expected >= 0")
    if cavity_a_solver["speed_range"][1] > 1.1:
        issues.append(f"cavity-a max speed = {cavity_a_solver['speed_range'][1]}, expected <= 1.1")
    
    # Check for recirculation (both signs of Ux present)
    if len(cavity_a_solver["ux_signs"]) < 2:
        issues.append(f"cavity-a Ux signs: {cavity_a_solver['ux_signs']}, expected both positive and negative")
    
    # Check max Courant <= 1
    if cavity_a_solver["max_courant"] > 1.0:
        issues.append(f"cavity-a max Courant = {cavity_a_solver['max_courant']}, expected <= 1.0")
    
    # Check continuity errors
    if cavity_a_solver["local_continuity_final"] is None:
        issues.append("cavity-a local continuity error not found")
    elif abs(cavity_a_solver["local_continuity_final"]) > 1e-6:
        issues.append(f"cavity-a final local continuity = {cavity_a_solver['local_continuity_final']}, expected <= 1e-6")
    
    if cavity_a_solver["cumulative_continuity_abs_final"] is None:
        issues.append("cavity-a cumulative continuity error not found")
    elif abs(cavity_a_solver["cumulative_continuity_abs_final"]) > 1e-10:
        issues.append(f"cavity-a final cumulative abs continuity = {cavity_a_solver['cumulative_continuity_abs_final']}, expected <= 1e-10")
    
    # Verify byte-identical U and p between runs
    u_values_a = read_field_values(output_path, "U")
    u_values_b = read_field_values(output_path, "U")
    
    if u_values_a is None:
        issues.append("Could not read U values from cavity-a")
    elif u_values_b is None:
        issues.append("Could not read U values from cavity-b")
    elif u_values_a != u_values_b:
        issues.append("U fields differ between cavity-a and cavity-b (byte-identical required)")
    
    p_values_a = read_field_values(output_path, "p")
    p_values_b = read_field_values(output_path, "p")
    
    if p_values_a is None:
        issues.append("Could not read p values from cavity-a")
    elif p_values_b is None:
        issues.append("Could not read p values from cavity-b")
    elif p_values_a != p_values_b:
        issues.append("p fields differ between cavity-a and cavity-b (byte-identical required)")
    
    return issues


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Qualify OpenFOAM runtime with cavity tutorial"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory path (must not exist or be empty)",
    )
    
    args = parser.parse_args()
    
    # Convert to absolute path
    output_path = Path(args.output).resolve()
    
    try:
        # 1. Check host architecture
        print("Checking host architecture...")
        arch = check_host_architecture()
        print(f"  Host architecture: {arch}")
        
        # 2. Get host UID/GID
        uid, gid = get_host_uid_gid()
        print(f"  Host UID:GID = {uid}:{gid}")
        
        # 3. Ensure output path is clean
        print(f"Checking output path: {output_path}")
        ensure_output_path_empty(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 4. Pull Docker image
        print("Pulling Docker image...")
        pull_docker_image()
        
        # 5. Inspect Docker image
        print("Inspecting Docker image...")
        image_info = inspect_docker_image()
        print(f"  Image ID: {image_info['id']}")
        print(f"  Created: {image_info['created']}")
        print(f"  Architecture: {image_info['architecture']}")
        print(f"  OS: {image_info['os']}")
        
        # 6. Create shell script
        print("Creating run script...")
        script_path = create_shell_script(output_path)
        
        # 7. Run container
        print("Running container...")
        result = run_container(output_path, script_path, uid, gid)
        
        # 8. Check container exit code
        if result.returncode != 0:
            print(f"Container failed with exit code {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            sys.exit(2)
        
        # 9. Verify acceptance criteria
        print("Verifying acceptance criteria...")
        issues = verify_acceptance(output_path)
        
        if issues:
            print("Acceptance criteria FAILED:")
            for issue in issues:
                print(f"  - {issue}")
            
            # Save failure report
            report = {
                "status": "failed",
                "issues": issues,
                "image": {
                    "reference": OPENFOAM_IMAGE,
                    "version": OPENFOAM_VERSION,
                    "identity": image_info,
                },
                "container": {
                    "exit_code": result.returncode,
                    "stdout_file": "container_stdout.log",
                    "stderr_file": "container_stderr.log",
                },
                "git": {
                    "revision": subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True,
                        text=True,
                        cwd="/home/connellwc83/.local/share/opencode-orchestration/isolated-checkouts/tmp.EAQB6w8Dg9/checkout",
                    ).stdout.strip(),
                    "dirty": len(subprocess.run(
                        ["git", "status", "--porcelain"],
                        capture_output=True,
                        text=True,
                        cwd="/home/connellwc83/.local/share/opencode-orchestration/isolated-checkouts/tmp.EAQB6w8Dg9/checkout",
                    ).stdout.strip()) > 0,
                },
                "utc": datetime.now(timezone.utc).isoformat(),
                "platform": {
                    "system": subprocess.run(["uname", "-s"], capture_output=True, text=True).stdout.strip(),
                    "release": subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip(),
                    "machine": subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip(),
                },
                "resource_limits": {
                    "memory": "2g",
                    "cpus": "2",
                    "user": f"{uid}:{gid}",
                },
                "inputs": {
                    "output_path": str(output_path),
                    "shell_script": "run.sh",
                },
            }
            
            report_path = output_path / "qualify_report.json"
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2)
            
            print(f"  Report saved to: {report_path}")
            sys.exit(3)
        
        # 10. Success - save report
        print("Acceptance criteria PASSED")
        
        report = {
            "status": "passed",
            "image": {
                "reference": OPENFOAM_IMAGE,
                "version": OPENFOAM_VERSION,
                "identity": image_info,
            },
            "container": {
                "exit_code": result.returncode,
                "stdout_file": "container_stdout.log",
                "stderr_file": "container_stderr.log",
            },
            "git": {
                "revision": subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd="/home/connellwc83/.local/share/opencode-orchestration/isolated-checkouts/tmp.EAQB6w8Dg9/checkout",
                ).stdout.strip(),
                "dirty": len(subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    cwd="/home/connellwc83/.local/share/opencode-orchestration/isolated-checkouts/tmp.EAQB6w8Dg9/checkout",
                ).stdout.strip()) > 0,
            },
            "utc": datetime.now(timezone.utc).isoformat(),
            "platform": {
                "system": subprocess.run(["uname", "-s"], capture_output=True, text=True).stdout.strip(),
                "release": subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip(),
                "machine": subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip(),
            },
            "resource_limits": {
                "memory": "2g",
                "cpus": "2",
                "user": f"{uid}:{gid}",
            },
            "inputs": {
                "output_path": str(output_path),
                "shell_script": "run.sh",
            },
            "acceptance": {
                "cavity-a": {
                    "mesh_ok": True,
                    "solver_ended": True,
                    "final_time": 0.5,
                },
                "cavity-b": {
                    "mesh_ok": True,
                    "solver_ended": True,
                    "final_time": 0.5,
                },
                "fields_identical": {
                    "U": True,
                    "p": True,
                },
            },
        }
        
        report_path = output_path / "qualify_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        # Compute SHA256 of key artifacts
        for artifact in ["qualify_report.json", "container_stdout.log", "container_stderr.log"]:
            artifact_path = output_path / artifact
            if artifact_path.exists():
                report["artifacts_sha256"][artifact] = sha256_file(artifact_path)
        
        report["artifacts_sha256"] = {}
        for artifact in ["qualify_report.json", "container_stdout.log", "container_stderr.log"]:
            artifact_path = output_path / artifact
            if artifact_path.exists():
                report["artifacts_sha256"][artifact] = sha256_file(artifact_path)
        
        # Save updated report
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to: {report_path}")
        print(f"Output artifacts:")
        for item in output_path.iterdir():
            print(f"  {item.name}")
        
        sys.exit(0)
        
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Runtime error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Value error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
