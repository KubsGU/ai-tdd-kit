"""Explicit worker routing exercises real task snapshots and Agent guards."""
import unittest

from test_controller import Fixture, tdd


class WorkerModelPolicyTests(Fixture, unittest.TestCase):
    def configure_models(self, value):
        self.config['worker_models'] = value
        self.save('.ai-tdd/config.json', self.config)
        self.c = tdd.Controller(self.root)

    def dispatch(self, role, **extra):
        return {'cwd': str(self.root), 'tool_name': 'Agent',
                'tool_input': {'subagent_type': 'ai-tdd:' + role,
                               'prompt': 'One reviewed behavior increment', **extra}}

    def test_explicit_haiku_implementer_is_allowed_after_real_red(self):
        self.configure_models({'implementer': 'haiku'})
        self.ready_red()
        self.assertIsNone(tdd.guard(self.dispatch('implementer', model='haiku')))

    def test_explicit_implementer_model_cannot_be_omitted_or_substituted(self):
        self.configure_models({'implementer': 'haiku'})
        self.ready_red()
        for override in ({}, {'model': 'inherit'}, {'model': 'sonnet'}, {'model': 'opus'},
                         {'model': None}, {'model': 'claude-haiku-4-5'}):
            with self.subTest(override=override):
                self.assertIsNotNone(tdd.guard(self.dispatch('implementer', **override)))

    def test_explicit_opus_author_and_verifier_require_opus_dispatch(self):
        self.configure_models({'test-author': 'opus', 'verifier': 'opus'})
        self.c.begin()
        for role in ('test-author', 'verifier'):
            with self.subTest(role=role):
                self.assertIsNone(tdd.guard(self.dispatch(role, model='opus')))
                self.assertIsNotNone(tdd.guard(self.dispatch(role)))
                self.assertIsNotNone(tdd.guard(self.dispatch(role, model='inherit')))

    def test_policy_rejects_unknown_roles_and_noncanonical_models(self):
        invalid = (None, [], 'haiku', {'reviewer': 'opus'}, {'implementer': ''},
                   {'implementer': None}, {'implementer': ['haiku']},
                   {'implementer': 'claude-haiku-4-5'}, {'implementer': 'Haiku'},
                   {'test-author': 'sonnet'}, {'test-author': 'haiku'},
                   {'verifier': 'sonnet'}, {'verifier': 'haiku'})
        for value in invalid:
            with self.subTest(value=value):
                self.config['worker_models'] = value
                self.save('.ai-tdd/config.json', self.config)
                with self.assertRaisesRegex(tdd.TddError, 'worker_models'):
                    tdd.Controller(self.root)

    def test_begin_freezes_and_compact_status_exposes_normalized_policy(self):
        self.configure_models({'implementer': 'sonnet'})
        self.c.begin()
        expected = {'test-author': 'inherit', 'implementer': 'sonnet', 'verifier': 'inherit'}
        self.assertIn('worker_models', self.state())
        self.assertEqual(self.state()['worker_models'], expected)
        self.assertEqual(tdd.compact_state(self.state()).get('worker_models'), expected)

    def test_default_policy_preserves_omitted_or_inherited_dispatch(self):
        self.c.begin()
        for role in ('test-author', 'verifier'):
            with self.subTest(role=role):
                self.assertIsNone(tdd.guard(self.dispatch(role)))
                self.assertIsNone(tdd.guard(self.dispatch(role, model='inherit')))
                self.assertIsNotNone(tdd.guard(self.dispatch(role, model='opus')))

    def test_changed_policy_blocks_dispatch_before_any_transition(self):
        self.c.begin()
        self.config['worker_models'] = {'verifier': 'opus'}
        self.save('.ai-tdd/config.json', self.config)
        decision = tdd.guard(self.dispatch('verifier', model='opus'))
        self.assertIsNotNone(decision)
        self.assertIn('Frozen worker model', decision)

    def test_setup_repair_cannot_change_worker_models(self):
        self.configure_models({'implementer': 'sonnet'})
        self.ready_red()
        self.c.reconfigure(reason='Repair runner discovery only', paths=[])
        self.config['worker_models'] = {'implementer': 'haiku'}
        self.save('.ai-tdd/config.json', self.config)
        with self.assertRaisesRegex(tdd.TddError, 'Frozen worker model'):
            self.c.rebase()
        self.assertEqual(self.state()['phase'], 'RECONFIGURE')

    def test_legacy_missing_policy_remains_compatible_only_with_inheritance(self):
        self.ready_red()
        state = self.state()
        state.pop('worker_models', None)
        self.save('.ai-tdd/state.json', state)
        self.assertIsNone(tdd.guard(self.dispatch('implementer')))
        self.c = tdd.Controller(self.root)
        self.c.reconfigure(reason='Repair runner discovery only', paths=[])
        self.assertEqual(self.state()['phase'], 'RECONFIGURE')

    def test_legacy_missing_policy_cannot_adopt_explicit_worker_models(self):
        self.configure_models({'implementer': 'haiku'})
        self.ready_red()
        state = self.state()
        state.pop('worker_models', None)
        self.save('.ai-tdd/state.json', state)
        decision = tdd.guard(self.dispatch('implementer', model='haiku'))
        self.assertIsNotNone(decision)
        self.assertIn('Frozen worker model', decision)
        with self.assertRaisesRegex(tdd.TddError, 'Frozen worker model'):
            tdd.Controller(self.root).reconfigure(reason='Repair setup only', paths=[])

    def test_lower_cost_routing_keeps_phase_and_fresh_worker_boundaries(self):
        self.configure_models({'implementer': 'haiku'})
        self.c.begin()
        self.assertIsNotNone(tdd.guard(self.dispatch('implementer', model='haiku')))
        self.new_test()
        self.c.red(tests=['test_threshold.FeeTests.test_threshold'], ac=['AC1'],
                   expect='AssertionError', because='AC1 independent literal zero')
        for extra in ({'resume': 'old-worker'}, {'run_in_background': True}, {'isolation': 'worktree'}):
            with self.subTest(extra=extra):
                self.assertIsNotNone(tdd.guard(self.dispatch('implementer', model='haiku', **extra)))
        nested = self.dispatch('implementer', model='haiku')
        nested.update(agent_id='worker-1', agent_type='ai-tdd:implementer')
        self.assertIsNotNone(tdd.guard(nested))
