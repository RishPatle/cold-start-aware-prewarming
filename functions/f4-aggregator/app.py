from flask import Flask, jsonify, request
import os
import time
from collections import Counter

app = Flask(__name__)

PROCESS_START_TIME = time.time()

# Alerting thresholds
ERROR_RATE_THRESHOLD = 0.10      # alert if >10% of records are errors
HIGH_SEVERITY_THRESHOLD = 3      # alert if >=3 high-severity records
KNOWN_ISSUE_THRESHOLD = 5        # alert if >=5 known issues found


def severity_band(score):
    """Map a numeric severity score to a band label."""
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


def aggregate(records):
    """Compute summary statistics over a batch of enriched records."""
    total = len(records)
    error_count = 0
    severity_bands = Counter()
    categories = Counter()
    subsystems = Counter()
    known_issues = 0
    should_alert_count = 0

    for r in records:
        # error detection (from F2's is_error, fall back to severity)
        sev = r.get("severity_score", 0)
        if r.get("is_error") or sev >= 3:
            error_count += 1

        severity_bands[severity_band(sev)] += 1

        cat = r.get("category") or r.get("subsystem_category") or "unknown"
        categories[cat] += 1

        sub = r.get("subsystem")
        if sub and sub != "unknown":
            subsystems[sub] += 1

        if r.get("known_issue"):
            known_issues += 1

        if r.get("should_alert"):
            should_alert_count += 1

    error_rate = round(error_count / total, 4) if total else 0.0

    summary = {
        "total_records": total,
        "error_count": error_count,
        "error_rate": error_rate,
        "severity_breakdown": dict(severity_bands),
        "category_breakdown": dict(categories),
        "known_issues_found": known_issues,
        "records_flagged_for_alert": should_alert_count,
        "top_subsystems": subsystems.most_common(5),
    }
    return summary


def build_alerts(summary):
    """Decide which alerts to raise based on the summary and thresholds."""
    alerts = []

    if summary["error_rate"] > ERROR_RATE_THRESHOLD:
        alerts.append({
            "level": "WARNING",
            "reason": f"error_rate {summary['error_rate']:.0%} exceeds "
                      f"{ERROR_RATE_THRESHOLD:.0%} threshold"
        })

    high = summary["severity_breakdown"].get("high", 0)
    if high >= HIGH_SEVERITY_THRESHOLD:
        alerts.append({
            "level": "CRITICAL",
            "reason": f"{high} high-severity records detected "
                      f"(threshold {HIGH_SEVERITY_THRESHOLD})"
        })

    if summary["known_issues_found"] >= KNOWN_ISSUE_THRESHOLD:
        alerts.append({
            "level": "WARNING",
            "reason": f"{summary['known_issues_found']} known issues found "
                      f"(threshold {KNOWN_ISSUE_THRESHOLD})"
        })

    return alerts


@app.route("/", methods=["POST"])
def aggregate_records():
    """Aggregate a batch of enriched records into a summary with alerts.

    Expected input (from F3):
      { "enriched": [...records...] }
    Also accepts: filtered / parsed / records keys for flexibility.
    """
    start = time.time()

    data = request.get_json(silent=True) or {}
    records = (
        data.get("enriched")
        or data.get("filtered")
        or data.get("parsed")
        or data.get("records")
        or []
    )

    summary = aggregate(records)
    alerts = build_alerts(summary)

    duration_ms = round((time.time() - start) * 1000, 4)

    return jsonify({
        "function": "f4-aggregator",
        "summary": summary,
        "alerts": alerts,
        "alert_count": len(alerts),
        "aggregate_time_ms": duration_ms,
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


@app.route("/", methods=["GET"])
def info():
    return jsonify({
        "function": "f4-aggregator",
        "description": "Aggregates enriched log records into summary statistics and alerts",
        "usage": "POST JSON {\"enriched\": [...records from F3...]}",
        "thresholds": {
            "error_rate": ERROR_RATE_THRESHOLD,
            "high_severity": HIGH_SEVERITY_THRESHOLD,
            "known_issue": KNOWN_ISSUE_THRESHOLD
        },
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)