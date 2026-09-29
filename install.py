#!/usr/bin/env python3
"""Install the gates into Claude Code.

    python3 install.py            copy gates to ~/.claude/gates and register them in ~/.claude/settings.json
    python3 install.py --dry-run  show what would change, change nothing

What it does:
  * copies gates/*.py to ~/.claude/gates/
  * copies spec/ to ~/.claude/skills/spec/ (the /spec skill)
  * copies gates.example.json to ~/.claude/gates.json if you have none yet
  * adds one PreToolUse entry per gate to ~/.claude/settings.json, after saving a
    backup next to it. Running it twice does not add anything twice.

It never removes hooks you already have.
"""
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE = Path.home() / ".claude"
TARGET = CLAUDE / "gates"

GATES = [  # (file, matcher)
    ("rm_gate.py", "Bash"),
    ("cost_gate.py", "Bash"),
    ("premium_model_gate.py", "Bash"),
    ("batch_gate.py", "Bash"),
    ("fanout_gate.py", "Workflow|Agent"),
]


def main():
    dry = "--dry-run" in sys.argv
    settings_path = CLAUDE / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        settings = {}
    pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    existing = json.dumps(pre)

    added = []
    for name, matcher in GATES:
        command = f"python3 {TARGET / name}"
        if command in existing:
            continue
        pre.append({"matcher": matcher, "hooks": [{"type": "command", "command": command, "timeout": 5}]})
        added.append(name)

    print(f"Gates folder:  {TARGET}")
    print(f"Settings file: {settings_path}")
    print("New hooks:     " + (", ".join(added) if added else "none, all five are already registered"))
    if dry:
        print("Dry run: nothing was changed.")
        return 0

    TARGET.mkdir(parents=True, exist_ok=True)
    for src in (HERE / "gates").glob("*.py"):
        shutil.copy2(src, TARGET / src.name)
    skill = CLAUDE / "skills" / "spec"
    skill.mkdir(parents=True, exist_ok=True)
    for src in (HERE / "spec").iterdir():
        if src.is_file():
            shutil.copy2(src, skill / src.name)
    config = CLAUDE / "gates.json"
    if not config.exists():
        shutil.copy2(HERE / "gates.example.json", config)
        print(f"Config:        {config} (new, edit it to taste)")

    if added:
        if settings_path.exists():
            backup = settings_path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(settings_path, backup)
            print(f"Backup:        {backup}")
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print("Done. Restart Claude Code so it reads the new hooks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
