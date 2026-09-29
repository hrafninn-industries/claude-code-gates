#!/usr/bin/env python3
"""fanout_gate: puts a number on a big fan-out and asks the human before it runs.

Why it exists: one research workflow started 276 sub-agents on the most
expensive model and used about 313 million tokens. The same job, run on a
cheaper fleet afterwards, took eight minutes.

What it does (PreToolUse on Workflow and Agent):
  * Workflow: estimates how many agents the script will start. Above
    "fanout.max_agents_without_asking" the call is turned into a question to the
    human, with the estimated token count in the question.
  * Agent: when the prompt looks like search/read/summarise work, the call goes
    through with a note asking whether a cheaper model could do it.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ask, load_config, log, note, read_event, run  # noqa: E402

RESEARCH = re.compile(
    r"\b(search|research|papers?|arxiv|google|web|sources|sweep|explore|survey|market|"
    r"competitors?|documentation|read through|summari[sz]e)\b", re.I)


def estimate_agents(script):
    """Rough upper estimate of the number of sub-agents a workflow script starts."""
    calls = len(re.findall(r"\bagent\s*\(", script))
    widths = [len(m.split("},")) for m in re.findall(r"=\s*\[([^\]]{80,})\]", script, re.S)]
    fanout = max(widths) if widths else 1
    nested = len(re.findall(r"parallel\s*\(", script))
    return max(calls * fanout * max(nested, 1), calls)


def main():
    cfg = load_config()
    conf = cfg["fanout"]
    event = read_event() or {}
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}

    if tool == "Workflow":
        script = ti.get("script") or ""
        agents = estimate_agents(script)
        if agents <= conf["max_agents_without_asking"]:
            return
        tokens = agents * conf["tokens_per_agent"]
        research = bool(RESEARCH.search(script + json.dumps(ti.get("args", ""))))
        log(cfg, "fanout", f"asked | ~{agents} agents | ~{tokens / 1e6:.0f}M tokens | research={research}")
        ask(
            f"About {agents} sub-agents, roughly {tokens / 1e6:.0f}M tokens. "
            + ("This looks like research, which a cheaper model can usually do. " if research else "")
            + "Approve only if the agent has said why a cheaper route will not work.",
            "FAN-OUT GATE: tell the user the estimate above in plain words and let them choose. "
            "Which part of this job needs this model's judgement? Can the rest go to a cheaper model or a script?",
        )
        return

    if tool == "Agent" and RESEARCH.search(str(ti.get("prompt", ""))):
        note("FAN-OUT GATE: this sub-agent prompt looks like search/read/summarise work. "
             "Does it need this model's judgement, or only time and eyes? A cheaper model may do it.")


if __name__ == "__main__":
    run(main)
