"""Execute pytest with actual exception types and complete per-node JSON evidence.

Uses pytest's public hooks; parallel xdist execution is unsupported.
"""
import argparse
import json
import os
from pathlib import Path
import sys

import pytest


class Evidence:
    def __init__(self):
        self.collected = []
        self.phases = {}
        self.results = {}

    def pytest_configure(self, config):
        if getattr(config.option, "numprocesses", None) not in (None, 0):
            raise pytest.UsageError("AI TDD pytest evidence requires serial execution; disable xdist")

    def pytest_itemcollected(self, item):
        self.collected.append(item.nodeid)

    def pytest_deselected(self, items):
        for item in items:
            self.results[item.nodeid] = self.result(item.nodeid, "skipped", detail="Deselected tests are not acceptance evidence")

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            nodeid = "collection:" + report.nodeid
            self.collected.append(nodeid)
            self.results[nodeid] = self.result(nodeid, "error" if report.failed else "skipped", "CollectionError", str(report.longrepr))

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        exception = call.excinfo.type.__name__ if call.excinfo else ""
        if report.skipped or hasattr(report, "wasxfail"):
            status = "skipped"
        elif report.failed:
            status = "failed" if report.when == "call" and exception else "error"
            exception = exception or "UnknownFailure"
        else:
            status = "passed"
        self.phases.setdefault(item.nodeid, {})[report.when] = self.result(item.nodeid, status, exception, str(report.longrepr or ""))

    @staticmethod
    def result(nodeid, status, exception="", detail=""):
        return {"id": nodeid, "status": status, "exception": exception, "detail": detail[:1200]}

    def report(self):
        rank = {"passed": 0, "failed": 1, "skipped": 2, "error": 3}
        for nodeid in self.collected:
            if nodeid in self.results:
                continue
            phases = self.phases.get(nodeid, {})
            result = max(phases.values(), key=lambda item: rank[item["status"]], default=None)
            if result is None or (result["status"] == "passed" and set(phases) != {"setup", "call", "teardown"}):
                result = self.result(nodeid, "error", "UnexecutedTest", "Collected test did not complete all execution phases")
            self.results[nodeid] = result
        return {"schema": 1, "collected": self.collected, "results": list(self.results.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    args, pytest_args = parser.parse_known_args()
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    sys.path.insert(0, os.getcwd())
    evidence = Evidence()
    code = pytest.main(pytest_args or ["tests", "-q"], plugins=[evidence])
    Path(args.report).write_text(json.dumps(evidence.report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
