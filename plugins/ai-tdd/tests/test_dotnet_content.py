"""Restored package content provenance and repository-owned shared assets."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class DotnetContentTests(unittest.TestCase):
    def setUp(self):
        loader = importlib.util.spec_from_file_location("native_dotnet_content_setup", SCRIPTS / "dotnet_setup.py")
        self.setup = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.setup)
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-dotnet-content-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo"
        self.project = self.root / "tests/Demo.Tests/Demo.Tests.csproj"
        self.source = self.root / "src/Demo/Demo.csproj"
        for project in (self.project, self.source):
            project.parent.mkdir(parents=True)
            project.write_text("<Project />", encoding="utf-8")
        self.cache = self.base / "packages"
        self.identity = "Contoso.Content/1.2.3"
        self.package = self.cache / self.identity.lower()
        self.asset = "tools/data/settings.json"
        self.import_name = "buildTransitive/net8.0/Contoso.Content.props"
        self.assets_path = self.project.parent / "obj/project.assets.json"
        self.generated = self.assets_path.parent / (self.project.name + ".nuget.g.props")
        self.assets_path.parent.mkdir()
        self.generated.write_text("<Project />", encoding="utf-8")
        for relative in (self.asset, self.import_name):
            path = self.package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic restored asset", encoding="utf-8")
        self.packages = {"contoso.parent": "5.0.0"}
        self.assets = {
            "version": 4, "packageFolders": {str(self.cache) + "/": {}},
            "project": {"restore": {"projectPath": str(self.project), "packagesPath": str(self.cache)},
                        "frameworks": {"net8.0": {"targetAlias": "net8.0"}}},
            "targets": {"net8.0": {
                "Contoso.Parent/5.0.0": {"type": "package", "dependencies": {"Contoso.Content": "1.2.3"}},
                self.identity: {"type": "package", "build": {self.import_name: {}}}}},
            "libraries": {self.identity: {"type": "package", "path": self.identity.lower(),
                                          "files": [self.asset, self.import_name]}}}
        self.metadata = {"Properties": {"TargetFramework": "net8.0", "NuGetPackageRoot": str(self.cache),
                                        "ProjectAssetsFile": str(self.assets_path)}}
        self.item = {"FullPath": str(self.package / self.asset),
                     "DefiningProjectFullPath": str(self.package / self.import_name)}

    def accepted(self):
        self.assets_path.write_text(json.dumps(self.assets), encoding="utf-8")
        return self.setup._package_input(self.metadata, self.packages, Path(self.item["FullPath"]),
                                         self.item, project=self.project)

    def content_file(self, kind="Content"):
        self.assets["targets"]["net8.0"][self.identity] = {
            "type": "package", "contentFiles": {self.asset: {"buildAction": kind, "codeLanguage": "any"}}}
        self.item.update(DefiningProjectFullPath=str(self.generated), NuGetPackageId="Contoso.Content",
                         NuGetPackageVersion="1.2.3", NuGetItemType=kind)

    def test_exact_transitive_build_asset_is_accepted_for_both_restore_schemas(self):
        for schema in (3, 4):
            self.assets["version"] = schema
            with self.subTest(schema=schema):
                self.assertTrue(self.accepted())

    def test_exact_buildtransitive_entry_is_supported(self):
        selected = self.assets["targets"]["net8.0"][self.identity]
        selected["buildTransitive"] = selected.pop("build")
        self.assertTrue(self.accepted())

    def test_generated_contentfiles_accept_content_and_none(self):
        for kind in ("Content", "None"):
            self.content_file(kind)
            with self.subTest(kind=kind):
                self.assertTrue(self.accepted())

    def test_recorded_fallback_cache_has_exact_package_ownership(self):
        fallback = self.base / "fallback"
        # Move only this synthetic package, preserving the primary restore cache.
        (fallback / "contoso.content").mkdir(parents=True, exist_ok=True)
        self.package.rename(fallback / self.identity.lower())
        self.package = fallback / self.identity.lower()
        self.assets["packageFolders"][str(fallback) + "/"] = {}
        self.item.update(FullPath=str(self.package / self.asset),
                         DefiningProjectFullPath=str(self.package / self.import_name))
        self.assertTrue(self.accepted())

    def test_v3_target_alias_selects_only_the_matching_normalized_framework(self):
        self.assets["version"] = 3
        self.metadata["Properties"]["TargetFramework"] = "net8.0-windows"
        self.assets["project"]["frameworks"] = {"net8.0-windows7.0": {"targetAlias": "net8.0-windows"}}
        self.assets["targets"]["net8.0-windows7.0"] = self.assets["targets"].pop("net8.0")
        self.assertTrue(self.accepted())
        self.metadata["Properties"]["TargetFramework"] = "net9.0-windows"
        self.assertFalse(self.accepted())

    def test_orphan_package_is_not_a_restored_dependency_of_direct_references(self):
        self.assets["targets"]["net8.0"]["Contoso.Parent/5.0.0"]["dependencies"] = {}
        self.assertFalse(self.accepted())

    def test_direct_dependency_root_requires_the_evaluated_exact_package_version(self):
        self.packages["contoso.parent"] = "5.0.1"
        self.assertFalse(self.accepted())
        self.packages["contoso.parent"] = "5.0"
        self.assertTrue(self.accepted())

    def test_transitive_package_through_explicit_project_reference_is_reachable(self):
        self.packages = {}
        referenced = "Demo/1.0.0"
        self.assets["targets"]["net8.0"][referenced] = {
            "type": "project", "dependencies": {"Contoso.Content": "1.2.3"}}
        self.assets["libraries"][referenced] = {"type": "project", "msbuildProject": "../../src/Demo/Demo.csproj"}
        self.metadata["Items"] = {"ProjectReference": [{"FullPath": str(self.source)}]}
        self.assertTrue(self.accepted())
        self.metadata["Items"]["ProjectReference"][0]["FullPath"] = str(self.root / "src/Unrelated/Unrelated.csproj")
        self.assertFalse(self.accepted())

    def test_package_asset_and_import_must_be_exact_listed_files(self):
        baseline = copy.deepcopy(self.assets)
        for relative in (self.asset, self.import_name):
            self.assets = copy.deepcopy(baseline)
            self.assets["libraries"][self.identity]["files"].remove(relative)
            with self.subTest(relative=relative):
                self.assertFalse(self.accepted())

    def test_import_must_be_selected_build_asset(self):
        self.assets["targets"]["net8.0"][self.identity]["build"] = {}
        self.assertFalse(self.accepted())

    def test_direct_reference_does_not_trust_unlisted_files_in_package_folder(self):
        self.packages = {"contoso.content": "1.2.3"}
        self.assets["libraries"][self.identity]["files"].remove(self.asset)
        self.assertFalse(self.accepted())

    def test_generated_contentfiles_require_matching_package_and_item_metadata(self):
        self.content_file()
        baseline = dict(self.item)
        for key, value in (("NuGetPackageId", "Contoso.Other"), ("NuGetPackageVersion", "1.2.4"),
                           ("NuGetItemType", "Compile"), ("NuGetItemType", "None")):
            self.item = {**baseline, key: value}
            with self.subTest(key=key, value=value):
                self.assertFalse(self.accepted())

    def test_generated_contentfiles_require_exact_project_generated_props(self):
        self.content_file()
        for defining in (self.project, self.source.parent / "obj/Demo.csproj.nuget.g.props",
                         self.generated.with_suffix(".targets")):
            self.item["DefiningProjectFullPath"] = str(defining)
            with self.subTest(defining=defining):
                self.assertFalse(self.accepted())

    def test_generated_contentfiles_require_selected_asset_and_matching_build_action(self):
        self.content_file()
        selected = self.assets["targets"]["net8.0"][self.identity]
        selected["contentFiles"][self.asset]["buildAction"] = "None"
        self.assertFalse(self.accepted())
        selected["contentFiles"] = {}
        self.assertFalse(self.accepted())

    def test_wrong_restore_owner_cache_version_and_framework_are_rejected(self):
        baseline = copy.deepcopy(self.assets)
        for mode in ("owner", "cache", "version", "framework", "unknown-schema", "unsafe-path"):
            self.assets = copy.deepcopy(baseline)
            if mode == "owner":
                self.assets["project"]["restore"]["projectPath"] = str(self.source)
            elif mode == "cache":
                self.assets["project"]["restore"]["packagesPath"] = str(self.base / "other")
            elif mode == "version":
                self.assets["libraries"][self.identity]["path"] = "contoso.content/1.2.4"
            elif mode == "framework":
                self.assets["targets"]["net9.0"] = self.assets["targets"].pop("net8.0")
            elif mode == "unknown-schema":
                self.assets["version"] = 99
            elif mode == "unsafe-path":
                self.assets["libraries"][self.identity]["path"] = "../private"
            with self.subTest(mode=mode):
                self.assertFalse(self.accepted())

    def test_user_authored_external_assets_are_rejected_even_when_package_is_restored(self):
        for path, defining in ((self.base / "shared/settings.json", self.package / self.import_name),
                               (self.package / self.asset, self.project)):
            self.item.update(FullPath=str(path), DefiningProjectFullPath=str(defining))
            with self.subTest(path=path, defining=defining):
                self.assertFalse(self.accepted())

    def test_shared_in_repository_content_is_protected_without_project_changes(self):
        shared = self.root / "shared/settings.json"
        shared.parent.mkdir()
        shared.write_text('{"synthetic": true}', encoding="utf-8")
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

        def evaluated(project, tfm=None, *, root=None):
            is_test = project == self.project
            return {"Properties": {"TargetFramework": "net8.0", "TargetFrameworks": "", "IsTestProject": str(is_test).lower()},
                    "Items": {"PackageReference": ([{"Identity": "xunit", "Version": "2.9.3"},
                        {"Identity": "xunit.runner.visualstudio", "Version": "3.0.0"},
                        {"Identity": "Microsoft.NET.Test.Sdk", "Version": "17.14.1"}] if is_test else []),
                        "Content": [{"FullPath": str(shared), "DefiningProjectFullPath": str(project)}]}}

        with mock.patch.object(self.setup, "evaluate", side_effect=evaluated), mock.patch.object(
                self.setup, "sdk_identity", return_value={"executable": "fixture", "sha256": "a" * 64, "version": "10.0.301"}):
            config = self.setup.configure(self.root)
        self.assertIn("shared/settings.json", config["protected_paths"])
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
