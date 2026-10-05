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
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET


class DotnetError(RuntimeError):
    pass


PROPERTIES = ("TargetFramework", "TargetFrameworks", "IsTestProject", "EnableMSTestRunner",
              "UseMicrosoftTestingPlatformRunner", "TestingPlatformDotnetTestSupport", "IsTestingPlatformApplication",
              "BaseOutputPath", "BaseIntermediateOutputPath", "MSBuildProjectExtensionsPath", "OutputPath",
              "IntermediateOutputPath", "RunSettingsFilePath", "VSTestSetting", "VSTestTestCaseFilter", "VSTestCliRunSettings", "NuGetPackageRoot", "ProjectAssetsFile")
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
    for flag in ("VSTestTestCaseFilter", "VSTestCliRunSettings"):
        if props.get(flag, "").strip():
            raise DotnetError("Implicit " + flag + " is unsupported; full unfiltered VSTest discovery/execution is required")
    packages = _packages(metadata)
    if any(name.startswith("microsoft.testing.platform") or name in {"mstest", "mstest.runner"} for name in packages):
        raise DotnetError("MTP packages are unsupported by the native xUnit/VSTest evidence path")
    _output_paths(project, metadata)
    return packages


RUNSETTINGS_FIELDS = {
    "RunConfiguration": set("MaxCpuCount ResultsDirectory TargetPlatform TargetFrameworkVersion TestSessionTimeout "
                            "DisableAppDomain DisableParallelization TestAdaptersPaths TreatTestAdapterErrorsAsWarnings "
                            "CollectSourceInformation EnvironmentVariables ExecutionThreadApartmentState BatchSize "
                            "CaptureStandardOutput CaptureDebugOutput DisableSharedTestHost TestCaseFilter".split()),
    "xUnit": set("AppDomain Culture DiagnosticMessages InternalDiagnosticMessages MaxParallelThreads MethodDisplay "
                 "MethodDisplayOptions NoAutoReporters ParallelAlgorithm ParallelizeAssembly ParallelizeTestCollections "
                 "PreEnumerateTheories PrintMaxEnumerableLength PrintMaxObjectDepth PrintMaxObjectMemberCount "
                 "PrintMaxStringLength ReporterSwitch Seed ShadowCopy ShowLiveOutput StopOnFail Explicit".split()),
    "NUnit": set("NumberOfTestWorkers DefaultTimeout Verbosity InternalTraceLevel WorkDirectory TestOutputXml "
                 "DumpXmlTestDiscovery DisplayName UseVsKeepEngineRunning ShadowCopyFiles UseDefaultAssemblyLoadContext "
                 "RandomSeed CollectSourceInformation PreFilter ShowInternalProperties ConsoleOut DiscoveryMethod "
                 "ThrowOnEachFailure SkipNonTestAssemblies ExplicitMode StopOnError Where".split()),
}


def _runsettings(root, project, metadata):
    """Preserve the effective existing file, while reviewing test-selection controls."""
    props = metadata["Properties"]
    value = props.get("VSTestSetting", "").strip() or props.get("RunSettingsFilePath", "").strip()
    if not value:
        return None
    path = Path(os.path.abspath(project.parent / msbuild_path(value)))
    try:
        relative = _relative(root, path)
        if any(part in {".ai-tdd", ".git"} or part.startswith(".env") for part in path.relative_to(root).parts):
            raise DotnetError("Private/control files cannot be runsettings inputs")
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise DotnetError("Expected a regular existing runsettings file of at most 1 MB")
        content = path.read_bytes()
        # Also cover UTF-16 XML. ElementTree must never expand a supplied DTD.
        declarations = content.lower().replace(b"\x00", b"")
        if b"<!doctype" in declarations or b"<!entity" in declarations:
            raise DotnetError("DTD/entity declarations are unsupported in runsettings")
        xml = ET.fromstring(content)
        if xml.tag != "RunSettings" or xml.attrib:
            raise DotnetError("Expected an unqualified RunSettings XML root")
        if any(not isinstance(node.tag, str) or "}" in node.tag for node in xml.iter()):
            raise DotnetError("Namespaced runsettings controls require explicit compatibility support")
        sections = set()
        for section in xml:
            if section.tag in sections:
                raise DotnetError("Duplicate runsettings section " + section.tag)
            sections.add(section.tag)
            if section.tag in {"DataCollectionRunSettings", "InProcDataCollectionRunSettings", "TestRunParameters", "LoggerRunSettings"}:
                # Collector Include/Exclude filters describe coverage, not test selection.
                continue
            if section.tag not in RUNSETTINGS_FIELDS:
                raise DotnetError("Unsupported runsettings section " + section.tag + "; requires a compatibility rule")
            fields = set()
            for node in section:
                location = section.tag + "/" + node.tag
                text = (node.text or "").strip().lower()
                if node.tag not in RUNSETTINGS_FIELDS[section.tag] or node.tag in fields or node.attrib:
                    raise DotnetError("Unsupported or ambiguous runsettings control " + location)
                fields.add(node.tag)
                if len(node) and location != "RunConfiguration/EnvironmentVariables":
                    raise DotnetError("Unsupported nested runsettings control " + location)
                if ((location in {"RunConfiguration/TestCaseFilter", "NUnit/Where"} and text)
                        or (location in {"xUnit/StopOnFail", "NUnit/StopOnError"} and text != "false")
                        or (location == "xUnit/PreEnumerateTheories" and text not in {"true", "false"})
                        or (location == "xUnit/Explicit" and text not in {"off", "on"})
                        or (location == "NUnit/ExplicitMode" and text not in {"strict", "relaxed"})):
                    raise DotnetError("Runsettings " + location + " can suppress cases or stop early; full native evidence is required")
        return {"path": relative, "sha256": hashlib.sha256(content).hexdigest()}
    except (OSError, ET.ParseError, DotnetError) as error:
        raise DotnetError("Existing runsettings for " + _relative(root, project) + " (" + value + "): " + str(error)) from error


