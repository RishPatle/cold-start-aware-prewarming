#!/usr/bin/env python3
"""
Pre-warming benchmark harness for the serverless log pipeline.

Extends the original cold/warm harness to measure THREE conditions,
all using the same fixed payload and the same scale-to-zero protocol:

  A  cold          : scale to zero, fire, measure (no warming)
  B  selective     : scale to zero, pre-warm F2/F3/F4 only (F1 left as
                     entry point), confirm warm, fire, measure
  C  warm-all      : scale to zero, pre-warm all four, confirm warm,
                     fire, measure

The pre-warming "trigger" is an HTTP warm-up call to each chosen stage,
followed by polling that stage's own reported process_uptime_seconds
until it is warm. This was chosen over min-scale=1 because it is
per-run, leaves no lingering revision state, and gives a verifiable
"is it warm yet?" signal on single-node Minikube/Knative.

Usage:
  python3 harness_prewarm.py --runs 20
  python3 harness_prewarm.py --runs 20 --conditions A,B,C
  python3 harness_prewarm.py --runs 5 --conditions B    # quick test
"""

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime

# ---- Cluster / request configuration (matches original harness) ----
ORCHESTRATOR_HOST = "orchestrator.default.192.168.49.2.sslip.io"
BASE_URL = "http://localhost"   # via minikube tunnel

# Stage name -> its Knative Host header
STAGE_HOSTS = {
    "f1-parser":     "f1-parser.default.192.168.49.2.sslip.io",
    "f2-filter":     "f2-filter.default.192.168.49.2.sslip.io",
    "f3-enricher":   "f3-enricher.default.192.168.49.2.sslip.io",
    "f4-aggregator": "f4-aggregator.default.192.168.49.2.sslip.io",
}

# Pods we require to be gone for a confirmed cold run
PIPELINE_FUNCS = ["f1-parser", "f2-filter", "f3-enricher",
                  "f4-aggregator", "orchestrator"]

# Which stages get warmed in each condition
CONDITION_WARM = {
    "A": [],                                                   # cold baseline
    "B": ["f2-filter", "f3-enricher", "f4-aggregator"],        # selective
    "C": ["f1-parser", "f2-filter", "f3-enricher", "f4-aggregator"],  # warm-all
}
CONDITION_LABEL = {
    "A": "cold-baseline",
    "B": "selective(F2-F4)",
    "C": "warm-all",
}

# Same fixed payload used everywhere (matches original harness)
SAMPLE_PAYLOAD = json.dumps({
    "lines": [
        "[Thu Jun 09 06:07:05 2005] [error] env.createBean2(): Factory error creating channel.jni:jni",
        "[Thu Jun 09 06:07:04 2005] [notice] LDAP: Built with OpenLDAP LDAP SDK",
        "[Thu Jun 09 06:07:05 2005] [warn] mod_jk child workerEnv in error state",
        "[Thu Jun 09 06:07:05 2005] [notice] Digest: done",
        "[Thu Jun 09 06:07:06 2005] [error] jk2_init() Can not init worker"
    ]
})

# A tiny payload just to wake a stage (does not need to do real work)
WARMUP_PAYLOAD = json.dumps({"lines": ["[Thu Jun 09 06:07:05 2005] [notice] warmup"]})

# A stage is considered "warm" once its reported uptime exceeds this.
# Fresh pods report ~0.05s; we require a small margin so we know the
# process has actually been up rather than just booted this instant.
WARM_UPTIME_THRESHOLD = 1.0   # seconds


# ------------------------------------------------------------------ #
#  Cluster helpers
# ------------------------------------------------------------------ #
def pods_running():
    """Number of pipeline pods currently running."""
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


def wait_for_scale_to_zero(timeout=180):
    """Block until all pipeline pods have terminated, or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if pods_running() == 0:
            return True
        time.sleep(5)
    return False


# ------------------------------------------------------------------ #
#  The pre-warming trigger
# ------------------------------------------------------------------ #
def call_stage(stage, payload, timeout=120):
    """POST to a single stage directly; return parsed JSON or None."""
    host = STAGE_HOSTS[stage]
    res = subprocess.run(
        ["curl", "-s", "-X", "POST",
         "-H", f"Host: {host}",
         "-H", "Content-Type: application/json",
         "-d", payload, BASE_URL],
        capture_output=True, text=True, timeout=timeout
    )
    try:
        return json.loads(res.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def stage_uptime(stage):
    """Return a stage's reported process_uptime_seconds (or None)."""
    body = call_stage(stage, WARMUP_PAYLOAD)
    if body is None:
        return None
    return body.get("process_uptime_seconds")


def prewarm_stages(stages, poll_timeout=120):
    """
    Warm the given stages and confirm each is warm.
    First call wakes the pod (may itself pay the cold start); we then
    poll uptime until it exceeds the warm threshold, so we KNOW the
    stage is warm before the measured request is fired.
    Returns True if all stages confirmed warm, else False.
    """
    if not stages:
        return True
    # Kick each stage once to start it waking.
    for s in stages:
        call_stage(s, WARMUP_PAYLOAD)
    # Poll each until warm.
    for s in stages:
        start = time.time()
        while time.time() - start < poll_timeout:
            up = stage_uptime(s)
            if up is not None and up >= WARM_UPTIME_THRESHOLD:
                break
            time.sleep(1)
        else:
            print(f"    WARNING: {s} did not confirm warm within {poll_timeout}s")
            return False
    return True


