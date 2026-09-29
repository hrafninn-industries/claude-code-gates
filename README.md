# claude-code-gates

Hooks that stop Claude Code before it spends money, deletes the wrong folder, or says "done" without proof.

Each gate came from something that went wrong in daily use at a small agency where one person works with several AI models all day. The gates run as `PreToolUse` hooks: Claude Code asks them before a command runs, and a gate can let the command through, deny it with a reason the agent can act on, or turn it into a question for you.

## What is in the box

| Gate | Stops | Lets through | Came from |
|---|---|---|---|
| `cost_gate` | Calls to paid per-call models (image, video, speech), also when the call sits inside a script the command runs | The same call when the command carries `# COST: <amount> — approved <by whom>` | About 215 image generations on a key everyone thought was free. Roughly 28 USD in one morning. |
| `batch_gate` | Loops, `find -exec`, `xargs` and bulk renames that change files | Loops that only read; any batch job with `# MODEL: <who> — <why>` | The agent ran a whole file clean-up on the most expensive model after walking past a reminder five times. |
| `rm_gate` | `rm` with `$`, `*` or `~` in the path, also inside `$( … )` | Literal paths, `git rm`, `echo "rm …"` | An empty variable turns `rm -rf "$DIR/"` into `rm -rf /`. |
| `premium_model_gate` | Selecting a model you list as premium (`--model`, `-m`, `MODEL=`) | The same with `# ESCALATE: <what the standard model could not do>` | The top model got picked because a task felt important, not because the standard one failed. |
| `fanout_gate` | Workflows that would start more than 10 sub-agents: you get a question with the estimated token count | Small workflows; single sub-agents (with a note if the job looks like research) | One research run started 276 sub-agents and used about 313 million tokens. |

Also included:

- **`/spec`**, a skill and a small script. Before a bigger job the agent writes down what "done" means as true-or-false criteria. `spec.py verify` refuses to pass until every criterion has evidence: what was run and what came out. Empty evidence, a few words, or a copy of the measuring method all fail.
- **`check`**, a one-second second opinion from a local model: `check "the migration is safe because every column has a default"`. The model is told to look for mistakes and to start with OK or WRONG.

Every approval is written to a log in `~/.claude/gates-logs/`, so you can read afterwards what was approved and why.

## Install

Requires Python 3.9 or newer. No packages to install.

```bash
git clone https://github.com/hrafninn-industries/claude-code-gates.git
cd claude-code-gates
python3 install.py --dry-run   # shows what will change
python3 install.py
```

`install.py` copies the gates to `~/.claude/gates/`, the skill to `~/.claude/skills/spec/`, creates `~/.claude/gates.json` if you have none, and adds five hooks to `~/.claude/settings.json`. It saves a backup of your settings first, never removes hooks you already have, and adds nothing twice if you run it again. Restart Claude Code afterwards.

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
```

The agent tells you the amount, you say yes, it runs again with `# COST: 8.00 USD — approved by Dana 14:05`, and the approval lands in `cost.log`.

The agent says a job is done:

```text
$ python3 spec.py verify specs/2026-09/SPEC_2026-09-29_CONTACT_FORM.md
✓ C1 The page renders without console errors at 1280 px.
    playwright 14:02, 0 console errors, screenshot shots/1280.png
✗ C2 The contact form sends a mail to the shop.
    evidence is too short to be evidence (8 characters)

FAILED: 1 of 2 criteria lack evidence. Do not say done.
```

## Settings

`~/.claude/gates.json` (see `gates.example.json`):

- `cost.currency`, `cost.api_patterns`, `cost.expensive_patterns`: what counts as a paid call.
- `batch.premium_models`, `batch.min_reason_chars`: which model names need a longer reason.
- `premium_model.models`: the models you treat as an escalation step.
- `fanout.max_agents_without_asking`: default 10.
- `log_dir`: where approvals are logged.

## Good to know

- **A gate that fails lets the command through.** Bad input, a missing config or an unreadable file never blocks your work. The flip side: these are guard rails against expensive habits, not a security boundary. A determined agent, or a person, can phrase a command the patterns do not catch.
- **They are pattern-based.** `cost_gate` only sees calls it has patterns for, and only in scripts named on the command line. Add your own providers in `gates.json`.
- **False alarms matter.** An early version of `batch_gate` stopped plain read-only loops and got in the way several times a day. Loops that only read now go through, and the commands that caused those alarms are part of the tests.

## Tests

```bash
python3 -m unittest -v
```

Every gate has commands it must stop and commands it must let through. The gates run as real subprocesses with a hook event on stdin, the same way Claude Code runs them.

## License

MIT. Not affiliated with or endorsed by Anthropic.

Made by [Hrafninn Industries](https://hrafninn.se), Kungsbacka, Sweden.
