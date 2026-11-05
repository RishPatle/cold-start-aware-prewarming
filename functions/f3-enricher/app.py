from flask import Flask, jsonify, request
import os
import time

app = Flask(__name__)

PROCESS_START_TIME = time.time()

# ============================================================
# Static "knowledge base" — in production this would be a DB.
# Each entry is keyed by a keyword we scan for in the message.
# ============================================================
KNOWLEDGE_BASE = {
    "ldap": {
        "subsystem": "LDAP",
        "subsystem_category": "authentication",
        "known_issue": False,
        "recommended_action": "log_only",
        "estimated_impact": "low",
    },
    "ssl": {
        "subsystem": "SSL",
        "subsystem_category": "security",
        "known_issue": False,
        "recommended_action": "log_only",
        "estimated_impact": "low",
    },
    "digest": {
        "subsystem": "Digest",
        "subsystem_category": "authentication",
        "known_issue": False,
        "recommended_action": "log_only",
        "estimated_impact": "low",
    },
    "suexec": {
        "subsystem": "suEXEC",
        "subsystem_category": "security",
        "known_issue": False,
        "recommended_action": "log_only",
        "estimated_impact": "low",
    },
    "jni": {
        "subsystem": "JNI",
        "subsystem_category": "runtime",
        "known_issue": True,
        "recommended_action": "investigate",
        "estimated_impact": "medium",
    },
    "factory error": {
        "subsystem": "ApplicationFactory",
        "subsystem_category": "runtime",
        "known_issue": True,
        "recommended_action": "investigate",
        "estimated_impact": "medium",
    },
    "createbean": {
        "subsystem": "BeanFactory",
        "subsystem_category": "runtime",
        "known_issue": True,
        "recommended_action": "investigate",
        "estimated_impact": "medium",
    },
    "vm": {
        "subsystem": "JVM",
        "subsystem_category": "runtime",
        "known_issue": False,
        "recommended_action": "monitor",
        "estimated_impact": "low",
    },
    "workerenv": {
        "subsystem": "WorkerEnv",
        "subsystem_category": "process_management",
        "known_issue": False,
        "recommended_action": "monitor",
        "estimated_impact": "low",
    },
    "mod_jk": {
        "subsystem": "mod_jk",
        "subsystem_category": "process_management",
        "known_issue": True,
        "recommended_action": "investigate",
        "estimated_impact": "high",
    },
    "scoreboard": {
        "subsystem": "Scoreboard",
        "subsystem_category": "process_management",
        "known_issue": False,
        "recommended_action": "log_only",
        "estimated_impact": "low",
    },
    "config.update": {
        "subsystem": "ConfigManager",
        "subsystem_category": "configuration",
        "known_issue": True,
        "recommended_action": "investigate",
        "estimated_impact": "medium",
    },
}

DEFAULT_ENRICHMENT = {
    "subsystem": "unknown",
    "subsystem_category": "unknown",
    "known_issue": False,
    "recommended_action": "log_only",
    "estimated_impact": "low",
}


def enrich_record(record):
    """Look up the message against the KB and add enrichment fields."""
    message = (record.get("message") or "").lower()

    enrichment = None
    matched_keyword = None
    for keyword, info in KNOWLEDGE_BASE.items():
        if keyword in message:
            enrichment = info
            matched_keyword = keyword
            break

    if enrichment is None:
        enrichment = DEFAULT_ENRICHMENT
        kb_hit = False
    else:
        kb_hit = True

    out = dict(record)
    out.update(enrichment)
    out["kb_matched_keyword"] = matched_keyword
    out["kb_hit"] = kb_hit
    return out


@app.route("/", methods=["POST"])
def enrich_records():
    """Enrich a batch of filtered records.

    Expected input (from F2):
      { "filtered": [...records from F2...] }

    Or, accepts these other shapes for flexibility:
      { "enriched": [...] }, { "parsed": [...] }, { "records": [...] }
    """
    start = time.time()

    data = request.get_json(silent=True) or {}
    records = (
        data.get("filtered")
        or data.get("enriched")
        or data.get("parsed")
        or data.get("records")
        or []
    )

    enriched = [enrich_record(r) for r in records]
    hits = sum(1 for r in enriched if r.get("kb_hit"))

    duration_ms = round((time.time() - start) * 1000, 4)

    return jsonify({
        "function": "f3-enricher",
        "records_in": len(records),
        "records_out": len(enriched),
        "lookups_performed": len(records),
        "lookups_hit_kb": hits,
        "enriched": enriched,
        "enrich_time_ms": duration_ms,
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


@app.route("/", methods=["GET"])
def info():
    return jsonify({
        "function": "f3-enricher",
        "description": "Enriches filtered log records with subsystem/issue/action context",
        "usage": "POST JSON {\"filtered\": [...records from F2...]}",
        "kb_size": len(KNOWLEDGE_BASE),
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)