def _restored_target(assets, tfm):
    """Select one evaluated framework, including NuGet v3's normalized alias."""
    targets = assets["targets"]
    if tfm in targets:
        return targets[tfm]
    frameworks = assets["project"].get("frameworks", {})
    aliases = [name for name, value in frameworks.items() if value.get("targetAlias") == tfm]
    if len(aliases) != 1:
        raise DotnetError("Restored package inputs need the evaluated target framework")
    return targets[aliases[0]]


def _exact_package_version(value):
    """Normalize an exact NuGet version without treating ranges as exact."""
    if not isinstance(value, str):
        return None
    matched = re.fullmatch(r"(\d+(?:\.\d+){0,3})(-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?"
                          r"(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", value)
    if not matched:
        return None
    components = [str(int(part)) for part in matched[1].split(".")]
    components.extend("0" for _ in range(3 - len(components)))
    if len(components) == 4 and components[-1] == "0":
        components.pop()
    return ".".join(components) + (matched[2] or "").lower()


def _restored_inputs(project, metadata, packages, package_root):
    """Read this project's restore result and its reachable package graph."""
    assets_path = Path(os.path.abspath(project.parent / msbuild_path(metadata["Properties"]["ProjectAssetsFile"])))
    if assets_path.resolve() != assets_path or project.parent / "obj" not in assets_path.parents:
        raise DotnetError("Restored inputs must use this project's own obj/ assets file")
    if not assets_path.is_file() or assets_path.stat().st_size > 20_000_000:
        raise DotnetError("Restored package inputs need an existing bounded assets file")
    assets = json.loads(assets_path.read_text(encoding="utf-8-sig"))
    if assets["version"] not in {3, 4}:
        raise DotnetError("Unsupported restored package metadata")
    restore = assets["project"]["restore"]
    if Path(msbuild_path(restore["projectPath"])).resolve() != project:
        raise DotnetError("Restored package inputs belong to another project")
    if Path(msbuild_path(restore["packagesPath"])).resolve() != package_root:
        raise DotnetError("Restored package inputs use another primary cache")
    folders = [Path(msbuild_path(name)).resolve() for name in assets["packageFolders"]]
    if package_root not in folders:
        raise DotnetError("Restored package cache is not recorded by this project")
    target = _restored_target(assets, metadata["Properties"]["TargetFramework"])
    by_name = {}
    for identity, selected in target.items():
        name, version = identity.split("/")
        if not name or not version or name.lower() in by_name or selected["type"] not in {"package", "project"}:
            raise DotnetError("Unsupported restored dependency graph")
        by_name[name.lower()] = identity
    pending = []
    for name, version in packages.items():
        identity = by_name.get(name.lower())
        exact = _exact_package_version(version)
        if identity is None or exact is None:
            continue
        if _exact_package_version(identity.split("/")[1]) != exact:
            raise DotnetError("Restore existing packages after an evaluated dependency version changes")
        pending.append(identity)
    # Transitive build assets can also flow through explicit ProjectReference
    # dependencies. Bind those graph roots to the evaluated project paths.
    references = {Path(os.path.abspath(project.parent / msbuild_path(item.get("FullPath") or item["Identity"])))
                  for item in metadata.get("Items", {}).get("ProjectReference", [])}
    for identity, selected in target.items():
        if selected["type"] == "project":
            library = assets["libraries"][identity]
            referenced = Path(os.path.abspath(project.parent / msbuild_path(library["msbuildProject"])))
            if referenced in references:
                pending.append(identity)
    reachable = set()
    while pending:
        identity = pending.pop()
        if identity in reachable:
            continue
        reachable.add(identity)
        dependencies = target[identity].get("dependencies", {})
        if not isinstance(dependencies, dict):
            raise DotnetError("Unsupported restored dependencies")
        pending.extend(by_name[name.lower()] for name in dependencies if name.lower() in by_name)
    return assets_path, target, assets["libraries"], folders, reachable


