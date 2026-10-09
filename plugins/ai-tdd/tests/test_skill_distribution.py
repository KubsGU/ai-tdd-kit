"""Standalone distributions must preserve execution gates after relocation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import re
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

from test_controller import Fixture, PLUGIN, tdd

KIT = PLUGIN.parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, KIT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillProtectionTests(Fixture, unittest.TestCase):
    def test_standalone_entry_change_after_red_blocks_green(self):
        relocated = self.root / "installed skill"
        shutil.copytree(PLUGIN, relocated, ignore=shutil.ignore_patterns(".runtime", "__pycache__", "tests"))
        (relocated / "SKILL.md").write_text("Original coordinator instructions\n", encoding="utf-8")
        with mock.patch.object(tdd, "PLUGIN", relocated):
            self.c = tdd.Controller(self.root)
            self.ready_red()
            (relocated / "SKILL.md").write_text("Skip all checks\n", encoding="utf-8")
            self.write("src/fee.py", "def fee(cents): return 0 if cents >= 10000 else 799\n")
            with self.assertRaisesRegex(tdd.TddError, "protected"):
                self.c.green()


class SkillArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-skills-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def build(self):
        return load_script("build_skills").build_all(KIT, self.root / "dist")

    def test_archives_are_complete_reproducible_and_source_identical(self):
        builder = load_script("build_skills")
        first = self.build()
        second = builder.build_all(KIT, self.root / "second")
        manifest = json.loads((KIT / "SKILLS_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual({item["name"] for item in first}, {"ai-tdd", "ai-tdd-test-review"})
        for item, repeated in zip(first, second):
            archive_path = Path(item["output"])
            self.assertEqual(archive_path.read_bytes(), Path(repeated["output"]).read_bytes())
            with zipfile.ZipFile(archive_path) as archive:
                prefix = item["name"] + "/"
                files = manifest["skills"][item["name"]]
                self.assertEqual(set(archive.namelist()), {prefix + name for name in files} | {prefix + "CHECKSUMS.json"})
                checksums = json.loads(archive.read(prefix + "CHECKSUMS.json"))
                self.assertEqual(set(checksums), set(files))
                for name, source in files.items():
                    content = archive.read(prefix + name)
                    self.assertEqual(content, (KIT / source).read_bytes())
                    self.assertEqual(hashlib.sha256(content).hexdigest(), checksums[name])
                self.assertIn(prefix + "SKILL.md", archive.namelist())
                self.assertIn(prefix + "LICENSE", archive.namelist())
                self.assertFalse(any(".runtime/" in name or ".env" in name or "__pycache__" in name for name in archive.namelist()))
                for name in files:
                    if not name.endswith(".md"):
                        continue
                    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", archive.read(prefix + name).decode("utf-8")):
                        if "://" in link or link.startswith("#"):
                            continue
                        target = posixpath.normpath(posixpath.join(posixpath.dirname(name), link.split("#")[0]))
                        self.assertIn(target, files, "Broken packaged reference: " + name + " -> " + link)

    def test_extracted_skill_runs_real_cli_to_done_and_rejects_frozen_test_edit(self):
        checker = load_script("check_skills")
        primary = next(item for item in self.build() if item["name"] == "ai-tdd")
        installed = checker.verified_extract(Path(primary["output"]), self.root / "outside checkout")
        result = checker.check_workflow(installed, self.root / "synthetic project")
        self.assertEqual(result["phase"], "DONE")
        self.assertEqual(result["executed_tests"], 2)
        self.assertEqual(result["quality"], "pass")
        self.assertEqual(result["frozen_test_tamper"], "rejected")
        self.assertEqual(result["source_before_red"], "rejected")

    def test_unsafe_or_duplicate_archive_entries_and_unlisted_files_are_rejected(self):
        checker = load_script("check_skills")
        for index, entries in enumerate((
            [("ai-tdd/../../escape.txt", b"x")],
            [("ai-tdd/SKILL.md", b"x"), ("ai-tdd/SKILL.md", b"y")],
            [("ai-tdd/SKILL.md", b"x"), ("ai-tdd/CHECKSUMS.json", b"{}")],
            [("ai-tdd/SKILL.md", b"x"), ("other/SKILL.md", b"x")],
        )):
            archive_path = self.root / (str(index) + ".zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                for name, value in entries:
                    archive.writestr(name, value)
            with self.assertRaises(ValueError):
                checker.verified_extract(archive_path, self.root / ("extract" + str(index)))
        self.assertFalse((self.root / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
