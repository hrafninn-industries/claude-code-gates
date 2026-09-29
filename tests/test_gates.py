"""Every gate: at least three commands it must STOP and three it must LET THROUGH.

Run from the repo root:  python3 -m unittest -v
The gates run as real subprocesses with a hook event on stdin, the way Claude Code runs them.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATES = ROOT / "gates"


class GateCase(unittest.TestCase):
    gate = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.logs = Path(cls.tmp.name) / "logs"
        cls.config = Path(cls.tmp.name) / "gates.json"
        cls.config.write_text(json.dumps({"log_dir": str(cls.logs)}))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_gate(self, tool_input, tool="Bash"):
        event = {"session_id": "test", "tool_name": tool, "tool_input": tool_input}
        env = dict(os.environ, CLAUDE_GATES_CONFIG=str(self.config))
        out = subprocess.run([sys.executable, str(GATES / self.gate)], input=json.dumps(event),
                             capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["hookSpecificOutput"] if out.stdout.strip() else {}

    def decision(self, command, tool="Bash"):
        ti = command if isinstance(command, dict) else {"command": command}
        return self.run_gate(ti, tool).get("permissionDecision", "allow")

    def assertStops(self, command, tool="Bash", how="deny"):
        self.assertEqual(self.decision(command, tool), how, f"should stop: {command!r}")

    def assertLetsThrough(self, command, tool="Bash"):
        self.assertEqual(self.decision(command, tool), "allow", f"should let through: {command!r}")

    def log_lines(self, name):
        path = self.logs / f"{name}.log"
        return path.read_text().splitlines() if path.exists() else []


class RmGate(GateCase):
    gate = "rm_gate.py"

    def test_stops_variable_path(self):
        self.assertStops('rm -rf "$BUILD_DIR/"')

    def test_stops_glob(self):
        self.assertStops("cd /tmp/out && rm *.png")

    def test_stops_tilde(self):
        self.assertStops("rm -r ~/projects/old")

    def test_stops_sudo_and_subshell(self):
        self.assertStops("echo start; sudo rm -rf $(cat list.txt)")

    def test_stops_rm_inside_command_substitution(self):
        self.assertStops('echo "cleaning $(rm -rf $TMPDIR/cache)"')

    def test_stops_other_ways_to_call_rm(self):
        for cmd in ('\\rm -rf "$D"', "/bin/rm -rf $D", "command rm -r ~/x", "ls | xargs -0 rm -f *.tmp"):
            with self.subTest(cmd=cmd):
                self.assertStops(cmd)

    def test_lets_literal_path_through(self):
        self.assertLetsThrough("rm /tmp/report-2026-09-29.txt")

    def test_lets_git_rm_through(self):
        self.assertLetsThrough("git rm --cached secrets.env")

    def test_lets_echo_of_rm_through(self):
        self.assertLetsThrough('echo "never run rm $X"')


class CostGate(GateCase):
    gate = "cost_gate.py"

    def test_stops_image_model_in_command(self):
        self.assertStops("python3 -c \"from google import genai; genai.Client().models."
                         "generate_content(model='gemini-3-pro-image', contents='cat')\"")

    def test_stops_video_model_in_curl(self):
        self.assertStops("curl https://generativelanguage.googleapis.com/v1beta/models/veo-3:predictLongRunning -d @req.json")

    def test_stops_call_hidden_in_script(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("from openai import OpenAI\nOpenAI().images.generate(model='gpt-image-1', prompt='x')\n")
        try:
            self.assertStops(f"python3 {f.name} --count 200")
        finally:
            os.unlink(f.name)

    def test_approved_call_goes_through_and_is_logged(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("from openai import OpenAI\nOpenAI().images.generate(model='gpt-image-1', prompt='x')\n")
        try:
            before = len(self.log_lines("cost"))
            self.assertLetsThrough(f"# COST: 0.40 USD — approved by Dana 14:05\npython3 {f.name}")
            self.assertEqual(len(self.log_lines("cost")), before + 1)
        finally:
            os.unlink(f.name)

    def test_lets_cheap_text_model_through(self):
        self.assertLetsThrough("python3 -c \"from google import genai; genai.Client().models."
                               "generate_content(model='gemini-3-flash', contents='hi')\"")

    def test_lets_grep_for_model_name_through(self):
        self.assertLetsThrough("grep -rn 'gemini-3-pro-image' docs/")

    def test_marker_without_approval_still_stops(self):
        self.assertStops("# COST: 5 USD\ncurl https://api.openai.com/v1/images -d '{\"model\":\"gpt-image-1\"}'")


class BatchGate(GateCase):
    gate = "batch_gate.py"

    # The three commands an earlier version wrongly stopped, word for word apart from temp paths.
    FALSE_ALARMS = [
        'for f in r_gpt.txt r_grok.txt r_gemini.txt r_nemo.txt r_spark.txt; do echo "################ $f"; cat $f; done',
        "for n in hrafninn hrafninn-industries hrafninnai; do printf \"%s: \" $n; "
        "gh api users/$n --jq '.type+\" exists\"' 2>/dev/null || echo \"free\"; done",
        "cd ~/.claude/hooks; wc -l *.py; for f in *.py; do echo \"== $f\"; sed -n 1,12p $f | "
        "grep -E '^\\s*(\"\"\"|#)' | head -6; done",
    ]

    def test_false_alarms_from_real_use_go_through(self):
        for cmd in self.FALSE_ALARMS:
            with self.subTest(cmd=cmd[:50]):
                self.assertLetsThrough(cmd)

    def test_lets_single_command_through(self):
        self.assertLetsThrough("ls -la src/")

    def test_lets_read_only_monitor_loop_through(self):
        self.assertLetsThrough("while true; do curl -s localhost:8080/status | jq .phase; sleep 3; done")

    def test_stops_writing_loop(self):
        self.assertStops("for f in *.md; do sed -i 's/foo/bar/' $f; done")

    def test_stops_loop_that_redirects_into_files(self):
        self.assertStops('for f in src/*.py; do cat header.txt $f > "out/$f"; done')

    def test_stops_find_exec(self):
        self.assertStops("find . -name '*.jpg' -exec mogrify -resize 50% {} \\;")

    def test_stops_xargs(self):
        self.assertStops("ls *.log | xargs gzip")

    def test_stops_hidden_write_after_do(self):
        self.assertStops("for f in a b c; do rm $f.tmp; done")

    def test_stops_loops_that_write_from_inside_a_tool(self):
        for cmd in ("for f in *.txt; do sed -n 's/a/b/w out.txt' $f; done",
                    "for f in *.csv; do awk '{print > \"split.txt\"}' $f; done",
                    "for n in 1 2 3; do gh api repos/o/r/issues -f title=x; done",
                    "for u in a b; do curl -s --output $u.html https://example.com/$u; done"):
            with self.subTest(cmd=cmd[:40]):
                self.assertStops(cmd)

    def test_marked_choice_goes_through_and_is_logged(self):
        before = len(self.log_lines("model-choice"))
        self.assertLetsThrough("# MODEL: local qwen — mechanical rename, no judgement needed\n"
                               "for f in *.md; do sed -i 's/foo/bar/' $f; done")
        self.assertEqual(len(self.log_lines("model-choice")), before + 1)

    def test_premium_model_needs_a_real_reason(self):
        self.assertStops("# MODEL: Opus — faster\nfor f in *.md; do sed -i 's/a/b/' $f; done")
        self.assertLetsThrough("# MODEL: Opus — every file needs a judgement call on legal wording\n"
                               "for f in *.md; do sed -i 's/a/b/' $f; done")


class PremiumModelGate(GateCase):
    gate = "premium_model_gate.py"

    def test_stops_model_flag(self):
        self.assertStops("codex exec --model gpt-5-pro 'refactor the parser'")

    def test_stops_env_variable(self):
        self.assertStops("OPENAI_MODEL=o3-pro python3 run.py")

    def test_stops_lazy_reason(self):
        self.assertStops("# ESCALATE: important task\nllm -m o3-pro 'plan the migration'")

    def test_stops_short_reason(self):
        self.assertStops("# ESCALATE: stuck\nllm -m o3-pro 'plan'")

    def test_stops_model_in_json_body(self):
        self.assertStops("curl https://api.example.com/v1/chat -d '{\"model\": \"o3-pro\", \"messages\": []}'")

    def test_lets_grep_for_name_through(self):
        self.assertLetsThrough("grep -rn 'o3-pro' logs/")

    def test_lets_standard_model_through(self):
        self.assertLetsThrough("codex exec --model gpt-5 'refactor the parser'")

    def test_real_escalation_goes_through_and_is_logged(self):
        before = len(self.log_lines("escalation"))
        self.assertLetsThrough("# ESCALATE: three fixes tried, cannot explain why the race only happens under load\n"
                               "llm -m o3-pro 'why does this deadlock'")
        self.assertEqual(len(self.log_lines("escalation")), before + 1)


class FanoutGate(GateCase):
    gate = "fanout_gate.py"

    BIG = ("const TOPICS = [" + ", ".join(f"{{name: 'topic{i}', q: 'question number {i}'}}" for i in range(30)) + "]\n"
           "await parallel(TOPICS.map(t => () => agent(`research ${t.q}`)))\n"
           "await parallel(TOPICS.map(t => () => agent(`verify ${t.q}`)))")

    def test_asks_before_big_workflow(self):
        self.assertStops({"script": self.BIG}, tool="Workflow", how="ask")

    def test_question_contains_the_estimate(self):
        out = self.run_gate({"script": self.BIG}, tool="Workflow")
        self.assertIn("sub-agents", out["permissionDecisionReason"])
        self.assertIn("M tokens", out["permissionDecisionReason"])

    def test_asks_for_research_sweep(self):
        script = self.BIG.replace("research", "search the web for")
        out = self.run_gate({"script": script}, tool="Workflow")
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("research", out["permissionDecisionReason"])

    def test_lets_small_workflow_through(self):
        self.assertLetsThrough({"script": "await agent('fix the typo in README')"}, tool="Workflow")

    def test_lets_agent_call_through_with_note(self):
        out = self.run_gate({"prompt": "search the docs for the retry setting"}, tool="Agent")
        self.assertNotIn("permissionDecision", out)
        self.assertIn("FAN-OUT GATE", out["additionalContext"])

    def test_ignores_other_tools(self):
        self.assertLetsThrough({"command": "ls"}, tool="Bash")


class GatesNeverBreak(unittest.TestCase):
    def test_garbage_input_is_let_through(self):
        for gate in GATES.glob("*_gate.py"):
            with self.subTest(gate=gate.name):
                out = subprocess.run([sys.executable, str(gate)], input="not json",
                                     capture_output=True, text=True, timeout=10)
                self.assertEqual(out.returncode, 0)
                self.assertEqual(out.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
