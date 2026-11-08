# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
"""An implicit ./work-map.json may only write .md files inside its own folder; an explicit config is trusted."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "scripts")
PIPE = os.path.join(SCRIPTS, "pipeline.py")
DEC = os.path.join(SCRIPTS, "decisions.py")
DEC_LINE = '- 2026-11-01 · session: abcd1234 · applies: [house] · from: house · live-slug · Sam (10:00 "yes") → do it · Why: ok\n'


class ImplicitConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.work = os.path.join(self.root, "work")
        self.out = os.path.join(self.root, "outside")
        os.makedirs(os.path.join(self.work, "demo"))
        os.makedirs(self.out)
        self.outside = os.path.join(self.out, "outside.md")
        self.notmd = os.path.join(self.work, "notes.txt")
        for p, text in ((self.outside, "# outside\n---\n" + DEC_LINE), (self.notmd, "# notes\n---\n")):
            with open(p, "w") as fh:
                fh.write(text)
        with open(os.path.join(self.work, "demo", "PIPELINE.md"), "w") as fh:
            fh.write("# demo\n")
        os.symlink(self.outside, os.path.join(self.work, "link.md"))
        self.env = {k: v for k, v in os.environ.items() if k != "WORK_MAP_CONFIG"}

    def cfg(self, name, decisions, pipeline=None):
        path = os.path.join(self.work, name)
        with open(path, "w") as fh:
            json.dump({"decisions": decisions, "pipeline": pipeline or ["demo/PIPELINE.md"]}, fh)
        return path

    def run_script(self, script, *argv):
        return subprocess.run([sys.executable, script, *argv], cwd=self.work, env=self.env,
                              capture_output=True, text=True)

    def dec_add(self, *extra):
        return self.run_script(DEC, "add", "--slug", "new-call", "--applies", "one", "--from", "p", "--who", "Sam",
                               "--time", "09:12", "--words", "y", "--call", "c", "--why", "w",
                               "--date", "2026-11-08", "--session", "12345678", *extra)

    def pipe_add(self, *extra):
        return self.run_script(PIPE, "add", "--project", "demo", "--item", "N", "--id", "n", "--status", "planned",
                               "--why", "w", *extra)

    def bad_targets(self):
        return {"absolute": self.outside, "dotdot": "../outside/outside.md", "symlink": "link.md", "not-md": "notes.txt"}

    def outside_bytes(self):
        out = []
        for path in (self.outside, self.notmd):
            with open(path, "rb") as fh:
                out.append(fh.read())
        return tuple(out)

    def test_implicit_config_outside_or_non_md_is_refused_for_decisions_add(self):
        before = self.outside_bytes()
        for name, target in self.bad_targets().items():
            self.cfg("work-map.json", [target])
            r = self.dec_add()
            self.assertEqual(r.returncode, 2, (name, r.stderr))
            self.assertIn("--config", r.stderr)
            self.assertEqual(self.outside_bytes(), before, name)

    def test_implicit_config_outside_or_non_md_is_refused_for_pipeline_file(self):
        before = self.outside_bytes()
        folder = {"absolute": "outside", "dotdot": "outside", "symlink": "work", "not-md": "work"}
        for name, target in self.bad_targets().items():
            self.cfg("work-map.json", ["DECISIONS.md"], [target])
            r = self.run_script(PIPE, "add", "--project", folder[name], "--item", "N", "--id", "n",
                                "--status", "planned", "--why", "w")
            self.assertEqual(r.returncode, 2, (name, r.stderr))
            self.assertIn("--config", r.stderr)
            self.assertEqual(self.outside_bytes(), before, name)

    def test_implicit_config_decision_files_outside_are_refused_by_pipeline_slug_check(self):
        before = self.outside_bytes()
        for name, target in self.bad_targets().items():
            self.cfg("work-map.json", [target])
            r = self.pipe_add("--decisions", "live-slug")
            self.assertEqual(r.returncode, 2, (name, r.stderr))
            self.assertIn("--config", r.stderr)
            self.assertEqual(self.outside_bytes(), before, name)
            with open(os.path.join(self.work, "demo", "PIPELINE.md")) as fh:
                self.assertEqual(fh.read(), "# demo\n")

    def test_pipeline_update_through_implicit_config_outside_is_refused(self):
        before = self.outside_bytes()
        with open(self.outside, "a") as fh:
            fh.write("- **X** · id: x · status: planned · why: w · spec: none · decisions: none\n")
        before = self.outside_bytes()
        self.cfg("work-map.json", ["DECISIONS.md"], ["../outside/outside.md"])
        r = self.run_script(PIPE, "update", "--project", "outside", "--id", "x", "--status", "parked")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(self.outside_bytes(), before)

    def test_same_config_given_explicitly_is_trusted(self):
        cfg = self.cfg("explicit.json", [self.outside])
        r = self.dec_add("--config", cfg)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.outside) as fh:
            self.assertIn("new-call", fh.read())
        # and through the environment variable
        self.env["WORK_MAP_CONFIG"] = cfg
        r = self.run_script(DEC, "add", "--slug", "env-call", "--applies", "one", "--from", "p", "--who", "Sam",
                            "--time", "09:12", "--words", "y", "--call", "c", "--why", "w",
                            "--date", "2026-11-08", "--session", "12345678")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_explicit_file_flag_stays_trusted(self):
        self.cfg("work-map.json", ["../outside/outside.md"])
        r = self.dec_add("--file", self.outside)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_normal_implicit_config_inside_the_folder_works(self):
        with open(os.path.join(self.work, "DECISIONS.md"), "w") as fh:
            fh.write("# D\n---\n" + DEC_LINE)
        self.cfg("work-map.json", ["DECISIONS.md"])
        r = self.dec_add()
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.pipe_add("--decisions", "live-slug")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.work, "demo", "PIPELINE.md")) as fh:
            self.assertIn("id: n ", fh.read())

    def test_no_config_default_decisions_file_symlinked_outside_is_refused(self):
        before = self.outside_bytes()
        os.symlink(self.outside, os.path.join(self.work, "DECISIONS.md"))
        r = self.dec_add()
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(self.outside_bytes(), before)


if __name__ == "__main__":
    unittest.main()