def _package_input(metadata, packages, path, item, *, project=None):
    """Allow exact package files owned by this project's restored dependencies.

    Package build imports and NuGet-generated contentFiles props are separate
    provenance paths. Neither permits arbitrary files under an external cache.
    """
    try:
        if project is None:
            return False
        package_root = Path(msbuild_path(metadata["Properties"]["NuGetPackageRoot"])).resolve()
        defining = Path(os.path.abspath(msbuild_path(item["DefiningProjectFullPath"])))
        path = Path(os.path.abspath(path))
        if path.resolve() != path or defining.resolve() != defining or not path.is_file() or not defining.is_file():
            return False
        assets_path, target, libraries, folders, reachable = _restored_inputs(project, metadata, packages, package_root)
        generated_props = assets_path.parent / (project.name + ".nuget.g.props")
        for identity in reachable:
            selected = target[identity]
            if selected["type"] != "package":
                continue
            library = libraries.get(identity, {})
            if (library.get("type") != "package" or library.get("path") != identity.lower()
                    or not isinstance(library.get("files"), list)):
                continue
            files = {msbuild_path(name) for name in library["files"]}
            for folder in folders:
                package = folder / library["path"]
                if package not in path.parents:
                    continue
                asset_name = path.relative_to(package).as_posix()
                if asset_name not in files:
                    continue
                if package in defining.parents:
                    import_name = defining.relative_to(package).as_posix()
                    build = {**selected.get("build", {}), **selected.get("buildTransitive", {})}
                    if (defining.suffix.lower() in {".props", ".targets"} and import_name in files
                            and import_name in build):
                        return True
                if defining == generated_props:
                    content = selected.get("contentFiles", {}).get(asset_name, {})
                    name, version = identity.split("/")
                    kind = item.get("NuGetItemType")
                    if (kind in {"None", "Content"} and content.get("buildAction") == kind
                            and item.get("NuGetPackageId", "").lower() == name.lower()
                            and item.get("NuGetPackageVersion") == version):
                        return True
        return False
    except (DotnetError, KeyError, TypeError, ValueError, OSError, AttributeError):
        return False


