from flask import Flask, jsonify, request
import os
import time
import requests

app = Flask(__name__)

PROCESS_START_TIME = time.time()

# Internal cluster URLs for each pipeline stage
STAGES = [
    {"name": "f1-parser",     "url": "http://f1-parser.default.svc.cluster.local"},
    {"name": "f2-filter",     "url": "http://f2-filter.default.svc.cluster.local"},
    {"name": "f3-enricher",   "url": "http://f3-enricher.default.svc.cluster.local"},
    {"name": "f4-aggregator", "url": "http://f4-aggregator.default.svc.cluster.local"},
]

# How long to wait for each stage (generous, to allow cold starts)
STAGE_TIMEOUT = 60


def call_stage(stage, payload, content_type="application/json"):
    """Call one pipeline stage and return (response_json, elapsed_ms, status)."""
    start = time.time()
    headers = {"Content-Type": content_type}
    if content_type == "application/json":
        resp = requests.post(stage["url"], json=payload, headers=headers, timeout=STAGE_TIMEOUT)
    else:
        resp = requests.post(stage["url"], data=payload, headers=headers, timeout=STAGE_TIMEOUT)
    elapsed_ms = round((time.time() - start) * 1000, 2)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return body, elapsed_ms, resp.status_code


@app.route("/", methods=["POST"])
def orchestrate():
    """Run the full pipeline F1 -> F2 -> F3 -> F4 sequentially.

    Input: raw log lines, either:
      - JSON {"lines": ["...", "..."]}   (passed to F1)
      - raw text body                     (single log line)

    Output: final F4 summary + per-stage timing breakdown.
    """
    overall_start = time.time()

    # Figure out the input for F1
    content_type = request.content_type or ""
    if "application/json" in content_type:
        f1_payload = request.get_json(silent=True) or {}
        f1_content_type = "application/json"
    else:
        f1_payload = request.get_data(as_text=True)
        f1_content_type = "text/plain"

    timings = []
    stage_uptimes = {}

    # ---- Stage 1: F1 Parser ----
    f1_out, f1_ms, f1_status = call_stage(STAGES[0], f1_payload, f1_content_type)
    timings.append({"stage": "f1-parser", "elapsed_ms": f1_ms, "status": f1_status})
    stage_uptimes["f1-parser"] = f1_out.get("process_uptime_seconds")

    # ---- Stage 2: F2 Filter ---- (F2 expects {"parsed": [...]})
    f2_in = {"parsed": f1_out.get("parsed", [])}
    f2_out, f2_ms, f2_status = call_stage(STAGES[1], f2_in)
    timings.append({"stage": "f2-filter", "elapsed_ms": f2_ms, "status": f2_status})
    stage_uptimes["f2-filter"] = f2_out.get("process_uptime_seconds")

    # ---- Stage 3: F3 Enricher ---- (F3 expects {"filtered": [...]})
    f3_in = {"filtered": f2_out.get("filtered", [])}
    f3_out, f3_ms, f3_status = call_stage(STAGES[2], f3_in)
    timings.append({"stage": "f3-enricher", "elapsed_ms": f3_ms, "status": f3_status})
    stage_uptimes["f3-enricher"] = f3_out.get("process_uptime_seconds")

    # ---- Stage 4: F4 Aggregator ---- (F4 expects {"enriched": [...]})
    f4_in = {"enriched": f3_out.get("enriched", [])}
    f4_out, f4_ms, f4_status = call_stage(STAGES[3], f4_in)
    timings.append({"stage": "f4-aggregator", "elapsed_ms": f4_ms, "status": f4_status})
    stage_uptimes["f4-aggregator"] = f4_out.get("process_uptime_seconds")

    total_ms = round((time.time() - overall_start) * 1000, 2)
    sum_stage_ms = round(sum(t["elapsed_ms"] for t in timings), 2)

    # Detect which stages were cold (uptime < 5s indicates fresh pod)
    cold_stages = [name for name, up in stage_uptimes.items()
                   if up is not None and up < 5.0]

    return jsonify({
        "function": "orchestrator",
        "pipeline_result": f4_out,
        "timings": {
            "per_stage_ms": timings,
            "sum_of_stages_ms": sum_stage_ms,
            "total_pipeline_ms": total_ms,
            "orchestration_overhead_ms": round(total_ms - sum_stage_ms, 2),
        },
        "stage_uptimes_s": stage_uptimes,
        "cold_stages_detected": cold_stages,
        "cold_stage_count": len(cold_stages),
        "orchestrator_uptime_s": round(time.time() - PROCESS_START_TIME, 4),
        "orchestrator_pod": os.environ.get("HOSTNAME", "unknown"),
    })


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


@app.route("/", methods=["GET"])
def info():
    return jsonify({
        "function": "orchestrator",
        "description": "Sequentially orchestrates the F1->F2->F3->F4 log pipeline",
        "stages": [s["name"] for s in STAGES],
        "usage": "POST JSON {\"lines\": [...]} or a raw log line",
        "orchestrator_uptime_s": round(time.time() - PROCESS_START_TIME, 4),
        "orchestrator_pod": os.environ.get("HOSTNAME", "unknown"),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)