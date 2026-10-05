"""Native unfiltered .NET execution with independently reconciled evidence.

Only existing supported VSTest frameworks are accepted; no user adapter is
authored and no exception type is inferred from text or reporter Cause.
"""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
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
NATIVE_XML_MAX_BYTES = 64 * 1024 * 1024
NATIVE_JSON_MAX_BYTES = 64 * 1024 * 1024


class NativeOwnershipError(DotnetError):
    """An unsafe native evidence path aborts the entire module plan."""


def _unique_names(names):
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != len(names):
        raise DotnetError("Full discovery needs nonempty unique test display names; ambiguous/empty discovery is unsupported")
    return names


DISCOVERY_PREFIX = re.compile(r"^TpTrace Verbose: [^\r\n]*, TestRequestSender\.OnDiscoveryMessageReceived: Received message: (.*)$")


def _guid(value):
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise DotnetError("Missing/malformed native VSTest ID") from error
    if not parsed.int:
        raise DotnetError("Empty native VSTest ID")
    return str(parsed)


def discovery_cases(trace):
    """Read fresh VSTest transport JSON, never the shortened --list-tests text.

    Stream diagnostic lines so unrelated build/host tracing need not fit in
    memory. Each native message retains the existing 5 MB evidence bound.
    Serialization blobs are discarded; only native identity metadata is kept.
    """
    cases, vs_ids, completion = {}, set(), None
    for line in trace.splitlines() if isinstance(trace, str) else trace:
        if len(line) > 5_000_000:
            raise DotnetError("Oversized VSTest discovery diagnostic message")
        match = DISCOVERY_PREFIX.fullmatch(line.rstrip("\r\n"))
        if not match:
            continue
        try:
            event = json.loads(match[1])
        except ValueError as error:
            raise DotnetError("Malformed VSTest discovery transport JSON") from error
        if not isinstance(event, dict):
            raise DotnetError("Unsupported VSTest discovery message")
        version = event.get("Version", 0)
        if type(version) is not int or version not in range(8):
            raise DotnetError("Unsupported VSTest discovery transport version")
        kind, payload = event.get("MessageType"), event.get("Payload")
        if kind == "TestSession.Message":
            if not isinstance(payload, dict) or type(payload.get("MessageLevel")) is not int or payload["MessageLevel"] not in (0, 1, 2):
                raise DotnetError("Malformed VSTest discovery diagnostic")
            if payload["MessageLevel"] != 0:
                raise DotnetError("VSTest reported a discovery warning/error; inspect local diagnostic logs")
            if not isinstance(payload.get("Message"), str) or "Skipping test case with duplicate ID" in payload["Message"]:
                raise DotnetError("Missing diagnostic text or duplicate xUnit case suppressed by discovery")
            continue
        if kind not in {"TestDiscovery.TestFound", "TestDiscovery.Completed"}:
            continue
        if completion is not None:
            raise DotnetError("Duplicate/late VSTest discovery lifecycle message")
        if kind == "TestDiscovery.Completed":
            if not isinstance(payload, dict) or payload.get("IsAborted") is not False:
                raise DotnetError("Incomplete/aborted VSTest discovery")
            completion = payload
            rows = payload.get("LastDiscoveredTests")
            if rows is None:
                rows = []
        else:
            rows = payload
        if not isinstance(rows, list):
            raise DotnetError("Missing structured VSTest discovery cases")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("Properties"), list):
                raise DotnetError("Missing native xUnit discovery properties")
            properties = {}
            for prop in row["Properties"]:
                if not isinstance(prop, dict) or not isinstance(prop.get("Key"), dict) or "Value" not in prop:
                    raise DotnetError("Malformed native discovery property")
                key = _text(prop["Key"], "Id")
                if key in properties:
                    raise DotnetError("Duplicate native discovery property")
                properties[key] = prop.get("Value")
            if "MSTestDiscoverer.TmiTestId" in properties:
                raise DotnetError("Unsupported override of native xUnit test ID")
            # Older wire protocols keep built-in TestCase fields in Properties.
            fields = {key: row.get(key, properties.get("TestCase." + key)) for key in
                      ("Id", "Source", "ExecutorUri", "FullyQualifiedName", "DisplayName")}
            if any(key in row and "TestCase." + key in properties and row[key] != properties["TestCase." + key] for key in fields):
                raise DotnetError("Conflicting native VSTest discovery identity fields")
            if version in (0, 1, 3) and any(key in row for key in fields) or version in (2, 4, 5, 6, 7) and any(key not in row for key in fields):
                raise DotnetError("Unsupported VSTest case layout for the negotiated transport version")
            case_id, vs_id = _text(properties, "XunitTestCaseUniqueID"), _guid(fields["Id"])
            if case_id in cases or vs_id in vs_ids:
                raise DotnetError("Duplicate native xUnit/VSTest discovery ID")
            source, uri = _text(fields, "Source"), _text(fields, "ExecutorUri")
            if not uri.startswith("executor://xunit/") or not Path(source).is_absolute():
                raise DotnetError("Unsupported discovery adapter/source identity")
            cases[case_id] = {"vstest_id": vs_id, "source": source, "executor_uri": uri,
                              "method": _text(fields, "FullyQualifiedName"), "display_name": _text(fields, "DisplayName")}
            vs_ids.add(vs_id)
    if completion is None or not cases or type(completion.get("TotalTests")) is not int or completion["TotalTests"] != len(cases):
        raise DotnetError("Missing/inconsistent full VSTest discovery completion and case count")
    sources = {case["source"] for case in cases.values()}
    full = completion.get("FullyDiscoveredSources")
    if len(sources) != 1 or not isinstance(full, list) or len(full) != 1 or not isinstance(full[0], str) or set(full) != sources:
        raise DotnetError("Discovery must completely enumerate exactly one native test assembly")
    for key in ("PartiallyDiscoveredSources", "NotDiscoveredSources", "SkippedDiscoverySources"):
        if completion.get(key) != []:
            raise DotnetError("VSTest discovery contains incomplete/skipped sources")
    return cases


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