def _external_absent_names(parts):
    """Absent editor links cannot refer to private, executable or runner inputs."""
    private = {".git", ".ai-tdd", ".ssh", ".aws", ".azure", ".gnupg", ".claude", ".codex"}
    controls = {name.lower() for name in PRESET_INPUTS} | {
        "config.json", "launchsettings.json", "appsettings.json", "packages.config",
        "pyproject.toml", "pytest.ini", "package.json", "package-lock.json", "pnpm-lock.yaml",
        "yarn.lock", "dockerfile", "makefile", "agents.md", "claude.md", "msbuild.rsp"}
    executable = {".cs", ".csproj", ".fs", ".fsproj", ".vb", ".vbproj", ".props", ".targets",
                  ".sln", ".slnx", ".runsettings", ".config", ".dll", ".exe", ".py", ".js",
                  ".cjs", ".mjs", ".sh", ".ps1", ".cmd", ".bat"}
    for part in parts:
        name = part.lower()
        if (name in private or name.startswith((".env", "directory.", "appsettings."))
                or name in controls or Path(name).suffix in executable
                or re.fullmatch(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", name)
                or part.endswith((".", " ")) or any(char in part for char in ':*?"<>|')):
            raise DotnetError("Private, build, runner or device paths cannot be absent external inputs")


def external_absent_snapshot(root, paths):
    """Freeze genuine absence without reading or granting ownership of external files.

    lstat each ancestor: exists()/resolve() alone can mistake a dangling link,
    inaccessible path or newly introduced junction for an absent regular file.
    """
    if not isinstance(paths, list):
        raise DotnetError("external_absent_inputs must be a list of canonical absolute paths")
    root = Path(root).resolve()
    seen, snapshot, size = set(), {}, 0
    for value in paths:
        if (not isinstance(value, str) or not value or len(value) > 4096
                or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
            raise DotnetError("Malformed or oversized absent external input path")
        size += len(value.encode("utf-8")) + 4
        if size > 5_000_000:
            raise DotnetError("Absent external input paths exceed the bounded configuration size")
        path = Path(value)
        if (not path.is_absolute() or value != str(path) or value != os.path.abspath(value)
                or path.anchor.startswith("\\\\") or path == root or root in path.parents
                or path in seen):
            raise DotnetError("Absent external inputs must be unique canonical local paths outside the root")
        _external_absent_names(path.parts[1:])
        seen.add(path)
        try:
            for cursor in [*reversed(path.parents), path]:
                try:
                    info = cursor.lstat()
                except FileNotFoundError:
                    continue
                if (stat.S_ISLNK(info.st_mode)
                        or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                    raise DotnetError("Absent external inputs cannot use symlinks or junctions")
                if cursor == path:
                    raise DotnetError("An absent external input now exists; repeat setup after reviewing ownership")
                if not stat.S_ISDIR(info.st_mode):
                    raise DotnetError("An absent external input has a non-directory ancestor")
        except OSError as error:
            raise DotnetError("Cannot establish external input absence: " + type(error).__name__) from error
        snapshot[value] = "absent"
    return dict(sorted(snapshot.items()))


def _external_absent_input(root, project, path, item):
    """Only an own-project, non-copying, consistent editor link can be absent."""
    try:
        full_path = Path(msbuild_path(item["FullPath"]))
        identity = Path(msbuild_path(item["Identity"]))
        link = Path(msbuild_path(item["Link"]))
        defining = Path(msbuild_path(item["DefiningProjectFullPath"]))
        if (not full_path.is_absolute() or full_path != Path(os.path.abspath(path))
                or identity.drive or identity.is_absolute() or full_path != Path(os.path.abspath(project.parent / identity))
                or link.drive or link.is_absolute() or ".." in link.parts or not link.parts
                or defining != project or not stat.S_ISREG(defining.lstat().st_mode)):
            return None
        _relative(root, defining)
        _external_absent_names(link.parts)
        for name in ("CopyToOutputDirectory", "CopyToPublishDirectory"):
            value = item.get(name, "")
            if not isinstance(value, str) or value.strip().lower() not in {"", "never"}:
                return None
        external_absent_snapshot(root, [str(full_path)])
        return full_path
    except (DotnetError, KeyError, TypeError, ValueError, OSError):
        return None


def configure(root):
    """Return controller configuration without writing or replacing any files."""
    root = Path(root).resolve()
    environment()
    files = list(_walk(root))
    projects = [path for path in files if path.suffix.lower() == ".csproj"]
    if not projects:
        raise DotnetError("No C# .csproj projects found below the selected root")
    global_path = root / "global.json"
    if global_path.is_file():
        try:
            settings = json.loads(global_path.read_text(encoding="utf-8-sig"))
        except ValueError as error:
            raise DotnetError("Repair malformed global.json before .NET setup") from error
        if settings.get("test", {}).get("runner", "VSTest").lower() != "vstest":
            raise DotnetError("global.json selects an unsupported test runner; native evidence requires VSTest")
    source_roots, test_roots, modules, linked_sources = [], [], [], []
    protected, external_absent = set(), set()
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
                module = {"project": relative, "tfm": tfm, "framework": framework, "adapter_version": adapter}
                settings = _runsettings(root, project, evaluated)
                if settings:
                    module["runsettings"] = settings
                    protected.add(settings["path"])
                modules.append(module)
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
                        absent = _external_absent_input(root, project, input_path, item) if kind in {"None", "Content"} else None
                        if absent is not None:
                            external_absent.add(absent)
                            continue
                        raise DotnetError("Unsafe evaluated " + kind + " input in " + relative + ": " + name
                                          + "; defining import: " + item.get("DefiningProjectFullPath", "<missing>")
                                          + ". Expected an in-root file or an exact restored NuGet asset/import. "
                                          "Use the repository root containing shared inputs, or restore existing packages and repeat init; "
                                          "do not edit the .csproj to bypass ownership.") from error
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
    config = {"schema": 1, "source_roots": sorted(source_roots), "test_roots": sorted(test_roots),
            "protected_paths": sorted(protected), "generated_roots": sorted(set(generated)), "timeout_seconds": min(3600, max(600, len(modules) * 60)),
            "max_attempts": 3, "runner": {"format": "json", "argv": [node, "--preserve-symlinks", "--preserve-symlinks-main", "{plugin}/scripts/tdd-launcher.cjs", "--dotnet-test", "--root", "{root}", "--report", "{report}"]},
            "dotnet": {"schema": 1, "sdk": sdk_identity(root), "modules": modules, "projects": [_relative(root, project) for project in projects]},
            "quality_checks": []}
    if any(module["framework"] == "xunit-vstest" for module in modules):
        config["dotnet"]["theory_mode"] = "runtime-parent-rows-v1"
    if external_absent:
        paths = sorted(str(path) for path in external_absent)
        external_absent_snapshot(root, paths)
        config["dotnet"]["external_absent_inputs"] = paths
    return config


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
