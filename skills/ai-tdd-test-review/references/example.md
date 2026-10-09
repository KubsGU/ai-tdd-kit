# Synthetic cache review example

All paths, names, code, and results below are illustrative. Neither this example
nor its counterexamples were executed. They contain no private repository data.

## Input supplied to the reviewer

Review these proposed tests against the contract. Do not modify or execute files.
Repository convention: neighboring tests use pytest and local fakes. No runner,
lint, format, type, or security-check output is supplied.

Contract:

- AC1: `Lookup.get(key)` returns the value supplied by its provider for that key.
- AC2: after a successful first lookup, subsequent lookups of the same key use the
  cached value and make no additional provider calls for the lifetime of `Lookup`.
- AC3: different keys have independent cache entries.

Proposed `tests/test_lookup.py`:

```python
class CountingProvider:
    def __init__(self):
        self.values = {"alpha": 17, "beta": 29}
        self.calls = []

    def get(self, key):
        self.calls.append(key)
        return self.values[key]


def test_returns_a_value():
    provider = CountingProvider()
    lookup = Lookup(provider)
    actual = lookup.get("alpha")
    assert actual == actual


def test_reuses_the_cached_value():
    provider = CountingProvider()
    lookup = Lookup(provider)
    first = lookup.get("alpha")
    second = lookup.get("alpha")
    assert (first, second) == (17, 17)
    assert provider.calls == ["alpha"]
```

The proposed implementation diff is not supplied. `Lookup` is the supplied public
API; the reviewer should not invent a package import or claim to have inspected it.

## Illustrative review output

### Scope and contract

Reviewed the three supplied cache clauses and the supplied test excerpt. Tests
are identified by path and function name; no runner IDs are available. The source,
full neighboring tests, and diff were not supplied, so implementation defects and
broader integration behavior remain unassessed. Contract scenarios were derived
before examining an implementation.

### Findings

- **P2 — self-equality does not establish AC1**, `tests/test_lookup.py::test_returns_a_value`.
  Observation: the only assertion compares `actual` with itself. Proposed,
  unexecuted counterexample: a `Lookup.get` that always returns `None` would satisfy
  this assertion for `"alpha"`; AC1 requires the provider's value, 17. This test
  cannot detect a lost or incorrect returned value. The second test already detects
  that particular faulty implementation. Remove the redundant weak test or replace
  it with a distinct contract scenario, preserving the useful second test.
- **P2 — AC3 has no check in the supplied tests.** Observation: every lookup uses
  `"alpha"`. Proposed, unexecuted counterexample: a single cache slot reused for
  every key would pass the useful repeated-key test but return 17 for `"beta"`,
  where AC1 and AC3 require 29. Add one focused two-key scenario; establish both
  values and repeat each key to check independent caching. This is a test gap,
  not a claim that the absent implementation contains that defect.

### Test assessment

| Test | Concrete fault detected | Independent oracle | Distinct value |
| --- | --- | --- | --- |
| `test_returns_a_value` | No meaningful returned-value fault for the shown integer/None outcomes. | None; self-equality is not AC1's expected value. | Redundant weak assertion; repair or remove while keeping useful coverage. |
| `test_reuses_the_cached_value` | Always returning `None`, returning a wrong value, or calling the provider again on the second successful same-key lookup. | AC1 fixes forwarding of the fake's declared value, 17; AC2 requires a single provider call. | Keep: the call assertion checks an explicitly observable cache contract and the pair of values checks forwarding. |

### Execution evidence

No execution evidence was supplied. This reviewer executed no commands. Lint,
format, type, and security checks are unverified. The call count above is an
assertion in code, not an observed executed count.

### Next actions and limits

Changes recommended: preserve `test_reuses_the_cached_value`; replace the weak
self-equality case with AC3's two-key scenario, then have the developer execute the
tests and existing repository checks. The excerpt does not establish empty-key,
exception-caching, expiry, concurrency, or persistence requirements. Do not add
those behaviors without a contract. This assessment does not certify completion.
