"""Node launch helper preserves model policy and only changes the child env."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "scripts/launch_claude.cjs"
NODE = shutil.which("node")
FLAGS = ["--preserve-symlinks", "--preserve-symlinks-main"]


@unittest.skipUnless(NODE, "Node.js is required for the launcher")
class NodeLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-node-launch-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / "project with spaces"
        self.project.mkdir()

    def api(self, body, **values):
        self.assertTrue(LAUNCHER.is_file(), "Node Claude launcher has not been implemented")
        script = ("const api=require(" + json.dumps(str(LAUNCHER)) + ");const input=JSON.parse(process.argv[1]);"
                  "try{" + body + "}catch(error){process.stdout.write(JSON.stringify({error:error.message}));process.exitCode=1;}")
        result = subprocess.run([NODE, *FLAGS, "-e", script, json.dumps({"project": str(self.project), **values})],
                                capture_output=True, text=True, timeout=15)
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)

    def test_environment_override_preserves_parent_and_ordinary_settings(self):
        parent = {"DISABLE_PROMPT_CACHING": "1", "DISABLE_PROMPT_CACHING_OPUS": "1",
                  "DISABLE_PROMPT_CACHING_SONNET": "1", "DISABLE_PROMPT_CACHING_HAIKU": "1",
                  "DISABLE_PROMPT_CACHING_FABLE": "1", "CLAUDE_CODE_SUBAGENT_MODEL": "haiku",
                  "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "0",
                  "ANTHROPIC_MODEL": "ordinary-parent-choice", "CLAUDE_SETTINGS": "ordinary-settings"}
        result, value = self.api("const original=JSON.stringify(input.parent);const child=api.launchEnvironment(input.parent);"
                                 "process.stdout.write(JSON.stringify({child,parent:input.parent,unchanged:original===JSON.stringify(input.parent)}));",
                                 parent=parent)
        self.assertEqual(result.returncode, 0, value)
        self.assertTrue(value["unchanged"])
        self.assertEqual(value["parent"], parent)
        self.assertEqual(value["child"], {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
                                           "ANTHROPIC_MODEL": "ordinary-parent-choice", "CLAUDE_SETTINGS": "ordinary-settings"})

    def test_default_parse_requests_sonnet_and_inherits_effort(self):
        result, value = self.api("process.stdout.write(JSON.stringify(api.parse(['--project',input.project])));")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value["model"], "sonnet")
        self.assertIsNone(value["effort"])
        self.assertEqual(Path(value["project"]), self.project)

    def test_explicit_model_effort_and_spaced_claude_options_are_preserved(self):
        result, value = self.api("const parsed=api.parse(['--project='+input.project,'--model','opus','--effort','high',"
                                 "'--','--add-dir','directory with spaces','a;b','$(touch marker)']);"
                                 "process.stdout.write(JSON.stringify({parsed,argv:api.launchArgv('native claude.exe',"
                                 "parsed.model,parsed.effort,parsed.extra)}));")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value["argv"], ["native claude.exe", "--model", "opus", "--effort", "high", "--add-dir",
                                         "directory with spaces", "a;b", "$(touch marker)"])

    def test_fallback_and_duplicate_model_effort_cannot_enter_passthrough(self):
        for option in ("--model", "--model=haiku", "--effort", "--effort=max", "--fallback-model", "--fallback-model=haiku"):
            with self.subTest(option=option):
                result, value = self.api("process.stdout.write(JSON.stringify(api.parse(['--project',input.project,"
                                         "'--',input.option,'haiku'])));", option=option)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fallback", value["error"].lower())

    def test_nonexistent_project_is_rejected_before_launch(self):
        result, value = self.api("process.stdout.write(JSON.stringify(api.parse(['--project',input.project+'/missing'])));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing directory", value["error"])

    def test_invalid_effort_and_missing_values_are_rejected(self):
        for args in (["--effort", "automatic"], ["--model"], ["--project"], ["--unknown"]):
            with self.subTest(args=args):
                result, value = self.api("process.stdout.write(JSON.stringify(api.parse(input.args)));", args=args)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(value["error"])

    def test_windows_cmd_only_install_requires_native_cli(self):
        command = self.project / "claude.cmd"
        command.write_text("@echo legacy\n", encoding="utf-8")
        result, value = self.api("process.stdout.write(JSON.stringify({executable:api.findClaude({"
                                 "platform:'win32',env:{PATH:input.project}})}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("native", value["error"].lower())

    def test_windows_native_executable_is_resolved_without_shell_wrappers(self):
        native = self.project / "claude.exe"
        native.write_bytes(b"native-cli-fixture")
        (self.project / "claude.cmd").write_text("@echo legacy\n", encoding="utf-8")
        result, value = self.api("process.stdout.write(JSON.stringify({executable:api.findClaude({"
                                 "platform:'win32',env:{PATH:input.project}})}));")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(Path(value["executable"]), native)

    def test_real_dry_run_needs_neither_python_nor_claude_on_path(self):
        self.assertTrue(LAUNCHER.is_file(), "Node Claude launcher has not been implemented")
        result = subprocess.run([NODE, *FLAGS, str(LAUNCHER), "--project", str(self.project), "--dry-run"],
                                env={**os.environ, "PATH": ""}, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value, {"project": str(self.project), "requested_model": "sonnet", "worker_model": "inherit",
                                 "effort": "Claude configuration", "foreground_workers": True,
                                 "native_prompt_caching": "not disabled by launch environment", "parent_settings_changed": False})

    def test_main_spawns_interactive_native_process_with_child_environment(self):
        native = self.project / "claude.exe"
        native.write_bytes(b"native-cli-fixture")
        result, value = self.api("const parent={PATH:input.project,DISABLE_PROMPT_CACHING:'1'};let launched;"
                                 "const status=api.main(['--project',input.project,'--model','opus','--','prompt with spaces'],{"
                                 "platform:'win32',env:parent,spawn:(executable,args,options)=>{"
                                 "launched={executable,args,options};return {status:7}}});"
                                 "process.stdout.write(JSON.stringify({status,launched,parent}));")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value["status"], 7)
        self.assertEqual(value["launched"]["args"], ["--model", "opus", "prompt with spaces"])
        self.assertEqual(value["launched"]["options"]["cwd"], str(self.project))
        self.assertEqual(value["launched"]["options"]["stdio"], "inherit")
        self.assertFalse(value["launched"]["options"]["shell"])
        self.assertFalse(value["launched"]["options"]["windowsHide"])
        self.assertEqual(value["parent"], {"PATH": str(self.project), "DISABLE_PROMPT_CACHING": "1"})
        self.assertEqual(value["launched"]["options"]["env"], {"PATH": str(self.project), "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"})


if __name__ == "__main__":
    unittest.main()
