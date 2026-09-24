#!/usr/bin/env python3
"""Pretty-prints the JSONL system log stream read from stdin (live).

Used by ``scripts/system-logs``: tail -F system_logs.txt | this formatter.
One line in, one colorized line out — no buffering, no state.
"""

import json
import sys

PHASE_COLORS = {
    "ingestion": "\033[36m",       # cyan
    "retrieval": "\033[33m",       # yellow
    "generation": "\033[32m",      # green
    "adjudication": "\033[35m",    # magenta
    "approval": "\033[34m",        # blue
}
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _fmt_value(value, limit: int = 110) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=True)
    else:
        text = str(value)
    text = text.replace("\n", " ")
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


def format_line(raw: str) -> str:
    raw = raw.rstrip("\n")
    if not raw:
        return ""
    try:
        record = json.loads(raw)
        if not isinstance(record, dict):
            return f"{DIM}{raw}{RESET}"
    except ValueError:
        return f"{DIM}{raw}{RESET}"

    ts = str(record.get("timestamp", ""))[:23].replace("T", " ")
    phase = str(record.get("phase", "?"))
    event = str(record.get("event", "?"))
    cid = record.get("correlation_id") or ""
    payload = record.get("payload") or {}

    color = PHASE_COLORS.get(phase, "\033[37m")

    parts = []
    for key, value in payload.items():
        # step/status are already encoded in the event name (e.g. parsing_completed)
        if key in ("step", "status"):
            continue
        parts.append(f"{key}={_fmt_value(value)}")

    event_colored = f"{BOLD}{color}{event:<34}{RESET}"
    phase_colored = f"{color}{phase:<12}{RESET}"
    fields = " ".join(parts)
    cid_short = f"{DIM}[{cid[:8]}]{RESET}" if cid else ""

    return f"{DIM}{ts}{RESET} {phase_colored} {event_colored} {fields} {cid_short}".rstrip()


def main() -> None:
    for line in sys.stdin:
        sys.stdout.write(format_line(line) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()