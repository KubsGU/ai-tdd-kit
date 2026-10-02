"""Build a native one-file controller interpreter; development dependency only."""
import argparse
import ast
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import sysconfig


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/ai-tdd/scripts"
PYINSTALLER_VERSION = "6.22.3"
SOURCES = ("runtime_entry.py", "tdd.py", "quality.py", "dotnet_runner.py", "dotnet_setup.py", "unittest_runner.py")


def platform_key():
    # Use the build interpreter's ABI; Windows environment hints may be absent.
    abi = sysconfig.get_platform().lower()
    architecture = next((value for suffix, value in (("amd64", "x64"), ("x86_64", "x64"),
                                                     ("arm64", "arm64"), ("aarch64", "arm64"))
                         if abi.endswith("-" + suffix)), None)
    if architecture is None and "universal2" in abi:
        architecture = {"x86_64": "x64", "arm64": "arm64"}.get(platform.machine())
    value = sys.platform + "-" + str(architecture)
    if value not in {"win32-x64", "linux-x64", "darwin-arm64"}:
        raise ValueError("Unsupported runtime build platform: " + value)
    return value


def hidden_imports():
    """Collect external sources' stdlib imports without freezing their code."""
    result = set()
    for name in SOURCES:
        source = SCRIPTS / name
        if not source.is_file():
            raise ValueError("Freeze all controller sources before building; missing " + name)
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"), filename=name)):
            imports = [item.name for item in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and not node.level else [])
            for imported in imports:
                if imported.split(".")[0] not in sys.stdlib_module_names:
                    raise ValueError("Bundled controller imports a third-party dependency: " + imported)
                result.add(imported)
    return sorted(result)


def license_text(explicit_python_license=None):
    # Prefer the installed distribution's full notices (not a downloaded source
    # LICENSE). CPython's libinstall target ships LICENSE.txt in the stdlib;
    # actions/setup-python retains it on Linux and in the macOS framework lib.
    candidates = [Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE",
                  Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"]
    python_license = explicit_python_license or next((candidate for candidate in candidates if candidate.is_file()), None)
    if python_license is None:
        raise ValueError("CPython distribution license was not found; provide it in the build interpreter's prefix")
    distribution = metadata.distribution("PyInstaller")
    pyinstaller_license = next((distribution.locate_file(item) for item in distribution.files
                               if str(item).endswith("licenses/COPYING.txt") or str(item).endswith("COPYING.txt")), None)
    if pyinstaller_license is None or not Path(pyinstaller_license).is_file():
        raise ValueError("PyInstaller license and bootloader exception were not found")
    return ("AI TDD bundled controller runtime notices\n\n"
            "CPython " + platform.python_version() + " distribution license and bundled component notices\n"
            "=" * 72 + "\n" + python_license.read_text(encoding="utf-8") + "\n\n"
            "PyInstaller " + PYINSTALLER_VERSION + " license and bootloader exception\n"
            "=" * 72 + "\n" + Path(pyinstaller_license).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.5.0")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/runtime")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "dist/runtime-work")
    parser.add_argument("--python-license", type=Path, help="CPython distribution license when the build prefix omits it")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", args.version):
        raise ValueError("Invalid runtime release version")
    installed = metadata.version("PyInstaller")
    if installed != PYINSTALLER_VERSION:
        raise ValueError("Build requires development-only PyInstaller==" + PYINSTALLER_VERSION)
    key = platform_key()
    name = "ai-tdd-controller-" + args.version + "-" + key
    output, work = args.output_dir.resolve(), args.work_dir.resolve()
    imports = hidden_imports()
    notices = license_text(args.python_license)
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    embedded_notices = work / "ai-tdd-runtime-LICENSES.txt"
    embedded_notices.write_text(notices, encoding="utf-8", newline="\n")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console", "--noupx",
               "--name", name, "--distpath", str(output), "--workpath", str(work / "build"),
               "--specpath", str(work), "--add-data", str(embedded_notices) + ":."]
    for module in imports:
        command.extend(["--hidden-import", module])
    command.append(str(SCRIPTS / "runtime_entry.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    executable = output / (name + (".exe" if sys.platform == "win32" else ""))
    license_path = output / (name + ".LICENSES.txt")
    license_path.write_bytes(embedded_notices.read_bytes())
    result = {
        "schema": 1, "version": args.version, "platform": key, "asset": executable.name,
        "size": executable.stat().st_size, "sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "python": platform.python_version(), "pyinstaller": installed,
        "build_dependencies": {item: metadata.version(item) for item in ("PyInstaller", "pyinstaller-hooks-contrib", "altgraph", "packaging")},
        "hidden_stdlib_imports": imports,
        "source_sha256": {"plugins/ai-tdd/scripts/" + name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest() for name in SOURCES},
        "build_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "licenses": {"asset": license_path.name, "size": license_path.stat().st_size,
                     "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(), "embedded_name": embedded_notices.name},
    }
    metadata_path = output / (name + ".json")
    metadata_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, metadata.PackageNotFoundError) as error:
        print("Runtime build: " + str(error), file=sys.stderr)
        raise SystemExit(1) from error
