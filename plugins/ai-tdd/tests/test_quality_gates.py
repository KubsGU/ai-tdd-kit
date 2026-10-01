"""Quality completion gates exercise real project commands and review evidence."""
import sys
import json
import subprocess
import unittest

from test_controller import Fixture, tdd


class QualityGateTests(Fixture, unittest.TestCase):
    def checks(self, code, inputs=None, limit=20):
        self.config['quality_checks'] = [{'name': 'repo-lint', 'kind': 'lint',
            'argv': ['{python}', '-B', '-c', code], 'inputs': inputs or []}]
        self.config['max_quality_runs'] = limit
        self.save('.ai-tdd/config.json', self.config)
        self.c = tdd.Controller(self.root)

    def test_failing_quality_baseline_cannot_start_a_task(self):
        self.checks('raise SystemExit(1)')
        with self.assertRaisesRegex(tdd.TddError, 'quality'):
            self.c.begin()
        self.assertFalse(self.c.state_path.exists())

    def test_completion_executes_quality_again_and_returns_to_editable_phase(self):
        self.checks("from pathlib import Path; p=Path('check-count.txt'); n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1)); raise SystemExit(1 if n >= 2 else 0)")
        self.ready_green()
        self.c.verify()
        self.review()
        # A flaky external tool becomes failing on its third execution.
        with self.assertRaisesRegex(tdd.TddError, 'quality'):
            self.c.finish()
        self.assertEqual(self.state()['phase'], 'GREEN')
        self.assertEqual(self.state()['quality_receipt']['status'], 'failed')
        self.assertNotIn('completion_receipt', self.state())
        self.assertEqual((self.root/'check-count.txt').read_text(), '3')

    def test_quality_inputs_are_frozen_without_manual_protected_path_duplication(self):
        self.write('lint-policy.txt', 'strict')
        self.checks('raise SystemExit(0)', ['lint-policy.txt'])
        self.ready_green()
        self.write('lint-policy.txt', 'ignore-errors')
        with self.assertRaisesRegex(tdd.TddError, 'protected'):
            self.c.verify()

    def test_mutating_formatter_is_rejected_and_source_repair_remains_possible(self):
        self.checks("from pathlib import Path; p=Path('format-count.txt'); n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1)); s=Path('src/fee.py'); s.write_text(s.read_text()+'# formatted\\n') if n >= 2 else None")
        self.ready_green()
        self.c.verify()
        self.review()
        with self.assertRaisesRegex(tdd.TddError, 'modified'):
            self.c.finish()
        self.assertEqual(self.state()['phase'], 'GREEN')

    def test_setup_repair_cannot_drop_quality_definitions(self):
        self.checks('raise SystemExit(0)')
        self.ready_red()
        self.c.reconfigure(reason='Repair runner setup', paths=[])
        self.config['quality_checks'] = []
        self.save('.ai-tdd/config.json', self.config)
        with self.assertRaisesRegex(tdd.TddError, 'quality'):
            self.c.rebase()

    def test_runner_repair_cannot_raise_quality_budget(self):
        self.checks('raise SystemExit(0)', limit=2)
        self.ready_red()
        self.c.reconfigure(reason='Repair runner setup', paths=[])
        self.config['max_quality_runs'] = 500
        self.save('.ai-tdd/config.json', self.config)
        with self.assertRaisesRegex(tdd.TddError, 'quality'):
            self.c.rebase()

    def test_missing_per_test_assessment_blocks_completion(self):
        self.ready_green()
        self.c.verify()
        self.review(test_assessment=[])
        with self.assertRaisesRegex(tdd.TddError, 'assessment'):
            self.c.finish()

    def test_no_configured_tools_is_reported_as_unchecked_not_passed(self):
        self.ready_green()
        self.c.verify()
        self.assertIn('quality_receipt', self.state())
        self.assertEqual(self.state()['quality_receipt']['status'], 'not_configured')
        self.review(quality_limitations=[])
        with self.assertRaisesRegex(tdd.TddError, 'quality limitations'):
            self.c.finish()

    def test_deleted_quality_receipt_invalidates_done_status(self):
        self.ready_green()
        self.c.verify()
        self.review()
        result = self.c.finish()
        self.assertIn('quality_receipt', result)
        path = self.root / '.ai-tdd/runs' / (result['quality_receipt']['id'] + '.quality.json')
        path.unlink()
        cli = subprocess.run([sys.executable, '-B', str(tdd.PLUGIN/'scripts/tdd.py'), '--root', str(self.root), 'status'], capture_output=True, encoding='utf-8')
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertFalse(json.loads(cli.stdout)['receipt_current'])
