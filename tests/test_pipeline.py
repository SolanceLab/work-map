# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# #!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import contextlib, io, json, os, shutil, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "scripts"))
import pipeline

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "writers")


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = os.path.join(self.tmp, "demo")
        os.makedirs(self.dir)
        self.pl = os.path.join(self.dir, "PIPELINE.md")
        shutil.copy(os.path.join(FIX, "PIPELINE.md"), self.pl)
        for n in ("DECISIONS.md", "DECISIONS-archive.md", "map.md"):
            shutil.copy(os.path.join(FIX, n), os.path.join(self.tmp, n))
        self.tk = os.path.join(self.tmp, "other")
        os.makedirs(self.tk)
        self.tkfile = os.path.join(self.tk, "PIPELINE.md")
        shutil.copy(os.path.join(FIX, "PIPELINE.md"), self.tkfile)
        self.cfg = os.path.join(self.tmp, "work-map.json")
        with open(self.cfg, "w") as f:
            json.dump({"map": [os.path.join(self.tmp, "map.md")], "pipeline": [self.pl, self.tkfile]}, f)
        self.dec = ["--decisions-file", os.path.join(self.tmp, "DECISIONS.md"),
                    "--decisions-file", os.path.join(self.tmp, "DECISIONS-archive.md")]

    def run_cmd(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(pipeline, "now_stamp", return_value="2026-11-10 20:57"):
            rc = pipeline.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def add(self, **kw):
        a = dict(project="demo", item="New thing", id="new-thing", status="planned", why="because")
        a.update(kw)
        argv = ["add"]
        for k, v in a.items():
            if v is not None:
                argv += ["--" + k.replace("_", "-"), v]
        return self.run_cmd(*(argv + ["--config", self.cfg] + self.dec))

    def text(self, p=None):
        with open(p or self.pl, encoding="utf-8") as f:
            return f.read()

    def rawof(self, p):
        with open(p, "rb") as f:
            return f.read()

    def raw(self):
        return self.rawof(self.pl)

    def test_01_add_writes_valid_line_under_section(self):
        rc, _, _ = self.add(detail="a detail", spec="specs/x.md", decisions="live-slug", worker="codex")
        self.assertEqual(rc, 0)
        lines = self.text().split("\n")
        i = lines.index("## Next")
        self.assertIn("- **New thing** · id: new-thing · worker: codex · status: planned · why: because · spec: specs/x.md · decisions: live-slug", lines[i + 2])
        self.assertEqual(lines[i + 3], "  - a detail")
        f = pipeline.parse_item_line(lines[i + 2])
        self.assertEqual((f["id"], f["status"], f["why"]), ("new-thing", "planned", "because"))
        self.assertEqual(pipeline.check([self.pl]), 0)

    def test_02_missing_or_empty_why_refused_file_unchanged(self):
        before = self.raw()
        rc, _, _ = self.add(why="")
        self.assertNotEqual(rc, 0)
        rc, _, _ = self.add(why="   ")
        self.assertNotEqual(rc, 0)
        with self.assertRaises(SystemExit):
            self.add(why=None)
        self.assertEqual(self.raw(), before)

    def test_03_bad_status_refused(self):
        before = self.raw()
        rc, _, err = self.add(status="started")
        self.assertNotEqual(rc, 0)
        self.assertIn("status", err)
        self.assertEqual(self.raw(), before)

    def test_04_unknown_decision_refused_archive_accepted(self):
        before = self.raw()
        rc, _, _ = self.add(decisions="no-such-slug")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.raw(), before)
        rc, _, _ = self.add(decisions="archived-slug")
        self.assertEqual(rc, 0)
        self.assertIn("decisions: archived-slug", self.text())

    def test_05_duplicate_id_refused(self):
        before = self.raw()
        rc, _, err = self.add(id="idea-thing")
        self.assertNotEqual(rc, 0)
        self.assertIn("duplicate", err)
        self.assertEqual(self.raw(), before)

    def test_06_project_to_file_resolution(self):
        self.assertEqual(pipeline.resolve_file("demo", self.cfg)[0], self.pl)
        self.assertEqual(pipeline.resolve_file("other", self.cfg)[0], self.tkfile)
        self.assertEqual(pipeline.resolve_file("old-demo", self.cfg), (self.pl, "demo"))
        rc, _, err = self.add(project="nowhere")
        self.assertNotEqual(rc, 0)
        self.assertIn("no PIPELINE for nowhere", err)
        # real add commands with several candidate files present: only the intended file changes
        others = []
        for name in ("alpha", "beta", "demo-two"):
            d = os.path.join(self.tmp, name)
            os.makedirs(d)
            shutil.copy(os.path.join(FIX, "PIPELINE.md"), os.path.join(d, "PIPELINE.md"))
            others.append(os.path.join(d, "PIPELINE.md"))
        cfg = os.path.join(self.tmp, "multi.json")
        with open(cfg, "w") as f:
            json.dump({"map": [os.path.join(self.tmp, "map.md")],
                       "pipeline": [others[0], self.pl, others[1], self.tkfile, others[2]]}, f)
        cands = others + [self.pl, self.tkfile]
        for project, target in (("demo", self.pl), ("other", self.tkfile), ("old-demo", self.pl),
                                ("older-demo", self.pl), ("beta", others[1])):
            snap = {p: self.rawof(p) for p in cands}
            rc, _, err = self.run_cmd("add", "--project", project, "--item", "T", "--id", "t-" + project,
                                      "--status", "planned", "--why", "w", "--config", cfg, *self.dec)
            self.assertEqual(rc, 0, err)
            for p in cands:
                now = self.rawof(p)
                if p == target:
                    self.assertNotEqual(now, snap[p], project)
                    self.assertIn(b"id: t-" + project.encode(), now)
                else:
                    self.assertEqual(now, snap[p], "%s touched %s" % (project, p))

    def test_07_project_field_only_when_folder_differs(self):
        self.add()
        self.assertNotIn("project:", [l for l in self.text().split("\n") if "new-thing" in l][0])
        rc, _, err = self.run_cmd("add", "--project", "other", "--item", "N", "--id", "new-thing-2", "--status",
                                  "planned", "--why", "w", "--file", self.pl)
        self.assertEqual(rc, 0, err)
        line = [l for l in self.text().split("\n") if "new-thing-2" in l][0]
        self.assertIn(" · project: other · ", line)

    def test_08_missing_section_created_in_order(self):
        self.add(status="planned")
        heads = [l for l in self.text().split("\n") if l.startswith("## ")]
        self.assertEqual(heads, ["## Now", "## Next", "## Later"])
        new = os.path.join(self.tmp, "fresh", "PIPELINE.md")
        os.makedirs(os.path.dirname(new))
        for sid, st in (("a", "dropped"), ("b", "idea"), ("c", "building"), ("d", "planned")):
            rc, _, _ = self.run_cmd("add", "--project", "fresh", "--item", sid, "--id", sid, "--status", st,
                                    "--why", "w", "--file", new)
            self.assertEqual(rc, 0)
        t = self.text(new)
        self.assertTrue(t.startswith("# fresh — PIPELINE"))
        self.assertEqual([l for l in t.split("\n") if l.startswith("## ")], ["## Now", "## Next", "## Later", "## Done"])

    def test_09_update_done_needs_devlog_and_moves(self):
        before = self.raw()
        rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "building-thing", "--status", "done")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.raw(), before)
        rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "building-thing", "--status", "done", "--devlog", "2026-11-10")
        self.assertEqual(rc, 0)
        old = before.decode("utf-8").split("\n")
        i0 = next(i for i, l in enumerate(old) if "id: building-thing" in l)
        details = old[i0 + 1:i0 + 4]
        self.assertEqual(details, ["  - first detail", "    - nested detail", "  - second   detail  "])
        # expected whole file: the item line gains status done + devlog; block removed from Now, appended under a new ## Done
        item = old[i0].replace("status: building", "status: done") + " · devlog: 2026-11-10 · touched: 2026-11-10 20:57"
        rest = old[:i0] + old[i0 + 4:]
        expected = "\n".join(rest).rstrip("\n") + "\n\n## Done\n\n" + "\n".join([item] + details) + "\n"
        self.assertEqual(self.raw(), expected.encode("utf-8"))
        lines = self.text().split("\n")
        i = lines.index("## Done")
        self.assertEqual(lines[i + 2:i + 6], [item] + details)
        self.assertEqual(self.run_cmd("update", "--file", self.pl, "--id", "ghost", "--status", "parked")[0], 2)

    def test_10_update_dropped_needs_detail(self):
        before = self.raw()
        rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "idea-thing", "--status", "dropped")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.raw(), before)
        rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "idea-thing", "--status", "dropped", "--add-detail", "died: no need")
        self.assertEqual(rc, 0)
        lines = self.text().split("\n")
        i = lines.index("## Done")
        self.assertIn("status: dropped", lines[i + 2])
        self.assertEqual(lines[i + 3], "  - died: no need")

    def test_11_check_reports_and_exit_codes(self):
        bad = os.path.join(self.tmp, "bad.md")
        with open(bad, "w") as f:
            f.write("## Now\n\n- **x** · id: dup · status: building · spec: none · decisions: none\n"
                    "- **y** · id: dup · status: idea · why: w · spec: none · decisions: none\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = pipeline.check([bad])
        self.assertEqual(rc, 1)
        self.assertIn("missing why", out.getvalue())
        self.assertIn("duplicate id dup", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.check([self.pl]), 0)
            self.assertEqual(pipeline.main(["check", bad]), 1)

    def test_12_failure_midwrite_restores_bytes(self):
        before = self.raw()
        with mock.patch.object(pipeline, "parse_item_line", return_value=None):
            rc, _, err = self.add()
        self.assertEqual(rc, 1)
        self.assertEqual(self.raw(), before)
        real = pipeline.parse_item_line
        calls = []
        def first_real(line):
            calls.append(line)
            return real(line) if len(calls) == 1 else None
        with mock.patch.object(pipeline, "parse_item_line", side_effect=first_real):
            rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "idea-thing", "--status", "parked")
        self.assertEqual(rc, 1)
        self.assertEqual(self.raw(), before)
        # an unexpected exception type from parse-back also restores the bytes and reports failure
        with mock.patch.object(pipeline, "parse_item_line", side_effect=RuntimeError("boom")):
            rc, _, err = self.add()
        self.assertEqual(rc, 1)
        self.assertIn("boom", err)
        self.assertEqual(self.raw(), before)
        n = []
        def boom_after_first(line):
            n.append(line)
            if len(n) == 1:
                return real(line)
            raise RuntimeError("boom")
        with mock.patch.object(pipeline, "parse_item_line", side_effect=boom_after_first):
            rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "idea-thing", "--status", "parked")
        self.assertEqual(rc, 1)
        self.assertEqual(self.raw(), before)
        # a non-Exception (Ctrl-C) restores the bytes and propagates
        with mock.patch.object(pipeline, "parse_item_line", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.add()
        self.assertEqual(self.raw(), before)

    def test_13_continuation_paragraph_moves_with_its_item(self):
        with open(self.pl, "w", encoding="utf-8") as f:
            f.write("# demo\n\n## Now\n\n- **A** · id: a · status: building · why: w · spec: none · decisions: none\n"
                    "  - first\n    continuation paragraph\n  - later detail\n- **B** · id: b · status: building · why: w · spec: none · decisions: none\n")
        rc, _, _ = self.run_cmd("update", "--file", self.pl, "--id", "a", "--status", "done", "--devlog", "2026-11-10")
        self.assertEqual(rc, 0)
        t = self.text()
        done = t.split("## Done")[1]
        for l in ("  - first", "    continuation paragraph", "  - later detail"):
            self.assertIn(l, done)
        self.assertNotIn("continuation paragraph", t.split("## Done")[0])

    def test_14_crlf_file_updates_and_keeps_crlf(self):
        crlf = self.raw().replace(b"\n", b"\r\n")
        with open(self.pl, "wb") as f:
            f.write(crlf)
        rc, _, err = self.run_cmd("update", "--file", self.pl, "--id", "building-thing", "--status", "parked")
        self.assertEqual(rc, 0, err)
        raw = self.raw()
        self.assertIn(b"status: parked", raw)
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_15_concurrent_adds_lose_nothing(self):
        import subprocess
        script = os.path.abspath(pipeline.__file__)
        procs = [subprocess.Popen([sys.executable, script, "add", "--project", "demo", "--file", self.pl,
                                   "--item", "T%d" % n, "--id", "t-%d" % n, "--status", "planned", "--why", "w"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for n in range(8)]
        self.assertEqual([p.wait() for p in procs], [0] * 8)
        t = self.text()
        for n in range(8):
            self.assertIn("id: t-%d " % n, t)

    def test_16_waiting_statuses_go_to_now_and_others_refused(self):
        for n, st in enumerate(("waiting", "waiting-on-sam", "waiting-on-alex")):
            rc, _, err = self.add(id="w-%d" % n, item="W%d" % n, status=st)
            self.assertEqual(rc, 0, err)
        t = self.text()
        now = t.split("## Now")[1].split("## ")[0]
        for n in range(3):
            self.assertIn("id: w-%d " % n, now)
        self.assertEqual(pipeline.check([self.pl]), 0)
        before = self.raw()
        for bad in ("waitingx", "waiting-", "waiting-on-", "waiting-on-Sam"):
            self.assertNotEqual(self.add(id="bad-w", item="B", status=bad)[0], 0, bad)
        self.assertEqual(self.raw(), before)

    def test_17_update_to_waiting_moves_to_now(self):
        rc, _, err = self.run_cmd("update", "--file", self.pl, "--id", "idea-thing", "--status", "waiting-on-sam")
        self.assertEqual(rc, 0, err)
        now = self.text().split("## Now")[1].split("## Later")[0]
        self.assertIn("id: idea-thing", now)

    def test_18_relative_config_with_globs(self):
        cfg = os.path.join(self.tmp, "rel.json")
        with open(cfg, "w") as f:
            json.dump({"map": ["map.md"], "pipeline": ["*/PIPELINE.md"], "decisions": ["DECISIONS*.md"]}, f)
        self.assertEqual(pipeline.resolve_file("old-demo", cfg), (self.pl, "demo"))
        rc, _, err = self.run_cmd("add", "--project", "demo", "--item", "G", "--id", "g", "--status", "planned",
                                  "--why", "w", "--decisions", "archived-slug", "--config", cfg)
        self.assertEqual(rc, 0, err)
        self.assertIn("id: g ", self.text())


class LockTest(unittest.TestCase):
    def test_planted_symlink_lock_is_refused_and_target_untouched(self):
        if pipeline.fcntl is None:
            self.skipTest("no fcntl")
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        victim = os.path.join(tmp, "victim.txt")
        with open(victim, "w") as fh:
            fh.write("keep me")
        target = os.path.join(tmp, "PIPELINE.md")
        with mock.patch.object(pipeline.tempfile, "gettempdir", return_value=tmp):
            lock_dir = pipeline._private_lock_dir()
            import hashlib
            key = hashlib.sha1(os.path.realpath(target).encode()).hexdigest()[:16]
            os.symlink(victim, os.path.join(lock_dir, "write-%s.lock" % key))
            with self.assertRaises(OSError):
                with pipeline.locked(target):
                    pass
        with open(victim) as fh:
            self.assertEqual(fh.read(), "keep me")

    def test_symlink_alias_and_real_path_share_one_lock(self):
        if pipeline.fcntl is None:
            self.skipTest("no fcntl")
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        real = os.path.join(tmp, "PIPELINE.md")
        open(real, "w").close()
        alias = os.path.join(tmp, "alias.md")
        os.symlink(real, alias)
        seen = []
        with mock.patch.object(pipeline.hashlib, "sha1", wraps=pipeline.hashlib.sha1) as sha:
            for path in (real, alias):
                with pipeline.locked(path):
                    pass
            seen = [c.args[0] for c in sha.call_args_list]
        self.assertEqual(len(set(seen)), 1)

    def test_lock_folder_is_private(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(pipeline.tempfile, "gettempdir", return_value=tmp):
            d = pipeline._private_lock_dir()
        self.assertEqual(os.stat(d).st_mode & 0o777, 0o700)


class DecisionsConfigTest(unittest.TestCase):
    def test_given_config_without_decisions_refuses_slug_check_exit_2(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pl = os.path.join(tmp, "demo", "PIPELINE.md")
        os.makedirs(os.path.dirname(pl))
        shutil.copy(os.path.join(FIX, "PIPELINE.md"), pl)
        shutil.copy(os.path.join(FIX, "DECISIONS.md"), os.path.join(tmp, "DECISIONS.md"))  # a silent fallback would accept live-slug
        before = open(pl, "rb").read()
        bad = {"broken.json": "{no", "empty.json": "{}", "nomatch.json": '{"decisions": ["none-here.md"]}'}
        old = os.getcwd()
        os.chdir(tmp)
        self.addCleanup(os.chdir, old)
        for name, text in bad.items():
            with open(os.path.join(tmp, name), "w") as fh:
                fh.write(text)
            for argv, env in (([ "--config", name], {}), ([], {"WORK_MAP_CONFIG": name})):
                err = io.StringIO()
                with contextlib.redirect_stderr(err), mock.patch.dict(os.environ, env):
                    rc = pipeline.main(["add", "--project", "demo", "--item", "N", "--id", "n", "--status", "planned",
                                        "--why", "w", "--decisions", "live-slug", "--file", pl, *argv])
                self.assertEqual(rc, 2, (name, err.getvalue()))
                self.assertIn("config", err.getvalue())
                self.assertEqual(open(pl, "rb").read(), before)
        # no config given at all: the local DECISIONS.md is used
        with contextlib.redirect_stderr(io.StringIO()), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WORK_MAP_CONFIG", None)
            rc = pipeline.main(["add", "--project", "demo", "--item", "N", "--id", "n", "--status", "planned",
                                "--why", "w", "--decisions", "live-slug", "--file", pl])
        self.assertEqual(rc, 0)


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.pl = os.path.join(self.tmp, "demo", "PIPELINE.md")
        os.makedirs(os.path.dirname(self.pl))
        shutil.copy(os.path.join(FIX, "PIPELINE.md"), self.pl)
        os.chmod(self.pl, 0o640)
        with open(self.pl, "rb") as fh:
            self.before = fh.read()

    def add(self, *extra):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = pipeline.main(["add", "--project", "demo", "--item", "N", "--id", "n", "--status", "planned",
                                "--why", "w", "--file", self.pl, *extra])
        return rc, err.getvalue()

    def test_failing_write_midway_leaves_original_and_no_temp_files(self):
        with mock.patch.object(pipeline.os, "fsync", side_effect=OSError("disk full")):
            rc, _ = self.add()
        self.assertEqual(rc, 1)
        with open(self.pl, "rb") as fh:
            self.assertEqual(fh.read(), self.before)
        self.assertEqual(os.listdir(os.path.dirname(self.pl)), ["PIPELINE.md"])

    def test_success_keeps_mode_and_goes_through_replace(self):
        with mock.patch.object(pipeline.os, "replace", wraps=os.replace) as rep:
            rc, err = self.add()
        self.assertEqual(rc, 0, err)
        self.assertEqual(rep.call_count, 1)
        self.assertEqual(os.stat(self.pl).st_mode & 0o777, 0o640)
        self.assertIn(b"id: n ", open(self.pl, "rb").read())

    def test_parse_back_failure_restores_by_replace(self):
        with mock.patch.object(pipeline, "parse_item_line", return_value=None), \
                mock.patch.object(pipeline.os, "replace", wraps=os.replace) as rep:
            rc, _ = self.add()
        self.assertEqual(rc, 1)
        self.assertEqual(rep.call_count, 2)
        with open(self.pl, "rb") as fh:
            self.assertEqual(fh.read(), self.before)

    def test_restore_failure_is_loud_and_leaves_a_backup(self):
        real = pipeline.atomic_write
        calls = []

        def flaky(path, data):
            calls.append(1)
            if len(calls) == 1:
                return real(path, data)
            raise OSError("cannot restore")
        with mock.patch.object(pipeline, "parse_item_line", return_value=None), \
                mock.patch.object(pipeline, "atomic_write", side_effect=flaky):
            rc, err = self.add()
        self.assertEqual(rc, 3)
        self.assertIn("RESTORE FAILED", err)
        backup = self.pl + ".work-map-backup"
        self.assertIn(backup, err)
        with open(backup, "rb") as fh:
            self.assertEqual(fh.read(), self.before)

    def test_target_vanishing_before_parse_back_is_restored(self):
        real = pipeline.atomic_write
        calls = []

        def write_then_vanish(path, data):
            calls.append(1)
            real(path, data)
            if len(calls) == 1:
                os.remove(path)
        with mock.patch.object(pipeline, "atomic_write", side_effect=write_then_vanish):
            rc, _ = self.add()
        self.assertEqual(rc, 1)
        with open(self.pl, "rb") as fh:
            self.assertEqual(fh.read(), self.before)

    def test_vanished_target_and_failed_restore_is_loud_exit_3(self):
        real = pipeline.atomic_write
        calls = []

        def flaky(path, data):
            calls.append(1)
            if len(calls) == 1:
                real(path, data)
                os.remove(path)
                return
            raise OSError("cannot restore")
        with mock.patch.object(pipeline, "atomic_write", side_effect=flaky):
            rc, err = self.add()
        self.assertEqual(rc, 3)
        self.assertIn("RESTORE FAILED", err)
        with open(self.pl + ".work-map-backup", "rb") as fh:
            self.assertEqual(fh.read(), self.before)

    def test_write_through_symlink_keeps_the_link(self):
        alias = os.path.join(self.tmp, "alias.md")
        os.symlink(self.pl, alias)
        self.pl_real = self.pl
        self.pl = alias
        rc, err = self.add()
        self.assertEqual(rc, 0, err)
        self.assertTrue(os.path.islink(alias))
        self.assertIn(b"id: n ", open(self.pl_real, "rb").read())


if __name__ == "__main__":
    unittest.main()
