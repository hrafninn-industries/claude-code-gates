#!/usr/bin/env python3
"""premium_model_gate: the most expensive model is an escalation step, not a default.

Why it exists: the top model gets picked because a task feels big or important,
not because the standard model failed. That habit is what burns the budget.

What it does (PreToolUse on Bash): a command that SELECTS a model listed under
"premium_model.models" in gates.json (via --model, -m, MODEL=..., model=...) is
denied until it carries

    # ESCALATE: <what the standard model could not do, at least 25 characters>

Mentioning the name (grep, docs, logs) is let through. Every escalation is
logged to <log_dir>/escalation.log, so someone can read the reasons afterwards.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import command_of, deny, first_line, load_config, log, read_event, run  # noqa: E402

MARK = re.compile(r"#\s*ESCALATE:\s*(?P<why>[^\n]+)", re.I)
BAD_REASONS = re.compile(r"^\s*(big|large|hard|difficult|important|better|complex)\b[\w\s]{0,20}$", re.I)


def selected_premium(cmd, models):
    for model in models:
        pick = re.compile(
            r"([A-Z_]*MODEL\s*=\s*['\"]?|\s-m\s+['\"]?|--model[=\s]+['\"]?|model\s*=\s*\\?['\"]?)"
            + re.escape(model), re.I)
        if pick.search(cmd):
            return model
    return None


def main():
    cfg = load_config()
    conf = cfg["premium_model"]
    cmd = command_of(read_event())
    if not cmd:
        return
    model = selected_premium(cmd, conf["models"])
    if not model:
        return
    mark = MARK.search(cmd)
    why = mark["why"].strip() if mark else ""
    if len(why) >= conf["min_reason_chars"] and not BAD_REASONS.match(why):
        log(cfg, "escalation", f"{model} | {why} | {first_line(cmd, MARK)}")
        return
    deny(
        f"PREMIUM MODEL GATE: {model} is an escalation step. Run the standard model first. If it got stuck "
        "on something concrete, send only that problem to the premium model and add the line "
        f"'# ESCALATE: <what the standard model could not do>' (at least {conf['min_reason_chars']} characters). "
        "'The task is big/important' is not a reason."
    )


if __name__ == "__main__":
    run(main)
