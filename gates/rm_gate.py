#!/usr/bin/env python3
"""rm_gate: denies rm when the path contains $, * or ~.

Why it exists: an empty variable turns `rm -rf "$DIR/"` into `rm -rf /`. A glob
or a tilde in the wrong place does the same kind of damage. The agent gets the
reason back and rewrites the command with literal paths, before a human is ever
asked to approve it.

What it does (PreToolUse on Bash): splits the command on ; & | newlines $( and
backticks, and denies any segment that starts with rm (or sudo rm) and has $, *
or ~ in its arguments. `git rm`, `echo rm $x` and literal paths are let through.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import command_of, deny, read_event, run  # noqa: E402


def dangerous_rm(cmd):
    for segment in re.split(r"[;&|\n`]+", cmd):
        # Check the segment itself and everything that starts inside a $( ... ).
        # Splitting on "$(" would throw away the "$" in "rm -rf $(cat list)".
        starts = [segment] + [segment[m.end():] for m in re.finditer(r"\$\(", segment)]
        for part in starts:
            # rm, \rm, /bin/rm, command rm, sudo rm, and rm run by xargs.
            m = re.match(r"\s*(?:sudo\s+|command\s+|exec\s+|xargs\s+(?:-\S+\s+)*)*\\?(?:/usr)?(?:/bin/)?rm\b(.*)",
                         part)
            if m and re.search(r"[$*~]", m.group(1)):
                return part.strip()
    return None


def main():
    event = read_event()
    if (event or {}).get("tool_name", "Bash") != "Bash":
        return
    hit = dangerous_rm(command_of(event))
    if hit:
        deny(
            f"RM GATE: '{hit[:80]}' has $, * or ~ in the path. Write the full literal path of each file, "
            "delete from Python with pathlib.Path.unlink(), or do not delete at all."
        )


if __name__ == "__main__":
    run(main)
