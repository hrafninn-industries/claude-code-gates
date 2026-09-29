# claude-code-gates

Hooks that make Claude Code ask before it spends money on paid models, runs batch jobs on an expensive model, or deletes with a variable path. Plus a `/spec` check that fails a job until every acceptance criterion has evidence.

Each gate came from something that went wrong in daily use at a small agency where one person works with several AI models all day. The gates run as `PreToolUse` hooks: Claude Code runs them before a tool call, and a gate can let the call through, deny it with a reason the agent can act on, or turn it into a question for you. They match patterns, so they catch the habits they were written for; see [Good to know](#good-to-know) for what they do not catch.

## What is in the box

| Gate | Catches | Lets through | Came from (our own logs) |
|---|---|---|---|
| `cost_gate` | Calls to paid per-call models (image, video, speech). It also reads the scripts named on the command line, so a call inside `python3 generate.py` is seen | The same call when the command carries an approval line (below) | About 215 image generations on a key everyone thought was free. Roughly 28 USD in one morning. |
| `batch_gate` | Loops, `find -exec`, `xargs` and bulk renames | Loops that only read; batch jobs that say who does them with `# MODEL: <who> — <why>` (a premium model needs a reason of 25+ characters) | Batch jobs over many files ran on the most expensive model without anyone deciding. A reminder was ignored five times in one day. |
| `rm_gate` | `rm` with `$`, `*` or `~` in the path, also inside `$( … )` | Literal paths, `git rm`, `echo "rm …"` | An empty variable turns `rm -rf "$DIR/"` into `rm -rf /`. |
| `premium_model_gate` | Selecting a model you list as premium (`--model`, `-m`, `MODEL=`) | The same with `# ESCALATE: <what the standard model could not do>` (25+ characters) | The top model got picked because a task felt important, not because the standard one had failed. |
| `fanout_gate` | Workflows that would start more than 10 sub-agents: instead of running, you get a question with the estimated token count | Small workflows and single sub-agents | One research run started 276 sub-agents and used about 313 million tokens. |

The approval line for `cost_gate` looks like this. The gate's message uses the currency set in `gates.json` (USD by default; the examples below use the default):

```text
# COST: <amount> <currency> — approved <by whom, when>
# COST: 8.00 USD — approved by Dana 14:05
```

Also included:

- **`/spec`**, a skill plus a script. Before a bigger job the agent writes down what "done" means as true-or-false criteria, each with how it will be measured. `spec.py verify` exits with an error until every criterion has evidence: what was run and what came out. Empty evidence, a few words, or a copy of the measuring method all fail. The skill tells the agent when to write a spec and to run `verify` before it says a job is done.
- **`check`**, a second opinion on a claim or plan from a local model, usually a few seconds with a model that is already loaded: `check "the migration is safe because every column has a default"`. The model is told to look for mistakes and to start with OK or WRONG.

## Install

Requires Python 3.9 or newer. Nothing else to install.

```bash
git clone https://github.com/hrafninn-industries/claude-code-gates.git
cd claude-code-gates
python3 install.py --dry-run   # shows what will change
python3 install.py
```

`install.py`:

- copies the gates to `~/.claude/gates/`
- copies the skill and `spec.py` to `~/.claude/skills/spec/`
- creates `~/.claude/gates.json` if you have none
- adds five hooks to `~/.claude/settings.json`, after saving a backup next to it

It never removes hooks you already have and adds nothing twice if you run it again. Restart Claude Code afterwards.

Specs are written to `./specs/` in the project you work in (set `SPEC_DIR` to change it):

```bash
python3 ~/.claude/skills/spec/spec.py new "contact form"
python3 ~/.claude/skills/spec/spec.py verify contact_form
```

For `check`, copy `bin/check` somewhere on your `PATH` and point it at a model:

```bash
export CHECK_URL=http://localhost:11434      # any Ollama server
export CHECK_MODEL=qwen3-coder:30b
# or any OpenAI-compatible server:
export CHECK_API=openai CHECK_URL=http://localhost:8000 CHECK_MODEL=my-model
```

## What it looks like

The agent tries to generate 200 images:

```text
COST GATE: this command calls a paid model (gpt-image-1). Work out what it will cost in USD,
show the amount to the user and wait for a yes. Then add the line
'# COST: <amount> USD — approved <by whom, when>' to the command and run it again.
Approved calls are logged.
```

The agent tells you the amount, you say yes, it runs the command again with the approval line, and the approval is written to `cost.log`.

The agent says a job is done:

```text
$ python3 ~/.claude/skills/spec/spec.py verify contact_form
✓ C1 The page renders without console errors at 1280 px.
    playwright 14:02, 0 console errors, screenshot shots/1280.png
✗ C2 The contact form sends a mail to the shop.
    evidence is too short to be evidence (8 characters)

FAILED: 1 of 2 criteria lack evidence. Do not say done.
```

## Settings

`~/.claude/gates.json` (see `gates.example.json`):

- `cost.currency`, `cost.api_patterns`, `cost.expensive_patterns`: what counts as a paid call. A command is caught only when it matches both an API pattern and an expensive-model pattern.
- `batch.premium_models`: names that, when written after `# MODEL:`, need the longer reason (`batch.min_reason_chars`).
- `premium_model.models`: models that may only be *selected* with an `# ESCALATE:` line. This is a different list from the one above: one is about who does a batch job, the other about which model a command calls.
- `fanout.max_agents_without_asking`: default 10. The estimate is the number of `agent(` calls, times the longest list in the script, times the number of `parallel(` calls (a missing list or `parallel(` counts as 1), times `fanout.tokens_per_agent` (default 1.13 million, from the 276-agent run). It is a rough upper guess, meant to make you look before you approve.
- `log_dir`: default `~/.claude/gates-logs/`. Four gates log what they let through: `cost_gate` to `cost.log`, `batch_gate` to `model-choice.log`, `premium_model_gate` to `escalation.log`, and `fanout_gate` logs each question it asks to `fanout.log`. `rm_gate` only denies, so it has nothing to log.

## Good to know

- **If a gate crashes, the command goes through.** Bad input, a missing config or an unreadable file never blocks your work. A gate that *denies* a command always blocks it; only a gate that fails to run lets it pass.
- **These are guard rails against expensive habits.** A determined agent, or a person, can phrase a command that the patterns do not catch. Do not rely on them to keep secrets or systems safe.
- **The approval lines are written by the agent.** Nothing checks that you really said yes to `# COST: 8.00 USD — approved by Dana`. What the gate does is force the agent to stop, work out an amount and put it in front of you, and it leaves a log line you can check afterwards. If you need a hard stop, keep the paid keys out of the environment the agent runs in.
- **They are pattern-based.** `cost_gate` only knows the providers it has patterns for, and only reads scripts named on the command line. Add your own in `gates.json`.
- **`fanout_gate` on single sub-agents:** when a sub-agent prompt looks like search or summarising work, the call goes through, and the agent gets a short note asking whether a cheaper model could do it.
- **False alarms matter.** An early version of `batch_gate` stopped plain read-only loops several times a day. Loops that only read now go through, and the commands that caused those alarms are part of the tests.

## Tests

```bash
python3 -m unittest -v
```

Every gate has commands it must stop and commands it must let through. The gates run as real subprocesses with a hook event on stdin, the same way Claude Code runs them.

## License

MIT. Not affiliated with or endorsed by Anthropic.

Made by [Hrafninn Industries](https://hrafninn.se), Kungsbacka, Sweden.
