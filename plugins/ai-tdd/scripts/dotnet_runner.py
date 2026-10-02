"""Native unfiltered .NET execution with independently reconciled evidence.

Only existing supported VSTest frameworks are accepted; no user adapter is
authored and no exception type is inferred from text or reporter Cause.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


_loader = importlib.util.spec_from_file_location("ai_tdd_dotnet_setup", Path(__file__).with_name("dotnet_setup.py"))
SETUP = importlib.util.module_from_spec(_loader)
_loader.loader.exec_module(SETUP)
DotnetError = SETUP.DotnetError
PREFIX = re.compile(r"^\[xUnit\.net \d{2}:\d{2}:\d{2}\.\d{2}\] (\{.*\})$")
# Concrete framework assertion types, never namespace/prefix matching.
ASSERTIONS = frozenset("Xunit.Sdk." + name for name in (
    "AllException", "CollectionException", "ContainsException", "DoesNotContainException", "EmptyException",
    "EndsWithException", "EqualException", "EquivalentException", "FailException", "FalseException",
    "InRangeException", "IsAssignableFromException", "IsNotTypeException", "IsTypeException", "MatchesException",
    "MultipleException", "NotEmptyException", "NotEqualException", "NotInRangeException", "NotNullException",
    "NotSameException", "NullException", "ProperSubsetException", "ProperSupersetException", "RaisesException",
    "SameException", "SingleException", "StartsWithException", "SubsetException", "SupersetException",
    "ThrowsAnyException", "ThrowsException", "TrueException"))
TERMINALS = {"test-passed": "passed", "test-failed": "failed", "test-skipped": "skipped", "test-not-run": "skipped"}


def _unique_names(names):
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != len(names):
        raise DotnetError("Full discovery needs nonempty unique test display names; ambiguous/empty discovery is unsupported")
    return names


def discovery_names(stdout):
    lines = stdout.splitlines()
    marker = "The following Tests are available:"
    indices = [i for i, line in enumerate(lines) if line.strip() == marker]
    if len(indices) != 1:
        raise DotnetError("VSTest full discovery marker is absent/ambiguous; fix SDK, build or discovery errors")
    names = []
    for line in lines[indices[0] + 1:]:
        if line.startswith("    ") and line.strip():
            names.append(line[4:].strip())
        elif line.strip() and not line.startswith("[xUnit.net "):
            raise DotnetError("Unexpected discovery output; full test inventory cannot be proven")
    return _unique_names(names)


def _events(stdout):
    events = []
    for line in stdout.splitlines():
        match = PREFIX.fullmatch(line)
        if match:
            try:
                event = json.loads(match[1])
            except ValueError as error:
                raise DotnetError("Malformed xUnit JSONReporter message") from error
            if not isinstance(event, dict) or not isinstance(event.get("$type"), str):
                raise DotnetError("Unsupported xUnit reporter schema")
            events.append(event)
    if not events:
        raise DotnetError("Missing typed xUnit JSONReporter output; existing xunit.runner.visualstudio >=3.0.0 is required")
    return events


def _text(event, key):
    value = event.get(key)
    if not isinstance(value, str) or not value:
        raise DotnetError("Missing native lifecycle field: " + key)
    return value


def _counts(event, terminals):
    expected = {"TestsTotal": len(terminals), "TestsFailed": sum(item == "test-failed" for item in terminals),
                "TestsSkipped": sum(item == "test-skipped" for item in terminals),
                "TestsNotRun": sum(item == "test-not-run" for item in terminals)}
    if any(type(event.get(key)) is not int or event[key] != value for key, value in expected.items()):
        raise DotnetError("Native lifecycle counts differ from executed tests")


def method_witness(stack, klass, method):
    if not isinstance(stack, str) or not isinstance(klass, str) or not isinstance(method, str) or not klass or not method:
        return False
    # The assertion must reach the actual method (or its compiler async state
    # machine); constructor/setup/Dispose frames alone never satisfy this.
    body = re.escape(klass) + r"\." + re.escape(method) + r"(?:\(|\[)"
    asynchronous = re.escape(klass) + r"\.\<" + re.escape(method) + r"\>d__\d+\.MoveNext\("
    return bool(re.search(r"(?:^|\s)at\s+(?:" + body + "|" + asynchronous + ")", stack))


def _failure(event, case):
    arrays = {name: event.get(name) for name in ("ExceptionTypes", "ExceptionParentIndices", "Messages", "StackTraces")}
    length = len(arrays["ExceptionTypes"]) if isinstance(arrays["ExceptionTypes"], list) else 0
    if not length or any(not isinstance(value, list) or len(value) != length for value in arrays.values()):
        raise DotnetError("Missing typed failure arrays; untyped failures are unsupported")
    for index in range(length):
        parent = arrays["ExceptionParentIndices"][index]
        if (type(parent) is not int or not -1 <= parent < index
                or not isinstance(arrays["Messages"][index], str)
                or arrays["ExceptionTypes"][index] is not None and not isinstance(arrays["ExceptionTypes"][index], str)
                or arrays["StackTraces"][index] is not None and not isinstance(arrays["StackTraces"][index], str)):
            raise DotnetError("Malformed native failure metadata")
    actual_type = arrays["ExceptionTypes"][0]
    assertion = actual_type in ASSERTIONS and method_witness(arrays["StackTraces"][0], case.get("TestClassName"), case.get("TestMethodName"))
    return {"status": "failed" if assertion else "error", "exception": "AssertionError" if assertion else actual_type or "UnknownFailure",
            "native_exception_types": arrays["ExceptionTypes"], "native_exception_parent_indices": arrays["ExceptionParentIndices"],
            "native_messages": arrays["Messages"], "native_stack_traces": arrays["StackTraces"], "native_cause": event.get("Cause"),
            "detail": "\n".join(arrays["Messages"])[:1200]}


def _xml(raw):
    if len(raw) > 5_000_000 or "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise DotnetError("Oversized or DTD/entity XML evidence is unsupported")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as error:
        raise DotnetError("Malformed native XML evidence") from error


def _trx(raw, outcomes):
    tree = _xml(raw)
    namespace = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"
    if tree.tag != namespace + "TestRun":
        raise DotnetError("TRX needs the native TestRun schema")
    actual = {}
    for item in tree.findall(namespace + "Results/" + namespace + "UnitTestResult"):
        name, outcome = item.get("testName"), item.get("outcome")
        if not name or name in actual or outcome not in {"Passed", "Failed", "NotExecuted"}:
            raise DotnetError("TRX contains missing/duplicate/unsupported outcomes")
        actual[name] = outcome
    expected = {name: {"test-passed": "Passed", "test-failed": "Failed", "test-skipped": "NotExecuted", "test-not-run": "NotExecuted"}[outcome]
                for name, outcome in outcomes.items()}
    if actual != expected:
        raise DotnetError("Fresh TRX and native reporter disagree on test inventory/outcomes")
    counters = tree.findall(namespace + "ResultSummary/" + namespace + "Counters")
    if len(counters) != 1:
        raise DotnetError("TRX requires one execution count summary")
    counts = {"total": len(actual), "passed": sum(value == "Passed" for value in actual.values()),
              "failed": sum(value == "Failed" for value in actual.values()),
              "executed": sum(value != "NotExecuted" for value in actual.values())}
    for key, value in counts.items():
        if counters[0].get(key) != str(value):
            raise DotnetError("TRX declared counts disagree with execution")
    for key in ("error", "timeout", "aborted", "inconclusive", "passedButRunAborted", "notRunnable", "disconnected", "inProgress", "pending"):
        if counters[0].get(key, "0") != "0":
            raise DotnetError("TRX records an incomplete/error run: " + key)
    if tree.findall(".//" + namespace + "RunInfo"):
        raise DotnetError("TRX run diagnostics prevent clean native evidence")


def reconcile(project, tfm, discovered, stdout, trx):
    """Join full discovered IDs with actual typed lifecycle and fresh TRX."""
    _unique_names(discovered)
    assembly, completed = None, False
    cases, finished_cases, tests, terminals, finished_tests = {}, set(), {}, {}, set()
    for event in _events(stdout):
        kind = event["$type"]
        if kind == "error-message" or kind.endswith("cleanup-failure"):
            raise DotnetError("Native framework/setup/cleanup error prevents acceptance evidence: " + kind)
        if kind == "test-assembly-starting":
            if assembly is not None:
                raise DotnetError("Each project/TFM run must contain exactly one test assembly")
            assembly = _text(event, "AssemblyUniqueID")
            continue
        if completed or assembly is None or event.get("AssemblyUniqueID") != assembly:
            raise DotnetError("Native event outside its single assembly lifecycle")
        if kind == "test-case-starting":
            case_id = _text(event, "TestCaseUniqueID")
            if case_id in cases:
                raise DotnetError("Duplicate native test case lifecycle")
            _text(event, "TestClassName")
            _text(event, "TestMethodName")
            cases[case_id] = event
        elif kind == "test-starting":
            test_id, case_id = _text(event, "TestUniqueID"), _text(event, "TestCaseUniqueID")
            if test_id in tests or case_id not in cases or case_id in finished_cases:
                raise DotnetError("Invalid/duplicate test-starting lifecycle")
            _text(event, "TestDisplayName")
            tests[test_id] = event
        elif kind in TERMINALS or kind == "test-finished":
            test_id = _text(event, "TestUniqueID")
            if test_id not in tests or test_id in finished_tests or event.get("TestCaseUniqueID") != tests[test_id]["TestCaseUniqueID"]:
                raise DotnetError("Test result lacks a matching active test lifecycle")
            if kind == "test-finished":
                if test_id not in terminals:
                    raise DotnetError("Test finished without a terminal result")
                finished_tests.add(test_id)
            else:
                if test_id in terminals:
                    raise DotnetError("Duplicate/contradictory terminal test result")
                terminals[test_id] = event
        elif kind == "test-case-finished":
            case_id = _text(event, "TestCaseUniqueID")
            members = [test_id for test_id, item in tests.items() if item["TestCaseUniqueID"] == case_id]
            if case_id not in cases or case_id in finished_cases or not members or any(item not in finished_tests for item in members):
                raise DotnetError("Incomplete/duplicate test case lifecycle")
            _counts(event, [terminals[item]["$type"] for item in members])
            finished_cases.add(case_id)
        elif kind == "test-assembly-finished":
            if set(tests) != finished_tests or set(cases) != finished_cases:
                raise DotnetError("Incomplete test lifecycle at assembly completion")
            _counts(event, [item["$type"] for item in terminals.values()])
            completed = True
    if not completed:
        raise DotnetError("Missing native assembly completion")
    names = [item["TestDisplayName"] for item in tests.values()]
    _unique_names(names)
    if set(names) != set(discovered):
        raise DotnetError("Full discovery differs from actual executed inventory; filters/retries/undiscovered theory rows are unsupported")
    outcomes = {tests[test_id]["TestDisplayName"]: event["$type"] for test_id, event in terminals.items()}
    _trx(trx, outcomes)
    results = []
    for test_id, event in terminals.items():
        item = tests[test_id]
        result = {"id": project + "|" + tfm + "|" + item["TestDisplayName"], "status": TERMINALS[event["$type"]], "exception": "", "detail": event.get("Reason", "")}
        if event["$type"] == "test-failed":
            result.update(_failure(event, cases[item["TestCaseUniqueID"]]))
        results.append(result)
    return {"schema": 1, "collected": [project + "|" + tfm + "|" + name for name in discovered], "results": results}


def _nunit_counts(node, cases):
    counts = {"testcasecount": len(cases), "total": len(cases),
              **{key: sum(case.get("result") == native for case in cases) for key, native in
                 (("passed", "Passed"), ("failed", "Failed"), ("skipped", "Skipped"), ("inconclusive", "Inconclusive"), ("warnings", "Warning"))}}
    for key, value in counts.items():
        if node.get(key) != str(value):
            raise DotnetError("NUnit declared " + key + " count differs from full leaf inventory")


def reconcile_nunit(project, tfm, discovery, execution, trx):
    """Use NUnit's own structured assertion records; preserve absent type data."""
    discovered_tree, tree = _xml(discovery), _xml(execution)
    if discovered_tree.tag != "NUnitXml" or tree.tag != "test-run":
        raise DotnetError("NUnit needs native discovery dump and result XML schemas")
    discovered_roots = [item for item in discovered_tree.iter("test-suite") if item.get("type") == "Assembly"]
    if not discovered_roots:
        discovered_roots = discovered_tree.findall("test-run")
    if len(discovered_roots) != 1:
        raise DotnetError("NUnit discovery must contain one explicit test assembly")
    discovered_cases, cases = list(discovered_roots[0].iter("test-case")), list(tree.iter("test-case"))
    names = _unique_names([case.get("fullname") for case in discovered_cases])
    actual_names = _unique_names([case.get("fullname") for case in cases])
    if set(names) != set(actual_names) or discovered_roots[0].get("testcasecount") != str(len(names)):
        raise DotnetError("Full NUnit discovery differs from executed native inventory")
    for attribute in ("classname", "methodname"):
        before = {case.get("fullname"): case.get(attribute) for case in discovered_cases}
        after = {case.get("fullname"): case.get(attribute) for case in cases}
        if before != after or any(not isinstance(item, str) or not item for item in after.values()):
            raise DotnetError("NUnit test identity changed or lacks native method metadata")
    _nunit_counts(tree, cases)
    for suite in tree.iter("test-suite"):
        children = list(suite.iter("test-case"))
        _nunit_counts(suite, children)
        if suite.find("failure") is not None:
            if (suite.get("result") != "Failed" or suite.get("site") != "Child" or suite.get("label", "")
                    or not any(case.get("result") == "Failed" for case in children)):
                raise DotnetError("NUnit suite setup/cleanup/infrastructure failure prevents acceptance evidence")
    results, outcomes = [], {}
    for case in cases:
        native, label, site = case.get("result"), case.get("label", ""), case.get("site", "Test")
        name = case.get("fullname")
        if native not in {"Passed", "Failed", "Skipped"}:
            raise DotnetError("NUnit incomplete/inconclusive/warning result is unsupported acceptance evidence")
        outcomes[name] = {"Passed": "test-passed", "Failed": "test-failed", "Skipped": "test-skipped"}[native]
        failure = case.find("failure")
        message = case.findtext("failure/message", case.findtext("reason/message", ""))
        stack = case.findtext("failure/stack-trace", "")
        assertions = [{"result": item.get("result"), "message": item.findtext("message", ""),
                       "stack_trace": item.findtext("stack-trace", "")} for item in case.findall("assertions/assertion")]
        result = {"id": project + "|" + tfm + "|" + name, "status": "passed" if native == "Passed" else "skipped" if native == "Skipped" else "error",
                  "exception": "" if native != "Failed" else "NUnitFrameworkFailure", "detail": message[:1200],
                  "native_result": native, "native_label": label, "native_site": site,
                  "native_runstate": case.get("runstate"), "native_stack_trace": stack, "native_assertions": assertions,
                  "native_failure_category": "nunit-" + (label.lower() if label else native.lower())}
        if native == "Passed" and (failure is not None or label):
            raise DotnetError("Contradictory NUnit passed outcome")
        if native == "Failed":
            if failure is None:
                raise DotnetError("NUnit failure lacks structured failure metadata")
            failed_assertions = [item for item in assertions if item["result"] == "Failed"]
            witness = lambda value: method_witness(value, case.get("classname"), case.get("methodname"))
            if (not label and site == "Test" and case.get("runstate") == "Runnable" and witness(stack)
                    and failed_assertions and all(witness(item["stack_trace"]) for item in failed_assertions)):
                result.update(status="failed", exception="AssertionError", native_failure_category="nunit-assertion")
        results.append(result)
    _trx(trx, outcomes)
    return {"schema": 1, "collected": [project + "|" + tfm + "|" + name for name in names], "results": results}


