"""Opt-in paired native Claude model benchmark; no trials without --run.

The fixed protocol keeps failures and reported usage, never rerolls a trial,
and writes only sanitized summaries. Raw transcripts remain ephemeral.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

from model_benchmark_cases import CASES, case_fingerprint

KIT = Path(__file__).resolve().parents[1]
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"]
PROFILES = {"whole": {"models": MODELS, "implementer_model": None},
            "mixed-haiku": {"models": ["claude-sonnet-5-5"], "implementer_model": "haiku"}}
PROTOCOL_REVISION = 2
SEED = 20261001
REPETITIONS = 2
MAX_BUDGET_USD = 3
MAX_TURNS = 60
TIMEOUT_SECONDS = 600
EVALUATOR_TIMEOUT_SECONDS = 780


def trial_plan(profile="whole"):
    rng = random.Random(SEED)
    blocks = [(case, repetition) for case in CASES for repetition in range(1, REPETITIONS + 1)]
    rng.shuffle(blocks)
    rows = []
    for block_id, (case, repetition) in enumerate(blocks, 1):
        models = PROFILES[profile]["models"].copy()
        rng.shuffle(models)
        for model in models:
            rows.append({"trial_id": f"{profile}-v{PROTOCOL_REVISION}-{case}-r{repetition}-{model}", "block": block_id,
                         "case": case, "repetition": repetition, "model": model, "profile": profile})
    return rows


def fingerprint_files(plugin):
    """Fail closed if the kit used by the trials changes during the experiment."""
    paths = [KIT / "scripts/evaluate_claude.py", KIT / "scripts/model_benchmark_cases.py",
             KIT / "scripts/benchmark_models.py", KIT / "scripts/launch_claude.py",
             KIT / "validation/MODEL_BENCHMARK_PROTOCOL.md"]
    paths += sorted(path for path in Path(plugin).rglob("*") if path.is_file()
                    and "tests" not in path.relative_to(plugin).parts
                    and "__pycache__" not in path.parts and path.suffix != ".pyc")
    result = {}
    for path in paths:
        label = "plugin/" + path.relative_to(plugin).as_posix() if path.is_relative_to(plugin) else path.relative_to(KIT).as_posix()
        result[label] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def protocol(plugin, profile="whole"):
    value = {"schema": 2, "revision": PROTOCOL_REVISION, "profile": profile,
             "seed": SEED, "repetitions": REPETITIONS, "models": PROFILES[profile]["models"],
             "worker_models": {"test-author": "inherit", "implementer": PROFILES[profile]["implementer_model"] or "inherit", "verifier": "inherit"},
             "trial_count": len(trial_plan(profile)), "max_budget_usd_per_trial": MAX_BUDGET_USD,
             "max_turns_per_trial": MAX_TURNS, "model_timeout_seconds": TIMEOUT_SECONDS,
             "evaluator_timeout_seconds": EVALUATOR_TIMEOUT_SECONDS,
             "effort_policy": "model-native default, no --effort; not equal reasoning budgets",
             "case_fingerprint": case_fingerprint(), "trial_plan": trial_plan(profile),
             "files": fingerprint_files(plugin)}
    value["protocol_fingerprint"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()
    return value


def run_trial(row, plugin, reports, capsules):
    target = reports / (row["trial_id"] + ".json")
    argv = [sys.executable, "-B", str(KIT / "scripts/evaluate_claude.py"),
            "--output", str(target), "--plugin-dir", str(plugin), "--case", row["case"],
            "--model", row["model"], "--timeout", str(TIMEOUT_SECONDS),
            "--max-turns", str(MAX_TURNS), "--max-budget-usd", str(MAX_BUDGET_USD),
            "--test-strength", "--require-usage", "--require-model-policy", "--quiet",
            "--project-artifact", str(capsules / (row["trial_id"] + ".zip"))]
    implementer = PROFILES[row["profile"]]["implementer_model"]
    if implementer:
        argv += ["--implementer-model", implementer]
    else:
        argv += ["--require-same-model"]
    started = time.monotonic()
    try:
        completed = subprocess.run(argv, cwd=KIT, capture_output=True, timeout=EVALUATOR_TIMEOUT_SECONDS)
        summary = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        if not isinstance(summary, dict) or not summary:
            summary = {"passed": False, "diagnostic": "Evaluator did not produce a sanitized report",
                       "evaluator_exit_code": completed.returncode}
    except subprocess.TimeoutExpired:
        try:
            summary = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        except (OSError, ValueError):
            summary = {}
        if not isinstance(summary, dict):
            summary = {}
        summary.update(passed=False, timed_out=True, evaluator_timed_out=True,
                       diagnostic="Evaluator exceeded its outer deadline; only existing final usage is retained")
    except (OSError, ValueError):
        summary = {"passed": False, "diagnostic": "Evaluator launch or report failed"}
    summary["evaluation_elapsed_seconds"] = round(time.monotonic() - started, 1)
    if summary.get("project_artifact", {}).get("saved"):
        summary["project_artifact"]["file"] = row["trial_id"] + ".zip"
    return {**row, "summary": summary}


def aggregate(rows):
    """Failures stay in denominators and costs; missing observations stay missing."""
    values = {}
    for model in MODELS:
        selected = [row for row in rows if row["model"] == model]
        summaries = [row["summary"] for row in selected]
        costs = [value.get("usage", {}).get("estimated_cost_usd") for value in summaries]
        numeric_costs = [cost for cost in costs if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0]
        elapsed = [value.get("model_elapsed_seconds") for value in summaries]
        strengths = [value.get("test_strength", {}) for value in summaries]
        values[model] = {
            "trials": len(selected), "passed": sum(value.get("passed") is True for value in summaries),
            "oracle_passed": sum(value.get("independent_behavior_checks", {}).get("passed") is True for value in summaries),
            "reported_cost_usd_total": round(sum(numeric_costs), 8) if len(numeric_costs) == len(selected) and selected else None,
            "reported_cost_usd_observed": round(sum(numeric_costs), 8), "cost_reports_missing": len(costs) - len(numeric_costs),
            "model_elapsed_seconds_total": round(sum(elapsed), 1) if elapsed and all(type(value) in (int, float) for value in elapsed) else None,
            "selected_mutants_detected": sum(value.get("detected", 0) for value in strengths),
            "selected_mutants_survived": sum(value.get("survived", 0) for value in strengths),
            "selected_mutants_unusable": sum(value.get("unusable", 0) for value in strengths),
            "test_strength_trials_unavailable": sum(value.get("available") is not True for value in strengths),
        }
    return values


def write_report(target, report):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Authorize these 18 native model calls with the frozen caps")
    parser.add_argument("--profile", choices=list(PROFILES), default="whole", help="Separate whole-model baseline or six-trial Haiku-implementer follow-up")
    parser.add_argument("--jobs", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--output", default=str(KIT / "dist/local-model-benchmark.json"))
    parser.add_argument("--plugin-dir", default=str(KIT / "plugins/ai-tdd"))
    args = parser.parse_args()
    plugin = Path(args.plugin_dir).resolve()
    frozen = protocol(plugin, args.profile)
    if not args.run:
        print(json.dumps(frozen, indent=2))
        return 0
    target = Path(args.output)
    capsules = target.parent / (target.stem + "-capsules")
    if target.exists() or capsules.exists():
        parser.error("Experiment report or capsules already exist; choose a distinct output, never overwrite prior trials")
    capsules.mkdir(parents=True)
    report = {"schema": 2, "status": "running", "protocol": frozen, "jobs": args.jobs,
              "capsule_directory": capsules.name,
              "cost_scope": "Claude final total_cost_usd, reported API-equivalent; not an invoice",
              "trials": [], "aggregate": aggregate([])}
    write_report(target, report)  # The protocol exists before any model process.
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ai-tdd-benchmark-reports-") as folder:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            plan = frozen["trial_plan"]
            blocks = [[row for row in plan if row["block"] == block] for block in sorted({row["block"] for row in plan})]
            for block in blocks:
                if fingerprint_files(plugin) != frozen["files"]:
                    report["status"] = "protocol_changed"
                    write_report(target, report)
                    raise SystemExit("Frozen benchmark inputs changed; remaining trials were not launched")
                futures = [pool.submit(run_trial, row, plugin, Path(folder), capsules) for row in block]
                for row, future in zip(block, futures):
                    completed = future.result()
                    report["trials"].append(completed)
                    report["aggregate"] = aggregate(report["trials"])
                    write_report(target, report)
                    summary = completed["summary"]
                    print(json.dumps({"trial_id": row["trial_id"], "passed": summary.get("passed"),
                                      "phase": summary.get("phase"), "cost_usd": summary.get("usage", {}).get("estimated_cost_usd"),
                                      "elapsed_seconds": summary.get("elapsed_seconds"),
                                      "strength": {name: summary.get("test_strength", {}).get(name) for name in ("detected", "survived", "unusable")}}), flush=True)
    report["status"] = "complete" if fingerprint_files(plugin) == frozen["files"] else "protocol_changed"
    report["elapsed_seconds"] = round(time.monotonic() - started, 1)
    report["aggregate"] = aggregate(report["trials"])
    write_report(target, report)
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
