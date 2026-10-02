"""Evaluate existing C# projects and configure the bounded xUnit/VSTest path.

Uses the installed .NET SDK; never changes projects, packages, or configuration.
MSBuild evaluation is executable project code, not a hostile-project sandbox.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


class DotnetError(RuntimeError):
    pass


PROPERTIES = ("TargetFramework", "TargetFrameworks", "IsTestProject", "EnableMSTestRunner",
              "UseMicrosoftTestingPlatformRunner", "TestingPlatformDotnetTestSupport", "IsTestingPlatformApplication",
              "BaseOutputPath", "BaseIntermediateOutputPath", "MSBuildProjectExtensionsPath", "OutputPath",
              "IntermediateOutputPath", "RunSettingsFilePath", "VSTestTestCaseFilter", "VSTestCliRunSettings", "NuGetPackageRoot", "ProjectAssetsFile")
ITEMS = ("PackageReference", "PackageVersion", "Compile", "ProjectReference", "None", "Content")
SKIP_DIRS = {".git", ".ai-tdd", "node_modules", ".venv"}
PRESET_INPUTS = ("global.json", ".editorconfig", "Directory.Build.props", "Directory.Build.targets",
                 "Directory.Packages.props", "NuGet.config", "NuGet.Config", "nuget.config",
                 "packages.lock.json", "xunit.runner.json")


def environment():
    env = dict(os.environ)
    env.update(DOTNET_CLI_UI_LANGUAGE="en-US", VSLANG="1033", DOTNET_NOLOGO="1",
               DOTNET_CLI_TELEMETRY_OPTOUT="1")
    for name in ("VSTEST_TESTCASEFILTER", "VSTEST_RUN_SETTINGS", "VSTEST_RUNSETTINGS"):
        if env.get(name):
            raise DotnetError("Remove " + name + ": filtered or implicit runsettings runs are unsupported")
    return env


def evaluate(project, tfm=None, *, root=None):
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise DotnetError("Install or select a supported .NET SDK on PATH, then repeat init")
    argv = [dotnet, "msbuild", str(project), "-nologo", "-getProperty:" + ",".join(PROPERTIES),
            "-getItem:" + ",".join(ITEMS)]
    if tfm:
        argv.append("-p:TargetFramework=" + tfm)
    try:
        process = subprocess.run(argv, cwd=root or project.parent, env=environment(), capture_output=True,
                                 encoding="utf-8", errors="replace", timeout=120, shell=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DotnetError(".NET MSBuild evaluation unavailable: " + type(error).__name__) from error
    if process.returncode:
        raise DotnetError("MSBuild evaluation failed for " + project.name + "; repair the existing SDK/project before init")
    try:
        value = json.loads(process.stdout)
    except ValueError as error:
        raise DotnetError("MSBuild must support JSON -getProperty/-getItem (MSBuild 17.8 or newer)") from error
    if not isinstance(value, dict) or not isinstance(value.get("Properties"), dict) or not isinstance(value.get("Items"), dict):
        raise DotnetError("MSBuild returned unsupported evaluated metadata")
    return value


def sdk_identity(root):
    executable = shutil.which("dotnet")
    if not executable:
        raise DotnetError("Select an existing .NET 8+ SDK on PATH before native setup")
    path = Path(executable).resolve()
    try:
        process = subprocess.run([str(path), "--version"], cwd=root, env=environment(), capture_output=True,
                                 encoding="utf-8", timeout=30, shell=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DotnetError("Cannot identify selected .NET SDK: " + type(error).__name__) from error
    version = process.stdout.strip()
    if process.returncode or not re.fullmatch(r"\d+\.\d+\.\d+", version) or int(version.split(".")[0]) < 8:
        raise DotnetError("Native .NET evidence requires a selected stable SDK 8+ (MSBuild 17.8+)")
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()
    return {"executable": str(path), "sha256": sha, "version": version}


def _relative(root, path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path or (path != root and root not in path.parents):
        raise DotnetError("Project inputs must remain inside the root without symlinks/junctions")
    return path.relative_to(root).as_posix()


def msbuild_path(value):
    """MSBuild accepts both separators on every supported host."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise DotnetError("MSBuild must return a nonempty evaluated file path")
    return value.replace("\\", "/")


