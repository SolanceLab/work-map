# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# #!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
"""decisions.py query: all-terms first, partial-match fallback, miss message, header skip."""
import os
import subprocess
import sys
import tempfile
import unittest

HEADER = "No line matches every term; closest matches:"
MISS = "No decision on record for: %s"
REG = [
    "# Decisions",
    "Header mentions zebraheader only.",
    "---",
    "- 2026-10-01 · alpha-beta · alpha beta gamma delta",
    "- 2026-10-02 · alpha-only · alpha beta",
    "- 2026-10-03 · squash-only-where-signature-diffable · squash and signature",
    "- 2026-10-04 · alpha-solo · alpha",
]
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "scripts", "decisions.py")


def ln(fragment):
    return next(i for i, l in enumerate(REG, 1) if fragment in l)


class Decisions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ws = os.path.join(tmp.name, "ws")
        self.mem = os.path.join(tmp.name, "mem")
        os.makedirs(self.ws)
        os.makedirs(self.mem)
        self.write(os.path.join(self.ws, "DECISIONS.md"), "\n".join(REG) + "\n")
        self.write(os.path.join(self.mem, "note.md"),
                   "Sam decided alpha gamma in memory.\nalpha gamma without the marker word.\n")

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def run_q(self, *terms):
        files = [os.path.join(self.ws, n) for n in ("DECISIONS.md", "DECISIONS-archive.md")
                 if os.path.exists(os.path.join(self.ws, n))]
        extra = [x for f in files for x in ("--file", f)] + ["--notes", self.mem]
        r = subprocess.run([sys.executable, SCRIPT, "query", *terms, *extra], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        return r.stdout

    def test_archive_found_when_present(self):
        self.write(os.path.join(self.ws, "DECISIONS-archive.md"), "# A\n\n---\n- 2026-01-02 · zebra-only-in-archive · Sam chose zebra\n")
        out = self.run_q("zebra")
        self.assertIn("DECISIONS-archive.md:", out)
        self.assertIn("zebra-only-in-archive", out)

    def test_archive_absent_is_fine(self):
        out = self.run_q("zebra")
        self.assertNotIn("DECISIONS-archive.md", out)

    def test_all_terms_hit_unchanged(self):
        out = self.run_q("alpha", "beta", "gamma", "delta")
        self.assertIn("DECISIONS.md:%d" % ln("alpha-beta"), out)
        self.assertIn("alpha beta gamma delta", out)
        self.assertNotIn("closest matches", out)
        self.assertNotIn("terms]", out)
        out = self.run_q("alpha", "gamma")
        self.assertIn("DECISIONS.md:%d" % ln("alpha-beta"), out)
        self.assertIn("note.md:1", out)
        self.assertNotIn("note.md:2", out)

    def test_partial_fallback_ranking_and_threshold(self):
        out = self.run_q("restructure", "archive", "squash", "signature").splitlines()
        self.assertEqual(out[0], HEADER)
        self.assertTrue(out[1].startswith("[2/4 terms] DECISIONS.md:%d" % ln("squash-only")), out[1])
        out = self.run_q("alpha", "beta", "gamma", "zzz").splitlines()
        self.assertEqual(out[0], HEADER)
        self.assertTrue(out[1].startswith("[3/4 terms] DECISIONS.md:%d" % ln("alpha-beta")))
        self.assertTrue(out[2].startswith("[2/4 terms] DECISIONS.md:%d" % ln("alpha-only")))
        self.assertIn("note.md:1", out[3])
        self.assertEqual(len(out), 4)
        text = "\n".join(out)
        self.assertNotIn("alpha-solo", text)
        self.assertNotIn("note.md:2", text)

    def test_recency_tiebreak(self):
        self.write(os.path.join(self.ws, "DECISIONS.md"), "# D\n---\n- old · foo bar\n- new · foo bar\n")
        out = self.run_q("foo", "bar", "baz")
        self.assertLess(out.index("new"), out.index("old"))

    def test_single_term_miss_prints_old_message(self):
        out = self.run_q("nonexistentterm")
        self.assertEqual(out.strip(), MISS % "nonexistentterm")
        self.assertNotIn("closest", out)
        self.assertEqual(self.run_q("qqq", "www").strip(), MISS % "qqq www")

    def test_header_skip(self):
        self.assertEqual(self.run_q("zebraheader").strip(), MISS % "zebraheader")
        out = self.run_q("zebraheader", "alpha")
        self.assertNotIn("DECISIONS.md:2 ", out)
        self.assertNotIn("zebraheader only", out)


if __name__ == "__main__":
    unittest.main()
