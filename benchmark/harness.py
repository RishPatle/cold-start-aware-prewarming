#!/usr/bin/env python3
"""
Cold-start benchmark harness for the serverless log pipeline.
Runs N measurements through the orchestrator, logging each to CSV.

Usage:
  python3 harness.py --mode cold --runs 10
  python3 harness.py --mode warm --runs 50
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime

ORCHESTRATOR_HOST = "orchestrator.default.192.168.49.2.sslip.io"
ORCHESTRATOR_URL = "http://localhost"

# The pipeline functions we need to confirm are scaled to zero for a cold run
PIPELINE_FUNCS = ["f1-parser", "f2-filter", "f3-enricher", "f4-aggregator", "orchestrator"]

# Sample input: a few raw Apache log lines
SAMPLE_PAYLOAD = json.dumps({
    "lines": [
        "[Thu Jun 09 06:07:05 2005] [error] env.createBean2(): Factory error creating channel.jni:jni",
        "[Thu Jun 09 06:07:04 2005] [notice] LDAP: Built with OpenLDAP LDAP SDK",
        "[Thu Jun 09 06:07:05 2005] [warn] mod_jk child workerEnv in error state",
        "[Thu Jun 09 06:07:05 2005] [notice] Digest: done",
        "[Thu Jun 09 06:07:06 2005] [error] jk2_init() Can not init worker"
    ]
})


def pods_running():
    """Return the number of pipeline pods currently running."""
    try:
        out = subprocess.run(
            ["kubectl", "get", "pods", "--no-headers"],
            capture_output=True, text=True, timeout=15
        ).stdout
    except subprocess.TimeoutExpired:
        return -1
    count = 0
    for line in out.strip().splitlines():
        if any(fn in line for fn in PIPELINE_FUNCS) and "Running" in line:
            count += 1
    return count


def wait_for_scale_to_zero(timeout=120):
    """Block until all pipeline pods have terminated, or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        n = pods_running()
        if n == 0:
            return True
        time.sleep(5)
    return False


def fire_request():
    """Send one request through the orchestrator, return (total_seconds, parsed_json)."""
    start = time.time()
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "-H", f"Host: {ORCHESTRATOR_HOST}",
            "-H", "Content-Type: application/json",
            "-d", SAMPLE_PAYLOAD,
            ORCHESTRATOR_URL,
        ],
        capture_output=True, text=True, timeout=300
    )
    elapsed = time.time() - start
    try:
        body = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        body = None
    return elapsed, body


def summarise(values, label):
    """Print simple stats for a list of numbers."""
    if not values:
        print(f"  {label}: no data")
        return
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    median = s[n // 2] if n % 2 else (s[n//2 - 1] + s[n//2]) / 2
    p95 = s[min(n - 1, int(round(0.95 * (n - 1))))]
    variance = sum((x - mean) ** 2 for x in s) / n
    stddev = variance ** 0.5
    print(f"  {label}:")
    print(f"    n={n}  mean={mean:.3f}s  median={median:.3f}s  "
          f"p95={p95:.3f}s  min={s[0]:.3f}s  max={s[-1]:.3f}s  stddev={stddev:.3f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["cold", "warm"], required=True)
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = f"results-{args.mode}-{ts}.csv"

    print(f"=== Benchmark: mode={args.mode}, runs={args.runs} ===")
    print(f"Logging to: {csv_path}\n")

    totals = []

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run", "mode", "total_curl_s", "pipeline_total_ms",
            "f1_ms", "f2_ms", "f3_ms", "f4_ms",
            "cold_stage_count", "timestamp"
        ])

        for i in range(1, args.runs + 1):
            if args.mode == "cold":
                print(f"[run {i}/{args.runs}] waiting for scale-to-zero...")
                if not wait_for_scale_to_zero():
                    print(f"[run {i}] WARNING: pods did not scale to zero in time, skipping")
                    continue

            elapsed, body = fire_request()

            if body is None:
                print(f"[run {i}] ERROR: no valid response, skipping")
                continue

            timings = body.get("timings", {})
            per_stage = {t["stage"]: t["elapsed_ms"] for t in timings.get("per_stage_ms", [])}
            pipeline_total = timings.get("total_pipeline_ms")
            cold_count = body.get("cold_stage_count")

            writer.writerow([
                i, args.mode, round(elapsed, 3), pipeline_total,
                per_stage.get("f1-parser"), per_stage.get("f2-filter"),
                per_stage.get("f3-enricher"), per_stage.get("f4-aggregator"),
                cold_count, datetime.now().isoformat()
            ])
            f.flush()  # write immediately so we never lose data

            totals.append(elapsed)
            print(f"[run {i}/{args.runs}] total={elapsed:.3f}s  "
                  f"pipeline={pipeline_total}ms  cold_stages={cold_count}")

    print(f"\n=== Summary ({args.mode}) ===")
    summarise(totals, "end-to-end (curl wall-clock)")
    print(f"\nRaw data saved to: {csv_path}")


if __name__ == "__main__":
    main()