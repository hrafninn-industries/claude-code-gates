"""spec.py verify must fail three bad specs and pass one good one."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def verify(name):
    return subprocess.run([sys.executable, str(ROOT / "spec" / "spec.py"), "verify", str(FIXTURES / name)],
                          capture_output=True, text=True, timeout=10)


class SpecVerify(unittest.TestCase):
    def test_missing_evidence_fails(self):
        out = verify("spec_missing_evidence.md")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no evidence", out.stdout)

    def test_too_short_evidence_fails(self):
        out = verify("spec_short_evidence.md")
        self.assertEqual(out.returncode, 1)
        self.assertIn("too short", out.stdout)

    def test_evidence_that_repeats_the_method_fails(self):
        out = verify("spec_evidence_repeats_method.md")
        self.assertEqual(out.returncode, 1)
        self.assertIn("only repeats", out.stdout)

    def test_new_then_verify_by_lowercase_name(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, SPEC_DIR=d)
            spec = [sys.executable, str(ROOT / "spec" / "spec.py")]
            made = subprocess.run(spec + ["new", "contact form"], capture_output=True, text=True, env=env)
            self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
            out = subprocess.run(spec + ["verify", "contact_form"], capture_output=True, text=True, env=env)
            self.assertEqual(out.returncode, 1)          # found, and failed: the template has no evidence
            self.assertIn("no evidence", out.stdout)

    def test_good_spec_passes(self):
        out = verify("spec_good.md")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("PASSED", out.stdout)


if __name__ == "__main__":
    unittest.main()
