"""Real isolated .NET workflow/evidence demonstrations; no AI calls.

Requires an existing .NET 8+ SDK and public NuGet connectivity. Every fixture,
CLI home and package cache is temporary; existing SDKs/projects are untouched.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


KIT = Path(__file__).resolve().parents[1]
PLUGIN = KIT / "plugins/ai-tdd"


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
    except BaseException:
        print("Synthetic .NET fixture and local failure logs retained at " + str(root), file=sys.stderr)
        raise
    else:
        # Validate the exact created target before recursive fixture cleanup.
        if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith("ai-tdd-dotnet-demo-"):
            raise RuntimeError("Refusing cleanup outside the explicitly created fixture directory")
        shutil.rmtree(root)


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
                    allowed = path is not None and kind in {"None", "Content"} and SETUP._package_input(metadata, packages, path, item, project=project)
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
    (root / "NuGet.config").write_text('<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>', encoding="utf-8")
    (source / "Demo.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    (source / "Fee.cs").write_text('namespace Demo; public static class Fee { public static int Calculate(int cents) => 799; }\n', encoding="utf-8")
    packages = ([('xunit', '2.9.3'), ('xunit.runner.visualstudio', '3.0.0')] if framework == "xunit" else
                [('NUnit', '3.14.0'), ('NUnit3TestAdapter', '4.5.0')]) + [('Microsoft.NET.Test.Sdk', '17.14.1')]
    references = ''.join(f'<PackageReference Include="{name}" Version="{version}"/>' for name, version in packages)
    # The linked-source opt-in uses an ordinary shared source arrangement for
    # local application-control policies that block a separate unsigned DLL.
    source_reference = ('<ProjectReference Include="../../src/Demo/Demo.csproj" ReferenceOutputAssembly="false"/><Compile Include="../../src/Demo/Fee.cs" Link="Fee.cs"/>'
                        if linked_source else '<ProjectReference Include="../../src/Demo/Demo.csproj"/>')
    (tests / "Demo.Tests.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><IsTestProject>true</IsTestProject><IsPackable>false</IsPackable></PropertyGroup><ItemGroup>' + references + source_reference + '</ItemGroup></Project>', encoding="utf-8")
    body = ('using Xunit; namespace Demo; public class Checks { [Fact] public void Baseline() { Assert.Equal(799, Fee.Calculate(100)); } }' if framework == "xunit" else
            'using NUnit.Framework; namespace Demo; public class Checks { [Test] public void Baseline() { Assert.That(Fee.Calculate(100), Is.EqualTo(799)); } }')
    (tests / "Checks.cs").write_text(body, encoding="utf-8")
    restore = subprocess.run(["dotnet", "restore", str(tests / "Demo.Tests.csproj"), "--configfile", str(root / "NuGet.config"), "--verbosity", "quiet"],
                             cwd=root, env=SETUP.environment(), capture_output=True, text=True, timeout=240)
    if restore.returncode:
        raise RuntimeError("Public isolated fixture restore failed; no user packages were changed")
    if configure:
        try:
            config = SETUP.configure(root)
        except SETUP.DotnetError:
            setup_diagnostics(root)
            raise
        (root / ".ai-tdd/config.json").write_text(json.dumps(config), encoding="utf-8")
    return source, tests


def native(root):
    path = root / ".ai-tdd" / ("native-" + uuid.uuid4().hex + ".json")
    try:
        code = RUNNER.run(root, path)
    except RUNNER.DotnetError:
        setup_diagnostics(root)
        raise
    return code, json.loads(path.read_text(encoding="utf-8"))


def theory_fixture(tests):
    """Two truncation boundaries: adapter 447 chars and v2 argument formatting.

    103 serializable rows force batched discovery as well as its completion
    tail. Two long strings have identical formatted names but distinct data.
    Long nested fixture paths are ordinary project inputs, never user changes.
    """
    directory = tests / ('long-theory-path-' + 'p' * 55) / ('nested-' + 'q' * 55)
    directory.mkdir(parents=True)
    prefix = 'SharedLongTheoryDisplayName' * 24
    data = ''.join(f'[InlineData({index})]' for index in range(103))
    values = 'C:/synthetic/' + 'long/path/' * 12
    code = ('using Xunit; namespace Demo; public class LongTheories { '
            f'[Theory(DisplayName="{prefix}")] {data} public void Adapter(int row) {{ Assert.InRange(row, 0, 102); }} '
            f'[Theory] [InlineData("{values}one")] [InlineData("{values}two")] '
            'public void Argument(string value) { Assert.True(value.EndsWith("one") || value.EndsWith("two")); } }')
    (directory / 'LongTheories.cs').write_text(code, encoding='utf-8')
    return directory / 'LongTheories.cs'


def theory_checks(root, report, path):
    rows = [row for row in report['results'] if row['display_name'].startswith(('SharedLongTheoryDisplayName', 'Demo.LongTheories.Argument'))]
    if len(rows) != 105 or len({row['id'] for row in rows}) != 105 or any(row['status'] != 'passed' for row in rows):
        raise RuntimeError('Long/identical theory names lost or misclassified native case identities')
    names = [row['display_name'] for row in rows]
    if len(set(names)) != 104 or max(map(len, names)) <= 447:
        raise RuntimeError('Fixture did not exercise both name truncation boundaries')
    logs = sorted((root / '.ai-tdd').rglob('discovery.diag.log'))
    if not logs or not any('"MessageType":"TestDiscovery.TestFound"' in log.read_text(encoding='utf-8-sig') for log in logs):
        raise RuntimeError('Native discovery did not exercise batched transport cases')
    return {'native_cases': 105, 'distinct_ids': 105, 'distinct_display_names': 104,
            'longest_display_name': max(map(len, names)), 'fixture_path_characters': len(str(path)),
            'batched_discovery': True, 'duplicate_formatted_names': True}


def evidence_demo(root, framework, linked_source=False):
    source, tests = fixture(root, framework, linked_source)
    code, baseline = native(root)
    if code or len(baseline["results"]) != 1 or baseline["results"][0]["status"] != "passed":
        raise RuntimeError("Native baseline was not one proven passing test")
    theory = None
    if framework == 'xunit':
        theory_path = theory_fixture(tests)
        code, long_report = native(root)
        if code or len(long_report['results']) != 106:
            raise RuntimeError('Native long-theory baseline was not fully passing')
        theory = theory_checks(root, long_report, theory_path)
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
            **({'long_theories': theory} if theory else {})}


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
    (folder / "spec.json").write_text(json.dumps({"version": 1, "goal": "Free delivery at 10000 cents",
        "acceptance": [{"id": "AC1", "description": "Fee is zero for a 10000-cent cart"}], "open_questions": []}), encoding="utf-8")
    (folder / "review-plan.json").write_text(json.dumps({"scenarios": [{"ac": "AC1", "case": "Literal boundary 10000 cents"}]}), encoding="utf-8")
    controller.begin()
    assertion = ('using Xunit; namespace Demo; public class Threshold { [Fact] public void Boundary() { Assert.Equal(0, Fee.Calculate(10000)); } }'
                 if framework == "xunit" else 'using NUnit.Framework; namespace Demo; public class Threshold { [Test] public void Boundary() { Assert.That(Fee.Calculate(10000), Is.EqualTo(0)); } }')
    (tests / "Threshold.cs").write_text(assertion, encoding="utf-8")
    # Discover the actual native case ID instead of constructing it from a name.
    _, red_report = native(root)
    red_rows = [row for row in red_report['results'] if row.get('display_name', row['id'].split('|')[-1]) == 'Demo.Threshold.Boundary']
    if len(red_rows) != 1 or red_rows[0]['exception'] != 'AssertionError':
        raise RuntimeError('Boundary RED case was not independently identified')
    test_id = red_rows[0]['id']
    controller.red(tests=[test_id], ac=["AC1"], expect="AssertionError", because="AC1 literal independent boundary expects zero")
    source.joinpath("Fee.cs").write_text('namespace Demo; public static class Fee { public static int Calculate(int cents) => cents >= 10000 ? 0 : 799; }\n', encoding="utf-8")
    controller.green()
    controller.verify()
    review = {"receipt_id": controller.state["green_receipt"]["id"], "checked_ac": ["AC1"], "findings": [],
              "limitations": ["Synthetic function; deterministic role simulation without AI calls"], "recommendation": "accept",
              "quality_receipt_id": controller.state["quality_receipt"]["id"], "quality_limitations": ["No lint/format/security checks configured in this synthetic fixture"],
              "repo_conventions": "Existing C# namespace/API and installed test framework preserved",
              "test_assessment": [{"test_id": test_id, "detects": "Inclusive boundary missing", "oracle": "AC1 explicitly makes 10000 cents free", "why_needed": "Tests the exact inclusive threshold"}]}
    (folder / "review.json").write_text(json.dumps(review), encoding="utf-8")
    result = controller.finish()
    return {"framework": framework, "source_mode": "linked-source" if linked_source else "project-reference", "controller_mode": "node-facade" if facade else "python-driver",
            "phase": result["phase"], "executed_tests": len(result["completion_receipt"]["results"]), "red_exception": "AssertionError",
            **({'long_theories': theory_checks(root, result['completion_receipt'], theory_path)} if theory_path else {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-only", action="store_true")
    parser.add_argument("--linked-source", action="store_true", help="Use shared source files when local application control blocks newly built referenced DLLs")
    parser.add_argument("--controller-facade", action="store_true", help="Run all workflow transitions through the production Node CLI")
    parser.add_argument("--packaged-executable", help="Seed a local built controller in an isolated plugin cache; implies facade mode and child PATH without Python")
    parser.add_argument("--framework", choices=("xunit", "nunit", "both"), default="both")
    parser.add_argument("--output")
    args = parser.parse_args()
    summaries = []
    packaged = None
    with fixture_directory() as root:
        with isolated_environment(root):
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
