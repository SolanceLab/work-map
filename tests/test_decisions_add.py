# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# #!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

SCRIPT = Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "decisions.py"
spec = importlib.util.spec_from_file_location("decisions", SCRIPT)
decisions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decisions)


class AddDecisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file = self.root / "DECISIONS.md"
        self.file.write_text("# Register\n---\n", encoding="utf-8")
        self.mem = self.root / "mem"
        self.mem.mkdir()

    def run_add(self, *extra):
        args = ["--slug", "my-call", "--applies", "one,two", "--from", "project",
                "--who", "Sam", "--time", "09:12", "--words", "yes",
                "--call", "do it", "--why", "Sam chose", "--date", "2026-11-08",
                "--session", "12345678", "--file", str(self.file)]
        return subprocess.run([sys.executable, str(SCRIPT), "add", *args, *extra],
                              capture_output=True, text=True)

    def test_format_and_parse(self):
        result = self.run_add()
        self.assertEqual(result.returncode, 0, result.stderr)
        line = self.file.read_text().splitlines()[-1]
        self.assertEqual(line, '- 2026-11-08 · session: 12345678 · applies: [one, two] · from: project · my-call · Sam (09:12 "yes") → do it · Why: Sam chose')
        self.assertEqual(decisions.parse_add_line(line)["slug"], "my-call")
        self.assertEqual(decisions.parse_add_line(line)["applies"], "one, two")

    def test_duplicates_old_and_new(self):
        for existing in ("- 2026-01-01 · my-call · old\n",
                         '- 2026-01-01 · session: 12345678 · applies: [house] · from: p · my-call · Sam (09:12 "x") → y · Why: z\n'):
            self.file.write_text(existing)
            result = self.run_add()
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.file.read_text(), existing)

    def test_bad_fields(self):
        for option, value in [("--slug", "BAD"), ("--time", "25:00"), ("--date", "2026-02-30"),
                              ("--words", "two\nlines"), ("--why", "bad · delimiter")]:
            before = self.file.read_bytes()
            result = self.run_add(option, value)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(self.file.read_bytes(), before)

    def test_kind_written_after_from(self):
        result = self.run_add("--kind", "standing")
        self.assertEqual(result.returncode, 0, result.stderr)
        line = self.file.read_text().splitlines()[-1]
        self.assertEqual(line, '- 2026-11-08 · session: 12345678 · applies: [one, two] · from: project · kind: standing · my-call · Sam (09:12 "yes") → do it · Why: Sam chose')
        self.assertEqual(decisions.parse_add_line(line)["kind"], "standing")

    def test_kind_rejects_other_values(self):
        before = self.file.read_bytes()
        self.assertEqual(self.run_add("--kind", "small").returncode, 2)
        self.assertEqual(self.file.read_bytes(), before)

    def test_parse_both_shapes(self):
        old = '- 2026-01-01 · session: 12345678 · applies: [house] · from: p · a-call · Sam (09:12 "x") → y · Why: z'
        new = '- 2026-01-01 · session: 12345678 · applies: [house] · from: p · kind: one-time · a-call · Sam (09:12 "x") → y · Why: z'
        self.assertIsNone(decisions.parse_add_line(old)["kind"])
        self.assertEqual(decisions.parse_add_line(new)["kind"], "one-time")
        self.assertEqual(decisions.parse_add_line(old)["slug"], decisions.parse_add_line(new)["slug"])

    def test_house_and_dry_run(self):
        before = self.file.read_bytes()
        result = self.run_add("--applies", "house", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("applies: [house]", result.stdout)
        self.assertEqual(self.file.read_bytes(), before)

    def test_missing_newline_and_query(self):
        self.file.write_text("# Register\n---\nold")
        self.assertEqual(self.run_add().returncode, 0)
        self.assertIn("old\n- 2026", self.file.read_text())
        result = subprocess.run([sys.executable, str(SCRIPT), "query", "my-call", "--file", str(self.file)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("my-call", result.stdout)

    def test_session_from_env_and_missing_session(self):
        args = ["--slug", "env-call", "--applies", "one", "--from", "project", "--who", "Sam", "--time", "09:12",
                "--words", "yes", "--call", "do it", "--why", "because", "--date", "2026-11-08", "--file", str(self.file)]
        env = {k: v for k, v in os.environ.items() if k != "WORK_MAP_SESSION"}
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "add", *args], capture_output=True, text=True, env=env).returncode, 2)
        env["WORK_MAP_SESSION"] = "abcd1234"
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "add", *args], capture_output=True, text=True, env=env).returncode, 0)
        self.assertIn("session: abcd1234", self.file.read_text())

    def test_config_decisions_file_is_the_default_target(self):
        import json
        cfg = self.root / "work-map.json"
        cfg.write_text(json.dumps({"decisions": ["DECISIONS.md"]}))
        args = ["--slug", "cfg-call", "--applies", "one", "--from", "project", "--who", "Sam", "--time", "09:12",
                "--words", "yes", "--call", "do it", "--why", "because", "--date", "2026-11-08",
                "--session", "12345678", "--config", str(cfg)]
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "add", *args], capture_output=True, text=True).returncode, 0)
        self.assertIn("cfg-call", self.file.read_text())

    def run_with(self, args, env_extra=None, cwd=None):
        env = {k: v for k, v in os.environ.items() if k != "WORK_MAP_CONFIG"}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              env=env, cwd=cwd or self.root)

    def add_args(self, *extra):
        return ["add", "--slug", "x-call", "--applies", "one", "--from", "p", "--who", "Sam", "--time", "09:12",
                "--words", "y", "--call", "c", "--why", "w", "--date", "2026-11-08", "--session", "12345678", *extra]

    def test_given_config_that_cannot_name_a_file_refuses_and_never_falls_back(self):
        fallback = self.root / "DECISIONS.md"  # exists in the cwd: a silent fallback would write here
        before = fallback.read_bytes()
        bad = {"missing.json": None, "broken.json": "{not json", "empty.json": "{}",
               "nolist.json": '{"decisions": []}', "nomatch.json": '{"decisions": ["nothing-here.md"]}'}
        for name, text in bad.items():
            if text is not None:
                (self.root / name).write_text(text)
            for extra, env in (([ "--config", str(self.root / name)], None), ([], {"WORK_MAP_CONFIG": str(self.root / name)})):
                r = self.run_with(self.add_args(*extra), env)
                self.assertEqual(r.returncode, 2, (name, r.stderr))
                self.assertIn("refused", r.stderr)
                self.assertEqual(fallback.read_bytes(), before)
                q = self.run_with(["query", "x-call", *extra], env)
                self.assertEqual(q.returncode, 2, (name, q.stdout))
                self.assertNotIn("DECISIONS.md", q.stdout)

    def test_no_config_at_all_still_uses_local_decisions_file(self):
        r = self.run_with(self.add_args())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("x-call", self.file.read_text())

    def test_failing_write_midway_leaves_original(self):
        before = self.file.read_bytes()
        with unittest.mock.patch.object(decisions.os, "fsync", side_effect=OSError("disk full")):
            rc = decisions.main(self.add_args("--file", str(self.file)))
        self.assertEqual(rc, 1)
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir() if p.is_file()), ["DECISIONS.md"])

    def test_target_vanishing_before_parse_back_is_restored(self):
        real = decisions.atomic_write
        calls = []

        def write_then_vanish(path, data):
            calls.append(1)
            real(path, data)
            if len(calls) == 1:
                os.remove(path)
        before = self.file.read_bytes()
        with unittest.mock.patch.object(decisions, "atomic_write", side_effect=write_then_vanish):
            rc = decisions.main(self.add_args("--file", str(self.file)))
        self.assertEqual(rc, 1)
        self.assertEqual(self.file.read_bytes(), before)

    def _fail_second_parse(self, exc):
        real = decisions.parse_add_line
        calls = []

        def fake(line):
            calls.append(1)
            if len(calls) >= 2:
                raise exc
            return real(line)
        return unittest.mock.patch.object(decisions, "parse_add_line", side_effect=fake)

    def test_interrupt_after_write_restores_then_reraises(self):
        before = self.file.read_bytes()
        with self._fail_second_parse(KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                decisions.main(self.add_args("--file", str(self.file)))
        self.assertEqual(self.file.read_bytes(), before)

    def test_unexpected_parse_back_error_restores(self):
        before = self.file.read_bytes()
        with self._fail_second_parse(RuntimeError("boom")):
            rc = decisions.main(self.add_args("--file", str(self.file)))
        self.assertEqual(rc, 1)
        self.assertEqual(self.file.read_bytes(), before)

    def test_vanished_target_and_failed_restore_is_loud_exit_3(self):
        real = decisions.atomic_write
        calls = []

        def flaky(path, data):
            calls.append(1)
            if len(calls) == 1:
                real(path, data)
                os.remove(path)
                return
            raise OSError("cannot restore")
        before = self.file.read_bytes()
        with unittest.mock.patch.object(decisions, "atomic_write", side_effect=flaky):
            rc = decisions.main(self.add_args("--file", str(self.file)))
        self.assertEqual(rc, 3)
        self.assertEqual(Path(str(self.file) + ".work-map-backup").read_bytes(), before)

    def test_racing_adds_both_land(self):
        import threading
        procs = []
        for n in range(8):
            args = ["add", "--slug", "race-%d" % n, "--applies", "one", "--from", "p", "--who", "Sam", "--time", "09:12",
                    "--words", "y", "--call", "c", "--why", "w", "--date", "2026-11-08", "--session", "12345678",
                    "--file", str(self.file)]
            procs.append(subprocess.Popen([sys.executable, str(SCRIPT), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.assertEqual([p.wait() for p in procs], [0] * 8)
        text = self.file.read_text()
        for n in range(8):
            self.assertIn(" race-%d " % n, text)

    def test_lock_is_held_across_read_and_write(self):
        order = []
        real_locked = decisions.locked
        import contextlib

        @contextlib.contextmanager
        def spy(path):
            order.append("lock")
            with real_locked(path):
                yield
            order.append("unlock")
        real_write = decisions.atomic_write

        def w(path, data):
            order.append("write")
            real_write(path, data)
        with unittest.mock.patch.object(decisions, "locked", spy), unittest.mock.patch.object(decisions, "atomic_write", w):
            self.assertEqual(decisions.main(self.add_args("--file", str(self.file))), 0)
        self.assertEqual(order, ["lock", "write", "unlock"])

    def test_restore_failure_is_loud_with_backup(self):
        real = decisions.atomic_write
        calls = []

        def flaky(path, data):
            calls.append(1)
            if len(calls) == 1:
                return real(path, data)
            raise OSError("cannot restore")
        before = self.file.read_bytes()
        with unittest.mock.patch.object(decisions, "parse_add_line", side_effect=[decisions.parse_add_line(
                '- 2026-11-08 · session: 12345678 · applies: [one] · from: p · x-call · Sam (09:12 "y") → c · Why: w'), None]), \
                unittest.mock.patch.object(decisions, "atomic_write", side_effect=flaky):
            rc = decisions.main(self.add_args("--file", str(self.file)))
        self.assertEqual(rc, 3)
        self.assertEqual(Path(str(self.file) + ".work-map-backup").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