def _walk(root):
    for current, directories, files in os.walk(root, followlinks=False):
        exclusions = SKIP_DIRS | ({"bin", "obj"} if any(Path(name).suffix.lower() == ".csproj" for name in files) else set())
        directories[:] = sorted(name for name in directories if name not in exclusions)
        for name in directories:
            _relative(root, Path(current) / name)
        for name in sorted(files):
            path = Path(current) / name
            _relative(root, path)
            yield path


def _packages(metadata):
    items = metadata["Items"]
    central = {item["Identity"].lower(): item.get("Version", "") for item in items.get("PackageVersion", [])}
    return {item["Identity"].lower(): item.get("VersionOverride") or item.get("Version") or central.get(item["Identity"].lower(), "")
            for item in items.get("PackageReference", [])}


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", value):
        raise DotnetError("The xUnit adapter needs a resolved stable exact package version; ranges/prereleases are unsupported")
    return tuple(int(part) for part in value.split("."))


def _output_paths(project, metadata):
    props = metadata["Properties"]
    for name in ("BaseOutputPath", "OutputPath", "BaseIntermediateOutputPath", "IntermediateOutputPath", "MSBuildProjectExtensionsPath"):
        value = props.get(name, "")
        if not value:
            continue
        path = (project.parent / msbuild_path(value)).resolve()
        base = project.parent / ("obj" if name in {"BaseIntermediateOutputPath", "IntermediateOutputPath", "MSBuildProjectExtensionsPath"} else "bin")
        if path != base and base not in path.parents:
            raise DotnetError("Custom " + name + " is unsupported: use the project's own bin/ and obj/ output directories")


def _profile(project, metadata):
    props = metadata["Properties"]
    for flag in ("EnableMSTestRunner", "UseMicrosoftTestingPlatformRunner", "TestingPlatformDotnetTestSupport", "IsTestingPlatformApplication"):
        value = props.get(flag, "").strip().lower()
        if value not in {"", "false"}:
            raise DotnetError("Microsoft.Testing.Platform or unknown " + flag + " is unsupported; this path requires VSTest")
    for flag in ("RunSettingsFilePath", "VSTestTestCaseFilter", "VSTestCliRunSettings"):
        if props.get(flag, "").strip():
            raise DotnetError("Implicit " + flag + " is unsupported; full unfiltered VSTest discovery/execution is required")
    packages = _packages(metadata)
    if any(name.startswith("microsoft.testing.platform") or name in {"mstest", "mstest.runner"} for name in packages):
        raise DotnetError("MTP packages are unsupported by the native xUnit/VSTest evidence path")
    _output_paths(project, metadata)
    return packages


def _testhost_input(project, metadata, packages, package_root, path, defining):
    """Bind Windows test-host content to the SDK's exact restored dependency."""
    try:
        sdk = packages["microsoft.net.test.sdk"]
        _version(sdk)
        assets_path = Path(os.path.abspath(project.parent / msbuild_path(metadata["Properties"]["ProjectAssetsFile"])))
        if assets_path.resolve() != assets_path or project.parent / "obj" not in assets_path.parents:
            return False
        if not assets_path.is_file() or assets_path.stat().st_size > 20_000_000:
            return False
        assets = json.loads(assets_path.read_text(encoding="utf-8-sig"))
        if assets["version"] not in {3, 4}:
            return False
        restore = assets["project"]["restore"]
        if Path(msbuild_path(restore["projectPath"])).resolve() != project:
            return False
        if Path(msbuild_path(restore["packagesPath"])).resolve() != package_root:
            return False
        if package_root not in [Path(msbuild_path(name)).resolve() for name in assets["packageFolders"]]:
            return False
        target = assets["targets"][metadata["Properties"]["TargetFramework"]]
        sdk_entry = target["Microsoft.NET.Test.Sdk/" + sdk]
        if sdk_entry["type"] != "package":
            return False
        version = sdk_entry["dependencies"]["Microsoft.TestPlatform.TestHost"]
        _version(version)
        identity = "Microsoft.TestPlatform.TestHost/" + version
        selected = target[identity]
        library = assets["libraries"][identity]
        if selected["type"] != "package" or library["type"] != "package" or library["path"] != identity.lower():
            return False
        package = package_root / identity.lower()
        if package not in path.parents or package not in defining.parents:
            return False
        asset_name = path.relative_to(package).as_posix()
        import_name = defining.relative_to(package).as_posix()
        if not isinstance(library["files"], list) or asset_name not in library["files"] or import_name not in library["files"]:
            return False
        build = {**selected.get("build", {}), **selected.get("buildTransitive", {})}
        return defining.suffix.lower() in {".props", ".targets"} and import_name in build
    except (DotnetError, KeyError, TypeError, ValueError, OSError):
        return False


