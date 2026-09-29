"""Shared helpers for the gates: config loading, logging and the hook reply format.

Every gate follows the same rule: if the gate itself fails (bad JSON, missing
config, unreadable file), the command is let through. A gate must never be the
reason your session breaks.
"""
import datetime
import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".claude" / "gates.json"

DEFAULTS = {
    "log_dir": "~/.claude/gates-logs",
    "cost": {
        "currency": "USD",
        # A command is only checked when it looks like a real API call ...
        "api_patterns": [
            r"generativelanguage\.googleapis", r"aiplatform\.googleapis",
            r"from google import genai", r"google\.genai", r"@google/genai",
            r"api\.openai\.com", r"from openai import", r"api\.anthropic\.com",
            r"import anthropic", r"api\.x\.ai", r"api\.replicate\.com",
        ],
        # ... and names a model or endpoint that costs real money per call.
        "expensive_patterns": [
            r"gemini-[\w.\-]*-image", r"imagen-\d", r"gemini-[\w.\-]*-tts",
            r"veo-\d", r"predictLongRunning", r"generateImages",
            r"gpt-image-\d", r"dall-e-\d", r"sora-\d",
        ],
    },
    "batch": {
        "premium_models": ["opus"],
        "min_reason_chars": 25,
    },
    "premium_model": {
        "models": ["o3-pro", "gpt-5-pro", "claude-opus"],
        "min_reason_chars": 25,
    },
    "fanout": {
        "max_agents_without_asking": 10,
        "tokens_per_agent": 1_130_000,
    },
}


def load_config():
    """Defaults, overridden per section by the user's gates.json (if any)."""
    cfg = json.loads(json.dumps(DEFAULTS))
    path = Path(os.environ.get("CLAUDE_GATES_CONFIG", DEFAULT_CONFIG)).expanduser()
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def read_event():
    """The hook event Claude Code sends on stdin, or None if it cannot be read."""
    try:
        return json.load(sys.stdin)
    except ValueError:
        return None


def command_of(event):
    return ((event or {}).get("tool_input") or {}).get("command") or ""


def first_line(cmd, skip=None):
    for line in cmd.splitlines():
        line = line.strip()
        if line and not (skip and skip.search(line)):
            return line[:100].replace("`", "")
    return ""


def log(cfg, name, text):
    """Append one line to <log_dir>/<name>.log. Logging problems are ignored."""
    try:
        folder = Path(cfg["log_dir"]).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{name}.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")
    except OSError:
        pass


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def ask(reason, context=""):
    out = {"hookEventName": "PreToolUse", "permissionDecision": "ask",
           "permissionDecisionReason": reason}
    if context:
        out["additionalContext"] = context
    print(json.dumps({"hookSpecificOutput": out}))


def note(context):
    """Let the call through, but put a note in front of the model."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": context}}))


def run(main):
    """Run a gate; any internal error lets the command through."""
    try:
        main()
    except Exception:  # noqa: BLE001 - a broken gate must never block work
        pass
    sys.exit(0)
