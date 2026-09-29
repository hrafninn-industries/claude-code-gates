#!/usr/bin/env python3
"""cost_gate: stops calls to paid, per-call models until a human has approved the amount.

Why it exists: a batch of ~215 image generations ran on a key everyone believed
was free. It was not. One morning, roughly 28 USD, nobody asked.

What it does (PreToolUse on Bash):
  * Looks at the command AND at the scripts the command runs (.py/.js/.mjs/.sh).
  * If it finds a real API call plus an expensive model (image, video, speech ...),
    the command is denied until it carries a line like

        # COST: 0.40 USD — approved by Dana 14:05

  * Every approved call is written to <log_dir>/cost.log.

Patterns and currency live in gates.json under "cost".
"""
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import command_of, deny, first_line, load_config, log, read_event, run  # noqa: E402

MARK = re.compile(r"#\s*COST:\s*(?P<amount>[^\n—–]*?\d[^\n—–]*?)\s*[—–-]+\s*(?P<ok>approved[^\n]*)", re.I)
SCRIPT = re.compile(r"[\w./~\-]+\.(?:py|mjs|js|sh)\b")
GATES_DIR = Path(__file__).resolve().parent


def script_text(cmd):
    """Text of the scripts a command runs, so a call hidden in a file is still seen."""
    parts = []
    for name in SCRIPT.findall(cmd)[:8]:
        path = Path(name).expanduser()
        try:
            if path.resolve().parent == GATES_DIR:  # our own patterns are not a call
                continue
            if path.is_file() and path.stat().st_size < 400_000:
                parts.append(path.read_text(errors="replace"))
        except OSError:
            pass
    return "\n".join(parts)


def find_paid_call(text, cfg):
    api = any(re.search(p, text, re.I) for p in cfg["api_patterns"])
    if not api:
        return None
    for p in cfg["expensive_patterns"]:
        m = re.search(p, text, re.I)
        if m:
            return m.group(0)
    return None


def main():
    cfg = load_config()
    cost = cfg["cost"]
    event = read_event()
    cmd = command_of(event)
    if not cmd:
        return
    model = find_paid_call(cmd, cost) or find_paid_call(script_text(cmd), cost)
    if not model:
        return
    mark = MARK.search(cmd)
    if mark:
        log(cfg, "cost", f"{mark['amount'].strip()} | {mark['ok'].strip()} | model {model} | "
                         f"{first_line(cmd, MARK)}")
        return
    deny(
        f"COST GATE: this command calls a paid model ({model}). Work out what it will cost in "
        f"{cost['currency']}, show the amount to the user and wait for a yes. Then add the line "
        f"'# COST: <amount> {cost['currency']} — approved <by whom, when>' to the command and run it again. "
        "Approved calls are logged."
    )


if __name__ == "__main__":
    run(main)