def _nunit_target(project, tfm, artifacts, root):
    argv = [shutil.which("dotnet"), "msbuild", str(project), "-nologo", "-p:TargetFramework=" + tfm,
            "-p:ArtifactsPath=" + str(artifacts), "-getProperty:TargetDir,TargetFileName"]
    process = subprocess.run(argv, cwd=root, env=SETUP.environment(), capture_output=True, encoding="utf-8", timeout=120)
    if process.returncode:
        raise DotnetError("Cannot evaluate NUnit discovery output directory")
    try:
        props = json.loads(process.stdout)["Properties"]
        target = Path(props["TargetDir"]).resolve()
        filename = props["TargetFileName"]
    except (ValueError, KeyError, TypeError) as error:
        raise DotnetError("Unsupported NUnit output metadata") from error
    if target != artifacts and artifacts not in target.parents or not filename or Path(filename).name != filename:
        raise DotnetError("NUnit artifacts must stay within the fresh owned bin/ directory")
    return target / "Dump" / ("D_" + filename + ".dump"), Path(filename).stem + ".xml"


def _process(argv, root, stdout_path, stderr_path, timeout):
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            result = subprocess.run(argv, cwd=root, env=SETUP.environment(), shell=False, stdout=stdout, stderr=stderr, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DotnetError("Native .NET execution failed: " + type(error).__name__ + "; inspect the local run logs") from error
    return result.returncode, stdout_path.read_text(encoding="utf-8-sig", errors="replace")


def run(root, report, config=None):
    root = Path(root).resolve()
    report = Path(report).absolute()
    if report.resolve() != report or root not in report.parents or report.exists():
        raise DotnetError("Runner report must be a fresh regular path below the selected project root")
    config = Path(config) if config else root / ".ai-tdd/config.json"
    if config.resolve() != config.absolute() or config.stat().st_size > 5_000_000:
        raise DotnetError("Unsafe .NET configuration path")
    value = json.loads(config.read_text(encoding="utf-8-sig"))
    configured = value.get("dotnet")
    if not isinstance(configured, dict) or configured.get("schema") != 1:
        raise DotnetError("Run init to configure the bounded native .NET runner")
    current = SETUP.configure(root)
    if current["dotnet"] != configured or current["generated_roots"] != value.get("generated_roots"):
        raise DotnetError("Evaluated .NET projects/frameworks/output ownership changed; repeat reviewed setup")
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise DotnetError(".NET SDK is unavailable on PATH")
    timeout = value.get("timeout_seconds", 600)
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise DotnetError(".NET runner timeout must be positive and at most 3600 seconds")
    folder = report.parent / (report.stem + "-dotnet-" + uuid.uuid4().hex)
    folder.mkdir(parents=False, exist_ok=False)
    report_data = {"schema": 1, "collected": [], "results": [], "native_modules": []}
    for index, module in enumerate(configured["modules"]):
        directory = folder / str(index)
        directory.mkdir()
        base = [dotnet, "test", str(root / module["project"]), "--framework", module["tfm"], "--verbosity", "minimal", "--nologo"]
        nunit = module["framework"] == "nunit-vstest"
        if nunit:
            artifacts = root / module["project"]
            artifacts = artifacts.parent / "bin" / ("ai-tdd-" + uuid.uuid4().hex)
            if artifacts.exists():
                raise DotnetError("NUnit artifacts directory must be fresh")
            dump, result_name = _nunit_target(root / module["project"], module["tfm"], artifacts, root)
            if dump.exists():
                raise DotnetError("NUnit discovery evidence must be fresh")
            base += ["--artifacts-path", str(artifacts)]
        discovery_args = ["--list-tests"] + (["--", "NUnit.DumpXmlTestDiscovery=true", "NUnit.DisplayName=FullName"] if nunit else [])
        discovery_code, discovery = _process(base + discovery_args, root, directory / "discovery.stdout.log", directory / "discovery.stderr.log", timeout)
        if discovery_code:
            raise DotnetError(".NET build/discovery failed; repair compilation or discovery before RED (local logs retained)")
        if nunit:
            if not dump.is_file() or dump.is_symlink() or dump.stat().st_size > 5_000_000:
                raise DotnetError("Missing fresh NUnit full discovery dump; repair discovery before RED")
            native_discovery = dump.read_text(encoding="utf-8-sig")
            (directory / "discovery.xml").write_text(native_discovery, encoding="utf-8")
        else:
            names = discovery_names(discovery)
        settings = (["NUnit.TestOutputXml=" + str(directory), "NUnit.DisplayName=FullName"] if nunit else
                    ["xUnit.ReporterSwitch=json", "xUnit.NoAutoReporters=true"])
        code, execution = _process(base + ["--no-build", "--no-restore", "--results-directory", str(directory),
                                          "--logger", "trx;LogFileName=result.trx", "--logger", "console;verbosity=normal", "--", *settings],
                                   root, directory / "execution.stdout.log", directory / "execution.stderr.log", timeout)
        if code not in (0, 1):
            raise DotnetError(".NET test execution did not produce a normal completed run")
        path = directory / "result.trx"
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 5_000_000:
            raise DotnetError("Missing fresh bounded TRX evidence")
        if nunit:
            native_results = directory / result_name
            if not native_results.is_file() or native_results.is_symlink() or native_results.stat().st_size > 5_000_000:
                raise DotnetError("Missing fresh NUnit native result XML; VSTest exit status alone is insufficient")
            evidence = reconcile_nunit(module["project"], module["tfm"], native_discovery, native_results.read_text(encoding="utf-8-sig"), path.read_text(encoding="utf-8-sig"))
        else:
            evidence = reconcile(module["project"], module["tfm"], names, execution, path.read_text(encoding="utf-8-sig"))
        failures = any(item["status"] in {"failed", "error"} for item in evidence["results"])
        if code != int(failures):
            raise DotnetError("Native exit status disagrees with executed outcomes")
        report_data["collected"].extend(evidence["collected"])
        report_data["results"].extend(evidence["results"])
        report_data["native_modules"].append({**module, "directory": directory.relative_to(root).as_posix(), "exit_code": code})
    with report.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report_data, ensure_ascii=False, indent=2) + "\n")
    return int(any(item["status"] in {"failed", "error"} for item in report_data["results"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", required=True)
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    try:
        return run(args.root, args.report, args.config)
    except (DotnetError, OSError, ValueError) as error:
        print("Native .NET evidence: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
