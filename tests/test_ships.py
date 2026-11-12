# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "ships.py"
sys.path.insert(0, str(SCRIPT.parent))
import work_map


def run(*args, cwd=None, env=None):
    e = {k: v for k, v in os.environ.items() if k not in ("WORK_MAP_CONFIG", "WORK_MAP_SESSION")}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), "add", *args], capture_output=True, text=True, cwd=cwd, env=e)


class Ships(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name).resolve()
        self.f = self.root / "ships.md"

    base = ["--project", "demo", "--version", "v1.0.0", "--sha", "abc1234", "--date", "2026-11-12"]

    def test_exact_line_and_parse_back(self):
        r = run(*self.base, "--decisions", "a,b", "--tasks", "t-1", "--session", "a1b2c3d4", "--file", str(self.f))
        self.assertEqual(r.returncode, 0, r.stderr)
        line = "2026-11-12 · session: a1b2c3d4 · project: demo · shipped v1.0.0 abc1234 · decisions: a, b · tasks closed: t-1"
        self.assertEqual(self.f.read_text().splitlines()[-1], line)
        rec = work_map.parse_ship(line, ("f", 1))
        self.assertEqual((rec["project"], rec["version"], rec["sha"]), ("demo", "v1.0.0", "abc1234"))

    def test_defaults_and_heading(self):
        r = run(*self.base, "--file", str(self.f))
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.f.read_text()
        self.assertTrue(text.startswith("# demo DEVLOG\n"))
        self.assertIn("session: unknown", text)
        self.assertTrue(text.endswith("decisions: none · tasks closed: none\n"))

    def test_env_session_and_missing_newline(self):
        self.f.write_text("notes")
        r = run(*self.base, "--file", str(self.f), env={"WORK_MAP_SESSION": "deadbeef"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.f.read_text().startswith("notes\n2026-11-12 · session: deadbeef"))

    def test_dry_run_writes_nothing(self):
        r = run(*self.base, "--file", str(self.f), "--dry-run")
        self.assertEqual(r.returncode, 0)
        self.assertIn("shipped v1.0.0 abc1234", r.stdout)
        self.assertFalse(self.f.exists())

    def test_bad_input_refused_file_unchanged(self):
        self.f.write_text("keep\n")
        cases = (["--sha", "xyz"], ["--version", "v 1"], ["--project", "a\nb"], ["--tasks", "a · b"], ["--decisions", "x[y]"])
        for bad in cases:
            args = list(self.base)
            if bad[0] in args:
                args[args.index(bad[0]) + 1] = bad[1]
            else:
                args += bad
            r = run(*args, "--file", str(self.f))
            self.assertEqual(r.returncode, 2, bad)
        self.assertEqual(self.f.read_text(), "keep\n")

    def test_duplicate_version_refused(self):
        self.assertEqual(run(*self.base, "--file", str(self.f)).returncode, 0)
        before = self.f.read_text()
        r = run(*self.base, "--file", str(self.f))
        self.assertEqual(r.returncode, 2)
        self.assertIn("already logged", r.stderr)
        self.assertEqual(self.f.read_text(), before)

    def config(self, ships):
        (self.root / "work-map.json").write_text(json.dumps({"ships": ships}))
        return str(self.root / "work-map.json")

    def test_config_picks_project_folder(self):
        for d in ("demo", "other"):
            (self.root / d).mkdir()
            (self.root / d / "DEVLOG.md").write_text("# x\n")
        cfg = self.config(["*/DEVLOG.md"])
        r = run(*self.base, "--config", cfg)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("shipped", (self.root / "demo" / "DEVLOG.md").read_text())
        self.assertNotIn("shipped", (self.root / "other" / "DEVLOG.md").read_text())

    def test_config_ambiguous_refused_and_only_one_used(self):
        for d in ("a", "b"):
            (self.root / d).mkdir()
            (self.root / d / "DEVLOG.md").write_text("# x\n")
        self.assertEqual(run(*self.base, "--config", self.config(["*/DEVLOG.md"])).returncode, 2)
        r = run(*self.base, "--config", self.config(["a/DEVLOG.md"]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_implicit_config_cannot_write_outside(self):
        out = self.root / "out"
        out.mkdir()
        inner = self.root / "in"
        inner.mkdir()
        (inner / "work-map.json").write_text(json.dumps({"ships": [str(out / "s.md")]}))
        r = run(*self.base, cwd=inner)
        self.assertEqual(r.returncode, 2)
        self.assertFalse((out / "s.md").exists())

    def test_no_config_defaults_to_devlog(self):
        r = run(*self.base, cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "DEVLOG.md").exists())

    def test_configured_literal_log_created_on_first_use(self):
        cfg = self.root / "cfg.json"
        cfg.write_text(json.dumps({"ships": ["notes/ships.md"]}))
        r = run(*self.base, "--config", str(cfg))
        self.assertEqual(r.returncode, 0, r.stderr)
        made = self.root / "notes" / "ships.md"
        self.assertTrue(made.read_text().startswith("# demo DEVLOG\n"))


if __name__ == "__main__":
    unittest.main()
