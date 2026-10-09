"""Real isolated .NET workflow/evidence demonstrations; no AI calls.

Requires an existing .NET 8+ SDK and public NuGet connectivity. Every fixture,
CLI home and package cache is temporary; existing SDKs/projects are untouched.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile


KIT = Path(__file__).resolve().parents[1]
PLUGIN = KIT / "plugins/ai-tdd"
CONTENT_CONSUMER = "AiTdd.Synthetic.Content.Consumer"
CONTENT_LEAF = "AiTdd.Synthetic.Content.Leaf"
CONTENT_VERSION = "1.0.0"
CONTENT_PAYLOAD = '{"synthetic": "restored-transitive-content"}\n'
BUILD_PAYLOAD = "restored-transitive-build-content\n"


def load(name, filename):
    loader = importlib.util.spec_from_file_location(name, PLUGIN / "scripts" / filename)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


SETUP = load("demo_dotnet_setup", "dotnet_setup.py")
RUNNER = load("demo_dotnet_runner", "dotnet_runner.py")
TDD = load("demo_dotnet_controller", "tdd.py")


@contextmanager
def isolated_environment(root):
    names = {"DOTNET_CLI_HOME": str(root / "cli-home"), "NUGET_PACKAGES": str(root / "nuget-packages"),
             "NUGET_HTTP_CACHE_PATH": str(root / "nuget-http"), "NUGET_PLUGINS_CACHE_PATH": str(root / "nuget-plugins"),
             "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_CLI_UI_LANGUAGE": "en-US", "DOTNET_NOLOGO": "1",
             "AI_TDD_PYTHON": sys.executable, "PYTHONDONTWRITEBYTECODE": "1"}
    previous = {name: os.environ.get(name) for name in names}
    os.environ.update(names)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def fixture_directory():
    """Retain only synthetic local fixture diagnostics when a check fails."""
    root = Path(tempfile.mkdtemp(prefix="ai-tdd-dotnet-demo-")).resolve()
    try:
        yield root
    except BaseException as error:
        print("Synthetic .NET fixture and local failure logs retained at " + str(root), file=sys.stderr)
        artifact_directory = os.environ.get("AI_TDD_DEMO_FAILURE_ARTIFACTS")
        if artifact_directory:
            try:
                collect_failure_artifacts(root, Path(artifact_directory), error)
            except Exception as capture_error:
                print("Could not collect synthetic failure artifacts: " + type(capture_error).__name__, file=sys.stderr)
        raise
    else:
        # Validate the exact created target before recursive fixture cleanup.
        if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith("ai-tdd-dotnet-demo-"):
            raise RuntimeError("Refusing cleanup outside the explicitly created fixture directory")
        shutil.rmtree(root)


def collect_failure_artifacts(root, destination, error):
    """Copy bounded diagnostics from this public demo's synthetic fixture only.

    CI explicitly opts into this helper. It never scans checkout directories,
    environment variables, binaries, package caches or user repositories. Log
    tails preserve underlying subprocess errors when no JSON receipt exists.
    """
    root = Path(root).absolute()
    if (root.parent != Path(tempfile.gettempdir()).resolve()
            or not root.name.startswith("ai-tdd-dotnet-demo-") or root.resolve() != root):
        raise RuntimeError("Artifact capture requires the explicitly created synthetic fixture directory")
    destination = Path(destination).resolve() / root.name
    if destination == root or root in destination.parents:
        raise RuntimeError("Failure artifacts must stay outside the source fixture")
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": 1, "scope": "generated-public-dotnet-fixture", "error_type": type(error).__name__,
                "files": [], "omitted_files": [], "limit_reached": False}
    candidates = []
    # These four folders are created by main; no other temporary tree is read.
    for name in ("xunit-evidence", "xunit-workflow", "nunit-evidence", "nunit-workflow"):
        folder = root / name / ".ai-tdd"
        if not folder.is_dir() or folder.resolve() != folder:
            continue
        for current, directories, filenames in os.walk(folder, followlinks=False):
            directories[:] = sorted(name for name in directories if (Path(current) / name).resolve() == Path(current) / name)
            for name in filenames:
                path = Path(current) / name
                if path.suffix.lower() not in {".log", ".json", ".trx", ".xml"}:
                    continue
                metadata = path.lstat()
                if (not stat.S_ISREG(metadata.st_mode) or path.resolve() != path
                        or getattr(metadata, "st_file_attributes", 0) & 0x400):
                    continue
                candidates.append((path, metadata.st_size))
    # Put subprocess stderr first so XML volume cannot hide the root failure.
    candidates.sort(key=lambda value: (0 if value[0].name.endswith("stderr.log") else
                                      1 if value[0].suffix.lower() == ".log" else 2,
                                      value[0].relative_to(root).as_posix()))
    remaining = 128 * 1024 * 1024
    for path, size in candidates:
        relative = path.relative_to(root).as_posix()
        if len(manifest["files"]) >= 256 or remaining <= 0:
            manifest["limit_reached"] = True
            break
        limit = min(1024 * 1024 if path.suffix.lower() == ".log" else 64 * 1024 * 1024, remaining)
        if size > limit and path.suffix.lower() != ".log":
            manifest["omitted_files"].append({"path": relative, "reason": "byte-limit", "original_bytes": size})
            continue
        with path.open("rb") as stream:
            if size > limit:
                stream.seek(-limit, os.SEEK_END)
            value = stream.read(limit + 1)
        if len(value) > limit:
            manifest["omitted_files"].append({"path": relative, "reason": "changed-during-capture"})
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        remaining -= len(value)
        manifest["files"].append({"path": relative, "original_bytes": size, "copied_bytes": len(value),
                                  "truncated": size > len(value)})
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Synthetic failure artifacts collected at " + str(destination), file=sys.stderr)
    return destination


def setup_diagnostics(root):
    """Capture bounded metadata from this generated public fixture only.

    No environment dump, source contents, account state or credentials are
    included. The executable project inputs and NuGet configuration here were
    authored above exclusively for the synthetic fixture.
    """
    root = Path(root).resolve()
    data = {"schema": 1, "scope": "generated-public-dotnet-fixture", "projects": [], "unsafe_inputs": []}
    fields = ("Identity", "FullPath", "DefiningProjectFullPath", "Link", "Version", "VersionOverride")
    for project in sorted(root.rglob("*.csproj"))[:10]:
        if any(part in {"bin", "obj"} for part in project.relative_to(root).parts):
            continue
        try:
            metadata = SETUP.evaluate(project, root=root)
            packages = SETUP._packages(metadata)
        except (SETUP.DotnetError, OSError, ValueError) as error:
            data["projects"].append({"project": project.relative_to(root).as_posix(), "evaluation_error": type(error).__name__})
            continue
        record = {"project": project.relative_to(root).as_posix(),
                  "properties": {key: str(metadata["Properties"].get(key, ""))[:1024] for key in SETUP.PROPERTIES}, "items": {}}
        for kind in SETUP.ITEMS:
            record["items"][kind] = [{key: str(item[key])[:1024] for key in fields if key in item}
                                      for item in metadata["Items"].get(kind, [])[:100]]
            if kind not in {"Compile", "ProjectReference", "None", "Content"}:
                continue
            for item in metadata["Items"].get(kind, [])[:100]:
                name = item.get("FullPath") or item.get("Identity", "")
                path = None
                try:
                    path = (project.parent / SETUP.msbuild_path(name)).absolute()
                    SETUP._relative(root, path)
                except (SETUP.DotnetError, OSError, ValueError):
                    allowed = path is not None and kind in {"None", "Content"} and (
                        SETUP._package_input(metadata, packages, path, item, project=project)
                        or SETUP._external_absent_input(root, project, path, item) is not None)
                    if not allowed and len(data["unsafe_inputs"]) < 20:
                        data["unsafe_inputs"].append({"project": record["project"], "kind": kind,
                            "item": {key: str(item[key])[:1024] for key in fields if key in item}, "package_allowed": False})
        data["projects"].append(record)
    path = root / ".ai-tdd/setup-diagnostics.json"
    value = json.dumps(data, ensure_ascii=False, indent=2)
    if len(value.encode("utf-8")) > 250_000:
        data = {"schema": 1, "scope": data["scope"], "unsafe_inputs": data["unsafe_inputs"], "truncated": True}
        value = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(value + "\n", encoding="utf-8")
    print("Synthetic setup diagnostics retained at " + str(path), file=sys.stderr)
    if data["unsafe_inputs"]:
        print(json.dumps({"synthetic_unsafe_inputs": data["unsafe_inputs"]}, ensure_ascii=False), file=sys.stderr)


def repository_inputs(root):
    """Hash authored project/configuration files, never user repository data."""
    names = ("src/Demo/Demo.csproj", "tests/Demo.Tests/Demo.Tests.csproj", "Directory.Build.props",
             "coverage.runsettings", "NuGet.config", "global.json")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names if (root / name).exists()}


def verify_external_absent_input(root, require_config=True):
    """Prove one project-authored absent link stays bound through native runs."""
    root = Path(root).resolve()
    expected = json.loads((root / ".ai-tdd/external-absent-input.json").read_text(encoding="utf-8"))["path"]
    path = Path(expected)
    if (str(Path(os.path.abspath(path))) != expected or path.resolve() != path
            or path == root or root in path.parents or path.name != ".dockerignore"):
        raise RuntimeError("Unsafe synthetic absent external input proof path")
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError("The project-authored linked external input must remain absent")
    if require_config:
        config_path = root / ".ai-tdd/config.json"
        if not config_path.is_file():
            raise RuntimeError("The absent external input proof requires evaluated native configuration")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("dotnet", {}).get("external_absent_inputs") != [expected]:
            raise RuntimeError("Native configuration must bind exactly the expected absent external input")
    return {"external_absent_input_count": 1, "project_authored_absent_content_bound": require_config,
            "external_absent_inputs_still_absent": True}


def verify_repository_inputs(root, require_config=True):
    before = json.loads((root / ".ai-tdd/repository-inputs.json").read_text(encoding="utf-8"))
    if repository_inputs(root) != before:
        raise RuntimeError("The kit changed an authored fixture project or existing repository configuration")
    return {"authored_inputs_unchanged": True, "authored_input_sha256": before,
            "inherited_runsettings": "coverage.runsettings",
            **verify_external_absent_input(root, require_config),
            **json.loads((root / ".ai-tdd/restored-content-proof.json").read_text(encoding="utf-8"))}


def restored_content_checks(root, project):
    metadata = SETUP.evaluate(project, tfm="net8.0", root=root)
    assets = json.loads(Path(metadata["Properties"]["ProjectAssetsFile"]).read_text(encoding="utf-8-sig"))
    package_root = Path(metadata["Properties"]["NuGetPackageRoot"]).resolve()
    targets = assets["targets"]["net8.0"]
    paths = {Path(item["FullPath"]).resolve(): item for item in metadata["Items"].get("Content", [])}
    content = "contentFiles/any/any/SyntheticData/payload.json"
    imported = "buildTransitive/" + CONTENT_LEAF + ".targets"
    direct = package_root / CONTENT_CONSUMER.lower() / CONTENT_VERSION / content
    transitive = package_root / CONTENT_LEAF.lower() / CONTENT_VERSION / "buildTransitive/build-payload.txt"
    generated = project.parent / "obj" / (project.name + ".nuget.g.props")
    if direct not in paths or Path(paths[direct]["DefiningProjectFullPath"]).resolve() != generated.resolve():
        raise RuntimeError("Fixture did not generate the standard NuGet contentFiles input")
    if targets[CONTENT_CONSUMER + "/" + CONTENT_VERSION].get("contentFiles", {}).get(content, {}).get("buildAction") != "Content":
        raise RuntimeError("Fixture standard Content was not selected by the restored target")
    if transitive not in paths or Path(paths[transitive]["DefiningProjectFullPath"]).resolve() != package_root / CONTENT_LEAF.lower() / CONTENT_VERSION / imported:
        raise RuntimeError("Fixture did not evaluate the transitive package's imported Content")
    if imported not in targets[CONTENT_LEAF + "/" + CONTENT_VERSION].get("build", {}):
        raise RuntimeError("Fixture transitive import was not selected by the restored target")
    value = {"nuget_contentfiles_package": CONTENT_CONSUMER + "/" + CONTENT_VERSION,
             "transitive_content_package": CONTENT_LEAF + "/" + CONTENT_VERSION,
             "contentfiles_generated_props_proven": True, "transitive_content_import_proven": True}
    (root / ".ai-tdd/restored-content-proof.json").write_text(json.dumps(value), encoding="utf-8")
    return value


def content_feed(root):
    """An ordinary restored NuGet dependency with two external Content owners.

    Standard contentFiles items are defined by generated nuget.g.props; the
    buildTransitive item is defined by the package's own import. This local
    public fixture requires no package publication or changes to user caches.
    """
    feed = root / ".ai-tdd/local-feed"
    feed.mkdir()
    packages = {
        CONTENT_LEAF: {
            "buildTransitive/build-payload.txt": BUILD_PAYLOAD,
            "buildTransitive/" + CONTENT_LEAF + ".targets":
                '<Project><ItemGroup><Content Include="$(MSBuildThisFileDirectory)build-payload.txt">'
                '<Link>SyntheticData/build-payload.txt</Link><TargetPath>SyntheticData/build-payload.txt</TargetPath>'
                '<CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory></Content></ItemGroup></Project>',
        },
        CONTENT_CONSUMER: {"contentFiles/any/any/SyntheticData/payload.json": CONTENT_PAYLOAD},
    }
    for name, contents in packages.items():
        extra = ('' if name == CONTENT_LEAF else '<contentFiles><files include="any/any/SyntheticData/payload.json" buildAction="Content" '
                 'copyToOutput="true" flatten="false"/></contentFiles><dependencies><group targetFramework="net8.0"><dependency id="' + CONTENT_LEAF +
                 '" version="[' + CONTENT_VERSION + ']"/></group></dependencies>')
        contents = {name + ".nuspec": '<?xml version="1.0"?><package><metadata><id>' + name + '</id><version>' + CONTENT_VERSION +
                    '</version><authors>AI TDD synthetic fixture</authors><description>Public isolated compatibility regression</description>' + extra + '</metadata></package>', **contents}
        path = feed / (name.lower() + "." + CONTENT_VERSION + ".nupkg")
        with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, value in contents.items():
                archive.writestr(zipfile.ZipInfo(filename, date_time=(2025, 1, 1, 0, 0, 0)), value.encode("utf-8"))
    return feed


def coverage_checks(root, directories=None):
    """Prove the inherited collector actually ran, using native attachments."""
    trx_paths = ([root / directory / "result.trx" for directory in directories] if directories is not None else
                 sorted((root / ".ai-tdd").rglob("result.trx")))
    if not trx_paths:
        raise RuntimeError("No native TRX runs available to verify existing coverage settings")
    covered = []
    for path in trx_paths:
        path = Path(os.path.abspath(path))
        if path.resolve() != path or root / ".ai-tdd" not in path.parents:
            raise RuntimeError("Unsafe native results directory for coverage proof")
        tree = ET.fromstring(path.read_text(encoding="utf-8-sig"))
        ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
        deployments = tree.findall("t:TestSettings/t:Deployment", ns)
        collectors = tree.findall("t:ResultSummary/t:CollectorDataEntries/t:Collector", ns)
        attachments = [node.get("href", "") for collector in collectors
                       if collector.get("uri", "").lower() == "datacollector://microsoft/coverletcodecoverage/1.0"
                       for node in collector.findall("t:UriAttachments/t:UriAttachment/t:A", ns)]
        if len(attachments) != 1:
            raise RuntimeError("Each native execution must have exactly one referenced coverage attachment")
        if len(deployments) != 1:
            raise RuntimeError("Coverage attachment requires one unambiguous native deployment directory")
        deployment = SETUP.msbuild_path(deployments[0].get("runDeploymentRoot", ""))
        href = SETUP.msbuild_path(attachments[0])
        # VSTest's TRX logger copies run-level collectors to Deployment/In/href;
        # the original GUID collector directory is another legitimate copy.
        # See microsoft/vstest TrxLogger/Utility/Converter.cs ToCollectorEntry.
        for name in (deployment, href):
            if (not name or Path(name).is_absolute() or ":" in name or "\x00" in name
                    or any(part in {"", ".", ".."} for part in name.split("/"))):
                raise RuntimeError("Unsafe coverage attachment: deployment and href must be relative local paths")
        if "/" in deployment or Path(href).name != "coverage.cobertura.xml":
            raise RuntimeError("Unsafe relative coverage attachment or deployment name")
        attachment = path.parent / deployment / "In" / href
        if attachment.resolve() != attachment or path.parent not in attachment.parents:
            raise RuntimeError("Unsafe referenced coverage attachment outside its fresh native directory")
        if not attachment.is_file() or attachment.stat().st_size > 10_000_000:
            raise RuntimeError("Missing or unbounded referenced coverage attachment")
        report = ET.fromstring(attachment.read_text(encoding="utf-8-sig"))
        classes = [node for node in report.iter("class") if node.get("name") == "Demo.Fee"]
        if not classes or not any(int(line.get("hits", "0")) > 0 for node in classes for line in node.iter("line")):
            raise RuntimeError("Coverage attachment did not witness execution of the synthetic feature")
        covered.append({"native_results": path.relative_to(root).as_posix(),
                        "coverage_attachment": attachment.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(attachment.read_bytes()).hexdigest()})
    return {"coverage_attached_runs": len(covered), "coverage_feature_hit_proven": True, "coverage_reports": covered}


def fixture(root, framework, linked_source=False, configure=True):
    source = root / "src/Demo"
    tests = root / "tests/Demo.Tests"
    source.mkdir(parents=True)
    tests.mkdir(parents=True)
    (root / ".ai-tdd").mkdir()
    sdk = os.environ.get("DOTNET_DEMO_SDK")
    if sdk:
        if not re.fullmatch(r"\d+\.\d+\.\d+", sdk) or int(sdk.split(".")[0]) < 8:
            raise ValueError("DOTNET_DEMO_SDK must select an exact stable installed SDK 8+")
        (root / "global.json").write_text(json.dumps({"sdk": {"version": sdk, "rollForward": "disable"}}), encoding="utf-8")
    content_feed(root)
    (root / "NuGet.config").write_text('<configuration><packageSources><clear/><add key="fixture" value=".ai-tdd/local-feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>', encoding="utf-8")
    (root / "Directory.Build.props").write_text('<Project><PropertyGroup><RunSettingsFilePath>$(MSBuildThisFileDirectory)coverage.runsettings</RunSettingsFilePath></PropertyGroup></Project>', encoding="utf-8")
    (root / "coverage.runsettings").write_text('<RunSettings><DataCollectionRunSettings><DataCollectors><DataCollector friendlyName="XPlat Code Coverage" enabled="True"><Configuration><Format>cobertura</Format><IncludeTestAssembly>true</IncludeTestAssembly></Configuration></DataCollector></DataCollectors></DataCollectionRunSettings></RunSettings>', encoding="utf-8")
    # A linked ancestor file can be intentionally absent: it contributes no
    # build/publish bytes. Use an uncreated UUID sibling, never a host file.
    absent = root.parent / ("ai-tdd-absent-" + uuid.uuid4().hex) / ".dockerignore"
    if absent.parent.exists() or absent.parent.is_symlink() or absent.exists() or absent.is_symlink():
        raise RuntimeError("Synthetic external input path unexpectedly exists")
    absent_include = Path(os.path.relpath(absent, source)).as_posix()
    (root / ".ai-tdd/external-absent-input.json").write_text(json.dumps({"path": str(absent)}), encoding="utf-8")
    (source / "Demo.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>'
        '<ItemGroup><Content Include="' + absent_include + '" Link=".dockerignore" CopyToOutputDirectory="Never" '
        'CopyToPublishDirectory="Never"/></ItemGroup></Project>', encoding="utf-8")
    (source / "Fee.cs").write_text('namespace Demo; public static class Fee { public static int Calculate(int cents) => 799; }\n', encoding="utf-8")
    packages = ([('xunit', '2.9.3'), ('xunit.runner.visualstudio', '3.0.0')] if framework == "xunit" else
                [('NUnit', '3.14.0'), ('NUnit3TestAdapter', '4.5.0')]) + [('Microsoft.NET.Test.Sdk', '17.14.1'),
                    ('coverlet.collector', '6.0.4'), (CONTENT_CONSUMER, CONTENT_VERSION)]
    references = ''.join(f'<PackageReference Include="{name}" Version="{version}"/>' for name, version in packages)
    # The linked-source opt-in uses an ordinary shared source arrangement for
    # local application-control policies that block a separate unsigned DLL.
    source_reference = ('<ProjectReference Include="../../src/Demo/Demo.csproj" ReferenceOutputAssembly="false"/><Compile Include="../../src/Demo/Fee.cs" Link="Fee.cs"/>'
                        if linked_source else '<ProjectReference Include="../../src/Demo/Demo.csproj"/>')
    (tests / "Demo.Tests.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><IsTestProject>true</IsTestProject><IsPackable>false</IsPackable></PropertyGroup><ItemGroup>' + references + source_reference + '</ItemGroup></Project>', encoding="utf-8")
    content = 'System.IO.File.ReadAllText(System.IO.Path.Combine(System.AppContext.BaseDirectory, "SyntheticData", '
    body = ('using Xunit; namespace Demo; public class Checks { [Fact] public void Baseline() { Assert.Equal(799, Fee.Calculate(100)); '
            'Assert.Equal(' + json.dumps(CONTENT_PAYLOAD) + ', ' + content + '"payload.json"))); '
            'Assert.Equal(' + json.dumps(BUILD_PAYLOAD) + ', ' + content + '"build-payload.txt"))); } }' if framework == "xunit" else
            'using NUnit.Framework; namespace Demo; public class Checks { [Test] public void Baseline() { Assert.That(Fee.Calculate(100), Is.EqualTo(799)); '
            'Assert.That(' + content + '"payload.json")), Is.EqualTo(' + json.dumps(CONTENT_PAYLOAD) + ')); '
            'Assert.That(' + content + '"build-payload.txt")), Is.EqualTo(' + json.dumps(BUILD_PAYLOAD) + ')); } }')
    (tests / "Checks.cs").write_text(body, encoding="utf-8")
    (root / ".ai-tdd/repository-inputs.json").write_text(json.dumps(repository_inputs(root)), encoding="utf-8")
    restore = subprocess.run(["dotnet", "restore", str(tests / "Demo.Tests.csproj"), "--configfile", str(root / "NuGet.config"), "--verbosity", "quiet"],
                             cwd=root, env=SETUP.environment(), capture_output=True, text=True, timeout=240)
    if restore.returncode:
        raise RuntimeError("Public isolated fixture restore failed; no user packages were changed")
    restored_content_checks(root, tests / "Demo.Tests.csproj")
    if configure:
        try:
            config = SETUP.configure(root)
        except SETUP.DotnetError:
            setup_diagnostics(root)
            raise
        (root / ".ai-tdd/config.json").write_text(json.dumps(config), encoding="utf-8")
    verify_repository_inputs(root, require_config=configure)
    return source, tests


def native(root):
    path = root / ".ai-tdd" / ("native-" + uuid.uuid4().hex + ".json")
    try:
        code = RUNNER.run(root, path)
    except RUNNER.DotnetError:
        setup_diagnostics(root)
        raise
    report = json.loads(path.read_text(encoding="utf-8"))
    if code not in (0, 1) or report.get("completion") != "complete":
        setup_diagnostics(root)
        raise RUNNER.DotnetError("Synthetic native run incomplete: " + json.dumps(report.get("diagnostics", []), ensure_ascii=False))
    coverage_checks(root, [module["directory"] for module in report["native_modules"]])
    verify_repository_inputs(root)
    return code, report


def native_report(root, value):
    """Resolve a controller receipt to its unchanged native evidence file."""
    if "native_modules" in value:
        return value
    run_id = value.get("id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise RuntimeError("Native proof requires a real controller receipt")
    report = json.loads((root / ".ai-tdd/runs" / (run_id + ".json")).read_text(encoding="utf-8"))
    if report["results"] != value["results"] or report["collected"] != value["collected"]:
        raise RuntimeError("Controller receipt differs from its native evidence")
    return report


def native_inventory(root, report):
    report = native_report(root, report)
    if len(report["native_modules"]) != 1:
        raise RuntimeError("Synthetic identity proof requires exactly one native module")
    directory = root / report["native_modules"][0]["directory"]
    if directory.resolve() != directory or root / ".ai-tdd" not in directory.parents:
        raise RuntimeError("Unsafe synthetic native evidence directory")
    with (directory / "discovery.diag.log").open(encoding="utf-8-sig") as stream:
        inventory = RUNNER.discovery_cases(iter(lambda: stream.readline(5_000_001), ""))
    return inventory, directory


def native_identity_checks(root, report, previous=None):
    """Audit parent discovery and aggregate TRX outcomes independently of rows.

    TRX execution GUIDs are only native execution witnesses; they are never
    fabricated as JSON child IDs or joined through truncated display names.
    """
    report = native_report(root, report)
    inventory, directory = native_inventory(root, report)
    expected, identities = defaultdict(Counter), set()
    for row in report["results"]:
        parent, child = row.get("native_case_id"), row.get("native_test_id")
        if parent not in inventory or not child or row.get("vstest_id") != inventory[parent]["vstest_id"]:
            raise RuntimeError("Missing or inconsistent native parent/child identity")
        identity = (parent, child, row["id"])
        if identity in identities:
            raise RuntimeError("Duplicate native child identity")
        identities.add(identity)
        expected[row["vstest_id"]][{"passed": "Passed", "failed": "Failed", "error": "Failed", "skipped": "NotExecuted"}[row["status"]]] += 1
    namespace = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"
    tree = ET.fromstring((directory / "result.trx").read_text(encoding="utf-8-sig"))
    actual, executions, parents = defaultdict(Counter), set(), defaultdict(set)
    for row in tree.findall(namespace + "Results/" + namespace + "UnitTestResult"):
        execution = row.get("executionId")
        if not execution or execution in executions:
            raise RuntimeError("TRX requires unique actual execution IDs")
        executions.add(execution)
        parents[row.get("testId")].add(execution)
        actual[row.get("testId")][row.get("outcome")] += 1
    if actual != expected:
        raise RuntimeError("TRX aggregate parent outcomes differ from actual runtime rows")
    native_parents = {value["vstest_id"]: value for value in inventory.values()}
    definitions = set()
    for definition in tree.findall(namespace + "TestDefinitions/" + namespace + "UnitTest"):
        parent = definition.get("id")
        methods, runs = definition.findall(namespace + "TestMethod"), definition.findall(namespace + "Execution")
        if parent not in native_parents or parent in definitions or len(methods) != 1 or len(runs) != 1:
            raise RuntimeError("TRX parent definitions do not bind exact discovery")
        case, method = native_parents[parent], methods[0]
        if (method.get("className", "") + "." + method.get("name", "") != case["method"]
                or Path(method.get("codeBase", "")) != Path(case["source"])
                or method.get("adapterTypeName") != case["executor_uri"]
                or runs[0].get("id") not in parents[parent]):
            raise RuntimeError("TRX parent method/source/execution binding differs from discovery")
        definitions.add(parent)
    if definitions != set(native_parents) or set(expected) != set(native_parents):
        raise RuntimeError("TRX parent inventory is incomplete")
    if previous is not None:
        earlier = {(row["native_case_id"], row["native_test_id"], row["id"]) for row in native_report(root, previous)["results"]}
        if earlier != identities:
            raise RuntimeError("Native child identities changed across an unchanged rerun")
    return {"discovered_parent_cases": len(inventory), "executed_native_rows": len(identities),
            "expanded_parent_cases": sum(sum(outcomes.values()) > 1 for outcomes in expected.values()),
            "aggregate_trx_binding_proven": True, "unchanged_run_child_ids_stable": previous is not None,
            "identity_limitation": "Native ordinal child IDs prove unchanged-run continuity; same-count MemberData reorder needs semantic review"}


def theory_fixture(tests):
    """Two truncation boundaries: adapter 447 chars and v2 argument formatting.

    Nonserializable MemberData proves deferred runtime rows. Another 103 Fact
    methods retain transport batching when each theory has one parent during
    discovery. Long nested fixture paths are ordinary synthetic inputs.
    """
    directory = tests / ('long-theory-path-' + 'p' * 55) / ('nested-' + 'q' * 55)
    directory.mkdir(parents=True)
    prefix = 'SharedLongTheoryDisplayName' * 24
    data = ''.join(f'[InlineData({index})]' for index in range(103))
    values = 'C:/synthetic/' + 'long/path/' * 12
    facts = ''.join(f'[Fact] public void ExistingLowCart{index:03d}() {{ Assert.Equal(799, Fee.Calculate({index})); }}'
                    for index in range(103))
    code = ('using Xunit; using System.Collections.Generic; namespace Demo; public class LongTheories { '
            f'[Theory(DisplayName="{prefix}")] {data} public void Adapter(int row) {{ Assert.InRange(row, 0, 102); }} '
            f'[Theory] [InlineData("{values}one")] [InlineData("{values}two")] '
            'public void Argument(string value) { Assert.True(value.EndsWith("one") || value.EndsWith("two")); } } '
            'public sealed class CartInput { public int Cents { get; } public string Label { get; } '
            'public CartInput(int cents, string label) { Cents = cents; Label = label; } public override string ToString() => Label; } '
            'public class DeferredTheories { public static IEnumerable<object[]> Rows() { '
            'yield return new object[] { new CartInput(100, "same cart") }; '
            'yield return new object[] { new CartInput(200, "same cart") }; '
            'yield return new object[] { new CartInput(300, "third cart") }; } '
            '[Theory] [MemberData(nameof(Rows), DisableDiscoveryEnumeration = true)] '
            'public void Objects(CartInput cart) { Assert.Equal(799, Fee.Calculate(cart.Cents)); } } '
            'public class TransportBatches { ' + facts + ' }')
    (directory / 'LongTheories.cs').write_text(code, encoding='utf-8')
    return directory / 'LongTheories.cs'


def theory_checks(root, report, path):
    rows = [row for row in report['results'] if row['display_name'].startswith(('SharedLongTheoryDisplayName', 'Demo.LongTheories.Argument'))]
    if len(rows) != 105 or len({row['id'] for row in rows}) != 105 or any(row['status'] != 'passed' for row in rows):
        raise RuntimeError('Long/identical theory names lost or misclassified native case identities')
    names = [row['display_name'] for row in rows]
    if len(set(names)) != 104 or max(map(len, names)) <= 447:
        raise RuntimeError('Fixture did not exercise both name truncation boundaries')
    inventory, directory = native_inventory(root, report)
    facts = [case for case in inventory.values() if case['method'].startswith('Demo.TransportBatches.ExistingLowCart')]
    trace = (directory / 'discovery.diag.log').read_text(encoding='utf-8-sig')
    if len(facts) != 103 or '"MessageType":"TestDiscovery.TestFound"' not in trace:
        raise RuntimeError('Native discovery did not exercise batched transport cases')
    return {'native_cases': 105, 'distinct_ids': 105, 'distinct_display_names': 104,
            'longest_display_name': max(map(len, names)), 'fixture_path_characters': len(str(path)),
            'batched_discovery': True, 'discovered_fact_methods': len(facts), 'duplicate_formatted_names': True}


def runtime_theory_checks(root, report, previous=None):
    proof = native_identity_checks(root, report, previous)
    inventory, _ = native_inventory(root, report)
    parents = {parent for parent, case in inventory.items() if case['method'] == 'Demo.DeferredTheories.Objects'}
    rows = [row for row in report['results'] if row['native_case_id'] in parents]
    if len(parents) != 1 or len(rows) != 3 or len({row['display_name'] for row in rows}) != 2:
        raise RuntimeError('Nonserializable MemberData did not prove distinct rows with duplicate formatted names')
    return {**proof, 'nonserializable_memberdata_rows': len(rows), 'nonserializable_discovered_parents': len(parents),
            'duplicate_memberdata_display_names': True, 'command_scoped_theory_enumeration': True}


def evidence_demo(root, framework, linked_source=False):
    source, tests = fixture(root, framework, linked_source)
    code, baseline = native(root)
    if code or len(baseline["results"]) != 1 or baseline["results"][0]["status"] != "passed":
        raise RuntimeError("Native baseline was not one proven passing test")
    theory, deferred = None, None
    if framework == 'xunit':
        theory_path = theory_fixture(tests)
        code, long_report = native(root)
        if code or len(long_report['results']) != 1 + 105 + 103 + 3:
            raise RuntimeError('Native long-theory baseline was not fully passing')
        theory = theory_checks(root, long_report, theory_path)
        repeat_code, repeated_report = native(root)
        if repeat_code:
            raise RuntimeError('Unchanged native runtime-row baseline failed on its repeat')
        deferred = runtime_theory_checks(root, repeated_report, previous=long_report)
        theory_path.unlink()
    tests.joinpath("Checks.cs").write_text((
        'using Xunit; namespace Demo; public class Checks { '
        '[Fact] public void Pass() {} [Fact] public void Assertion() { Assert.Equal(0, Fee.Calculate(10000)); } '
        '[Fact] public void Error() { throw new System.InvalidOperationException("synthetic"); } '
        '[Fact(Skip="synthetic")] public void Skip() {} } '
        'public class Setup { public Setup() { Assert.Fail("synthetic setup"); } [Fact] public void Body() {} } '
        'public class Cleanup : System.IDisposable { [Fact] public void Body() {} public void Dispose() { Assert.Fail("synthetic cleanup"); } }'
        if framework == "xunit" else
        'using NUnit.Framework; namespace Demo; public class Checks { '
        '[Test] public void Pass() {} [Test] public void Assertion() { Assert.That(Fee.Calculate(10000), Is.EqualTo(0)); } '
        '[Test] public void Error() { throw new System.InvalidOperationException("synthetic"); } '
        '[Test,Ignore("synthetic")] public void Skip() {} } '
        'public class Setup { [SetUp] public void Start() { Assert.Fail("synthetic setup"); } [Test] public void Body() {} } '
        'public class Cleanup { [Test] public void Body() {} [TearDown] public void End() { Assert.Fail("synthetic cleanup"); } }'), encoding="utf-8")
    code, report = native(root)
    statuses = {item.get('display_name', item["id"].split("|")[-1]): item["status"] for item in report["results"]}
    expected = {"Demo.Checks.Pass": "passed", "Demo.Checks.Assertion": "failed", "Demo.Checks.Error": "error",
                "Demo.Checks.Skip": "skipped", "Demo.Setup.Body": "error", "Demo.Cleanup.Body": "error"}
    if code != 1 or statuses != expected:
        raise RuntimeError("Native classification disagreed with the independently specified outcomes: " + json.dumps(statuses))
    source.joinpath("Fee.cs").write_text("synthetic invalid C#", encoding="utf-8")
    try:
        native(root)
    except RUNNER.DotnetError:
        build_rejected = True
    else:
        raise RuntimeError("Compile error incorrectly produced acceptance evidence")
    return {"framework": framework, "source_mode": "linked-source" if linked_source else "project-reference", "full_inventory": len(report["collected"]), "statuses": statuses, "build_failure_rejected": build_rejected,
            "repository_compatibility": {**verify_repository_inputs(root), **coverage_checks(root)},
            **({'long_theories': theory, 'deferred_theories': deferred} if theory else {})}


class FacadeController:
    """The demo driver reads JSON; all production transitions use Node CLI."""
    def __init__(self, root, plugin, env):
        self.root, self.plugin, self.env = root, plugin, env
        self.node = shutil.which("node")
        if not self.node:
            raise RuntimeError("Node.js is required for the controller facade fixture")
        self.command("init")

    @property
    def state(self):
        return json.loads((self.root / ".ai-tdd/state.json").read_text(encoding="utf-8"))

    def command(self, name, *arguments):
        result = subprocess.run([self.node, "--preserve-symlinks", "--preserve-symlinks-main",
                                 str(self.plugin / "scripts/tdd-launcher.cjs"), "--root", str(self.root), name, *arguments],
                                cwd=self.root, env=self.env, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode:
            raise RuntimeError("Native facade " + name + " failed: " + (result.stderr or result.stdout)[-2000:])
        return json.loads(result.stdout)

    def begin(self):
        return self.command("begin")

    def red(self, tests, ac, expect, because):
        return self.command("red", "--tests", *tests, "--ac", *ac, "--expect", expect, "--because", because)

    def green(self):
        return self.command("green")

    def verify(self):
        return self.command("verify")

    def finish(self):
        self.command("finish")
        return self.state


def packaged_plugin(root, executable):
    """Seed a trusted supplied build in an isolated, integrity-pinned cache."""
    executable = Path(executable).resolve()
    if not executable.is_file() or executable.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("--packaged-executable needs a bounded local built controller")
    plugin = root / "packaged-plugin"
    shutil.copytree(PLUGIN, plugin, ignore=shutil.ignore_patterns(".runtime", "__pycache__"))
    version = json.loads((plugin / "runtime-manifest.json").read_text(encoding="utf-8"))["version"]
    key = {"win32": "win32-x64", "linux": "linux-x64", "darwin": "darwin-arm64"}.get(sys.platform)
    if not key:
        raise ValueError("Unsupported packaged fixture platform")
    name = "ai-tdd-controller-" + version + "-" + key + (".exe" if sys.platform == "win32" else "")
    target = plugin / ".runtime" / version / key / name
    target.parent.mkdir(parents=True)
    shutil.copy2(executable, target)
    with target.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()
    manifest = {"version": version, "platforms": {key: {"url": "https://github.com/KubsGU/ai-tdd-kit/releases/download/v" + version + "/" + name,
                 "sha256": sha, "size": target.stat().st_size}}}
    (plugin / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    node, dotnet = shutil.which("node"), shutil.which("dotnet")
    if not node or not dotnet:
        raise RuntimeError("The packaged fixture requires installed Node.js and .NET")
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(sorted({str(Path(node).resolve().parent), str(Path(dotnet).resolve().parent)}))
    env.pop("AI_TDD_PYTHON", None)
    env.pop("PYTHONPATH", None)
    if any(shutil.which(name, path=env["PATH"]) for name in ("python", "python3", "py")):
        raise RuntimeError("Packaged fixture child PATH must contain only Node.js/.NET, with no Python")
    return plugin, env, {"platform": key, "sha256": sha, "version": version, "child_python_available": False}


def workflow_demo(root, framework, linked_source=False, facade=None):
    source, tests = fixture(root, framework, linked_source, configure=facade is None)
    folder = root / ".ai-tdd"
    theory_path = theory_fixture(tests) if framework == 'xunit' else None
    try:
        controller = FacadeController(root, *facade) if facade else TDD.Controller(root)
    except (RuntimeError, SETUP.DotnetError):
        setup_diagnostics(root)
        raise
    verify_repository_inputs(root)
    (folder / "spec.json").write_text(json.dumps({"version": 1, "goal": "Free delivery at or above 10000 cents",
        "acceptance": [{"id": "AC1", "description": "Fee is zero for carts at or above 10000 cents"}], "open_questions": []}), encoding="utf-8")
    (folder / "review-plan.json").write_text(json.dumps({"scenarios": [{"ac": "AC1", "case": "Literal boundary 10000 cents"}]}), encoding="utf-8")
    controller.begin()
    assertion = ('using Xunit; using System.Collections.Generic; namespace Demo; public class Threshold { '
                 'public static IEnumerable<object[]> Rows() { yield return new object[] { new CartInput(10000, "boundary") }; '
                 'yield return new object[] { new CartInput(10001, "boundary") }; } '
                 '[Theory] [MemberData(nameof(Rows), DisableDiscoveryEnumeration = true)] '
                 'public void Boundary(CartInput cart) { Assert.Equal(0, Fee.Calculate(cart.Cents)); } }'
                 if framework == "xunit" else 'using NUnit.Framework; namespace Demo; public class Threshold { [Test] public void Boundary() { Assert.That(Fee.Calculate(10000), Is.EqualTo(0)); } }')
    (tests / "Threshold.cs").write_text(assertion, encoding="utf-8")
    # Discover the actual native case ID instead of constructing it from a name.
    _, red_report = native(root)
    if framework == 'xunit':
        inventory, _ = native_inventory(root, red_report)
        parents = {parent for parent, case in inventory.items() if case['method'] == 'Demo.Threshold.Boundary'}
        red_rows = [row for row in red_report['results'] if row['native_case_id'] in parents]
        if len(parents) != 1 or len({row['display_name'] for row in red_rows}) != 1:
            raise RuntimeError('Runtime boundary theory must have one discovered parent and duplicate child display names')
        native_identity_checks(root, red_report)
    else:
        red_rows = [row for row in red_report['results'] if row.get('display_name', row['id'].split('|')[-1]) == 'Demo.Threshold.Boundary']
    if len(red_rows) != (2 if framework == 'xunit' else 1) or any(row['exception'] != 'AssertionError' for row in red_rows):
        raise RuntimeError('Boundary RED case was not independently identified')
    test_ids = [row['id'] for row in red_rows]
    controller.red(tests=test_ids, ac=["AC1"], expect="AssertionError", because="AC1 literal inclusive boundary and its immediate neighbor expect zero")
    source.joinpath("Fee.cs").write_text('namespace Demo; public static class Fee { public static int Calculate(int cents) => cents >= 10000 ? 0 : 799; }\n', encoding="utf-8")
    controller.green()
    controller.verify()
    review = {"receipt_id": controller.state["green_receipt"]["id"], "checked_ac": ["AC1"], "findings": [],
              "limitations": ["Synthetic function; deterministic role simulation without AI calls"], "recommendation": "accept",
              "quality_receipt_id": controller.state["quality_receipt"]["id"], "quality_limitations": ["No lint/format/security checks configured in this synthetic fixture"],
              "repo_conventions": "Existing C# namespace/API and installed test framework preserved",
              "test_assessment": [{"test_id": test_id, "detects": "Inclusive boundary or next cart missing", "oracle": "AC1 explicitly makes carts at or above 10000 cents free", "why_needed": "Distinct native rows exercise exact boundary and immediate neighbor"} for test_id in test_ids]}
    (folder / "review.json").write_text(json.dumps(review), encoding="utf-8")
    result = controller.finish()
    return {"framework": framework, "source_mode": "linked-source" if linked_source else "project-reference", "controller_mode": "node-facade" if facade else "python-driver",
            "phase": result["phase"], "executed_tests": len(result["completion_receipt"]["results"]), "red_exception": "AssertionError",
            "repository_compatibility": {**verify_repository_inputs(root), **coverage_checks(root)},
            **({'long_theories': theory_checks(root, result['completion_receipt'], theory_path),
                'deferred_theories': {**runtime_theory_checks(root, result['completion_receipt'], previous=result['green_receipt']),
                    'new_feature_red_native_rows': len(test_ids), 'new_feature_red_parent_cases': 1,
                    'new_feature_red_exception': 'AssertionError', 'new_feature_child_ids_survive_green_and_completion':
                        set(test_ids).issubset(result['completion_receipt']['collected'])}} if theory_path else {})}


def failure_probe(root):
    """Deliberately fail real native compilation to exercise CI log retention."""
    source, _ = fixture(root, "xunit")
    source.joinpath("Fee.cs").write_text("synthetic invalid C# for failure artifact probe\n", encoding="utf-8")
    (root / ".ai-tdd/spec.json").write_text(json.dumps({"version": 1, "goal": "Public synthetic failure diagnostic probe",
        "acceptance": [{"id": "AC1", "description": "Retain the actual native compiler failure"}], "open_questions": []}), encoding="utf-8")
    (root / ".ai-tdd/review-plan.json").write_text(json.dumps({"scenarios": [
        {"ac": "AC1", "case": "Deliberately invalid generated C# must fail before a baseline receipt exists"}]}), encoding="utf-8")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Intentional failure probe requires installed Node.js")
    with (root / ".ai-tdd/probe-controller.stdout.log").open("wb") as stdout, (root / ".ai-tdd/probe-controller.stderr.log").open("wb") as stderr:
        subprocess.run([node, "--preserve-symlinks", "--preserve-symlinks-main", str(PLUGIN / "scripts/tdd-launcher.cjs"),
                        "--root", str(root), "begin"], cwd=root, env=dict(os.environ), stdout=stdout, stderr=stderr,
                       timeout=600, check=True)
    raise RuntimeError("Intentional failure artifact probe unexpectedly accepted invalid C#")


def main():
    global PLUGIN, SETUP, RUNNER, TDD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-only", action="store_true")
    parser.add_argument("--linked-source", action="store_true", help="Use shared source files when local application control blocks newly built referenced DLLs")
    parser.add_argument("--controller-facade", action="store_true", help="Run all workflow transitions through the production Node CLI")
    parser.add_argument("--packaged-executable", help="Seed a local built controller in an isolated plugin cache; implies facade mode and child PATH without Python")
    parser.add_argument("--framework", choices=("xunit", "nunit", "both"), default="both")
    parser.add_argument("--output")
    parser.add_argument("--failure-probe", action="store_true", help="Intentionally fail a generated native compile to verify CI artifact retention")
    parser.add_argument("--plugin-root", type=Path, help="Exercise an extracted standalone skill's unchanged runtime sources")
    args = parser.parse_args()
    if args.plugin_root:
        PLUGIN = args.plugin_root.resolve()
        SETUP = load("skill_dotnet_setup", "dotnet_setup.py")
        RUNNER = load("skill_dotnet_runner", "dotnet_runner.py")
        TDD = load("skill_dotnet_controller", "tdd.py")
    summaries = []
    packaged = None
    with fixture_directory() as root:
        with isolated_environment(root):
            if args.failure_probe:
                probe_root = root / "xunit-workflow"
                probe_root.mkdir()
                failure_probe(probe_root)
            facade = (PLUGIN, dict(os.environ)) if args.controller_facade else None
            if args.packaged_executable:
                plugin, child_env, packaged = packaged_plugin(root, args.packaged_executable)
                facade = (plugin, child_env)
            for framework in ("xunit", "nunit") if args.framework == "both" else [args.framework]:
                evidence_root = root / (framework + "-evidence")
                evidence_root.mkdir()
                value = {"evidence": evidence_demo(evidence_root, framework, args.linked_source)}
                if not args.runner_only:
                    workflow_root = root / (framework + "-workflow")
                    workflow_root.mkdir()
                    value["workflow"] = workflow_demo(workflow_root, framework, args.linked_source, facade)
                summaries.append(value)
    result = {"fixtures": summaries, "note": "Real installed SDK/framework executions; no AI calls, global installation or user-project edits"}
    if packaged:
        result["packaged_runtime"] = packaged
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