# ------------------------------------------------------------------ #
#  The measured request (matches original harness)
# ------------------------------------------------------------------ #
def fire_request():
    """Send one request through the orchestrator; return (secs, json)."""
    start = time.time()
    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         "-H", f"Host: {ORCHESTRATOR_HOST}",
         "-H", "Content-Type: application/json",
         "-d", SAMPLE_PAYLOAD, BASE_URL],
        capture_output=True, text=True, timeout=300
    )
    elapsed = time.time() - start
    try:
        body = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        body = None
    return elapsed, body


# ------------------------------------------------------------------ #
#  Stats
# ------------------------------------------------------------------ #
def summarise(values, label):
    if not values:
        print(f"  {label}: no data")
        return None
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    p95 = s[min(n - 1, int(round(0.95 * (n - 1))))]
    stddev = (sum((x - mean) ** 2 for x in s) / n) ** 0.5
    print(f"  {label}: n={n}  mean={mean:.3f}s  median={median:.3f}s  "
          f"p95={p95:.3f}s  min={s[0]:.3f}s  max={s[-1]:.3f}s  stddev={stddev:.3f}s")
    return {"n": n, "mean": mean, "median": median, "p95": p95,
            "min": s[0], "max": s[-1], "stddev": stddev}


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #
def run_condition(cond, runs, writer, fh):
    """Run one condition `runs` times, logging each. Return list of totals."""
    warm_stages = CONDITION_WARM[cond]
    stages_warmed = len(warm_stages)
    totals = []
    print(f"\n=== Condition {cond} ({CONDITION_LABEL[cond]}) | "
          f"warming {stages_warmed} stage(s): {warm_stages or 'none'} ===")

    for i in range(1, runs + 1):
        # 1. Always start from a confirmed cold pipeline.
        print(f"[{cond} run {i}/{runs}] waiting for scale-to-zero...")
        if not wait_for_scale_to_zero():
            print(f"[{cond} run {i}] WARNING: not cold in time, skipping")
            continue

        # 2. Pre-warm the chosen subset (if any) and confirm warm.
        if warm_stages:
            print(f"[{cond} run {i}] pre-warming {warm_stages} ...")
            ok = prewarm_stages(warm_stages)
            if not ok:
                print(f"[{cond} run {i}] WARNING: warm not confirmed, skipping")
                continue

        # 3. Fire the measured request through the orchestrator.
        elapsed, body = fire_request()
        if body is None:
            print(f"[{cond} run {i}] ERROR: no valid response, skipping")
            continue

        timings = body.get("timings", {})
        per_stage = {t["stage"]: t["elapsed_ms"]
                     for t in timings.get("per_stage_ms", [])}
        pipeline_total = timings.get("total_pipeline_ms")
        cold_count = body.get("cold_stage_count")

        writer.writerow([
            cond, CONDITION_LABEL[cond], i, round(elapsed, 3), pipeline_total,
            per_stage.get("f1-parser"), per_stage.get("f2-filter"),
            per_stage.get("f3-enricher"), per_stage.get("f4-aggregator"),
            cold_count, stages_warmed, datetime.now().isoformat()
        ])
        fh.flush()
        totals.append(elapsed)
        print(f"[{cond} run {i}/{runs}] total={elapsed:.3f}s  "
              f"pipeline={pipeline_total}ms  cold_stages={cold_count}")

    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20,
                    help="runs per condition (default 20)")
    ap.add_argument("--conditions", default="A,B,C",
                    help="comma list of A,B,C (default all)")
    args = ap.parse_args()

    conditions = [c.strip().upper() for c in args.conditions.split(",")
                  if c.strip().upper() in ("A", "B", "C")]

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = f"results-prewarm-{ts}.csv"

    print(f"=== Pre-warming benchmark: conditions={conditions}, "
          f"runs each={args.runs} ===")
    print(f"Logging to: {csv_path}")

    summary = {}
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "condition", "condition_label", "run", "total_curl_s",
            "pipeline_total_ms", "f1_ms", "f2_ms", "f3_ms", "f4_ms",
            "cold_stage_count", "stages_warmed", "timestamp"
        ])
        for cond in conditions:
            totals = run_condition(cond, args.runs, writer, fh)
            summary[cond] = totals

    print("\n\n================  SUMMARY  ================")
    stats = {}
    for cond in conditions:
        stats[cond] = summarise(summary[cond],
                                f"Condition {cond} ({CONDITION_LABEL[cond]})")

    # Comparison table (median latency, % reduction vs cold, stages warmed)
    if "A" in stats and stats["A"]:
        cold_median = stats["A"]["median"]
        print("\n---- Comparison (median latency) ----")
        print(f"{'Cond':<6}{'Label':<20}{'Median(s)':<12}"
              f"{'% vs cold':<12}{'Stages warmed':<14}")
        for cond in conditions:
            st = stats[cond]
            if not st:
                continue
            med = st["median"]
            red = 100.0 * (cold_median - med) / cold_median if cold_median else 0
            warmed = len(CONDITION_WARM[cond])
            print(f"{cond:<6}{CONDITION_LABEL[cond]:<20}{med:<12.3f}"
                  f"{red:<12.1f}{warmed:<14}")

    print(f"\nRaw data saved to: {csv_path}")
    print("Next: run analyse_prewarm.py on that CSV for the chart.")


if __name__ == "__main__":
    main()