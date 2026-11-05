from flask import Flask, jsonify, request
import os
import time
import re
from datetime import datetime

app = Flask(__name__)

PROCESS_START_TIME = time.time()

# Apache error log regex pattern
# Matches: [Thu Jun 09 06:07:05 2005] [error] message text here
LOG_PATTERN = re.compile(
    r'^\[(?P<timestamp>[^\]]+)\]\s+'      # [Thu Jun 09 06:07:05 2005]
    r'\[(?P<level>[^\]]+)\]\s+'            # [error]
    r'(?P<message>.*)$'                    # rest of line = message
)

def parse_apache_timestamp(ts_str):
    """Convert 'Thu Jun 09 06:07:05 2005' to ISO format '2005-06-09T06:07:05'."""
    try:
        dt = datetime.strptime(ts_str, "%a %b %d %H:%M:%S %Y")
        return dt.isoformat()
    except ValueError:
        return None

def parse_log_line(line):
    """Parse a single Apache error log line into structured fields."""
    line = line.strip()
    if not line:
        return None
    
    match = LOG_PATTERN.match(line)
    if not match:
        return {
            "timestamp_raw": None,
            "timestamp_iso": None,
            "level": "unparseable",
            "message": line,
            "parse_success": False
        }
    
    ts_raw = match.group("timestamp")
    return {
        "timestamp_raw": ts_raw,
        "timestamp_iso": parse_apache_timestamp(ts_raw),
        "level": match.group("level").lower(),
        "message": match.group("message").strip(),
        "parse_success": True
    }

@app.route("/", methods=["POST"])
def parse():
    """Parse one or more Apache log lines.
    
    Accepts either:
    - A single raw log line in the request body (text/plain)
    - A JSON object with 'lines' array
    """
    start = time.time()
    
    content_type = request.content_type or ""
    
    if "application/json" in content_type:
        # Batch mode: {"lines": ["line1", "line2", ...]}
        data = request.get_json(silent=True) or {}
        lines = data.get("lines", [])
    else:
        # Single line mode: raw text body
        raw = request.get_data(as_text=True)
        lines = [raw] if raw.strip() else []
    
    parsed_records = [r for r in (parse_log_line(l) for l in lines) if r is not None]
    duration_ms = round((time.time() - start) * 1000, 4)
    
    return jsonify({
        "function": "f1-parser",
        "records_in": len(lines),
        "records_out": len(parsed_records),
        "parsed": parsed_records,
        "parse_time_ms": duration_ms,
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })

@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200

@app.route("/", methods=["GET"])
def info():
    """Info endpoint — useful for warm-up pings and human inspection."""
    return jsonify({
        "function": "f1-parser",
        "description": "Parses Apache error log lines into structured JSON",
        "usage": "POST a raw log line in the body, or JSON {\"lines\": [...]}",
        "process_uptime_seconds": round(time.time() - PROCESS_START_TIME, 4),
        "pod": os.environ.get("HOSTNAME", "unknown")
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)