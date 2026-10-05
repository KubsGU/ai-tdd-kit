"""New task presets freeze runtime theory mode and budget larger full suites."""
import unittest

import test_dotnet_runner as fixtures


class DotnetPresetPolicyTests(unittest.TestCase):
    setUp = fixtures.DotnetSetupTests.setUp
    metadata = fixtures.DotnetSetupTests.metadata
    configure = fixtures.DotnetSetupTests.configure
    large_projects = fixtures.DotnetSetupTests.large_projects

    def test_runtime_parent_row_policy_is_explicit_and_bound_to_evaluated_setup(self):
        config = self.configure()
        self.assertEqual(config["dotnet"].get("theory_mode"), "runtime-parent-rows-v1")

    def test_large_solution_receives_full_suite_budget_before_task_freeze(self):
        self.large_projects(70)
        config = self.configure()
        self.assertEqual(len(config["dotnet"]["modules"]), 35)
        self.assertEqual(config["timeout_seconds"], 2100)


if __name__ == "__main__":
    unittest.main()
