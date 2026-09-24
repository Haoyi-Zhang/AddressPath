#!/usr/bin/env python3
"""Bounded, offline reproduction of all retained model-level evidence.

The campaign is split into four resumable stages so each invocation remains
well below the documented per-run budget.  ``--stage all`` is convenient on an
unconstrained workstation; the README's four-command sequence is the most
portable route in quota-limited environments.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import os
import resource
import subprocess
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
STAGES = ("core", "tpeg-middle", "tpeg-tail", "validation")
TIMING_FIELDS = {"producer_cpu_s", "oracle_cpu_s", "checker_cpu_s", "wall_s"}
RESOURCE_FIELDS = {"cpu_s", "wall_s", "peak_rss_kib"}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def semantic(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in TIMING_FIELDS}


def without(mapping: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in fields}


def compare_json_exact(left: Path, right: Path, label: str) -> None:
    if read(left) != read(right):
        raise AssertionError(f"{label} differs: {left.name}")


def compare_csv_columns(left: Path, right: Path, fields: list[str], label: str) -> None:
    with left.open(newline="", encoding="utf-8") as handle:
        a = [{field: row[field] for field in fields} for row in csv.DictReader(handle)]
    with right.open(newline="", encoding="utf-8") as handle:
        b = [{field: row[field] for field in fields} for row in csv.DictReader(handle)]
    if a != b:
        raise AssertionError(f"{label} differs")


class Campaign:
    def __init__(self, output: str, stage: str):
        self.out = (ROOT / output).resolve()
        if self.out == ROOT or ROOT not in self.out.parents:
            raise ValueError("output must be a subdirectory of the repository")
        self.relative = self.out.relative_to(ROOT)
        self.stage = stage
        self.steps: list[dict[str, Any]] = []
        self.cpu0 = time.process_time()
        self.wall0 = time.monotonic()
        self.child0 = resource.getrusage(resource.RUSAGE_CHILDREN)

    def note(self, message: str) -> None:
        print(message, flush=True)

    def marker(self, stage: str) -> Path:
        return self.out / f"stage-{stage}.json"

    def require(self, *stages: str) -> None:
        missing = [stage for stage in stages if not self.marker(stage).is_file()]
        if missing:
            raise ValueError("required reproduction stage(s) missing: " + ", ".join(missing))
        failed = [stage for stage in stages if read(self.marker(stage)).get("status") != "PASS"]
        if failed:
            raise ValueError("required reproduction stage(s) did not pass: " + ", ".join(failed))

    def prepare(self) -> None:
        if hasattr(os, "sched_getaffinity"):
            allowed = sorted(os.sched_getaffinity(0))
            os.sched_setaffinity(0, {allowed[0]})
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 125))

    def run(self, arguments: list[str], timeout: int = 110) -> None:
        command = [sys.executable, *arguments]
        label = " ".join(arguments)
        self.note(f"[reproduce:{self.stage}] START {label}")
        started = time.monotonic()
        environment = {
            **os.environ,
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            captured = exc.stdout or ""
            if isinstance(captured, bytes):
                captured = captured.decode("utf-8", errors="replace")
            self.steps.append({
                "arguments": arguments,
                "returncode": None,
                "wall_s": elapsed,
                "output": captured,
                "failure": f"timeout after {timeout} seconds",
            })
            self.note(f"[reproduce:{self.stage}] TIMEOUT {label} ({elapsed:.2f}s)")
            raise RuntimeError(f"reproduction step timed out after {timeout}s: {label}") from exc
        elapsed = time.monotonic() - started
        self.steps.append({
            "arguments": arguments,
            "returncode": result.returncode,
            "wall_s": elapsed,
            "output": result.stdout,
        })
        self.note(f"[reproduce:{self.stage}] END   {label} ({elapsed:.2f}s)")
        if result.returncode:
            raise RuntimeError("reproduction step failed: " + arguments[0] + "\n" + result.stdout)

    def finish(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        child1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        record: dict[str, Any] = {
            "stage": self.stage,
            "status": "PASS",
            "parent_cpu_s": time.process_time() - self.cpu0,
            "child_cpu_s": (child1.ru_utime + child1.ru_stime)
            - (self.child0.ru_utime + self.child0.ru_stime),
            "wall_s": time.monotonic() - self.wall0,
            "parent_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "child_peak_rss_kib": child1.ru_maxrss,
            "steps": self.steps,
        }
        record["total_cpu_s"] = record["parent_cpu_s"] + record["child_cpu_s"]
        if extra:
            record.update(extra)
        write(self.marker(self.stage), record)
        self.note(json.dumps({key: value for key, value in record.items() if key != "steps"}, indent=2))
        return record


def compare_arithmetic(out: Path) -> None:
    names = [f"case-{index:03}.json" for index in range(1, 87)]
    if sorted(path.name for path in (out / "cases").glob("*.json")) != names:
        raise AssertionError("generated arithmetic case inventory differs")
    for name in names:
        compare_json_exact(out / "cases" / name, ROOT / "cases" / name, "arithmetic input")
        if semantic(read(out / "results" / name)) != semantic(read(ROOT / "results" / name)):
            raise AssertionError("arithmetic result differs: " + name)
    expected = sorted(path.name for path in (ROOT / "results" / "certificates").glob("*.json"))
    actual = sorted(path.name for path in (out / "results" / "certificates").glob("*.json"))
    if expected != actual:
        raise AssertionError("arithmetic certificate inventory differs")
    for name in expected:
        compare_json_exact(
            out / "results" / "certificates" / name,
            ROOT / "results" / "certificates" / name,
            "arithmetic certificate",
        )


def compare_tpeg_inputs(out: Path) -> None:
    names = [f"tpeg-{index:03}.json" for index in range(1, 73)]
    if sorted(path.name for path in (out / "tpeg_cases").glob("*.json")) != names:
        raise AssertionError("generated TPEG case inventory differs")
    for name in names:
        compare_json_exact(out / "tpeg_cases" / name, ROOT / "tpeg_cases" / name, "TPEG input")


def compare_tpeg_range(out: Path, start: int, end: int) -> None:
    for index in range(start, end + 1):
        name = f"tpeg-{index:03}.json"
        if semantic(read(out / "tpeg_results" / name)) != semantic(read(ROOT / "tpeg_results" / name)):
            raise AssertionError("TPEG result differs: " + name)
        expected_cert = ROOT / "tpeg_results" / "certificates" / name
        actual_cert = out / "tpeg_results" / "certificates" / name
        if expected_cert.exists() != actual_cert.exists():
            raise AssertionError("TPEG certificate presence differs: " + name)
        if expected_cert.exists():
            compare_json_exact(actual_cert, expected_cert, "TPEG certificate")


def stage_core(campaign: Campaign) -> dict[str, Any]:
    if campaign.out.exists():
        raise ValueError("output already exists; remove it before starting the core stage")
    campaign.out.mkdir(parents=True)
    campaign.run(["generate.py", "--output", str(campaign.relative / "cases")])
    for start in range(1, 87, 12):
        campaign.run([
            "run_cases.py", "--start", str(start), "--end", str(min(86, start + 11)),
            "--output", str(campaign.relative / "results"),
        ])
    compare_arithmetic(campaign.out)

    campaign.run(["generate_tpeg.py", "--output", str(campaign.relative / "tpeg_cases")])
    compare_tpeg_inputs(campaign.out)
    for start, end in ((1, 8), (9, 16), (17, 24), (25, 26)):
        campaign.run([
            "run_tpeg_cases.py", "--start", str(start), "--end", str(end),
            "--output", str(campaign.relative / "tpeg_results"),
        ])
    compare_tpeg_range(campaign.out, 1, 26)
    return campaign.finish({"arithmetic_cases": 86, "tpeg_cases_completed": 26})


def stage_tpeg_middle(campaign: Campaign) -> dict[str, Any]:
    campaign.require("core")
    for start, end in ((27, 32), (33, 38)):
        campaign.run([
            "run_tpeg_cases.py", "--start", str(start), "--end", str(end),
            "--output", str(campaign.relative / "tpeg_results"),
        ])
    compare_tpeg_range(campaign.out, 27, 38)
    return campaign.finish({"tpeg_cases_completed": 12})


def stage_tpeg_tail(campaign: Campaign) -> dict[str, Any]:
    campaign.require("core", "tpeg-middle")
    for start, end in ((39, 44), (45, 56), (57, 72)):
        campaign.run([
            "run_tpeg_cases.py", "--start", str(start), "--end", str(end),
            "--output", str(campaign.relative / "tpeg_results"),
        ])
    compare_tpeg_range(campaign.out, 39, 72)
    expected = sorted(path.name for path in (ROOT / "tpeg_results" / "certificates").glob("*.json"))
    actual = sorted(path.name for path in (campaign.out / "tpeg_results" / "certificates").glob("*.json"))
    if expected != actual:
        raise AssertionError("complete TPEG certificate inventory differs")
    return campaign.finish({"tpeg_cases_completed": 34, "tpeg_cases_total": 72})


def stage_validation(campaign: Campaign) -> dict[str, Any]:
    campaign.require("core", "tpeg-middle", "tpeg-tail")
    campaign.run(["run_tests.py", "--output", str(campaign.relative / "validation")])
    tests = read(campaign.out / "validation" / "tests.json")
    retained_tests = read(ROOT / "validation" / "tests.json")
    for key in [
        "methods", "passed", "failures", "errors", "arithmetic_certificate_calls",
        "tpeg_certificate_calls", "accepted", "rejected",
        "finite_cover_state_visit_upper_bound", "signature_cover_state_visit_upper_bound",
        "certificate_calls",
    ]:
        if tests[key] != retained_tests[key]:
            raise AssertionError("test evidence differs: " + key)

    campaign.run(["exhaustive_meta.py", "--output", str(campaign.relative / "validation" / "meta-check.json")])
    meta = read(campaign.out / "validation" / "meta-check.json")
    if without(meta, RESOURCE_FIELDS) != without(read(ROOT / "validation" / "meta-check.json"), RESOURCE_FIELDS):
        raise AssertionError("exhaustive TPEG meta-check evidence differs")

    campaign.run([
        "exhaustive_arithmetic_meta.py", "--output",
        str(campaign.relative / "validation" / "arithmetic-meta-check.json"),
    ])
    arithmetic_meta = read(campaign.out / "validation" / "arithmetic-meta-check.json")
    if without(arithmetic_meta, RESOURCE_FIELDS) != without(
        read(ROOT / "validation" / "arithmetic-meta-check.json"), RESOURCE_FIELDS
    ):
        raise AssertionError("exhaustive arithmetic meta-check evidence differs")

    campaign.run([
        "summarize.py", "--source", str(campaign.relative / "results"),
        "--output", str(campaign.relative / "tables"),
    ])
    for name in ["families.csv", "families.tex", "accounting.csv"]:
        if (campaign.out / "tables" / name).read_bytes() != (ROOT / "tables" / name).read_bytes():
            raise AssertionError("arithmetic report table differs: " + name)
    if without(read(campaign.out / "tables" / "summary.json"), RESOURCE_FIELDS) != without(
        read(ROOT / "tables" / "summary.json"), RESOURCE_FIELDS
    ):
        raise AssertionError("arithmetic aggregate differs")

    campaign.run([
        "summarize_tpeg.py", "--source", str(campaign.relative / "tpeg_results"),
        "--output", str(campaign.relative / "tables"),
    ])
    for name in ["tpeg-families.csv", "tpeg-families.tex", "tpeg-methods.csv"]:
        if (campaign.out / "tables" / name).read_bytes() != (ROOT / "tables" / name).read_bytes():
            raise AssertionError("TPEG report table differs: " + name)
    compare_csv_columns(
        campaign.out / "tables" / "tpeg-scaling.csv",
        ROOT / "tables" / "tpeg-scaling.csv",
        ["paths", "enumerated_states", "distinct_signatures", "maximal_signatures", "certificate_bytes"],
        "TPEG scaling structure",
    )
    old_tpeg = without(read(ROOT / "tables" / "tpeg-summary.json"), RESOURCE_FIELDS)
    new_tpeg = without(read(campaign.out / "tables" / "tpeg-summary.json"), RESOURCE_FIELDS)
    old_tpeg["maxima"] = without(old_tpeg["maxima"], {"wall_s"})
    new_tpeg["maxima"] = without(new_tpeg["maxima"], {"wall_s"})
    if old_tpeg != new_tpeg:
        raise AssertionError("TPEG aggregate differs")

    for arguments in [
        ["src/checker.py", "cases/case-002.json", "results/certificates/case-002.json"],
        ["src/tpeg_checker.py", "tpeg_cases/tpeg-021.json", "tpeg_results/certificates/tpeg-021.json"],
        ["src/tpeg_checker.py", "tpeg_cases/tpeg-044.json", "tpeg_results/certificates/tpeg-044.json"],
    ]:
        campaign.run(arguments)

    current = campaign.finish({
        "test_methods": tests["methods"],
        "arithmetic_meta_models": arithmetic_meta["models"],
        "tpeg_meta_antichains": meta["maximal_signature_antichains"],
    })
    stages = [read(campaign.marker(stage)) for stage in STAGES]
    report = {
        "status": "PASS",
        "arithmetic_cases": 86,
        "tpeg_cases": 72,
        "arithmetic_meta_models": arithmetic_meta["models"],
        "tpeg_meta_antichains": meta["maximal_signature_antichains"],
        "test_methods": tests["methods"],
        "workers": 1,
        "stages": stages,
        "total_cpu_s": sum(stage["total_cpu_s"] for stage in stages),
        "cumulative_stage_wall_s": sum(stage["wall_s"] for stage in stages),
        "peak_rss_kib": max(
            max(stage["parent_peak_rss_kib"], stage["child_peak_rss_kib"])
            for stage in stages
        ),
        "scope": (
            "Fresh generation and execution of 86 arithmetic regressions and 72 TPEG models; "
            "certificate comparison; independent finite oracles; 74 mutation-oriented test "
            "methods; exhaustive 3,915-model arithmetic and 2,865-antichain TPEG meta-checks; "
            "aggregate tables; and standalone checker entry points. Paper compilation is separate."
        ),
    }
    write(campaign.out / "report.json", report)
    campaign.note(json.dumps({key: value for key, value in report.items() if key != "stages"}, indent=2))
    return current


STAGE_FUNCTIONS: dict[str, Callable[[Campaign], dict[str, Any]]] = {
    "core": stage_core,
    "tpeg-middle": stage_tpeg_middle,
    "tpeg-tail": stage_tpeg_tail,
    "validation": stage_validation,
}


def run_one(output: str, stage: str) -> None:
    campaign = Campaign(output, stage)
    campaign.prepare()
    STAGE_FUNCTIONS[stage](campaign)


def main(output: str, stage: str) -> None:
    if stage == "all":
        out = (ROOT / output).resolve()
        if out.exists():
            raise ValueError("output already exists; remove it before running all stages")
        for name in STAGES:
            run_one(output, name)
        return
    run_one(output, stage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="reproduction")
    parser.add_argument("--stage", choices=(*STAGES, "all"), default="all")
    args = parser.parse_args()
    try:
        main(args.output, args.stage)
    except (ValueError, OSError, RuntimeError, AssertionError) as exc:
        raise SystemExit(f"REPRODUCTION FAILED: {type(exc).__name__}: {exc}")
