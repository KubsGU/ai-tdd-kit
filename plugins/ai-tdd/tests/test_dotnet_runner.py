"""Native .NET evidence contracts; hand-derived xUnit/VSTest message fixtures."""
import copy
import importlib.util
import json
from pathlib import Path, PurePosixPath
import posixpath
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def messages(outcome="test-passed", exception="Xunit.Sdk.EqualException", stack="at Demo.Checks.Total()"):
    ids = {"AssemblyUniqueID": "assembly", "TestCollectionUniqueID": "collection",
           "TestClassUniqueID": "class", "TestMethodUniqueID": "method", "TestCaseUniqueID": "case"}
    result = [{"$type": "test-assembly-starting", "AssemblyUniqueID": "assembly"},
              {"$type": "test-case-starting", **ids, "TestCaseDisplayName": "Demo.Checks.Total",
               "TestClassName": "Demo.Checks", "TestMethodName": "Total"},
              {"$type": "test-starting", **ids, "TestUniqueID": "test", "TestDisplayName": "Demo.Checks.Total"}]
    terminal = {"$type": outcome, **ids, "TestUniqueID": "test", "ExecutionTime": 0.01}
    if outcome == "test-failed":
        terminal.update(Cause="Assertion", ExceptionTypes=[exception], ExceptionParentIndices=[-1],
                        Messages=["assert failed"], StackTraces=[stack])
    result.extend([terminal, {"$type": "test-finished", **ids, "TestUniqueID": "test", "ExecutionTime": 0.01},
                   {"$type": "test-case-finished", **ids, "TestsTotal": 1,
                    "TestsFailed": int(outcome == "test-failed"), "TestsSkipped": int(outcome == "test-skipped"), "TestsNotRun": 0},
                   {"$type": "test-assembly-finished", "AssemblyUniqueID": "assembly", "TestsTotal": 1,
                    "TestsFailed": int(outcome == "test-failed"), "TestsSkipped": int(outcome == "test-skipped"), "TestsNotRun": 0}])
    return result


def console(events):
    return "\n".join("[xUnit.net 00:00:01.00] " + json.dumps(item) for item in events)


def trx(outcome="Passed", total=1):
    return (f'<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">'
            f'<Results><UnitTestResult testName="Demo.Checks.Total" outcome="{outcome}" /></Results>'
            f'<ResultSummary><Counters total="{total}" executed="{int(outcome != "NotExecuted")}" passed="{int(outcome == "Passed")}" '
            f'failed="{int(outcome == "Failed")}" notExecuted="{int(outcome == "NotExecuted")}" /></ResultSummary></TestRun>')


class DotnetEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((SCRIPTS / "dotnet_runner.py").is_file(), "Native .NET runner is missing")
        loader = importlib.util.spec_from_file_location("native_dotnet_runner", SCRIPTS / "dotnet_runner.py")
        self.runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.runner)

    def report(self, events=None, xml=None, names=None):
        return self.runner.reconcile("tests/Demo.csproj", "net8.0", names or ["Demo.Checks.Total"],
                                     console(events or messages()), xml or trx())

    def test_native_assertion_with_body_stack_is_the_only_red_witness(self):
        report = self.report(messages("test-failed"), trx("Failed"))
        self.assertEqual(report["collected"], ["tests/Demo.csproj|net8.0|Demo.Checks.Total"])
        self.assertEqual(report["results"][0]["exception"], "AssertionError")
        self.assertEqual(report["results"][0]["native_exception_types"], ["Xunit.Sdk.EqualException"])

    def test_cause_assertion_does_not_promote_runtime_or_constructor_failures(self):
        for exception, stack in [("System.InvalidOperationException", "at Demo.Checks.Total()"),
                                 ("Xunit.Sdk.EqualException", "at Demo.Checks..ctor()"),
                                 ("Application.AssertionException", "at Demo.Checks.Total()")]:
            with self.subTest(exception=exception, stack=stack):
                result = self.report(messages("test-failed", exception, stack), trx("Failed"))["results"][0]
                self.assertEqual(result["status"], "error")
                self.assertNotEqual(result["exception"], "AssertionError")

    def test_skip_is_preserved_and_unknown_failure_types_cannot_be_red(self):
        self.assertEqual(self.report(messages("test-skipped"), trx("NotExecuted"))["results"][0]["status"], "skipped")
        events = messages("test-failed")
        events[3].pop("ExceptionTypes")
        with self.assertRaises(self.runner.DotnetError):
            self.report(events, trx("Failed"))

    def test_duplicate_missing_and_cleanup_lifecycle_fail_closed(self):
        missing = messages()
        missing.pop(4)
        cleanup = messages() + [{"$type": "test-class-cleanup-failure", "ExceptionTypes": ["Xunit.Sdk.EqualException"]}]
        duplicate = messages()
        duplicate.insert(4, copy.deepcopy(duplicate[3]))
        for events in (missing, cleanup, duplicate):
            with self.subTest(events=events), self.assertRaises(self.runner.DotnetError):
                self.report(events)

    def test_discovery_and_trx_inventory_must_match_actual_execution(self):
        for names, xml in [(["Demo.Checks.Other"], trx()), (["Demo.Checks.Total"] * 2, trx()),
                           (["Demo.Checks.Total"], trx("Failed")), (["Demo.Checks.Total"], trx(total=2))]:
            with self.subTest(names=names, xml=xml), self.assertRaises(self.runner.DotnetError):
                self.report(names=names, xml=xml)

    def test_arbitrary_embedded_json_is_not_a_reporter_message(self):
        with self.assertRaises(self.runner.DotnetError):
            self.runner.reconcile("tests/Demo.csproj", "net8.0", ["Demo.Checks.Total"],
                                  "captured output " + console(messages()), trx())

    def nunit(self, result="Failed", label="", stack="at Demo.Checks.Total()", suite_failure=""):
        attributes = 'label="' + label + '"' if label else ""
        leaf = ('<test-case id="1" name="Total" fullname="Demo.Checks.Total" methodname="Total" classname="Demo.Checks" '
                f'runstate="Runnable" result="{result}" {attributes}><failure><message>synthetic</message>'
                f'<stack-trace>{stack}</stack-trace></failure><assertions><assertion result="Failed">'
                f'<message>synthetic</message><stack-trace>{stack}</stack-trace></assertion></assertions></test-case>')
        discovery = '<NUnitXml><test-run testcasecount="1">' + leaf + '</test-run></NUnitXml>'
        xml = (f'<test-run testcasecount="1" total="1" passed="{int(result == "Passed")}" failed="{int(result == "Failed")}" '
               f'skipped="{int(result == "Skipped")}" inconclusive="0" warnings="0" result="{result}">'
               + (f'<test-suite result="Failed" site="TearDown" label="Error" testcasecount="1" total="1" passed="1" failed="0" skipped="0" inconclusive="0" warnings="0"><failure><message>suite</message></failure>{leaf}</test-suite>'
                  if suite_failure else leaf) + '</test-run>')
        return discovery, xml, trx("Passed" if result == "Passed" else "NotExecuted" if result == "Skipped" else "Failed")

    def test_nunit_uses_full_native_names_and_body_assertion_category(self):
        self.assertTrue(callable(getattr(self.runner, "reconcile_nunit", None)), "Native NUnit evidence is missing")
        report = self.runner.reconcile_nunit("tests/Demo.csproj", "net8.0", *self.nunit())
        self.assertEqual(report["collected"], ["tests/Demo.csproj|net8.0|Demo.Checks.Total"])
        self.assertEqual(report["results"][0]["exception"], "AssertionError")
        self.assertEqual(report["results"][0]["native_failure_category"], "nunit-assertion")
        self.assertNotIn("native_exception_types", report["results"][0])

    def test_nunit_setup_runtime_and_suite_cleanup_are_not_red(self):
        self.assertTrue(callable(getattr(self.runner, "reconcile_nunit", None)), "Native NUnit evidence is missing")
        for label, stack in [("Error", "at Demo.Checks.Total()"), ("", "at Demo.Checks.SetUp()")]:
            with self.subTest(label=label, stack=stack):
                report = self.runner.reconcile_nunit("tests/Demo.csproj", "net8.0", *self.nunit(label=label, stack=stack))
                self.assertEqual(report["results"][0]["status"], "error")
        with self.assertRaises(self.runner.DotnetError):
            self.runner.reconcile_nunit("tests/Demo.csproj", "net8.0", *self.nunit(result="Passed", suite_failure="yes"))

    def test_nunit_inventories_and_skip_remain_explicit(self):
        self.assertTrue(callable(getattr(self.runner, "reconcile_nunit", None)), "Native NUnit evidence is missing")
        evidence = self.nunit(result="Skipped", label="Ignored")
        self.assertEqual(self.runner.reconcile_nunit("tests/Demo.csproj", "net8.0", *evidence)["results"][0]["status"], "skipped")
        discovery, xml, native_trx = self.nunit()
        with self.assertRaises(self.runner.DotnetError):
            self.runner.reconcile_nunit("tests/Demo.csproj", "net8.0", discovery.replace("Demo.Checks.Total", "Demo.Checks.Other"), xml, native_trx)


class DotnetSetupTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((SCRIPTS / "dotnet_setup.py").is_file(), "Native .NET setup is missing")
        loader = importlib.util.spec_from_file_location("native_dotnet_setup", SCRIPTS / "dotnet_setup.py")
        self.setup = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.setup)
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-dotnet-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for relative in ("src/Demo/Demo.csproj", "tests/Demo.Tests/Demo.Tests.csproj", "Directory.Packages.props", "NuGet.config"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<Project />", encoding="utf-8")

    def metadata(self, project, tfm=None, *, root=None):
        is_test = "Tests" in project.name
        return {"Properties": {"TargetFramework": tfm or "net8.0", "TargetFrameworks": "", "IsTestProject": str(is_test).lower(),
                "EnableMSTestRunner": "false", "UseMicrosoftTestingPlatformRunner": "false", "TestingPlatformDotnetTestSupport": "false",
                "BaseOutputPath": "bin/", "BaseIntermediateOutputPath": "obj/", "MSBuildProjectExtensionsPath": str(project.parent / "obj")},
                "Items": {"PackageReference": ([{"Identity": "xunit", "Version": "2.9.3"},
                        {"Identity": "xunit.runner.visualstudio", "Version": "3.0.0"},
                        {"Identity": "Microsoft.NET.Test.Sdk", "Version": "17.14.1"}] if is_test else []),
                          "PackageVersion": [], "Compile": [], "ProjectReference": [], "None": [], "Content": []}}

    def configure(self):
        with mock.patch.object(self.setup, "evaluate", side_effect=self.metadata), mock.patch.object(
                self.setup, "sdk_identity", return_value={"executable": "fixture-dotnet", "sha256": "a" * 64, "version": "10.0.301"}, create=True):
            return self.setup.configure(self.root)

    def test_setup_builds_project_ownership_and_exact_generated_exclusions(self):
        config = self.configure()
        self.assertEqual(config["source_roots"], ["src/Demo"])
        self.assertEqual(config["test_roots"], ["tests/Demo.Tests"])
        self.assertEqual(set(config["generated_roots"]), {"src/Demo/bin", "src/Demo/obj", "tests/Demo.Tests/bin", "tests/Demo.Tests/obj"})
        self.assertEqual(config["dotnet"]["modules"][0]["project"], "tests/Demo.Tests/Demo.Tests.csproj")
        self.assertIn("Directory.Packages.props", config["protected_paths"])
        self.assertIn("NuGet.config", config["protected_paths"])
        self.assertIn("{report}", config["runner"]["argv"])
        self.assertIn("--dotnet-test", config["runner"]["argv"])

    def test_old_adapter_mtp_and_custom_output_are_actionable_rejections(self):
        original = self.metadata
        for mode in ("old", "mtp", "output"):
            def altered(project, tfm=None, *, root=None):
                value = original(project, tfm)
                if mode == "old" and "Tests" in project.name:
                    value["Items"]["PackageReference"][1]["Version"] = "2.8.2"
                if mode == "mtp":
                    value["Properties"]["UseMicrosoftTestingPlatformRunner"] = "true"
                if mode == "output":
                    value["Properties"]["BaseOutputPath"] = "../../shared-build/"
                return value
            with self.subTest(mode=mode), mock.patch.object(self.setup, "evaluate", side_effect=altered):
                with self.assertRaises(self.setup.DotnetError):
                    self.setup.configure(self.root)

    def test_existing_config_is_never_overwritten(self):
        path = self.root / ".ai-tdd/config.json"
        path.parent.mkdir()
        path.write_text('{"existing": true}', encoding="utf-8")
        self.configure()
        self.assertEqual(path.read_text(encoding="utf-8"), '{"existing": true}')

    def test_preset_binds_creation_of_missing_build_and_test_inputs(self):
        config = self.configure()
        folder = self.root / ".ai-tdd"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        loader = importlib.util.spec_from_file_location("native_dotnet_controller", SCRIPTS / "tdd.py")
        controller_module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(controller_module)
        controller = controller_module.Controller(self.root)
        before = controller.protected(include_tests=False)
        controller.state = {"fixed": before}
        for relative in ("Directory.Build.targets", "global.json", ".editorconfig", "packages.lock.json",
                         "src/Directory.Build.props", "src/Directory.Packages.props", "src/NuGet.config",
                         "src/Demo/Directory.Build.targets", "src/Demo/packages.lock.json",
                         "tests/xunit.runner.json", "tests/Demo.Tests/xunit.runner.json"):
            with self.subTest(relative=relative):
                path = self.root / relative
                self.assertFalse(path.exists())
                path.write_text("synthetic new configuration", encoding="utf-8")
                try:
                    self.assertTrue(before != controller.protected(include_tests=False),
                                    "Creating a preset input must change the protected fingerprint")
                    self.assertIn(relative, config["protected_paths"])
                    self.assertIsNone(before[relative])
                    with self.assertRaisesRegex(controller_module.TddError, "Changed protected artifacts"):
                        controller.fixed(include_tests=False)
                finally:
                    path.unlink()

    def test_setup_freezes_actual_sdk_and_runner_rejects_sdk_drift(self):
        config = self.configure()
        self.assertEqual(config["dotnet"].get("sdk"), {"executable": "fixture-dotnet", "sha256": "a" * 64, "version": "10.0.301"})
        folder = self.root / ".ai-tdd"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        changed = copy.deepcopy(config)
        changed["dotnet"]["sdk"]["version"] = "10.0.302"
        loader = importlib.util.spec_from_file_location("native_dotnet_sdk_runner", SCRIPTS / "dotnet_runner.py")
        runner = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(runner)
        with mock.patch.object(runner.SETUP, "configure", return_value=changed), self.assertRaises(runner.DotnetError):
            runner.run(self.root, folder / "fresh.json")
        self.assertFalse((folder / "fresh.json").exists())

    def test_linked_compile_is_allowed_only_from_an_explicit_source_project(self):
        original = self.metadata
        source = self.root / "src/Demo/Fee.cs"
        source.write_text("namespace Demo;", encoding="utf-8")
        for target, valid in [(source, True), (self.root / "tests/Unowned/Helper.cs", False),
                              (self.root.parent / "external.cs", False), (self.root / ".ai-tdd/private.cs", False)]:
            def linked(project, tfm=None, *, root=None):
                value = original(project, tfm)
                if "Tests" in project.name:
                    value["Items"]["Compile"] = [{"Identity": str(target), "FullPath": str(target)}]
                return value
            with self.subTest(target=target), mock.patch.object(self.setup, "evaluate", side_effect=linked), mock.patch.object(
                    self.setup, "sdk_identity", return_value={"executable": "fixture", "sha256": "a" * 64, "version": "10.0.301"}):
                if valid:
                    self.assertEqual(self.setup.configure(self.root)["source_roots"], ["src/Demo"])
                else:
                    with self.assertRaises(self.setup.DotnetError):
                        self.setup.configure(self.root)

    def test_source_project_cannot_link_a_test_owned_compile_input(self):
        original = self.metadata
        def linked(project, tfm=None, *, root=None):
            value = original(project, tfm)
            if "Tests" not in project.name:
                value["Items"]["Compile"] = [{"Identity": str(self.root / "tests/Demo.Tests/Checks.cs")}]
            return value
        with mock.patch.object(self.setup, "evaluate", side_effect=linked), self.assertRaises(self.setup.DotnetError):
            self.setup.configure(self.root)

    def test_msbuild_default_backslashes_are_owned_paths_on_posix(self):
        class PosixModel(PurePosixPath):
            def resolve(self):
                return PosixModel(posixpath.normpath(str(self)))
        project = PosixModel("/fixture/src/Demo/Demo.csproj")
        metadata = {"Properties": {"BaseOutputPath": "bin\\", "OutputPath": "bin\\Debug\\net8.0\\",
                    "BaseIntermediateOutputPath": "obj\\", "IntermediateOutputPath": "obj\\Debug\\net8.0\\",
                    "MSBuildProjectExtensionsPath": "/fixture/src/Demo/obj/"}}
        try:
            self.setup._output_paths(project, metadata)
        except self.setup.DotnetError as error:
            self.fail("Default SDK output paths must remain owned on POSIX: " + str(error))
        for value in ("..\\outside\\", "bin\\..\\..\\outside\\"):
            metadata["Properties"]["OutputPath"] = value
            with self.subTest(value=value), self.assertRaises(self.setup.DotnetError):
                self.setup._output_paths(project, metadata)

    def test_msbuild_package_and_item_backslashes_are_normalized_consistently(self):
        self.assertTrue(callable(getattr(self.setup, "msbuild_path", None)), "MSBuild path normalization is missing")
        self.assertEqual(self.setup.msbuild_path("obj\\Debug\\net8.0\\"), "obj/Debug/net8.0/")
        self.assertEqual(self.setup.msbuild_path("..\\..\\src\\Demo\\Demo.csproj"), "../../src/Demo/Demo.csproj")

    def test_windows_transitive_testhost_content_requires_exact_restored_provenance(self):
        cache_temp = tempfile.TemporaryDirectory(prefix="ai-tdd-dotnet-package-contract-")
        self.addCleanup(cache_temp.cleanup)
        cache = Path(cache_temp.name).resolve()
        project = self.root / "tests/Demo.Tests/Demo.Tests.csproj"
        assets_path = project.parent / "obj/project.assets.json"
        assets_path.parent.mkdir()
        host = "Microsoft.TestPlatform.TestHost/17.14.1"
        package = cache / host.lower()
        defining_relative = "build/net8.0/Microsoft.TestPlatform.TestHost.props"
        content_relatives = ["build/net8.0/x64/testhost.exe", "build/net8.0/x64/testhost.dll"]
        for relative in [defining_relative, *content_relatives]:
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic package asset", encoding="utf-8")
        assets = {"version": 4, "packageFolders": {str(cache) + "/": {}},
                  "project": {"restore": {"projectPath": str(project), "packagesPath": str(cache)}},
                  "targets": {"net8.0": {
                      "Microsoft.NET.Test.Sdk/17.14.1": {"type": "package", "dependencies": {"Microsoft.TestPlatform.TestHost": "17.14.1"}},
                      host: {"type": "package", "build": {defining_relative: {}}}}},
                  "libraries": {host: {"type": "package", "path": host.lower(), "files": [defining_relative, *content_relatives]}}}
        original = self.metadata

        def metadata(current, tfm=None, *, root=None):
            value = original(current, tfm)
            if current == project:
                value["Properties"].update(NuGetPackageRoot=str(cache), ProjectAssetsFile=str(assets_path))
                value["Items"]["Content"] = [
                    {"Identity": str(package / relative), "FullPath": str(package / relative),
                     "DefiningProjectFullPath": str(package / defining_relative), "Link": Path(relative).name}
                    for relative in content_relatives]
            return value

        sdk = {"executable": "fixture", "sha256": "a" * 64, "version": "10.0.301"}
        for schema in (3, 4):
            assets["version"] = schema
            assets_path.write_text(json.dumps(assets), encoding="utf-8")
            with self.subTest(schema=schema), mock.patch.object(self.setup, "evaluate", side_effect=metadata), mock.patch.object(
                    self.setup, "sdk_identity", return_value=sdk):
                try:
                    config = self.setup.configure(self.root)
                except self.setup.DotnetError as error:
                    self.fail("Standard Windows test-host package assets need exact transitive provenance: " + str(error))
        self.assertFalse(any("testhost" in relative.lower() for relative in config["protected_paths"]))
        for mode in ("unlisted-file", "unlisted-import", "different-import", "different-version", "different-tfm",
                     "missing-sdk-dependency", "outside-assets", "different-owner", "private-content", "wrong-cache"):
            altered = copy.deepcopy(assets)
            current_metadata = metadata(project)
            if mode == "unlisted-file":
                altered["libraries"][host]["files"].remove(content_relatives[0])
            elif mode == "unlisted-import":
                altered["targets"]["net8.0"][host]["build"] = {}
            elif mode == "different-import":
                current_metadata["Items"]["Content"][0]["DefiningProjectFullPath"] = str(project)
            elif mode == "different-version":
                altered["libraries"][host]["path"] = "microsoft.testplatform.testhost/17.14.0"
            elif mode == "different-tfm":
                altered["targets"]["net10.0"] = altered["targets"].pop("net8.0")
            elif mode == "missing-sdk-dependency":
                altered["targets"]["net8.0"]["Microsoft.NET.Test.Sdk/17.14.1"]["dependencies"] = {}
            elif mode == "outside-assets":
                outside = cache / "project.assets.json"
                outside.write_text(json.dumps(altered), encoding="utf-8")
                current_metadata["Properties"]["ProjectAssetsFile"] = str(outside)
            elif mode == "different-owner":
                altered["project"]["restore"]["projectPath"] = str(self.root / "src/Demo/Demo.csproj")
            elif mode == "private-content":
                current_metadata["Items"]["Content"][0]["FullPath"] = str(cache / "private/testhost.exe")
            elif mode == "wrong-cache":
                altered["project"]["restore"]["packagesPath"] = str(cache / "different-cache")
            assets_path.write_text(json.dumps(altered), encoding="utf-8")

            def rejected(current, tfm=None, *, root=None):
                return current_metadata if current == project else original(current, tfm)

            with self.subTest(mode=mode), mock.patch.object(self.setup, "evaluate", side_effect=rejected), mock.patch.object(
                    self.setup, "sdk_identity", return_value=sdk):
                with self.assertRaises(self.setup.DotnetError):
                    self.setup.configure(self.root)


if __name__ == "__main__":
    unittest.main()
