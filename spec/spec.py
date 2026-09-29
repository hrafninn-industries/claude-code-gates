#!/usr/bin/env python3
"""spec.py: write down what "done" means before the work starts, and refuse "done" without evidence.

    spec.py new "<title>"      create a spec from TEMPLATE.md
    spec.py list               show every spec and how many criteria have evidence
    spec.py verify <file>      the gate before the word "done": exit 1 if any criterion lacks evidence
    spec.py close <file>       verify, then stamp the spec as done

A criterion counts as met only when its EVIDENCE line says what was actually run
and what came out. Empty evidence, a placeholder, a few words, or a copy of the
MEASURED BY line all fail. Specs live in $SPEC_DIR (default: ./specs).
"""
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("SPEC_DIR", "specs")).expanduser()
TEMPLATE = Path(__file__).with_name("TEMPLATE.md")
EMPTY = {"", "—", "-", "–", "tbd", "todo", "n/a", "?", "done", "ok", "checked", "yes"}
MIN_EVIDENCE = 12

TTY = sys.stdout.isatty()
GREEN, RED, YELLOW, GREY, END = (("\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m")
                                 if TTY else ("", "", "", "", ""))


def slug(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()[:50] or "SPEC"


def criteria(text):
    """Every criterion block: [{id, ticked, text, measured, evidence}]."""
    out, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*-\s*\[( |x|X)\]\s*(C\d+)\s*[·:.\-]?\s*(.*)$", line)
        if not m:
            continue
        item = {"id": m.group(2), "ticked": m.group(1).lower() == "x",
                "text": m.group(3).strip(), "measured": "", "evidence": ""}
        for follow in lines[i + 1:]:
            if re.match(r"^\s*-\s*\[( |x|X)\]", follow) or re.match(r"^#{1,6}\s", follow):
                break
            mm = re.match(r"^\s*MEASURED BY\s*:\s*(.*)$", follow, re.I)
            if mm:
                item["measured"] = mm.group(1).strip()
            me = re.match(r"^\s*EVIDENCE\s*:\s*(.*)$", follow, re.I)
            if me:
                item["evidence"] = me.group(1).strip()
        out.append(item)
    return out


def squash(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def problem(item):
    """None if the criterion holds, otherwise the reason it fails."""
    ev = item["evidence"]
    if ev.strip().lower() in EMPTY:
        return "no evidence"
    if ev.startswith("<") and ev.endswith(">"):
        return "evidence is still the template placeholder"
    if len(ev) < MIN_EVIDENCE:
        return f"evidence is too short to be evidence ({len(ev)} characters)"
    if item["measured"] and squash(ev) == squash(item["measured"]):
        return "evidence only repeats how it is measured: what was the result?"
    if item["text"].startswith("<"):
        return "criterion is still the template placeholder"
    if not item["ticked"]:
        return "evidence is there but the box is not ticked"
    return None


def find(arg):
    path = Path(arg)
    if path.is_file():
        return path
    hits = [p for p in sorted(ROOT.glob("**/*.md")) if arg.lower() in p.name.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit(f"{RED}No spec matches: {arg}{END}")
    sys.exit(f"{RED}Several specs match {arg}:{END}\n  " + "\n  ".join(map(str, hits)))


def cmd_new(title):
    now = datetime.now()
    folder = ROOT / now.strftime("%Y-%m")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"SPEC_{now:%Y-%m-%d}_{slug(title)}.md"
    n = 2
    while path.exists():
        path = folder / f"SPEC_{now:%Y-%m-%d}_{slug(title)}_{n}.md"
        n += 1
    path.write_text(TEMPLATE.read_text(encoding="utf-8")
                    .replace("{TITLE}", title)
                    .replace("{DATE}", now.strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    print(f"{GREEN}Spec created{END}\n{path}")
    print(f"{GREY}Fill in every section, show it to the person who asked, and wait for a yes before building.{END}")


def cmd_list():
    files = sorted(ROOT.glob("**/SPEC_*.md"))
    if not files:
        print(f"{GREY}No specs yet in {ROOT}.{END}")
        return
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        status = (re.search(r"\*\*Status:\*\*\s*(\S+)", text) or [None, "?"])[1]
        items = criteria(text)
        left = sum(1 for c in items if problem(c))
        print(f"{status:<8} {len(items) - left}/{len(items)} criteria met  {f.relative_to(ROOT)}")


def cmd_verify(arg, quiet=False):
    path = find(arg)
    text = path.read_text(encoding="utf-8", errors="ignore")
    items = criteria(text)
    if not items:
        print(f"{RED}FAILED{END}: the spec has no criteria. Without measurable criteria it is a wish list.\n{path}")
        sys.exit(1)
    failed = []
    for c in items:
        why = problem(c)
        if why:
            failed.append(c)
            print(f"{RED}✗ {c['id']}{END} {c['text'][:70]}\n    {RED}{why}{END}")
        elif not quiet:
            print(f"{GREEN}✓ {c['id']}{END} {c['text'][:70]}\n    {GREY}{c['evidence'][:100]}{END}")
    empty = [s for s in ("OUT OF SCOPE", "RISKS", "MUST NOT BREAK")
             if re.search(rf"^## {s}\s*\n\s*<", text, re.M)]
    if empty and not quiet:
        print(f"{YELLOW}! Sections not filled in: {', '.join(empty)}{END}")
    if re.search(r"\*\*Approved:\*\*\s*no", text) and not quiet:
        print(f"{YELLOW}! The spec is not marked as approved. Did you get a yes before building?{END}")
    if failed:
        print(f"\n{RED}FAILED: {len(failed)} of {len(items)} criteria lack evidence. Do not say done.{END}")
        sys.exit(1)
    if not quiet:
        print(f"\n{GREEN}PASSED: {len(items)} criteria, all with evidence.{END}")
    return path


def cmd_close(arg):
    path = cmd_verify(arg, quiet=True)
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\*\*Status:\*\*\s*\S+", "**Status:** done", text, count=1)
    if "**Closed:**" not in text:
        text = text.replace("**Approved:**", f"**Closed:** {datetime.now():%Y-%m-%d %H:%M} · **Approved:**", 1)
    path.write_text(text, encoding="utf-8")
    print(f"{GREEN}Closed{END}: {path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    verb, *rest = sys.argv[1:]
    if verb == "new" and rest:
        cmd_new(" ".join(rest))
    elif verb == "list":
        cmd_list()
    elif verb == "verify" and rest:
        cmd_verify(rest[0])
    elif verb == "close" and rest:
        cmd_close(rest[0])
    else:
        sys.exit(__doc__)
