"""CI-only fresh-process doctor timings; actual native self-tests must pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/ai-tdd"
NODE_FLAGS = ["--preserve-symlinks", "--preserve-symlinks-main"]


def checked_json(command, environment):
    result = subprocess.run(command, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30,
                            check=False)
    if result.returncode:
        raise ValueError("Actual runtime command failed: " + result.stderr.strip())
    try:
        return json.loads(result.stdout)
    except ValueError as error:
        raise ValueError("Actual runtime command did not return valid JSON") from error


def doctor_samples(command, environment):
    samples = []
    for _ in range(3):
        started = time.perf_counter()
        value = checked_json(command, environment)
        elapsed = time.perf_counter() - started
        if not isinstance(value, dict) or value.get("hook_health") != "pass":
            raise ValueError("Actual doctor hook self-test did not pass")
        samples.append(elapsed)
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packaged-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.packaged_executable.resolve()
    if not binary.is_file() or args.packaged_executable.is_symlink():
        raise ValueError("An actual native runtime executable is required")
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Timing output must be fresh; choose a new output path")
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js must be installed on the CI host")
    platform_probe = subprocess.run([node, "-p", "process.platform+'-'+process.arch"], capture_output=True, text=True,
                                    timeout=10, check=True).stdout.strip()
    if platform_probe not in {"win32-x64", "linux-x64", "darwin-arm64"}:
        raise ValueError("Unsupported timing platform")
    version = json.loads((PLUGIN / "runtime-manifest.json").read_text(encoding="utf-8"))["version"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", version):
        raise ValueError("Invalid pinned runtime version")
    suffix = ".exe" if platform_probe.startswith("win32-") else ""
    asset = "ai-tdd-controller-" + version + "-" + platform_probe + suffix
    if binary.name != asset:
        raise ValueError("Native executable must match the pinned platform asset")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    manifest = {"version": version, "platforms": {platform_probe: {
        "url": "https://github.com/KubsGU/ai-tdd-kit/releases/download/v" + version + "/" + asset,
        "sha256": digest, "size": binary.stat().st_size,
    }}}
    reports = {}
    with tempfile.TemporaryDirectory(prefix="ai-tdd-runtime-measure-") as temporary:
        sandbox = Path(temporary).resolve()
        node_folder = sandbox / "node-only"
        node_folder.mkdir()
        isolated_node = node_folder / ("node.exe" if os.name == "nt" else "node")
        shutil.copy2(node, isolated_node)
        for backend in ("python", "bundled"):
            plugin = sandbox / backend
            shutil.copytree(PLUGIN / "scripts", plugin / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            (plugin / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            environment = dict(os.environ)
            if backend == "bundled":
                cached = plugin / ".runtime" / version / platform_probe / asset
                cached.parent.mkdir(parents=True)
                shutil.copy2(binary, cached)
                environment["PATH"] = str(node_folder)
                environment.pop("AI_TDD_PYTHON", None)
                if shutil.which("python", path=environment["PATH"]) or shutil.which("python3", path=environment["PATH"]):
                    raise ValueError("Bundled timing must exclude system Python from PATH")
            else:
                environment["AI_TDD_PYTHON"] = sys.executable
            command = [str(isolated_node), *NODE_FLAGS, str(plugin / "scripts/tdd-launcher.cjs")]
            identity = checked_json(command + ["--runtime-info"], environment)
            if identity.get("backend") != backend or (backend == "bundled" and identity.get("binary_sha256") != digest):
                raise ValueError("Timing runtime identity does not match the requested backend")
            samples = doctor_samples(command + ["doctor"], environment)
            reports[backend] = {"runtime_info": identity, "doctor_seconds": samples,
                                "median_seconds": statistics.median(samples)}
    result = {"schema": 1, "ok": True, "platform": platform_probe, "sample_count_per_backend": 3,
              "method": "Each fresh controller process runs doctor and its actual nested hook self-test; filesystem caches are uncontrolled",
              "bundled_python_on_path": False, "results": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
