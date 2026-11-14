# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# #!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "plugin", "scripts"))
import work_map  # noqa: E402

DECISIONS = """\
- 2026-11-01 · session: s1abc234 · applies: [demo] · from: demo · keep-it-plain · Sam (10:00 "plain") → Keep it plain · Why: readers are not engineers
- 2026-11-02 · session: s1abc234 · applies: [demo] · from: demo · publish-yes-demo-v1 · Sam (11:00 "yes") → Publish v1 · Why: she said yes
- 2026-11-03 · session: s1abc234 · applies: [demo] · from: demo · direct-call · Sam (12:00 "ok") → Direct call · Why: stated in the commit
"""
PIPELINE = """\
- **Alpha feature** · project: demo · id: alpha · session: s1abc234 · status: building · why: users asked for alpha · spec: specs/alpha.md · decisions: keep-it-plain, publish-yes-demo-v1
- **Beta feature** · project: demo · id: beta · session: s1abc234 · status: planned · why: beta follows alpha · spec: none · decisions: missing-call
- **Shared one** · project: demo · id: shared · status: planned
- **Shared two** · project: other · id: shared · status: planned
"""


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class WhyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        p = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": self.tmp, "GIT_CONFIG_NOSYSTEM": "1",
                                         "GIT_CONFIG_GLOBAL": os.devnull, "HOME": self.tmp})
        p.start()
        self.addCleanup(p.stop)
        self.repo = os.path.join(self.tmp, "my repo")
        os.mkdir(self.repo)
        hooks = os.path.join(self.tmp, "hooks")
        os.mkdir(hooks)
        self.g("init", "-q")
        for k, v in (("user.name", "Test"), ("user.email", "test@example.com"),
                     ("commit.gpgsign", "false"), ("core.hooksPath", hooks)):
            self.g("config", k, v)
        self.c1 = self.commit("notes.txt", "line one\n", "Add notes", "Work: alpha\nSession: sess0001")
        self.c2 = self.commit("notes.txt", "line two\n", "Edit notes", "Work: alpha")
        self.c3 = self.commit("other.txt", "x\n", "Plain change")
        self.c4 = self.commit("other.txt", "y\n", "Ghost work", "Work: ghost-item")
        self.c5 = self.commit("beta.txt", "b\n", "Beta work", "Work: demo/beta, alpha")
        self.c6 = self.commit("multi.txt", "m\n", "Multi trailers",
                              "Work: demo/beta\nWork: alpha\nSession: sessA\nSession: sessB")
        self.c7 = self.commit("shared.txt", "s\n", "Shared id", "Work: shared")
        self.c8 = self.commit("two words.txt", "w\n", "Spaced file", "Work: demo/beta")
        self.c9 = self.commit("dec.txt", "d\n", "Direct decision", "Decision: direct-call")
        self.c10 = self.commit("appr.txt", "a\n", "Approval only", "Decision: publish-yes-demo-v1")
        with open(os.path.join(self.tmp, "PIPELINE.md"), "w") as fh:
            fh.write(PIPELINE)
        with open(os.path.join(self.tmp, "DECISIONS.md"), "w") as fh:
            fh.write(DECISIONS)
        self.cfg = os.path.join(self.tmp, "work-map.json")
        with open(self.cfg, "w") as fh:
            json.dump({"decisions": [os.path.join(self.tmp, "DECISIONS.md")],
                       "pipeline": [os.path.join(self.tmp, "PIPELINE.md")]}, fh)

    def g(self, *a):
        return subprocess.run(["git", "-C", self.repo] + list(a), check=True, capture_output=True, text=True).stdout

    def commit(self, path, text, subject, body=None):
        with open(os.path.join(self.repo, path), "a") as fh:
            fh.write(text)
        self.g("add", "--", path)
        self.g(*(["commit", "-q", "-m", subject] + (["-m", body] if body else [])))
        return self.g("rev-parse", "HEAD").strip()

    def run_why(self, *argv, cwd=None):
        old = os.getcwd()
        os.chdir(cwd or self.repo)
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = work_map.main(["--config", self.cfg] + list(argv))
        finally:
            os.chdir(old)
        return code, out.getvalue(), err.getvalue()

    def why(self, *argv, **kw):
        return self.run_why("why", *argv, **kw)

    def notes(self):
        return os.path.join(self.repo, "notes.txt")

    def add_note(self, sha, text):
        self.g("notes", "--ref=work-map", "add", "-m", text, sha)

    def test_note_only_commit_followed_like_trailer(self):
        sha = self.commit("note1.txt", "n\n", "Noted change")
        self.add_note(sha, "Work: alpha\nSession: notesess")
        code, out, _ = self.why(sha)
        self.assertEqual(code, 0)
        for s in ("pipeline:demo/alpha · Alpha feature · building", "decision:keep-it-plain · Keep it plain",
                  "session: notesess"):
            self.assertIn(s, out)

    def test_note_keys_case_insensitive_and_other_lines_ignored(self):
        sha = self.commit("note2.txt", "n\n", "Noted two")
        self.add_note(sha, "hello there\nwork: demo/beta, alpha\nDECISION: direct-call\nrandom: x")
        _, out, _ = self.why(sha)
        self.assertIn("pipeline:demo/beta", out)
        self.assertIn("pipeline:demo/alpha", out)
        self.assertIn("decision: direct-call", out)

    def test_trailer_and_note_merge_without_duplicates(self):
        sha = self.commit("note3.txt", "n\n", "Merge change", "Work: alpha\nSession: trailsess")
        self.add_note(sha, "Work: alpha, demo/beta\nSession: notesess")
        code, out, _ = self.why(sha, "--json")
        data = json.loads(out)
        self.assertEqual([w["id"] for w in data[0]["work"]], ["alpha", "demo/beta"])
        self.assertEqual(data[0]["session"], "trailsess")
        commits = work_map.parse_log(self.g("log", "-1", "--date=short", "--no-notes", "--notes=" + work_map.NOTES_REF,
                                            "--format=" + work_map.GIT_FMT, sha))
        self.assertEqual(commits[0]["work"], ["alpha", "demo/beta"])

    def test_note_on_file_target(self):
        sha = self.commit("note4.txt", "n\n", "File noted")
        self.add_note(sha, "Work: demo/beta")
        _, out, _ = self.why(os.path.join(self.repo, "note4.txt"))
        self.assertIn("pipeline:demo/beta", out)

    def test_no_notes_ref_still_works(self):
        self.assertEqual(self.g("notes", "--ref=work-map", "list"), "")
        code, out, err = self.why(self.c1)
        self.assertEqual(code, 0, err)
        self.assertIn("session: sess0001", out)

    def test_other_notes_ref_not_read(self):
        sha = self.commit("note5.txt", "n\n", "Other ref")
        self.g("notes", "add", "-m", "Work: alpha", sha)
        code, out, _ = self.why(sha)
        self.assertEqual(code, 0)
        self.assertNotIn("pipeline:demo/alpha", out)
        self.assertIn("1 commits without a Work line", out)

    def test_commit_target(self):
        code, out, _ = self.why(self.c1)
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[0].startswith("commit " + self.c1[:7]))
        for s in ("pipeline:demo/alpha · Alpha feature · building", "why: users asked for alpha",
                  "decision:keep-it-plain · Keep it plain", "why: readers are not engineers",
                  "spec: specs/alpha.md", "session: sess0001"):
            self.assertIn(s, out)
        idx = [next(i for i, l in enumerate(out.splitlines()) if s in l)
               for s in ("commit ", "pipeline:demo/alpha", "decision:keep-it-plain", "spec:", "session:")]
        self.assertEqual(idx, sorted(idx))

    def test_publish_yes_skipped(self):
        _, out, _ = self.why(self.c1)
        _, js, _ = self.why(self.c1, "--json")
        for text in (out, js):
            for s in ("publish-yes", "Publish v1", "she said yes"):
                self.assertNotIn(s, text)

    def test_file_target_newest_first_and_dedupe(self):
        code, out, _ = self.why(self.notes())
        self.assertEqual(code, 0)
        self.assertLess(out.index("Edit notes"), out.index("Add notes"))
        self.assertEqual(out.count("pipeline:demo/alpha ·"), 1)
        self.assertIn("work: alpha (above)", out)
        blocks = out.split("commit ")
        self.assertIn("session: s1abc234", [b for b in blocks if "Edit notes" in b][0])
        self.assertIn("session: sess0001", [b for b in blocks if "Add notes" in b][0])

    def test_path_line_blame(self):
        _, out, _ = self.why(self.notes() + ":2")
        self.assertIn("Edit notes", out)
        self.assertNotIn("Add notes", out)
        _, out, _ = self.why(self.notes() + ":1")
        self.assertIn("Add notes", out)
        self.assertNotIn("Edit notes", out)

    def test_file_target_from_outside_repo(self):
        code, out, _ = self.why(self.notes(), cwd=self.tmp)
        self.assertEqual(code, 0)
        self.assertIn("Edit notes", out)
        self.assertIn("Add notes", out)

    def test_path_with_space(self):
        code, out, _ = self.why(os.path.join(self.repo, "two words.txt"))
        self.assertEqual(code, 0)
        self.assertIn("Spaced file", out)

    def test_unknown_work_id(self):
        code, out, _ = self.why(self.c4)
        self.assertEqual(code, 0)
        self.assertIn("work: ghost-item (not in the record)", out)

    def test_ambiguous_bare_id(self):
        code, out, _ = self.why(self.c7)
        self.assertEqual(code, 0)
        self.assertIn("work: shared (ambiguous: pipeline:demo/shared, pipeline:other/shared", out)
        self.assertNotIn("Shared one", out)
        self.assertNotIn("Shared two", out)
        w = json.loads(self.why(self.c7, "--json")[1])[0]["work"][0]
        self.assertFalse(w["found"])
        self.assertEqual(sorted(w["ambiguous"]), ["pipeline:demo/shared", "pipeline:other/shared"])

    def test_multiple_trailers(self):
        _, out, _ = self.why(self.c6)
        self.assertIn("pipeline:demo/beta", out)
        self.assertIn("pipeline:demo/alpha", out)
        self.assertIn("session: sessA", out)
        self.assertNotIn("sessB", out)

    def test_no_trailer_count(self):
        _, out, _ = self.why(os.path.join(self.repo, "other.txt"))
        self.assertEqual(out.splitlines()[-1], "1 commits without a Work line")
        self.assertNotIn("Plain change", out)

    def test_missing_decision_and_no_spec(self):
        _, out, _ = self.why(self.c5)
        self.assertIn("pipeline:demo/beta · Beta feature · planned", out)
        self.assertIn("decision:missing-call (not in the record)", out)
        self.assertNotIn("spec: none", out)
        self.assertIn("pipeline:demo/alpha · Alpha feature", out)

    def test_direct_decision_trailer(self):
        code, out, _ = self.why(self.c9)
        self.assertEqual(code, 0)
        self.assertIn("decision: direct-call · Direct call", out)
        self.assertIn("why: stated in the commit", out)

    def test_direct_approval_skipped(self):
        code, out, _ = self.why(self.c10)
        self.assertEqual(code, 0)
        self.assertNotIn("publish-yes", out)
        self.assertIn("1 commits without a Work line", out)
        self.assertNotIn("Approval only", out)

    def test_json_shape(self):
        code, out, _ = self.why(self.notes(), "--json")
        data = json.loads(out)
        self.assertEqual(len(data), 2)
        self.assertEqual(set(data[0]), {"commit", "date", "subject", "work", "decisions", "session"})
        self.assertEqual(data[0]["commit"], self.c2)
        self.assertEqual(set(data[0]["work"][0]), {"id", "found", "title", "status", "why", "spec", "decisions"})
        self.assertEqual(data[0]["work"][0]["decisions"],
                         [{"id": "decision:keep-it-plain", "call": "Keep it plain", "why": "readers are not engineers"}])
        self.assertRegex(data[0]["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_limit(self):
        _, out, _ = self.why(self.notes(), "--limit", "1")
        self.assertIn("Edit notes", out)
        self.assertNotIn("Add notes", out)
        self.assertEqual(self.why(self.notes(), "--limit", "0")[0], 2)

    def test_bad_ref_exit_2(self):
        code, out, err = self.why("no-such-ref-xyz")
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("work_map: why:"))

    def test_commit_outside_repo_exit_2(self):
        self.assertEqual(self.why("HEAD", cwd=self.tmp)[0], 2)

    def test_file_outside_repo_exit_2(self):
        os.mkdir(os.path.join(self.tmp, "loose"))
        f = os.path.join(self.tmp, "loose", "a.txt")
        open(f, "w").write("a\n")
        self.assertEqual(self.why(f)[0], 2)

    def test_unborn_head_exit_2(self):
        e = os.path.join(self.tmp, "empty")
        os.mkdir(e)
        subprocess.run(["git", "-C", e, "init", "-q"], check=True, capture_output=True)
        self.assertEqual(self.why("HEAD", cwd=e)[0], 2)
        f = os.path.join(e, "x.txt")
        open(f, "w").write("x\n")
        self.assertEqual(self.why(f, cwd=e)[0], 2)

    def test_folder_target_exit_2(self):
        self.assertEqual(self.why(self.repo)[0], 2)

    def test_line_out_of_range_exit_2(self):
        self.assertEqual(self.why(self.notes() + ":99")[0], 2)

    def test_untracked_file_exit_1(self):
        f = os.path.join(self.repo, "new.txt")
        open(f, "w").write("n\n")
        code, out, _ = self.why(f)
        self.assertEqual(code, 1)
        self.assertIn("no commits found", out)

    def test_staged_file_exit_1(self):
        open(os.path.join(self.repo, "new2.txt"), "w").write("n\n")
        self.g("add", "new2.txt")
        self.assertEqual(self.why(os.path.join(self.repo, "new2.txt"))[0], 1)

    def test_uncommitted_line_exit_1(self):
        open(self.notes(), "a").write("line three\n")
        code, out, _ = self.why(self.notes() + ":3")
        self.assertEqual(code, 1)
        self.assertIn("not committed yet", out)


class VersionTests(unittest.TestCase):
    def test_versions_agree(self):
        def load(*p):
            with open(os.path.join(ROOT, *p)) as fh:
                return json.load(fh)
        m = load(".claude-plugin", "marketplace.json")
        versions = {load("plugin", ".claude-plugin", "plugin.json")["version"],
                    load("plugin", ".codex-plugin", "plugin.json")["version"],
                    m["metadata"]["version"], m["plugins"][0]["version"]}
        self.assertEqual(len(versions), 1, versions)
        with open(os.path.join(ROOT, "CHANGELOG.md")) as fh:
            self.assertIn("## " + versions.pop(), fh.read())


if __name__ == "__main__":
    unittest.main()
