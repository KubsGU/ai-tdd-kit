"""Verify extracted ZIP and install into isolated Claude settings, never user's."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def call(argv, root, env):
    result = subprocess.run(argv, cwd=root, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=90)
    if result.returncode:
        raise RuntimeError("Installation check failed: " + " ".join(argv[:3]) + ": " + result.stderr[:1000])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    args = parser.parse_args()
    cli, node = shutil.which("claude"), shutil.which("node")
    if not cli or not node:
        raise SystemExit("Claude Code and Node.js on PATH are required")
    with tempfile.TemporaryDirectory(prefix="ai-tdd-install-") as folder:
        temp = Path(folder)
        with zipfile.ZipFile(args.archive) as archive:
            for name in archive.namelist():
                if not name.startswith("ai-tdd-kit/") or Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
                    raise RuntimeError("Unsafe archive member")
            archive.extractall(temp)
        root = temp / "ai-tdd-kit"
        checksums = json.loads((root / "CHECKSUMS.json").read_text(encoding="utf-8"))
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "CHECKSUMS.json"}
        if actual != set(checksums):
            raise RuntimeError("Archive inventory differs from checksum manifest")
        for name, expected in checksums.items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("Checksum mismatch")
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(temp / "isolated-claude-settings")
        env.pop("CLAUDECODE", None)
        call([cli, "plugin", "validate", "--strict", str(root)], root, env)
        call([cli, "plugin", "validate", "--strict", str(root / "plugins/ai-tdd")], root, env)
        call([cli, "plugin", "marketplace", "add", str(root)], root, env)
        call([cli, "plugin", "install", "ai-tdd@ai-tdd-kit", "--scope", "user"], root, env)
        listing = call([cli, "plugin", "list"], root, env)
        if "ai-tdd@ai-tdd-kit" not in listing:
            raise RuntimeError("Installed plugin absent from isolated inventory")
        payload = {"cwd": str(temp), "hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "sample.txt"}}
        hook = subprocess.run([node, "--preserve-symlinks-main", str(root / "plugins/ai-tdd/scripts/hook-launcher.cjs")], input=json.dumps(payload), capture_output=True, encoding="utf-8", env=env, timeout=20)
        if hook.returncode or hook.stdout.strip():
            raise RuntimeError("Inactive-project hook failed")
        print(json.dumps({"checksums": "pass", "marketplace_validation": "pass", "plugin_validation": "pass", "isolated_install": "pass", "inactive_hook": "pass", "files": len(checksums), "user_settings_changed": False}))


if __name__ == "__main__":
    main()