def _package_input(metadata, packages, path, item, *, project=None):
    """Allow adapter runtime assets added by the resolved package's own props.

    These are ordinary external tool dependencies, never copied to config or
    treated as repository-owned input files. User-authored external links fail.
    """
    package_root = metadata["Properties"].get("NuGetPackageRoot", "")
    defining = item.get("DefiningProjectFullPath", "")
    if not package_root or not defining:
        return False
    defining = Path(os.path.abspath(msbuild_path(defining)))
    path = Path(os.path.abspath(path))
    if path.resolve() != path or defining.resolve() != defining:
        return False
    package_root = Path(msbuild_path(package_root)).resolve()
    for name, version in packages.items():
        package = package_root / name / version
        if package in path.parents and package in defining.parents:
            return True
    return project is not None and _testhost_input(project, metadata, packages, package_root, path, defining)


def configure(root):
    """Return controller configuration without writing or replacing any files."""
    root = Path(root).resolve()
    environment()
    files = list(_walk(root))
    projects = [path for path in files if path.suffix.lower() == ".csproj"]
    if not projects:
        raise DotnetError("No C# .csproj projects found below the selected root")
    if len(projects) > 50:
        raise DotnetError("Native .NET setup supports at most 50 explicit projects")
    global_path = root / "global.json"
    if global_path.is_file():
        try:
            settings = json.loads(global_path.read_text(encoding="utf-8-sig"))
        except ValueError as error:
            raise DotnetError("Repair malformed global.json before .NET setup") from error
        if settings.get("test", {}).get("runner", "VSTest").lower() != "vstest":
            raise DotnetError("global.json selects an unsupported test runner; native evidence requires VSTest")
    source_roots, test_roots, modules, linked_sources = [], [], [], []
    protected = set()
    generated = []
    for project in projects:
        relative = _relative(root, project)
        directory = _relative(root, project.parent)
        if directory == ".":
            raise DotnetError("Place source and test projects in disjoint subdirectories; root-level .csproj ownership is unsupported")
        metadata = evaluate(project, root=root)
        packages = _profile(project, metadata)
        test_flag = metadata["Properties"].get("IsTestProject", "").lower()
        is_test = test_flag == "true" or any(name in packages for name in ("xunit", "xunit.v3", "xunit.v3.core", "nunit", "mstest.testframework", "microsoft.net.test.sdk"))
        if test_flag not in {"", "true", "false"}:
            raise DotnetError("Unknown evaluated IsTestProject for " + relative)
        (test_roots if is_test else source_roots).append(directory)
        protected.add(relative)
        generated.extend([directory + "/bin", directory + "/obj"])
        frameworks = metadata["Properties"].get("TargetFrameworks", "") or metadata["Properties"].get("TargetFramework", "")
        tfms = frameworks.split(";")
        if not tfms or any(not re.fullmatch(r"net\d+(?:\.\d+)?(?:-[A-Za-z0-9.]+)?", tfm) for tfm in tfms) or len(set(tfms)) != len(tfms):
            raise DotnetError("Projects need explicit, unique supported TargetFramework/TargetFrameworks values")
        for tfm in tfms:
            evaluated = evaluate(project, tfm, root=root) if len(tfms) > 1 else metadata
            tfm_packages = _profile(project, evaluated)
            if is_test:
                adapter = tfm_packages.get("xunit.runner.visualstudio", "")
                xunit = any(name in tfm_packages for name in ("xunit", "xunit.v3", "xunit.v3.core"))
                nunit = "nunit" in tfm_packages
                if xunit == nunit or "microsoft.net.test.sdk" not in tfm_packages:
                    raise DotnetError("Unsupported/mixed framework in " + relative + ": native support requires existing xUnit or NUnit with Microsoft.NET.Test.Sdk; MSTest is unsupported because TRX loses assertion types")
                if xunit:
                    if not adapter or _version(adapter) < (3, 0, 0):
                        raise DotnetError("xunit.runner.visualstudio >=3.0.0 is required for typed native evidence; upgrade is a separate user decision")
                    framework = "xunit-vstest"
                else:
                    adapter = tfm_packages.get("nunit3testadapter", "")
                    if not adapter or _version(adapter) < (4, 5, 0) or _version(tfm_packages["nunit"]) < (3, 14, 0):
                        raise DotnetError("Native NUnit evidence requires existing NUnit >=3.14.0 and NUnit3TestAdapter >=4.5.0; upgrade is a separate user decision")
                    framework = "nunit-vstest"
                modules.append({"project": relative, "tfm": tfm, "framework": framework, "adapter_version": adapter})
            for kind in ("Compile", "ProjectReference", "None", "Content"):
                for item in evaluated["Items"].get(kind, []):
                    name = item.get("FullPath") or item.get("Identity", "")
                    if not name:
                        raise DotnetError("MSBuild input lacks a file path")
                    input_path = (project.parent / msbuild_path(name)).absolute()
                    try:
                        _relative(root, input_path)
                    except DotnetError as error:
                        if kind in {"None", "Content"} and _package_input(evaluated, tfm_packages, input_path, item, project=project):
                            continue
                        raise DotnetError("Unsafe evaluated " + kind + " input in " + relative
                                          + "; require in-root ownership or the resolved package's own imported assets") from error
                    input_path = Path(os.path.abspath(input_path))
                    if any(part in {".ai-tdd", ".git"} or part.startswith(".env") for part in input_path.relative_to(root).parts):
                        raise DotnetError("Private/control paths cannot be evaluated project inputs")
                    if kind == "Compile" and project.parent not in input_path.parents:
                        linked_sources.append((is_test, input_path))
                    if kind in {"None", "Content"} and input_path.is_file() and input_path.suffix.lower() != ".cs":
                        protected.add(_relative(root, input_path))
    if not source_roots or not test_roots:
        raise DotnetError("Native setup requires separate source and test C# projects")
    roots = sorted(set(source_roots + test_roots))
    if len(roots) != len(projects) or any(Path(a) in Path(b).parents for a in roots for b in roots if a != b):
        raise DotnetError("Each C# project needs its own disjoint directory; shared/nested project ownership is unsupported")
    for is_test, path in linked_sources:
        if not is_test or not any(root / owned in path.parents for owned in source_roots):
            raise DotnetError("Linked C# Compile inputs must belong to another explicit source project inside the root")
    for project in projects:
        directory = project.parent
        while True:
            # Bind missing inputs as well as existing ones: adding inherited
            # configuration during a task must change the protected fingerprint.
            protected.update(_relative(root, directory / name) for name in PRESET_INPUTS)
            if directory == root:
                break
            directory = directory.parent
    for path in files:
        name = path.name.lower()
        if (path.suffix.lower() in {".csproj", ".sln", ".slnx", ".runsettings", ".props", ".targets"}
                or name in {"global.json", "nuget.config", ".editorconfig", "packages.lock.json", "xunit.runner.json"}
                or name.startswith("directory.")
                or any(part.lower() in {"fixtures", "testdata", "snapshots", "__snapshots__"} for part in path.parts)):
            protected.add(_relative(root, path))
    node = shutil.which("node") or "node"
    return {"schema": 1, "source_roots": sorted(source_roots), "test_roots": sorted(test_roots),
            "protected_paths": sorted(protected), "generated_roots": sorted(set(generated)), "timeout_seconds": 600,
            "max_attempts": 3, "runner": {"format": "json", "argv": [node, "--preserve-symlinks", "--preserve-symlinks-main", "{plugin}/scripts/tdd-launcher.cjs", "--dotnet-test", "--root", "{root}", "--report", "{report}"]},
            "dotnet": {"schema": 1, "sdk": sdk_identity(root), "modules": modules, "projects": [_relative(root, project) for project in projects]},
            "quality_checks": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(configure(Path(args.root)), ensure_ascii=False, indent=2))
        return 0
    except DotnetError as error:
        print("Native .NET setup: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
