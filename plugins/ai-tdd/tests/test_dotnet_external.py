"""Absent editor links never expand project ownership or hide later inputs."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import test_dotnet_runner as fixtures


class ExternalAbsentInputTests(unittest.TestCase):
    metadata = fixtures.DotnetSetupTests.metadata

    def setUp(self):
        loader = importlib.util.spec_from_file_location("external_dotnet_setup", fixtures.SCRIPTS / "dotnet_setup.py")
        self.setup = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.setup)
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-absent-link-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo"
        self.source = self.root / "src/Demo/Demo.csproj"
        self.test = self.root / "tests/Demo.Tests/Demo.Tests.csproj"
        for project in (self.source, self.test):
            project.parent.mkdir(parents=True)
            project.write_text('<Project><ItemGroup><Content Include="../../../.dockerignore" '
                               'Link=".dockerignore" /></ItemGroup></Project>', encoding="utf-8")
        self.absent = self.base / ".dockerignore"
        self.kind = "Content"
        self.item = self.linked(self.absent)

    def linked(self, path, project=None):
        project = project or self.source
        return {"Identity": os.path.relpath(path, project.parent), "FullPath": str(path),
                "DefiningProjectFullPath": str(project), "Link": path.name,
                "CopyToOutputDirectory": "", "CopyToPublishDirectory": ""}

    def configure(self, *, include=True, duplicate=False):
        def evaluated(project, tfm=None, *, root=None):
            value = self.metadata(project, tfm, root=root)
            if project == self.source and include:
                value["Items"][self.kind] = [dict(self.item)]
                if duplicate:
                    value["Items"]["None"] = [dict(self.item)]
            return value

        with mock.patch.object(self.setup, "evaluate", side_effect=evaluated), mock.patch.object(
                self.setup, "sdk_identity", return_value={"executable": "fixture", "sha256": "a" * 64, "version": "10.0.301"}):
            return self.setup.configure(self.root)

    def test_absent_project_owned_editor_link_is_recorded_without_project_edits(self):
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        for kind in ("Content", "None"):
            self.kind = kind
            with self.subTest(kind=kind):
                config = self.configure()
                self.assertEqual(config["dotnet"]["external_absent_inputs"], [str(self.absent)])
                self.assertEqual(config["dotnet"]["projects"], ["src/Demo/Demo.csproj", "tests/Demo.Tests/Demo.Tests.csproj"])
                self.assertEqual(len(config["dotnet"]["modules"]), 1)
                self.assertEqual(before, {name: Path(name).read_bytes() for name in before})
                self.assertFalse((self.root / ".ai-tdd").exists())

    def test_normal_configuration_is_unchanged_and_duplicate_links_are_recorded_once(self):
        self.assertNotIn("external_absent_inputs", self.configure(include=False)["dotnet"])
        self.assertEqual(self.configure(duplicate=True)["dotnet"]["external_absent_inputs"], [str(self.absent)])
        self.item.update(CopyToOutputDirectory="Never", CopyToPublishDirectory="never")
        self.assertEqual(self.configure()["dotnet"]["external_absent_inputs"], [str(self.absent)])

    def test_newly_existing_external_link_is_rejected_by_reconfiguration_and_snapshot(self):
        config = self.configure()
        paths = config["dotnet"]["external_absent_inputs"]
        self.assertEqual(self.setup.external_absent_snapshot(self.root, paths), {str(self.absent): "absent"})
        self.absent.write_text("new input must invalidate evidence", encoding="utf-8")
        with self.assertRaises(self.setup.DotnetError):
            self.configure()
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("Do not read appeared external content")):
            with self.assertRaises(self.setup.DotnetError):
                self.setup.external_absent_snapshot(self.root, paths)

    def test_missing_link_false_identity_or_wrong_defining_project_do_not_expand_ownership(self):
        baseline = dict(self.item)
        alternatives = [("Link", ""), ("Link", "../outside.txt"), ("Link", str(self.absent)),
                        ("Identity", "../../../different.txt"), ("Identity", str(self.absent)),
                        ("FullPath", str(self.base / "different.txt")),
                        ("DefiningProjectFullPath", str(self.test)),
                        ("DefiningProjectFullPath", str(self.source.parent / "Directory.Build.props")),
                        ("DefiningProjectFullPath", "")]
        for key, value in alternatives:
            self.item = {**baseline, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(self.setup.DotnetError):
                self.configure()
        self.item = baseline
        del self.item["Link"]
        with self.assertRaises(self.setup.DotnetError):
            self.configure()

    def test_copy_to_output_and_publish_controls_must_explicitly_disable_copy(self):
        baseline = dict(self.item)
        for key in ("CopyToOutputDirectory", "CopyToPublishDirectory"):
            for value in ("Always", "PreserveNewest", "IfDifferent", "false", True, None):
                self.item = {**baseline, key: value}
                with self.subTest(key=key, value=value), self.assertRaises(self.setup.DotnetError):
                    self.configure()

    def test_existing_outside_content_and_missing_compile_remain_unsupported(self):
        self.absent.write_text("already existing", encoding="utf-8")
        with self.assertRaises(self.setup.DotnetError):
            self.configure()
        self.absent.unlink()
        self.kind = "Compile"
        with self.assertRaises(self.setup.DotnetError):
            self.configure()

    def test_absent_private_source_build_and_runner_inputs_are_never_accepted(self):
        denied = [".env", ".env.local", ".git/config", ".ai-tdd/config.json", ".ssh/id_rsa",
                  ".aws/credentials", "App.cs", "Shared.props", "Shared.targets", "Project.csproj",
                  "coverage.runsettings", "xunit.runner.json", "Directory.Build.props", "global.json",
                  "NuGet.config", "tool.py", "tool.ps1", "config.json"]
        for relative in denied:
            path = self.base / relative
            self.item = self.linked(path)
            with self.subTest(path=relative), self.assertRaises(self.setup.DotnetError):
                self.configure()
            with self.subTest(snapshot=relative), self.assertRaises(self.setup.DotnetError):
                self.setup.external_absent_snapshot(self.root, [str(path)])
        self.item = self.linked(self.absent)
        for link in ("Shared.cs", ".git/config", "coverage.runsettings"):
            self.item["Link"] = link
            with self.subTest(link=link), self.assertRaises(self.setup.DotnetError):
                self.configure()

    def test_snapshot_rejects_malformed_duplicate_in_root_and_noncanonical_paths(self):
        malformed = [None, str(self.absent), [None], [1], [""], ["relative.txt"],
                     [str(self.root / "missing.txt")], [str(self.absent), str(self.absent)],
                     [str(self.base / "x/../missing.txt")], [str(self.base / "missing.txt") + "\x00"],
                     [str(self.base / "missing.txt") + "\n"], [str(self.base / "missing.txt") + "\ud800"],
                     [str(self.base / ("x" * 4097))]]
        for paths in malformed:
            with self.subTest(paths=paths), self.assertRaises(self.setup.DotnetError):
                self.setup.external_absent_snapshot(self.root, paths)
        self.assertEqual(self.setup.external_absent_snapshot(self.root, []), {})

    def test_snapshot_is_deterministic_and_has_no_project_count_limit(self):
        paths = [str(self.base / ("missing-" + str(index) + ".txt")) for index in range(200)]
        snapshot = self.setup.external_absent_snapshot(self.root, list(reversed(paths)))
        self.assertEqual(snapshot, dict.fromkeys(sorted(paths), "absent"))
        self.assertEqual(list(snapshot), sorted(paths))

    def test_snapshot_rejects_directory_file_device_or_permission_denied_ancestors(self):
        folder = self.base / "directory"
        folder.mkdir()
        with self.assertRaises(self.setup.DotnetError):
            self.setup.external_absent_snapshot(self.root, [str(folder)])
        file = self.base / "not-a-directory"
        file.write_text("regular ancestor", encoding="utf-8")
        with self.assertRaises(self.setup.DotnetError):
            self.setup.external_absent_snapshot(self.root, [str(file / "missing.txt")])
        with mock.patch.object(Path, "lstat", side_effect=PermissionError("synthetic inaccessible ancestor")):
            with self.assertRaises(self.setup.DotnetError):
                self.setup.external_absent_snapshot(self.root, [str(self.absent)])
        with self.assertRaises(self.setup.DotnetError):
            self.setup.external_absent_snapshot(self.root, [str(self.base / "NUL")])

    def directory_link(self, alias, target):
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                self.skipTest("Directory symlink privilege unavailable")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)],
                                    capture_output=True, encoding="utf-8")
            if result.returncode:
                self.skipTest("Directory symlink/junction privilege unavailable")

    def test_existing_and_new_symlink_or_junction_ancestors_are_rejected(self):
        target = self.base / "real-directory"
        target.mkdir()
        alias = self.base / "directory-alias"
        path = alias / "missing.txt"
        self.assertEqual(self.setup.external_absent_snapshot(self.root, [str(path)]), {str(path): "absent"})
        self.directory_link(alias, target)
        self.item = self.linked(path)
        with self.assertRaises(self.setup.DotnetError):
            self.configure()
        with self.assertRaises(self.setup.DotnetError):
            self.setup.external_absent_snapshot(self.root, [str(path)])

    def test_dangling_leaf_and_ancestor_links_are_not_absence(self):
        for directory in (False, True):
            alias = self.base / ("dangling-folder" if directory else "dangling.txt")
            target = self.base / ("uncreated-folder" if directory else "uncreated.txt")
            try:
                alias.symlink_to(target, target_is_directory=directory)
            except OSError:
                self.skipTest("Dangling symlink privilege unavailable")
            path = alias / "missing.txt" if directory else alias
            self.item = self.linked(path)
            with self.subTest(directory=directory), self.assertRaises(self.setup.DotnetError):
                self.configure()
            with self.subTest(snapshot=directory), self.assertRaises(self.setup.DotnetError):
                self.setup.external_absent_snapshot(self.root, [str(path)])


if __name__ == "__main__":
    unittest.main()
