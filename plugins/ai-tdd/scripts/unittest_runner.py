"""Real unittest discovery/execution with per-test JSON evidence."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.items = {}

    def startTest(self, test):
        super().startTest(test)
        self.items[test.id()] = {"id": test.id(), "status": "passed", "exception": "", "detail": ""}

    def record(self, test, status, err=None, reason=""):
        self.items[test.id()] = {"id": test.id(), "status": status, "exception": err[0].__name__ if err else "", "detail": str(err[1])[:1200] if err else reason[:1200]}

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "failed", err)

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error", err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped", reason=reason)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.record(test, "failed" if issubclass(err[0], test.failureException) else "error", err)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, "skipped", reason="expectedFailure is not acceptance evidence")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "error", reason="Unexpected success")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-dir", default="tests")
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--top-level-dir")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    sys.path.insert(0, os.getcwd())
    suite = unittest.TestLoader().discover(args.start_dir, args.pattern, args.top_level_dir)
    collected = [test.id() for test in flatten(suite)]
    result = Result()
    suite.run(result)
    Path(args.report).write_text(json.dumps({"schema": 1, "collected": collected, "results": list(result.items.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"collected": len(collected), "executed": result.testsRun, "successful": result.wasSuccessful()}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
