# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import os, subprocess, sys, tempfile, unittest
from pathlib import Path

ANCHOR = "<!-- work-map: newest first -->"
SCRIPT = Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "ships.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


def run(*args, cwd=None):
    e = {k: v for k, v in os.environ.items() if k not in ("WORK_MAP_CONFIG", "WORK_MAP_SESSION")}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd, env=e)


class DevlogWriter(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name).resolve()
        self.f = self.root / "DEVLOG.md"
        self.start = "# demo DEVLOG\n\n%s\n- 2026-11-01 · session: x · project: demo · older · proof: ship v0\n" % ANCHOR
        self.f.write_text(self.start)

    cp = ["checkpoint", "--project", "demo", "--text", "it works", "--date", "2026-11-15", "--session", "a1b2c3d4"]
    dv = ["deviation", "--project", "demo", "--step", "step 7", "--who", "Sam", "--time", "10:14",
          "--words", "skip it", "--what", "skipped step 7", "--why", "no need", "--date", "2026-11-15", "--session", "a1b2c3d4"]

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
        return err

    def test_commit_proof(self):
        r = self.go(self.cp, "--commit", SHA.upper())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.under_anchor(), "- 2026-11-15 · session: a1b2c3d4 · project: demo · it works · proof: commit 0123456")

    def test_two_commits(self):
        self.assertEqual(self.go(self.cp, "--commit", "abcdef1", "--commit", SHA).returncode, 0)
        self.assertTrue(self.under_anchor().endswith("proof: commit abcdef1, commit 0123456"))

    def test_ship_proof(self):
        self.assertEqual(self.go(self.cp, "--ship", "v1.2.0").returncode, 0)
        self.assertTrue(self.under_anchor().endswith("it works · proof: ship v1.2.0"))

    def test_spoken_proof(self):
        r = self.go(self.cp, "--who", "Sam", "--time", "14:03", "--words", "yes do it")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.under_anchor().endswith('it works · proof: Sam (14:03 "yes do it")'))

    def test_deviation_line(self):
        r = self.go(self.dv)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.under_anchor(), '- 2026-11-15 · session: a1b2c3d4 · project: demo · deviation: step 7 · Sam (10:14 "skip it") → skipped step 7 · Why: no need')

    def test_newest_first_and_old_line_kept(self):
        self.go(self.cp, "--ship", "v1")
        self.go(self.cp, "--ship", "v2")
        lines = self.f.read_text().splitlines()
        i = lines.index(ANCHOR)
        self.assertTrue(lines[i + 1].endswith("ship v2"))
        self.assertTrue(lines[i + 2].endswith("ship v1"))
        self.assertIn("older", lines[i + 3])
        self.assertEqual(lines[:i + 1], self.start.splitlines()[:3])

    def test_refusals_leave_file_untouched(self):
        cases = [
            self.cp,                                                        # no proof
            self.cp + ["--commit", "xyz1234"],                              # bad sha
            self.cp + ["--commit", "abc12"],                                # short sha
            self.cp + ["--who", "Sam", "--time", "25:00", "--words", "w"],  # bad time
            self.cp + ["--who", "Sam", "--time", "9:00", "--words", "w"],
            self.cp + ["--who", "Sam", "--time", "10:00"],                 # missing words
            self.cp + ["--commit", SHA, "--ship", "v1"],                    # two proofs
            self.cp + ["--commit", SHA, "--date", "2026-02-31"],            # bad date
            ["checkpoint", "--project", "demo", "--text", " ", "--commit", SHA],
            ["checkpoint", "--project", "demo", "--text", "a · b", "--commit", SHA],
            ["checkpoint", "--project", "demo", "--text", "a\nb", "--commit", SHA],
        ]
        for c in cases:
            with self.subTest(c=c, oneline=True):
                err = self.refused(self.go(c))
                self.assertEqual(len(err), 1, err)

    def test_deviation_refusals(self):
        def without(flag):
            a, i = list(self.dv), self.dv.index(flag)
            del a[i:i + 2]
            return a
        def swap(flag, val):
            a = list(self.dv)
            a[a.index(flag) + 1] = val
            return a
        cases = [without(f) for f in ("--step", "--who", "--time", "--words", "--what", "--why")]
        cases += [swap("--why", ""), swap("--what", "a · b"), swap("--step", "a\nb"), swap("--time", "24:00"),
                  swap("--words", "x\ny"), swap("--who", "A · B"), swap("--who", 'Sam (x)'), swap("--who", 'A"B'), swap("--who", "A → B")]
        for c in cases:
            with self.subTest(c=c):
                err = self.refused(self.go(c))
                self.assertEqual(len(err), 1, err)

    def test_two_anchors_refused(self):
        self.start = self.start + ANCHOR + "\n"
        self.f.write_text(self.start)
        self.refused(self.go(self.cp, "--ship", "v1"))
        self.refused(self.go(self.dv))

    def test_no_anchor_refused_names_file(self):
        self.start = "# demo DEVLOG\n- line\n"
        self.f.write_text(self.start)
        err = self.refused(self.go(self.cp, "--ship", "v1"))
        self.assertEqual(len(err), 1)
        self.assertIn(str(self.f), err[0])

    def test_missing_file_without_new_path_refused_and_new_file_created(self):
        new = self.root / "sub" / "NEW.md"
        r = run(*self.cp, "--ship", "v1", "--file", str(new))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(new.read_text().splitlines()[:3], ["# demo DEVLOG", "", ANCHOR])
        self.assertTrue(new.read_text().splitlines()[3].endswith("ship v1"))
        cfg = self.root / "work-map.json"
        cfg.write_text('{"ships": ["gone.md"]}')
        r = run(*self.cp, "--ship", "v1", "--config", str(cfg))
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.root / "gone.md").exists())

    def test_dry_run_writes_nothing(self):
        r = self.go(self.cp, "--ship", "v1", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ship v1", r.stdout)
        self.assertEqual(self.f.read_text(), self.start)
        new = self.root / "n.md"
        run(*self.cp, "--ship", "v1", "--dry-run", "--file", str(new))
        self.assertFalse(new.exists())

    def test_config_ships_target(self):
        cfg = self.root / "work-map.json"
        cfg.write_text('{"ships": ["DEVLOG.md"]}')
        r = run(*self.cp, "--ship", "v1", "--config", str(cfg))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.under_anchor().endswith("ship v1"))

    def test_add_unchanged(self):
        r = run("add", "--project", "demo", "--version", "v9", "--sha", "abc1234", "--date", "2026-11-15", "--session", "s", "--file", str(self.f))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("shipped v9 abc1234", self.under_anchor())


if __name__ == "__main__":
    unittest.main()
