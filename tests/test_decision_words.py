# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
"""decisions.py query --decision-words / config decision_words widen --notes only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

PATTERN = r"\(\w+, \d{1,2} \w{3}\)"
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "scripts", "decisions.py")


class DecisionWords(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.notes = os.path.join(self.tmp.name, "notes.md")
        with open(self.notes, "w") as fh:
            fh.write("(Sam, 3 Mar) we keep CSV export\nwe decided to keep csv backups\n")
        self.reg = os.path.join(self.tmp.name, "DECISIONS.md")
        with open(self.reg, "w") as fh:
            fh.write("# D\n---\n- 2026-01-01 · csv-reg · csv in register\n")

    def run_q(self, *args, cfg=None):
        env = dict(os.environ)
        env.pop("WORK_MAP_CONFIG", None)
        argv = [sys.executable, SCRIPT, "query", "csv", "--file", self.reg, "--notes", self.notes] + list(args)
        return subprocess.run(argv, capture_output=True, text=True, cwd=self.tmp.name, env=env)

    def test_not_found_without_socket(self):
        out = self.run_q().stdout
        self.assertNotIn("Sam", out)
        self.assertIn("decided", out)

    def test_found_with_flag(self):
        self.assertIn("Sam", self.run_q("--decision-words", PATTERN).stdout)

    def test_found_with_config(self):
        cfg = os.path.join(self.tmp.name, "c.json")
        with open(cfg, "w") as fh:
            json.dump({"decisions": ["DECISIONS.md"], "decision_words": [PATTERN]}, fh)
        self.assertIn("Sam", self.run_q("--config", cfg).stdout)

    def test_decision_files_unaffected(self):
        out = self.run_q("--decision-words", "zzzz").stdout
        self.assertIn("csv in register", out)

    def test_bad_regex_exits_2(self):
        r = self.run_q("--decision-words", "(unclosed")
        self.assertEqual(r.returncode, 2)
        self.assertIn("(unclosed", r.stderr)


if __name__ == "__main__":
    unittest.main()
