"""Verify downloaded skills and exercise the relocated production Node controller."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile


def verified_extract(archive_path, destination):
    """Validate before writing any file, including checksums and exact inventory."""
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        seen, roots, data = set(), set(), {}
        for entry in entries:
            name = entry.filename
            parts = name.split("/")
            if ("\\" in name or ":" in name or any(part in ("", ".", "..") for part in parts)
                    or len(parts) < 2 or name.casefold() in seen or PurePosixPath(name).is_absolute()
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("Unsafe or duplicate archive entry")
            roots.add(parts[0])
            seen.add(name.casefold())
            data[name] = archive.read(entry)
        if len(roots) != 1:
            raise ValueError("Expected one top-level skill directory")
        name = roots.pop()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
            raise ValueError("Invalid skill name")
        prefix = name + "/"
        if not all(prefix + required in data for required in ("SKILL.md", "README.md", "LICENSE", "CHECKSUMS.json")):
            raise ValueError("Missing standalone skill contents")
        checksums = json.loads(data.pop(prefix + "CHECKSUMS.json"))
        if {prefix + relative for relative in checksums} != set(data):
            raise ValueError("Archive inventory differs from checksum manifest")
        for relative, expected in checksums.items():
            if hashlib.sha256(data[prefix + relative]).hexdigest() != expected:
                raise ValueError("Checksum mismatch")
        root = destination / name
        if root.exists():
            raise ValueError("Refusing to overwrite an existing installation")
        # This checker writes only to a caller-selected fresh test destination.
        data[prefix + "CHECKSUMS.json"] = archive.read(prefix + "CHECKSUMS.json")
        for relative, value in data.items():
            target = destination / relative
            if destination not in target.resolve().parents:
                raise ValueError("Extraction escaped test destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
    return root


def check_workflow(plugin, root):
    """Real subprocess receipts, no AI calls or claimed host hook installation."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js required for relocated workflow check")
    root = Path(root).resolve()
    for folder in ("src", "tests", ".ai-tdd"):
        (root / folder).mkdir(parents=True)
    folder = root / ".ai-tdd"
    config = json.loads((plugin / "templates/config.unittest.json").read_text(encoding="utf-8"))
    # A real check of every source file's syntax, rather than a successful no-op.
    config["quality_checks"] = [{"name": "syntax", "kind": "typecheck", "argv": ["{python}", "-B", "syntax_check.py"], "timeout_seconds": 20}]
    (root / "syntax_check.py").write_text("import ast\nfrom pathlib import Path\nfor path in Path('src').rglob('*.py'):\n    ast.parse(path.read_text(), filename=str(path))\n", encoding="utf-8")
    config["protected_paths"].append("syntax_check.py")
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (folder / "spec.json").write_text(json.dumps({"version": 1, "goal": "Free fee at 10000 cents",
        "acceptance": [{"id": "AC1", "description": "Fee is zero at 10000 cents"}], "open_questions": []}), encoding="utf-8")
    (folder / "review-plan.json").write_text(json.dumps({"scenarios": [{"ac": "AC1", "case": "Literal inclusive boundary"}]}), encoding="utf-8")
    source, baseline = root / "src/fee.py", root / "tests/test_fee.py"
    source.write_text("def fee(cents): return 799\n", encoding="utf-8")
    baseline.write_text("import unittest\nfrom src.fee import fee\nclass FeeTests(unittest.TestCase):\n    def test_regular(self): self.assertEqual(fee(100), 799)\n", encoding="utf-8")
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    env["AI_TDD_PYTHON"] = sys.executable

    def call(*args, reject=None):
        process = subprocess.run([node, "--preserve-symlinks", "--preserve-symlinks-main", str(plugin / "scripts/tdd-launcher.cjs"),
                                  "--root", str(root), *args], cwd=root, env=env, capture_output=True,
                                 encoding="utf-8", errors="replace", timeout=60)
        if reject:
            if process.returncode == 0 or reject.lower() not in process.stderr.lower():
                raise RuntimeError("Expected rejection missing: " + process.stderr[:500])
            return None
        if process.returncode:
            raise RuntimeError("Relocated CLI failed: " + process.stderr[:1000])
        return json.loads(process.stdout)

    call("begin")
    test_id = "test_threshold.Threshold.test_boundary"
    (root / "tests/test_threshold.py").write_text("import unittest\nfrom src.fee import fee\nclass Threshold(unittest.TestCase):\n    def test_boundary(self): self.assertEqual(fee(10000), 0)\n", encoding="utf-8")
    source.write_text("def fee(cents): return 123\n", encoding="utf-8")
    call("red", "--tests", test_id, "--ac", "AC1", "--because", "AC1 literal zero", reject="source")
    source.write_text("def fee(cents): return 799\n", encoding="utf-8")
    call("red", "--tests", test_id, "--ac", "AC1", "--because", "AC1 literal zero")
    old = baseline.read_bytes()
    baseline.write_text("# removed baseline assertions\n", encoding="utf-8")
    call("green", reject="protected")
    baseline.write_bytes(old)
    source.write_text("def fee(cents): return 0 if cents >= 10000 else 799\n", encoding="utf-8")
    green = call("green")
    call("verify")
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    review = {"receipt_id": state["green_receipt"]["id"], "quality_receipt_id": state["quality_receipt"]["id"],
        "checked_ac": ["AC1"], "findings": [], "limitations": ["Synthetic deterministic role simulation; no host agent execution"],
        "recommendation": "accept", "repo_conventions": "Existing integer-cent API and unittest conventions preserved",
        "quality_limitations": ["Syntax check only; no lint, security or formatting tools in this synthetic fixture"],
        "test_assessment": [{"test_id": test_id, "detects": "Exclusive boundary or missing fee waiver", "oracle": "AC1 literal zero at 10000 cents",
                             "why_needed": "Distinct boundary complements the regular-fee baseline"}]}
    (folder / "review.json").write_text(json.dumps(review), encoding="utf-8")
    call("finish")
    result = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    return {"phase": result["phase"], "executed_tests": len(result["completion_receipt"]["results"]),
            "quality": "pass" if result["quality_receipt"]["status"] == "passed" else "fail",
            "red_exception": "AssertionError", "green": green["phase"], "source_before_red": "rejected", "frozen_test_tamper": "rejected"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--claude-install", action="store_true", help="Validate/register the native bundle in temporary Claude settings")
    parser.add_argument("--native-dotnet", action="store_true", help="Run real xUnit/NUnit workflows from the extracted skill; requires existing SDK and NuGet")
    parser.add_argument("--packaged-executable", type=Path, help="Use a supplied native interpreter for .NET child processes with Python absent from PATH")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix="ai-tdd-skills-check-") as temporary:
        temp = Path(temporary)
        for archive in args.archives:
            installed = verified_extract(archive, temp / "downloaded")
            item = {"skill": installed.name, "checksums": "pass"}
            if installed.name == "ai-tdd":
                item["workflow"] = check_workflow(installed, temp / "project with spaces")
                if args.native_dotnet:
                    evidence = temp / "dotnet-evidence.json"
                    command = [sys.executable, "-B", str(Path(__file__).with_name("dotnet_demo.py")),
                               "--plugin-root", str(installed), "--controller-facade", "--output", str(evidence)]
                    if args.packaged_executable:
                        command.extend(["--packaged-executable", str(args.packaged_executable.resolve())])
                    process = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=900)
                    if process.returncode:
                        raise RuntimeError("Extracted native workflow failed: " + process.stderr[-2000:])
                    item["dotnet"] = json.loads(evidence.read_text(encoding="utf-8"))
                if args.claude_install:
                    from check_install import call
                    cli = shutil.which("claude")
                    if not cli:
                        raise RuntimeError("Claude Code CLI not available")
                    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(temp / "isolated-claude-settings"))
                    env.pop("CLAUDECODE", None)
                    call([cli, "plugin", "validate", "--strict", str(installed)], installed, env)
                    call([cli, "plugin", "marketplace", "add", str(installed)], installed, env)
                    call([cli, "plugin", "install", "ai-tdd@ai-tdd-local-skills", "--scope", "user"], installed, env)
                    listing = call([cli, "plugin", "list"], installed, env)
                    if "ai-tdd@ai-tdd-local-skills" not in listing:
                        raise RuntimeError("Native plugin missing from isolated inventory")
                    item["claude_install"] = "pass"
                    item["user_settings_changed"] = False
            results.append(item)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
