"""Verify an anonymous released-runtime bootstrap with Python absent from child PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


PLUGIN = Path(__file__).resolve().parents[1] / "plugins/ai-tdd"
NODE_FLAGS = ["--preserve-symlinks", "--preserve-symlinks-main"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Bootstrap output must be fresh")
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js is required")
    platform = subprocess.check_output([node, "-p", "process.platform+'-'+process.arch"], text=True).strip()
    manifest = json.loads((PLUGIN / "runtime-manifest.json").read_text(encoding="utf-8"))
    asset = manifest["platforms"][platform]
    with tempfile.TemporaryDirectory(prefix="ai-tdd-public-runtime-") as temporary:
        root = Path(temporary).resolve()
        plugin = root / "plugin"
        shutil.copytree(PLUGIN, plugin, ignore=shutil.ignore_patterns("__pycache__", ".runtime"))
        node_folder = root / "node-only"
        node_folder.mkdir()
        isolated_node = node_folder / ("node.exe" if os.name == "nt" else "node")
        shutil.copy2(node, isolated_node)
        environment = dict(os.environ)
        environment["PATH"] = str(node_folder)
        for key in ("AI_TDD_PYTHON", "PYTHONPATH", "PYTHONHOME"):
            environment.pop(key, None)
        if any(shutil.which(name, path=environment["PATH"]) for name in ("python", "python3", "py")):
            raise ValueError("Bootstrap child PATH must exclude Python")
        command = [str(isolated_node), *NODE_FLAGS, str(plugin / "scripts/tdd-launcher.cjs")]

        def call(arguments, timeout):
            process = subprocess.run(command + arguments, cwd=root, env=environment, capture_output=True,
                                     text=True, encoding="utf-8", timeout=timeout, check=False)
            if process.returncode:
                raise ValueError("Released-runtime bootstrap failed: " + process.stderr.strip())
            return json.loads(process.stdout)

        setup = call(["setup-runtime", "--root", str(root)], 150)
        identity = call(["--runtime-info"], 30)
        if setup.get("backend") != "bundled" or identity.get("backend") != "bundled":
            raise ValueError("Bootstrap did not select the downloaded runtime")
        if setup.get("binary_sha256") != asset["sha256"] or identity.get("binary_sha256") != asset["sha256"]:
            raise ValueError("Downloaded runtime identity differs from the pinned release")
        binaries = list((plugin / ".runtime").rglob(Path(asset["url"]).name))
        if len(binaries) != 1 or binaries[0].stat().st_size != asset["size"]:
            raise ValueError("Downloaded runtime inventory differs from the pinned release")
        if hashlib.sha256(binaries[0].read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError("Downloaded runtime bytes differ from the pinned release")
        if call(["--root", str(root), "doctor"], 30).get("hook_health") != "pass":
            raise ValueError("Downloaded runtime doctor and nested hook did not pass")
    result = {"schema": 1, "ok": True, "version": manifest["version"], "platform": platform,
              "url": asset["url"], "sha256": asset["sha256"], "size": asset["size"],
              "anonymous_download": True, "python_on_child_path": False, "hook_health": "pass"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
