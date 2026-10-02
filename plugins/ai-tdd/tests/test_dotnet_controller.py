"""Preserve controller authority while adding native .NET setup/runtime paths."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest import mock
import unittest

from test_controller import Fixture, PLUGIN, tdd


class DotnetControllerTests(Fixture, unittest.TestCase):
    def test_native_setup_without_csharp_projects_returns_actionable_error(self):
        with self.assertRaisesRegex(tdd.TddError, 'No C# .csproj'):
            tdd.dotnet_configuration(self.root)

    def hook_without_python(self, tool='Read'):
        env = dict(os.environ, PATH='', AI_TDD_PYTHON=str(self.root / 'missing-python'))
        payload = {'cwd': str(self.root), 'tool_name': tool, 'tool_input': {'file_path': 'src/fee.py'}}
        return subprocess.run([shutil.which('node'), '--preserve-symlinks', '--preserve-symlinks-main',
                               str(PLUGIN / 'scripts/hook-launcher.cjs')], input=json.dumps(payload),
                              env=env, capture_output=True, encoding='utf-8', timeout=20)

    def test_inactive_hook_needs_no_python_and_does_not_download(self):
        result = self.hook_without_python()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_active_hook_missing_runtime_denies_without_downloading(self):
        self.c.begin()
        result = self.hook_without_python()
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual(decision['permissionDecision'], 'deny')
        self.assertIn('setup-runtime', decision['permissionDecisionReason'])

    def test_selftest_does_not_skip_runtime_validation(self):
        result = self.hook_without_python('AI_TDD_SELFTEST')
        decision = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual(decision['permissionDecision'], 'deny')
        self.assertNotEqual(decision['permissionDecisionReason'], tdd.SELFTEST_REASON)

    def test_init_detects_dotnet_without_overwriting_project_files(self):
        (self.root / '.ai-tdd/config.json').unlink()
        self.write('src/App.csproj', '<Project Sdk="Microsoft.NET.Sdk" />')
        original = (self.root / 'src/App.csproj').read_bytes()
        loader = Path(PLUGIN / 'scripts/dotnet_setup.py')
        expected = dict(self.config, dotnet={'schema': 1})
        with mock.patch.object(tdd, 'dotnet_configuration', return_value=expected) as configure:
            result = tdd.init(self.root)
        configure.assert_called_once_with(self.root)
        self.assertEqual(json.loads((self.root / '.ai-tdd/config.json').read_text()), expected)
        self.assertEqual((self.root / 'src/App.csproj').read_bytes(), original)
        self.assertIn('.NET', result['next'])
        self.assertTrue(loader.is_file())

    def test_bundled_controller_does_not_pass_bootloader_as_project_python(self):
        with mock.patch.object(tdd.sys, 'frozen', True, create=True), mock.patch.dict(os.environ, {'AI_TDD_PYTHON': str(self.root / 'missing-python')}):
            with self.assertRaisesRegex(tdd.TddError, 'Project Python'):
                tdd.Controller(self.root).run('baseline')

    def test_python_project_can_use_actual_python_with_bundled_controller(self):
        actual_python = tdd.sys.executable
        with mock.patch.object(tdd.sys, 'frozen', True, create=True), mock.patch.dict(os.environ, {'AI_TDD_PYTHON': actual_python}):
            controller = tdd.Controller(self.root)
            self.assertEqual(controller.run('baseline')['exit_code'], 0)
            self.assertEqual(controller.project_python, str(Path(actual_python).resolve()))

    def dotnet_outputs(self, recreate=True):
        self.write('src/App.csproj', '<Project Sdk="Microsoft.NET.Sdk" />')
        self.write('tests/App.Tests.csproj', '<Project Sdk="Microsoft.NET.Sdk" />')
        self.config['protected_paths'] += ['src/App.csproj', 'tests/App.Tests.csproj']
        self.config['generated_roots'] = ['src/bin', 'src/obj', 'tests/bin', 'tests/obj']
        self.save('.ai-tdd/config.json', self.config)
        if recreate:
            self.c = tdd.Controller(self.root)

    def test_exact_node_controller_command_is_allowed(self):
        prefix = 'node "' + (PLUGIN / 'scripts/tdd-launcher.cjs').as_posix() + '" --root "' + self.root.as_posix() + '" '
        self.assertTrue(tdd.controller_command(prefix + 'status', self.root, PLUGIN))
        for suffix in ['setup-runtime', '--runtime-info', '--dotnet-test', 'init', 'status; echo bypass', 'status | cat']:
            with self.subTest(suffix=suffix):
                self.assertFalse(tdd.controller_command(prefix + suffix, self.root, PLUGIN))
        other = prefix.replace('tdd-launcher.cjs', 'dotnet_runner.py')
        self.assertFalse(tdd.controller_command(other + 'status', self.root, PLUGIN))
        self.assertFalse(tdd.controller_command(prefix + 'status', self.root.parent, PLUGIN))

    def test_only_explicit_project_outputs_are_excluded(self):
        self.dotnet_outputs()
        before = self.c.source()
        (self.root / 'src/bin/Debug').mkdir(parents=True)
        self.write('src/bin/Debug/App.dll', 'generated assembly')
        (self.root / 'src/obj').mkdir()
        self.write('src/obj/GeneratedAssemblyInfo.cs', '// generated')
        self.assertEqual(before, self.c.source())
        self.write('src/fee.py', 'def fee(cents):\n    return 123\n')
        self.assertNotEqual(before, self.c.source())
        self.write('src/App.csproj', '<Project Sdk="changed" />')
        self.assertNotEqual(before, self.c.source())

    def test_unconfigured_output_names_are_still_fingerprinted(self):
        (self.root / 'src/bin').mkdir()
        self.write('src/bin/user-tool.cs', 'important user input')
        self.assertIn('src/bin/user-tool.cs', self.c.source())

    def test_exclusions_cannot_hide_ownership_or_arbitrary_inputs(self):
        self.dotnet_outputs()
        for value in [['src'], ['tests'], ['src/config'], ['src/bin/nested'], ['src/bin', 'src/bin'], 'src/bin', None]:
            with self.subTest(value=value):
                self.config['generated_roots'] = value
                self.save('.ai-tdd/config.json', self.config)
                with self.assertRaisesRegex(tdd.TddError, 'generated'):
                    tdd.Controller(self.root)

    def test_generated_directories_are_not_worker_write_ownership(self):
        self.dotnet_outputs()
        self.ready_red()
        payload = {'cwd': str(self.root), 'tool_name': 'Write', 'agent_type': 'ai-tdd:implementer',
                   'agent_id': 'implementation-worker', 'tool_input': {'file_path': str(self.root / 'src/bin/Bypass.cs')}}
        reason = tdd.guard(payload)
        self.assertIsNotNone(reason)
        self.assertIn('generated', reason)
        payload['tool_input']['file_path'] = str(self.root / 'src/fee.py')
        self.assertIsNone(tdd.guard(payload))

    def test_setup_repair_cannot_change_output_exclusions(self):
        self.dotnet_outputs()
        self.ready_red()
        self.c.reconfigure(reason='diagnosed runner argument issue', paths=[])
        self.config['generated_roots'] = []
        self.save('.ai-tdd/config.json', self.config)
        with self.assertRaisesRegex(tdd.TddError, 'generated'):
            tdd.Controller(self.root).rebase()

    def test_environment_binds_actual_controller_binary(self):
        executable = self.root / 'synthetic-controller.exe'
        executable.write_bytes(b'first runtime')
        with mock.patch.object(tdd.sys, 'executable', str(executable)):
            before = tdd.environment()
            executable.write_bytes(b'changed runtime at identical path')
            self.assertNotEqual(before, tdd.environment())

    def test_new_native_runtime_inputs_are_protected(self):
        expected = ['scripts/tdd-launcher.cjs', 'scripts/runtime_entry.py', 'scripts/dotnet_runner.py',
                    'scripts/dotnet_setup.py', 'runtime-manifest.json', 'references/dotnet.md']
        protected = self.c.protected()
        self.assertTrue(all('plugin/' + item in protected for item in expected))

    def test_legacy_state_does_not_retroactively_accept_exclusions(self):
        self.c.begin()
        self.dotnet_outputs(recreate=False)
        with self.assertRaisesRegex(tdd.TddError, 'generated'):
            tdd.Controller(self.root)


if __name__ == '__main__':
    unittest.main()
