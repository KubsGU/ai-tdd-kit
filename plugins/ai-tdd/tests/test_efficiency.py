"""Model launch and usage accounting tests; no model calls."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

KIT = Path(__file__).resolve().parents[3]


def module(name):
    path = KIT / 'scripts' / (name + '.py')
    if not path.is_file():
        raise AssertionError('Missing efficiency helper: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class LaunchTests(unittest.TestCase):
    def test_ordinary_launch_requests_sonnet_and_keeps_explicit_opus_available(self):
        launcher = module('launch_claude')
        with tempfile.TemporaryDirectory() as project:
            for selected, expected in (([], 'sonnet'), (['--model', 'opus'], 'opus')):
                with self.subTest(selected=selected), mock.patch('sys.argv', ['launcher', '--project', project] + selected), mock.patch.object(launcher.shutil, 'which', return_value='claude'), mock.patch.object(launcher.subprocess, 'call', return_value=0) as call:
                    self.assertEqual(launcher.main(), 0)
                    argv = call.call_args.args[0]
                    self.assertEqual(argv[argv.index('--model') + 1], expected)

    def test_launcher_opens_the_selected_project(self):
        launcher = module('launch_claude')
        with tempfile.TemporaryDirectory() as project:
            with mock.patch('sys.argv', ['launcher', '--project', project]), mock.patch.object(launcher.shutil, 'which', return_value='claude'), mock.patch.object(launcher.subprocess, 'call', return_value=0) as call:
                try:
                    self.assertEqual(launcher.main(), 0)
                except SystemExit:
                    self.fail('Launcher cannot select the feature project')
                self.assertEqual(Path(call.call_args.kwargs['cwd']), Path(project).resolve())

    def test_quality_launch_enables_cache_without_mutating_parent(self):
        launcher = module('launch_claude')
        original = {'DISABLE_PROMPT_CACHING': '1', 'DISABLE_PROMPT_CACHING_FABLE': '1', 'CLAUDE_CODE_SUBAGENT_MODEL': 'haiku', 'CLAUDE_CODE_SUBAGENT_MODEL_FORCE': '1', 'PATH': 'unchanged'}
        child = launcher.launch_environment(original)
        self.assertEqual(child['CLAUDE_CODE_DISABLE_BACKGROUND_TASKS'], '1')
        self.assertEqual(child['PATH'], 'unchanged')
        self.assertNotIn('DISABLE_PROMPT_CACHING', child)
        self.assertNotIn('DISABLE_PROMPT_CACHING_FABLE', child)
        self.assertNotIn('CLAUDE_CODE_SUBAGENT_MODEL', child)
        self.assertNotIn('CLAUDE_CODE_SUBAGENT_MODEL_FORCE', child)
        self.assertEqual(original['DISABLE_PROMPT_CACHING'], '1')

    def test_launcher_preserves_explicit_model_and_effort(self):
        launcher = module('launch_claude')
        argv = launcher.launch_argv('claude', 'claude-opus-5-5', 'high', ['--continue'])
        self.assertIn('claude-opus-5-5', argv)
        self.assertEqual(argv[argv.index('--effort')+1], 'high')
        self.assertIn('--continue', argv)
        self.assertNotIn('--fallback-model', argv)

    def test_launcher_does_not_disable_normal_permissions_or_mcp(self):
        launcher = module('launch_claude')
        argv = launcher.launch_argv('claude', 'opus', None, [])
        self.assertNotIn('--dangerously-skip-permissions', argv)
        self.assertNotIn('--setting-sources', argv)
        self.assertNotIn('--strict-mcp-config', argv)
        self.assertNotIn('--effort', argv)


class UsageTests(unittest.TestCase):
    def test_whole_tree_usage_is_taken_from_final_model_totals(self):
        helper = module('evaluate_claude')
        self.assertTrue(hasattr(helper, 'summarize_usage'), 'No whole-tree usage accounting')
        usage = helper.summarize_usage({'total_cost_usd': 0.7, 'usage': {'cache_read_input_tokens': 2}, 'modelUsage': {
            'claude-opus-5-5': {'inputTokens': 10, 'outputTokens': 20, 'cacheReadInputTokens': 80, 'cacheCreationInputTokens': 10, 'costUSD': 0.7}}})
        self.assertEqual(usage['totals']['cache_read_input_tokens'], 80)
        self.assertEqual(usage['cache_read_fraction'], 0.8)
        self.assertEqual(usage['estimated_cost_usd'], 0.7)

    def test_missing_usage_is_unavailable_not_zero(self):
        helper = module('evaluate_claude')
        self.assertTrue(hasattr(helper, 'summarize_usage'), 'No unavailable usage handling')
        usage = helper.summarize_usage({})
        self.assertFalse(usage['available'])
        self.assertIsNone(usage['totals'])
        self.assertIsNone(usage['cache_read_fraction'])
        self.assertIsNone(usage['estimated_cost_usd'])

    def test_partial_usage_does_not_manufacture_a_cache_hit_rate(self):
        helper = module('evaluate_claude')
        self.assertTrue(hasattr(helper, 'summarize_usage'), 'No partial usage handling')
        usage = helper.summarize_usage({'modelUsage': {'custom-model': {'outputTokens': 25}}})
        self.assertIsNone(usage['cache_read_fraction'])
        self.assertIsNone(usage['totals'])

    def test_invalid_numeric_usage_is_not_accepted_as_real_evidence(self):
        helper = module('evaluate_claude')
        usage = helper.summarize_usage({'total_cost_usd': float('nan'), 'modelUsage': {'custom-model': {'inputTokens': True, 'outputTokens': 2, 'cacheReadInputTokens': -1, 'cacheCreationInputTokens': 0}}})
        self.assertIsNone(usage['estimated_cost_usd'])
        self.assertIsNone(usage['cache_read_fraction'])
