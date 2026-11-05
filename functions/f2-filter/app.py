from flask import Flask, jsonify, request
import os
import time

app = Flask(__name__)

PROCESS_START_TIME = time.time()

# ---------- Filter / classification rules ----------

# Map log level → severity score (0 = lowest, 3 = highest)
SEVERITY_MAP = {
    "debug":   0,
    "info":    0,
    "notice":  1,
    "warn":    2,
    "warning": 2,
    "error":   3,
    "crit":    3,
    "critical": 3,
    "alert":   3,
    "fatal":   3,
    "emerg":   3,
}

# Map log level → category (human-readable grouping)
CATEGORY_MAP = {
    "debug":   "DEBUG",
    "info":    "INFO",
    "notice":  "INFO",
    "warn":    "WARNING",
    "warning": "WARNING",
    "error":   "APPLICATION_ERROR",
    "crit":    "CRITICAL",
    "critical": "CRITICAL",
    "alert":   "CRITICAL",
    "fatal":   "CRITICAL",
    "emerg":   "CRITICAL",
}

# Levels we keep in the pipeline. Lower-severity stuff gets dropped.
KEEP_LEVELS = {"notice", "warn", "warning", "error", "crit", "critical",
               "alert", "fatal", "emerg"}

# If severity_score >= this, mark should_alert = true
ALERT_THRESHOLD = 3


def classify_record(record):
    """Take one parsed record and add classification fields."""
    level = (record.get("level") or "").lower()
    severity = SEVERITY_MAP.get(level, 0)
    category = CATEGORY_MAP.get(level, "UNKNOWN")
    is_error = severity >= 3
    should_alert = severity >= ALERT_THRESHOLD
    kept = level in KEEP_LEVELS or level == "unparseable"

    # Copy the original record and add the new fields
    out = dict(record)
    out["category"] = category
    out["severity_score"] = severity
    out["is_error"] = is_error
    out["should_alert"] = should_alert
    out["kept"] = kept
    return out


@app.route("/", methods=["POST"])
def filter_records():
    """Filter and classify a batch of parsed log records.

    Expected input (from F1):
      {
        "parsed": [ {...record1...}, {...record2...}, ... ],
        ...other F1 fields ignored
      }

    Output:
      {
        "function": "f2-filter",
        "filtered": [...records that passed the filter...],
        "records_in": N,
        "records_out": M,
        "records_dropped": N-M,
        ...
      }
    """
    start = time.time()

    data = request.get_json(silent=True) or {}
    records = data.get("parsed") or data.get("filtered") or data.get("records") or []

    classified = [classify_record(r) for r in records]
    kept = [r for r in classified if r.get("kept")]

    duration_ms = round((time.time() - start) * 1000, 4)

    return jsonify({
        "function": "f2-filter",
        "records_in": len(records),
        "records_out": len(kept),
        "records_dropped": len(records) - len(kept),
        "filtered": kept,
        "filter_time_ms": duration_ms,
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


@app.route("/", methods=["GET"])
def info():
    return jsonify({
        "function": "f2-filter",
        "description": "Classifies parsed log records and drops low-severity noise",
        "usage": "POST JSON {\"parsed\": [...records from F1...]}",
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)