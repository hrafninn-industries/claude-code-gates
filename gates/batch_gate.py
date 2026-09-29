#!/usr/bin/env python3
"""batch_gate: makes the agent say who should do a batch job before it starts one.

Why it exists: a reminder was not enough. In one day the agent walked past a
"consider a cheaper model" note five times and ran a whole file clean-up on the
most expensive model.

What it does (PreToolUse on Bash):
  * Commands that change many files (loops that write, find -exec, xargs, bulk
    rename/convert, os.walk/rglob) are denied until they carry

        # MODEL: <who does it> — <why>

  * Choosing a premium model (default: "opus") needs a reason of at least 25 characters.
  * Every choice is written to <log_dir>/model-choice.log.

Loops that only READ (cat, head, sed -n, grep, wc, ls, echo, gh api, curl without
-X/-d ...) are let through. An early version stopped plain read loops, and a gate
that cries wolf gets switched off.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import command_of, deny, first_line, load_config, log, read_event, run  # noqa: E402

BATCH = [
    r"\bfor\s+\w+\s+in\b[\s\S]*?\bdo\b",
    r"\bwhile\b[^\n]*\bread\b",
    r"\bfind\b[^\n]*-(exec|delete)\b",
    r"\|\s*xargs\b",
    r"\b(mogrify|convert)\b[^\n]*\*",
    r"\brename\b[^\n]*\*",
    r"\bos\.walk\(|\.rglob\(|\bglob\.glob\(",
]
MARK = re.compile(r"#\s*MODEL:\s*(?P<who>[^\n—–]+?)\s*[—–-]+\s*(?P<why>[^\n]+)", re.I)

READ_ONLY = {
    "cat", "head", "tail", "grep", "egrep", "rg", "wc", "ls", "echo", "printf", "stat", "file",
    "sha256sum", "md5sum", "du", "df", "basename", "dirname", "realpath", "readlink", "test",
    "true", "false", "jq", "sort", "uniq", "cut", "tr", "column", "nl", "diff", "cmp", "less",
    "ffprobe", "identify", "date", "sleep", "pgrep", "ps", "which", "type", "[", "[[", "awk",
    "sed", "gh", "curl", "git", "cd", "pwd", "done", "fi", "for", "continue", "break",
}
# Shell keywords that come BEFORE a command: the word after them is what gets checked.
LEADING = {"do", "then", "else", "elif", "if", "while", "until", "!", "time"}
WRITES = [
    r"(?<![0-9&])>\s*(?!&|/dev/null)",   # redirect into a file (2>/dev/null and 2>&1 are fine)
    r"\bsed\b[^|;&\n]*\s-i",              # sed in place
    r"\bawk\b[^|;&\n]*-i\s*inplace",
    r"\bgh\s+(repo|pr|issue|release)\s+(create|delete|edit|merge|close)",
    r"\bgh\s+api\b[^|;&\n]*(-X\s*(POST|PUT|PATCH|DELETE)|--method\s+(POST|PUT|PATCH|DELETE))",
    r"\bcurl\b[^|;&\n]*(-X\s*(POST|PUT|PATCH|DELETE)|\s-d\s|--data|-F\s|-T\s|-o\s|-O\b)",
    r"\bgit\s+(push|commit|reset|checkout|clean|rm|mv|add|rebase|merge)\b",
]


def loop_is_read_only(cmd):
    """True when every command in the text is on the read-only list and nothing writes."""
    if any(re.search(p, cmd) for p in WRITES):
        return False
    body = re.sub(r"'[^']*'|\"[^\"]*\"", "''", cmd)          # quoted text is data, not commands
    for segment in re.split(r"[;&|\n]+|\$\(|`|\)", body):
        words = segment.strip().split()
        while words and (words[0] in LEADING or re.match(r"^\w+=", words[0])):  # keywords, VAR=value
            words = words[1:]
        if not words:
            continue
        if words[0].startswith("#"):
            continue
        if words[0] not in READ_ONLY:
            return False
    return True


def main():
    cfg = load_config()
    batch = cfg["batch"]
    event = read_event()
    cmd = command_of(event)
    if not cmd or not any(re.search(p, cmd, re.I) for p in BATCH):
        return
    if loop_is_read_only(cmd):
        return
    mark = MARK.search(cmd)
    premium = mark and any(m.lower() in mark["who"].lower() for m in batch["premium_models"])
    short = premium and len(mark["why"].strip()) < batch["min_reason_chars"]
    if mark and not short:
        log(cfg, "model-choice", f"{mark['who'].strip()} | {mark['why'].strip()} | {first_line(cmd, MARK)}")
        return
    extra = (f"A premium model needs a reason of at least {batch['min_reason_chars']} characters. "
             if short else "")
    deny(
        "BATCH GATE: this command works through many files. " + extra +
        "Decide who should do it first: a cheaper model, a local model, a script, or you, if handing it "
        "off costs more than it saves. Then add the line '# MODEL: <who> — <why>' to the command and run "
        "it again. The choice is logged for review."
    )


if __name__ == "__main__":
    run(main)
