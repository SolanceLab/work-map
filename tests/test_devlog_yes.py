# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ANCHOR = "<!-- work-map: newest first -->"
SCRIPT = Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "ships.py"
sys.path.insert(0, str(SCRIPT.parent))
import work_map
import test_why

YES = '- 2026-11-14 · session: a1b2c3d4 · project: demo · publish-yes demo v1.0.0 · yes: Sam (10:14 "yes publish it")'


def run(*args, cwd=None):
    e = {k: v for k, v in os.environ.items() if k not in ("WORK_MAP_CONFIG", "WORK_MAP_SESSION")}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd, env=e)


class YesWriterTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name).resolve()
        self.f = self.root / "DEVLOG.md"
        self.start = "# demo DEVLOG\n\n%s\n- 2026-11-01 · session: x · project: demo · older · proof: ship v0\n" % ANCHOR
        self.f.write_text(self.start)
        self.yes = ["yes", "--project", "demo", "--tag", "v2.0.0", "--who", "Sam", "--time", "10:14",
                    "--words", "yes publish it", "--date", "2026-11-15", "--session", "a1b2c3d4"]

    def go(self, base, *extra):
        return run(*base, *extra, "--file", str(self.f))

    def under_anchor(self):
        lines = self.f.read_text().splitlines()
        return lines[lines.index(ANCHOR) + 1]

    def refused(self, r):
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.f.read_text(), self.start)
        err = r.stderr.strip().splitlines()
        self.assertTrue(err and "Traceback" not in r.stderr, r.stderr)
        self.assertEqual(len(err), 1, r.stderr)

    def swap(self, flag, value):
        base = list(self.yes)
        base[base.index(flag) + 1] = value
        return base

    def without(self, flag):
        base = list(self.yes)
        i = base.index(flag)
        del base[i:i + 2]
        return base

    def test_exact_line(self):
        r = self.go(self.yes)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.under_anchor(), '- 2026-11-15 · session: a1b2c3d4 · project: demo · publish-yes demo v2.0.0 · yes: Sam (10:14 "yes publish it")')
        self.assertIn("older", self.f.read_text())

    def test_exact_line_with_note(self):
        r = self.go(self.yes, "--note", "after the review")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.under_anchor(), '- 2026-11-15 · session: a1b2c3d4 · project: demo · publish-yes demo v2.0.0 · yes: Sam (10:14 "yes publish it") · after the review')

    def test_repo_override(self):
        r = self.go(self.yes, "--repo", "demo-plugin")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("· project: demo · publish-yes demo-plugin v2.0.0 ·", self.under_anchor())

    def test_tag_main(self):
        self.assertEqual(self.go(self.swap("--tag", "main")).returncode, 0)
        self.assertIn("publish-yes demo main ·", self.under_anchor())

    def test_refusals_leave_file_untouched(self):
        cases = [self.without("--who"), self.without("--time"), self.without("--words"), self.without("--tag"),
                 self.swap("--time", "25:00"), self.swap("--time", "9:00"),
                 self.swap("--tag", "v2 .0"), self.swap("--tag", ""),
                 self.yes + ["--repo", "a b"],
                 self.swap("--words", 'say "yes"'), self.swap("--words", "a · b"), self.swap("--who", "A · B"),
                 self.yes + ["--note", "a · b"], self.yes + ["--note", " "],
                 self.swap("--date", "2026-02-31")]
        for base in cases:
            with self.subTest(args=base):
                r = self.go(base)
                self.assertEqual(r.returncode, 2)
                self.refused(r)

    def test_duplicate_repo_tag_refused(self):
        self.assertEqual(self.go(self.yes).returncode, 0)
        self.start = self.f.read_text()
        r = self.go(self.swap("--words", "again"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("already has a publish yes", r.stderr)
        self.refused(r)
        self.assertEqual(self.go(self.swap("--tag", "v2.0.1")).returncode, 0)
        self.assertEqual(self.go(self.yes, "--repo", "other").returncode, 0)

    def test_duplicate_refused_in_dry_run(self):
        self.assertEqual(self.go(self.yes).returncode, 0)
        self.start = self.f.read_text()
        r = self.go(self.yes, "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.refused(r)

    def test_dry_run_writes_nothing(self):
        r = self.go(self.yes, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("publish-yes demo v2.0.0", r.stdout)
        self.assertEqual(self.f.read_text(), self.start)
        n = self.root / "n.md"
        r = run(*self.yes, "--dry-run", "--file", str(n))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(n.exists())

    def test_no_anchor_refused(self):
        self.start = "# demo DEVLOG\n- line\n"
        self.f.write_text(self.start)
        r = self.go(self.yes)
        self.assertEqual(r.returncode, 2)
        self.refused(r)
        self.assertIn("DEVLOG.md", r.stderr)

    def test_reader_skips_yes_line(self):
        self.go(self.yes, "--note", "shipped later")
        line = self.under_anchor()
        self.assertIsNone(work_map.parse_ship(line, ("DEVLOG.md", 1)))
        ship = "- 2026-11-15 · session: s · project: demo · shipped v1 abc1234 · decisions: publish-yes demo v1 · tasks closed: none"
        self.assertIsNotNone(work_map.parse_ship(ship, ("DEVLOG.md", 1)))

    def test_is_yes_line(self):
        self.go(self.yes)
        self.assertTrue(work_map.is_yes_line(self.under_anchor()))
        self.assertTrue(work_map.is_yes_line(YES))
        self.assertFalse(work_map.is_yes_line("- 2026-11-15 · session: s · project: demo · shipped v1 abc1234 · decisions: publish-yes demo v1 · tasks closed: none"))
        self.assertFalse(work_map.is_yes_line("- 2026-11-14 · decisions: publish-yes-demo-v1"))
        self.assertFalse(work_map.is_yes_line("- 2026-11-15 · session: x · project: demo · publish-yes migration completed · proof: commit abc1234"))
        self.assertFalse(work_map.is_yes_line("- publish-yes demo v1 · yes: Sam (10:00 \"y\")"))


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class YesNotInWhyTests(unittest.TestCase):
    setUp = test_why.WhyTests.setUp
    g = test_why.WhyTests.g
    commit = test_why.WhyTests.commit
    run_why = test_why.WhyTests.run_why
    why = test_why.WhyTests.why
    with_devlog = test_why.WhyTests.with_devlog
    with_dated_item = test_why.WhyTests.with_dated_item

    def test_yes_line_with_sha_not_shown(self):
        sha = self.commit("y1.txt", "n\n", "Yes sha")
        self.with_devlog(ANCHOR + "\n" + YES + " · after %s\n" % sha[:7] + "- fixed in %s\n" % sha[:7])
        _, out, _ = self.why(sha)
        self.assertIn("devlog: DEVLOG.md:L3 · - fixed in", out)
        self.assertNotIn("publish-yes", out)
        data = json.loads(self.why(sha, "--json")[1])
        self.assertEqual(len(data[0]["devlog"]), 1)
        self.assertEqual(data[0]["devlog"][0]["line"], 3)
        self.assertNotIn("publish-yes", json.dumps(data))

    def test_only_yes_line_mention_counts_bare(self):
        sha = self.commit("y2.txt", "n\n", "Yes only")
        self.with_devlog(ANCHOR + "\n" + YES + " · after %s\n" % sha[:7])
        _, out, _ = self.why(sha)
        self.assertNotIn("publish-yes", out)
        self.assertEqual(out.strip().splitlines()[-1], "1 commits without a Work line or DEVLOG mention")
        self.assertNotIn("publish-yes", self.why(sha, "--json")[1])

    def test_yes_line_by_work_item_date_not_shown(self):
        sha = self.with_dated_item(ANCHOR + "\n" + YES + "\n- 2026-11-14 chose plain words\n")
        _, out, _ = self.why(sha)
        self.assertIn("DEVLOG.md:L3 · - 2026-11-14 chose plain words", out)
        self.assertNotIn("publish-yes", out)
        hits = json.loads(self.why(sha, "--json")[1])[0]["devlog"]
        self.assertNotIn("publish-yes", json.dumps(hits))
        self.assertEqual(hits[0]["line"], 3)

    def test_yes_line_under_day_heading_not_shown(self):
        sha = self.with_dated_item("## 14 November 2026\n" + YES + "\n- kept it plain\n")
        _, out, _ = self.why(sha)
        self.assertNotIn("publish-yes", out)
        self.assertIn("kept it plain", out)
        self.assertNotIn("publish-yes", self.why(sha, "--json")[1])

    def test_ship_line_with_publish_yes_decision_still_shown(self):
        sha = self.commit("y3.txt", "n\n", "Shipped")
        self.with_devlog("- 2026-11-14 · session: s · project: demo · shipped v1 %s · decisions: publish-yes demo v1 · tasks closed: none\n" % sha[:7])
        _, out, _ = self.why(sha)
        self.assertIn("devlog: DEVLOG.md:L1", out)

    def test_checkpoint_naming_publish_yes_stays_visible(self):
        sha = self.commit("y4.txt", "n\n", "Checkpointed")
        self.with_devlog("- 2026-11-15 · session: x · project: demo · publish-yes migration completed · proof: commit %s\n" % sha[:7])
        _, out, _ = self.why(sha)
        self.assertIn("devlog: DEVLOG.md:L1", out)


if __name__ == "__main__":
    unittest.main()