def _policy_failure(types, messages):
    return any(exception == "System.IO.FileLoadException" and
               re.search(r"(?<![0-9a-f])0x800711c7(?![0-9a-f])", message, re.I)
               for exception, message in zip(types, messages))


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
    policy_blocked = _policy_failure(arrays["ExceptionTypes"], arrays["Messages"])
    if policy_blocked:
        assertion, actual_type = False, "System.IO.FileLoadException"
    result = {"status": "failed" if assertion else "error", "exception": "AssertionError" if assertion else actual_type or "UnknownFailure",
            "native_exception_types": arrays["ExceptionTypes"], "native_exception_parent_indices": arrays["ExceptionParentIndices"],
            "native_messages": arrays["Messages"], "native_stack_traces": arrays["StackTraces"], "native_cause": event.get("Cause"),
            "detail": "\n".join(arrays["Messages"])[:1200]}
    if policy_blocked:
        result.update(native_failure_code="application_control_blocked", native_hresult="0x800711C7")
    return result


def _read_native_xml(path, label):
    """Read a bounded regular native XML file; distinguish missing from unsafe."""
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise DotnetError("Missing fresh " + label + " evidence") from error
    except OSError as error:
        raise DotnetError("Unsafe " + label + " evidence: " + type(error).__name__) from error
    try:
        if (not stat.S_ISREG(info.st_mode) or path.resolve() != path.absolute()
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise DotnetError("Unsafe " + label + " evidence: expected a regular file without links/junctions")
        if info.st_size > NATIVE_XML_MAX_BYTES:
            raise DotnetError("Oversized " + label + " evidence: " + str(info.st_size) + " bytes; limit 64 MiB")
        with path.open("rb") as stream:
            raw = stream.read(NATIVE_XML_MAX_BYTES + 1)
        if len(raw) > NATIVE_XML_MAX_BYTES:
            raise DotnetError("Oversized " + label + " evidence: limit 64 MiB")
        return raw.decode("utf-8-sig")
    except OSError as error:
        raise DotnetError("Unsafe " + label + " evidence: " + type(error).__name__) from error
    except UnicodeDecodeError as error:
        raise DotnetError("Malformed " + label + " evidence: expected UTF-8 XML") from error


def _xml(raw):
    if len(raw) > NATIVE_XML_MAX_BYTES or len(raw.encode("utf-8")) > NATIVE_XML_MAX_BYTES:
        raise DotnetError("Oversized native XML evidence: limit 64 MiB")
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise DotnetError("DTD/entity XML evidence is unsupported")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as error:
        raise DotnetError("Malformed native XML evidence") from error


def _trx(raw, outcomes, native=None, *, parent_rows=False):
    tree = _xml(raw)
    namespace = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"
    if tree.tag != namespace + "TestRun":
        raise DotnetError("TRX needs the native TestRun schema")
    if parent_rows:
        containers = tree.findall(namespace + "Results")
        if (len(containers) != 1 or any(item.tag != namespace + "UnitTestResult" for item in containers[0])
                or tree.findall(".//" + namespace + "InnerResults")
                or len(tree.findall(".//" + namespace + "UnitTestResult")) != len(containers[0])):
            raise DotnetError("Runtime theory TRX requires one flat Results container of native UnitTestResult rows")
    actual, parent_executions = {}, {}
    executions = set()
    for item in tree.findall(namespace + "Results/" + namespace + "UnitTestResult"):
        name, outcome = (_guid(item.get("testId")) if native else item.get("testName")), item.get("outcome")
        if not name or name in actual and not parent_rows or outcome not in {"Passed", "Failed", "NotExecuted"}:
            raise DotnetError("TRX contains missing/duplicate/unsupported outcomes")
        if parent_rows:
            actual.setdefault(name, []).append(outcome)
        else:
            actual[name] = outcome
        if native:
            execution_id = _guid(item.get("executionId"))
            if execution_id in executions:
                raise DotnetError("TRX contains duplicate executions")
            executions.add(execution_id)
            parent_executions.setdefault(name, set()).add(execution_id)
    if native:
        definitions = {}
        for definition in tree.findall(namespace + "TestDefinitions/" + namespace + "UnitTest"):
            test_id = _guid(definition.get("id"))
            methods, runs = definition.findall(namespace + "TestMethod"), definition.findall(namespace + "Execution")
            if test_id in definitions or test_id not in native or len(methods) != 1 or len(runs) != 1:
                raise DotnetError("TRX definitions disagree with native discovery identity")
            method, case = methods[0], native[test_id]
            if (method.get("className", "") + "." + method.get("name", "") != case["method"]
                    or method.get("adapterTypeName") != case["executor_uri"]
                    or Path(method.get("codeBase", "")) != Path(case["source"])
                    or _guid(runs[0].get("id")) not in parent_executions.get(test_id, set())):
                raise DotnetError("TRX method/source/execution differs from discovered native test")
            definitions[test_id] = definition
        if set(definitions) != set(native):
            raise DotnetError("TRX is missing native test definitions")
    translation = {"test-passed": "Passed", "test-failed": "Failed", "test-skipped": "NotExecuted", "test-not-run": "NotExecuted"}
    expected = ({name: [translation[outcome] for outcome in rows] for name, rows in outcomes.items()} if parent_rows else
                {name: translation[outcome] for name, outcome in outcomes.items()})
    mismatch = (set(actual) != set(expected) or any(Counter(actual[name]) != Counter(expected[name]) for name in actual)) if parent_rows else actual != expected
    if mismatch:
        raise DotnetError("Fresh TRX and native reporter disagree on test inventory/outcomes")
    counters = tree.findall(namespace + "ResultSummary/" + namespace + "Counters")
    if len(counters) != 1:
        raise DotnetError("TRX requires one execution count summary")
    leaves = [value for rows in actual.values() for value in rows] if parent_rows else list(actual.values())
    counts = {"total": len(leaves), "passed": sum(value == "Passed" for value in leaves),
              "failed": sum(value == "Failed" for value in leaves),
              "executed": sum(value != "NotExecuted" for value in leaves)}
    for key, value in counts.items():
        if counters[0].get(key) != str(value):
            raise DotnetError("TRX declared counts disagree with execution")
    for key in ("error", "timeout", "aborted", "inconclusive", "passedButRunAborted", "notRunnable", "disconnected", "inProgress", "pending"):
        if counters[0].get(key, "0") != "0":
            raise DotnetError("TRX records an incomplete/error run: " + key)
    if tree.findall(".//" + namespace + "RunInfo"):
        raise DotnetError("TRX run diagnostics prevent clean native evidence")


def reconcile(project, tfm, discovered, stdout, trx, *, runtime_theories=False):
    """Join full discovered IDs with actual typed lifecycle and fresh TRX."""
    if not isinstance(discovered, dict) or not discovered:
        raise DotnetError("Full structured xUnit discovery is required")
    assembly, completed = None, False
    cases, case_tests, finished_cases, tests, terminals, finished_tests = {}, {}, set(), {}, {}, set()
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
        if runtime_theories and kind in {"test-starting", "test-finished", "test-case-finished", *TERMINALS}:
            parent = cases.get(event.get("TestCaseUniqueID"))
            if parent is None or any(_text(event, key) != parent[key] for key in
                                     ("TestCollectionUniqueID", "TestClassUniqueID", "TestMethodUniqueID")):
                raise DotnetError("Native row/case ancestry differs from its exact active parent lifecycle")
        if kind == "test-case-starting":
            case_id = _text(event, "TestCaseUniqueID")
            if case_id in cases:
                raise DotnetError("Duplicate native test case lifecycle")
            _text(event, "TestClassName")
            _text(event, "TestMethodName")
            if runtime_theories:
                for key in ("TestCollectionUniqueID", "TestClassUniqueID", "TestMethodUniqueID"):
                    _text(event, key)
            if case_id not in discovered or event["TestClassName"] + "." + event["TestMethodName"] != discovered[case_id]["method"]:
                raise DotnetError("Native execution case/method differs from full discovery")
            cases[case_id] = event
        elif kind == "test-starting":
            test_id, case_id = _text(event, "TestUniqueID"), _text(event, "TestCaseUniqueID")
            if test_id in tests or case_id not in cases or case_id in finished_cases:
                raise DotnetError("Invalid/duplicate test-starting lifecycle")
            _text(event, "TestDisplayName")
            if case_id in case_tests and not runtime_theories:
                raise DotnetError("Exactly one test per discovered case is required; delayed theory rows/retries are unsupported")
            tests[test_id] = event
            case_tests.setdefault(case_id, []).append(test_id)
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
            members = case_tests.get(case_id, [])
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
    if set(cases) != set(discovered):
        raise DotnetError("Full discovery differs from actual executed inventory; filters/retries/undiscovered theory rows are unsupported")
    if runtime_theories:
        outcomes = {discovered[case_id]["vstest_id"]: [terminals[test_id]["$type"] for test_id in members]
                    for case_id, members in case_tests.items()}
    else:
        outcomes = {discovered[tests[test_id]["TestCaseUniqueID"]]["vstest_id"]: event["$type"] for test_id, event in terminals.items()}
    # The native adapter supplies only parent VSTest IDs to TRX. Compare all
    # independent row outcomes under each exact parent, without inventing a
    # reporter-child to randomly assigned TRX execution GUID association.
    _trx(trx, outcomes, {case["vstest_id"]: case for case in discovered.values()}, parent_rows=runtime_theories)
    results = []
    for test_id, event in terminals.items():
        item = tests[test_id]
        identity = project + "|" + tfm + "|xunit:" + item["TestCaseUniqueID"]
        if runtime_theories:
            identity += "|test:" + test_id
        result = {"id": identity, "display_name": item["TestDisplayName"],
                  "native_case_id": item["TestCaseUniqueID"], "vstest_id": discovered[item["TestCaseUniqueID"]]["vstest_id"],
                  "status": TERMINALS[event["$type"]], "exception": "", "detail": event.get("Reason", "")}
        if runtime_theories:
            result["native_test_id"] = test_id
        if event["$type"] == "test-failed":
            result.update(_failure(event, cases[item["TestCaseUniqueID"]]))
        results.append(result)
    collected = [item["id"] for item in results] if runtime_theories else [project + "|" + tfm + "|xunit:" + case_id for case_id in discovered]
    return {"schema": 1, "collected": collected, "results": results}


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
        target = Path(SETUP.msbuild_path(props["TargetDir"])).resolve()
        filename = SETUP.msbuild_path(props["TargetFileName"])
    except (ValueError, KeyError, TypeError) as error:
        raise DotnetError("Unsupported NUnit output metadata") from error
    if target != artifacts and artifacts not in target.parents or not filename or Path(filename).name != filename:
        raise NativeOwnershipError("NUnit artifacts must stay within the fresh owned bin/ directory")
    return target / "Dump" / ("D_" + filename + ".dump"), Path(filename).stem + ".xml"


def _process(argv, root, stdout_path, stderr_path, timeout):
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            result = subprocess.run(argv, cwd=root, env=SETUP.environment(), shell=False, stdout=stdout, stderr=stderr, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DotnetError("Native .NET execution failed: " + type(error).__name__ + "; inspect the local run logs") from error
    return result.returncode, stdout_path.read_text(encoding="utf-8-sig", errors="replace")


def _native_diagnostic(stdout, stderr=""):
    """Classify advisory failures from typed records, never assertion evidence."""
    try:
        events = _events(stdout)
    except DotnetError:
        events = []
    runtime = None
    for event in events:
        if event.get("$type") != "test-failed" and event.get("$type") != "error-message" and not event.get("$type", "").endswith("cleanup-failure"):
            continue
        try:
            failure = _failure(event, {})
        except DotnetError:
            continue
        for exception, message in zip(failure["native_exception_types"], failure["native_messages"]):
            if exception == "System.IO.FileLoadException" and re.search(r"(?<![0-9a-f])0x800711c7(?![0-9a-f])", message, re.I):
                return {"kind": "application-control", "code": "application_control_blocked", "exception_type": exception, "hresult": "0x800711C7",
                        "message": "Windows Application Control blocked an assembly; repair its trusted build/install provenance before rerunning. Policy was not changed."}
            if runtime is None and exception and exception not in ASSERTIONS:
                code = ("assembly_load_failure" if exception in {"System.IO.FileLoadException", "System.IO.FileNotFoundException",
                                                                "System.BadImageFormatException", "System.Reflection.ReflectionTypeLoadException"}
                        else "native_runtime_error")
                runtime = {"kind": "native-runtime-error", "code": code, "exception_type": exception, "message": message[:1200]}
    # This is only a failure advisory, never a lifecycle/assertion witness.
    # The existing adapter may fail before it can emit typed JSON records.
    # Recognize its concrete catastrophic exception header and exact Windows
    # HRESULT, without depending on localized descriptions of the policy.
    header = re.search(r"(?m)^\s*(?:\[xUnit\.net \d{2}:\d{2}:\d{2}\.\d{2}\]\s+[^\r\n:]+:\s+)?"
                       r"Catastrophic failure:\s*System\.IO\.FileLoadException(?:\s|:)", stderr)
    if header and re.search(r"(?<![0-9a-f])0x800711c7(?![0-9a-f])", stderr[header.start():], re.I):
        return {"kind": "application-control", "code": "application_control_blocked", "exception_type": "System.IO.FileLoadException",
                "hresult": "0x800711C7", "evidence_source": "adapter-stderr",
                "message": "The existing xUnit adapter reports an assembly blocked by Windows Application Control before native JSON. Policy was not changed."}
    return runtime or {}


def _advisory_stderr(path):
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.resolve() != path.absolute() or info.st_size > 1_000_000
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return ""
        with path.open("rb") as stream:
            raw = stream.read(1_000_001)
        return raw.decode("utf-8-sig", errors="replace") if len(raw) <= 1_000_000 else ""
    except OSError:
        return ""


def _logs(directory, root):
    names = ("discovery.stdout.log", "discovery.stderr.log", "discovery.diag.log", "discovery.xml",
             "execution.stdout.log", "execution.stderr.log", "result.trx")
    return {name: (directory / name).relative_to(root).as_posix() for name in names if (directory / name).is_file()}


def _write_progress(report, data, *, initial=False):
    raw = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if len(raw.encode("utf-8")) > NATIVE_JSON_MAX_BYTES:
        raise DotnetError("Normalized native report exceeds the 64 MiB evidence bound; full native logs are retained")
    if initial:
        with report.open("x", encoding="utf-8") as stream:
            stream.write(raw)
        return
    info = report.lstat()
    if (not stat.S_ISREG(info.st_mode) or report.resolve() != report.absolute()
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
        raise DotnetError("Unsafe native progress report path")
    temporary = report.with_name(report.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(raw)
        os.replace(temporary, report)
    finally:
        temporary.unlink(missing_ok=True)


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
    absent_inputs = configured.get("external_absent_inputs", [])
    absent_before = SETUP.external_absent_snapshot(root, absent_inputs)
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise DotnetError(".NET SDK is unavailable on PATH")
    timeout = value.get("timeout_seconds", 600)
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise DotnetError(".NET runner timeout must be positive and at most 3600 seconds")
    folder = report.parent / (report.stem + "-dotnet-" + uuid.uuid4().hex)
    folder.mkdir(parents=False, exist_ok=False)
    report_data = {"schema": 1, "completion": "incomplete", "planned_module_count": len(configured["modules"]),
                   "collected": [], "results": [], "diagnostics": [],
                   "native_modules": [{**module, "status": "pending"} for module in configured["modules"]]}
    _write_progress(report, report_data, initial=True)
    for index, module in enumerate(configured["modules"]):
        directory = folder / str(index)
        directory.mkdir()
        receipt = report_data["native_modules"][index]
        receipt.update(status="running", directory=directory.relative_to(root).as_posix(), phase="discovery")
        execution = ""
        _write_progress(report, report_data)
        try:
            base = [dotnet, "test", str(root / module["project"]), "--framework", module["tfm"], "--verbosity", "minimal", "--nologo"]
            if module.get("runsettings"):
                base += ["--settings", str(root / module["runsettings"]["path"])]
            nunit = module["framework"] == "nunit-vstest"
            runtime_theories = not nunit and configured.get("theory_mode") == "runtime-parent-rows-v1"
            theory_settings = ["xUnit.PreEnumerateTheories=false"] if runtime_theories else []
            if nunit:
                artifacts = (root / module["project"]).parent / "bin" / ("ai-tdd-" + uuid.uuid4().hex)
                if artifacts.exists():
                    raise DotnetError("NUnit artifacts directory must be fresh")
                dump, result_name = _nunit_target(root / module["project"], module["tfm"], artifacts, root)
                if dump.exists():
                    raise DotnetError("NUnit discovery evidence must be fresh")
                base += ["--artifacts-path", str(artifacts)]
            discovery_log = directory / "discovery.diag.log"
            discovery_args = ["--list-tests"] + (["--", "NUnit.DumpXmlTestDiscovery=true", "NUnit.DisplayName=FullName"] if nunit else
                                                ["--diag", str(discovery_log), "--", "RunConfiguration.BatchSize=100", *theory_settings])
            discovery_code, discovery = _process(base + discovery_args, root, directory / "discovery.stdout.log", directory / "discovery.stderr.log", timeout)
            receipt["discovery_exit_code"] = discovery_code
            if discovery_code:
                raise DotnetError(".NET build/discovery failed; repair compilation or discovery before RED (local logs retained)")
            if nunit:
                native_discovery = _read_native_xml(dump, "NUnit full discovery XML")
                (directory / "discovery.xml").write_text(native_discovery, encoding="utf-8")
            else:
                if not discovery_log.is_file() or discovery_log.is_symlink():
                    raise DotnetError("Missing fresh structured VSTest discovery diagnostics")
                with discovery_log.open(encoding="utf-8-sig") as stream:
                    inventory = discovery_cases(iter(lambda: stream.readline(5_000_001), ""))
                receipt["discovery_case_count"] = len(inventory)
                owned_bin = (root / module["project"]).parent / "bin"
                native_source = Path(next(iter(inventory.values()))["source"])
                if owned_bin not in native_source.parents or native_source.resolve() != native_source:
                    raise NativeOwnershipError("Native discovery assembly must remain inside its owned project bin directory")
            receipt["phase"] = "execution"
            _write_progress(report, report_data)
            settings = (["NUnit.TestOutputXml=" + str(directory), "NUnit.DisplayName=FullName"] if nunit else
                        ["xUnit.ReporterSwitch=json", "xUnit.NoAutoReporters=true", *theory_settings])
            code, execution = _process(base + ["--no-build", "--no-restore", "--results-directory", str(directory),
                                              "--logger", "trx;LogFileName=result.trx", "--logger", "console;verbosity=normal", "--", *settings],
                                       root, directory / "execution.stdout.log", directory / "execution.stderr.log", timeout)
            receipt["exit_code"] = code
            if code not in (0, 1):
                raise DotnetError(".NET test execution did not produce a normal completed run")
            receipt["phase"] = "reconciliation"
            native_trx = _read_native_xml(directory / "result.trx", "TRX")
            if nunit:
                evidence = reconcile_nunit(module["project"], module["tfm"], native_discovery,
                                           _read_native_xml(directory / result_name, "NUnit native result XML"), native_trx)
            else:
                evidence = reconcile(module["project"], module["tfm"], inventory, execution, native_trx, runtime_theories=runtime_theories)
            failures = any(item["status"] in {"failed", "error"} for item in evidence["results"])
            if code != int(failures):
                raise DotnetError("Native exit status disagrees with executed outcomes")
            report_data["collected"].extend(evidence["collected"])
            report_data["results"].extend(evidence["results"])
            receipt.update(status="complete", executed_row_count=len(evidence["results"]))
            receipt.pop("phase", None)
        except (DotnetError, OSError, ValueError) as error:
            advisory = _native_diagnostic(execution, _advisory_stderr(directory / "execution.stderr.log"))
            diagnostic = {"module_index": index, "project": module["project"], "tfm": module["tfm"],
                          "phase": receipt["phase"], "kind": "native-" + receipt["phase"] + "-error", "message": str(error),
                          "code": "native_" + receipt["phase"] + "_error",
                          "logs": _logs(directory, root)}
            if isinstance(error.__cause__, subprocess.TimeoutExpired):
                diagnostic["kind"] = "native-process-timeout"
                diagnostic["code"] = "native_process_timeout"
            elif isinstance(error.__cause__, OSError):
                diagnostic["kind"] = "native-process-launch-error"
                diagnostic["code"] = "native_process_launch_error"
            if advisory:
                diagnostic.update(advisory)
                diagnostic["reconciliation_error"] = str(error)
            receipt.update(status="incomplete", diagnostics=[diagnostic])
            report_data["diagnostics"].append(diagnostic)
            if isinstance(error, NativeOwnershipError):
                diagnostic["kind"] = "native-ownership-error"
                diagnostic["code"] = "native_ownership_error"
                _write_progress(report, report_data)
                raise
        # External absence remains a global ownership invariant even when the
        # native module fails. A drift aborts all remaining work and can never
        # be transformed into a completed acceptance report.
        try:
            if SETUP.external_absent_snapshot(root, absent_inputs) != absent_before:
                raise DotnetError("External absent project input changed during native execution")
        except DotnetError as error:
            diagnostic = {"module_index": index, "phase": "ownership", "kind": "native-ownership-error", "message": str(error),
                          "code": "native_ownership_error",
                          "logs": _logs(directory, root)}
            receipt.update(status="incomplete", diagnostics=receipt.get("diagnostics", []) + [diagnostic])
            report_data["diagnostics"].append(diagnostic)
            _write_progress(report, report_data)
            raise
        _write_progress(report, report_data)
    if SETUP.external_absent_snapshot(root, absent_inputs) != absent_before:
        raise DotnetError("External absent project input changed during native execution")
    if report_data["diagnostics"]:
        return 2
    report_data["completion"] = "complete"
    _write_progress(report, report_data)
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
