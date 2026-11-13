# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# decisions.py add --supersedes, the SUPERSEDED mark in the reader, and the newest-first query with its count line.
import importlib.util, io, json, subprocess, sys, tempfile, unittest, unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugin" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import work_map
spec = importlib.util.spec_from_file_location("decisions", SCRIPTS / "decisions.py")
decisions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decisions)


def line(date, slug, call="the call", words="yes"):
    return '- %s · session: 12345678 · applies: [one] · from: project · %s · Sam (09:12 "%s") → %s · Why: because' % (date, slug, words, call)


class Base(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.file = self.root / "DECISIONS.md"

    def write(self, *rows):
        self.file.write_text("# Register\n---\n" + "\n".join(rows) + "\n", encoding="utf-8")

    def add(self, slug, *extra, file=None):
        args = ["--slug", slug, "--applies", "one", "--from", "project", "--who", "Sam", "--time", "09:12",
                "--words", "yes", "--call", "new call", "--why", "because", "--date", "2026-11-13",
                "--session", "12345678", "--file", str(file or self.file), *extra]
        return subprocess.run([sys.executable, str(SCRIPTS / "decisions.py"), "add", *args], capture_output=True, text=True)

    def query(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            decisions.main(["query", *args])
        return out.getvalue().splitlines()


class Supersede(Base):
    def test_marks_old_line_and_survives_parser_and_query(self):
        self.write(line("2026-11-01", "old-call", call="old way"))
        r = self.add("new-call", "--supersedes", "old-call")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.file.read_text().splitlines()
        self.assertIn(" · old-call · SUPERSEDED by new-call · Sam (", rows[2])
        rec = work_map.parse_decision(rows[2], ("f", 3))
        self.assertEqual((rec["status"], rec["superseded_by"], rec["slug"]), ("superseded", "new-call", "old-call"))
        self.assertNotIn(rec["status"], work_map.OPEN_STATUSES)
        self.assertEqual(work_map.public(rec)["superseded_by"], "new-call")
        self.assertIn("superseded", work_map.one_line(rec))
        self.assertEqual(decisions.parse_add_line(rows[3])["slug"], "new-call")
        q = self.query("old", "--file", str(self.file))
        self.assertTrue(q[0].endswith("[superseded by new-call] " + rows[2]) or "[superseded by new-call]" in q[0], q)

    def test_dry_run_prints_both_and_writes_nothing(self):
        self.write(line("2026-11-01", "old-call"))
        before = self.file.read_bytes()
        r = self.add("new-call", "--supersedes", "old-call", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 2)
        self.assertIn("SUPERSEDED by new-call", r.stdout)
        self.assertEqual(self.file.read_bytes(), before)

    def refused(self, *rows, supersedes="old-call", slug="new-call", expect=""):
        self.write(*rows)
        before = self.file.read_bytes()
        r = self.add(slug, "--supersedes", supersedes)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(expect, r.stderr)
        self.assertEqual(self.file.read_bytes(), before)

    def test_missing_slug_refused(self):
        self.refused(line("2026-11-01", "other"), expect="no line with slug old-call")

    def test_ambiguous_slug_refused_with_line_numbers(self):
        self.refused(line("2026-11-01", "old-call"), line("2026-11-02", "old-call"), expect="lines 3, 4")

    def test_already_superseded_names_replacer(self):
        marked = line("2026-11-01", "old-call").replace(" · old-call · ", " · old-call · SUPERSEDED by first-new · ")
        self.refused(marked, expect="already superseded by first-new")

    def test_equal_to_slug_refused(self):
        self.refused(line("2026-11-01", "old-call"), supersedes="new-call", expect="itself")

    def test_old_slug_only_in_another_config_file_refused(self):
        other = self.root / "OTHER.md"
        other.write_text("---\n" + line("2026-11-01", "old-call") + "\n", encoding="utf-8")
        self.write(line("2026-11-02", "unrelated"))
        cfg = self.root / "work-map.json"
        cfg.write_text(json.dumps({"decisions": ["DECISIONS.md", "OTHER.md"]}), encoding="utf-8")
        before = (self.file.read_bytes(), other.read_bytes())
        r = subprocess.run([sys.executable, str(SCRIPTS / "decisions.py"), "add", "--slug", "new-call", "--applies", "one",
                            "--from", "project", "--who", "Sam", "--time", "09:12", "--words", "yes", "--call", "c",
                            "--why", "w", "--date", "2026-11-13", "--session", "12345678", "--config", str(cfg),
                            "--supersedes", "old-call"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("OTHER.md", r.stderr)
        self.assertEqual((self.file.read_bytes(), other.read_bytes()), before)

    def test_duplicate_new_slug_refused_by_existing_check(self):
        self.write(line("2026-11-01", "old-call"), line("2026-11-02", "new-call"))
        before = self.file.read_bytes()
        self.assertNotEqual(self.add("new-call", "--supersedes", "old-call").returncode, 0)
        self.assertEqual(self.file.read_bytes(), before)

    def test_failure_after_write_restores_both_lines(self):
        self.write(line("2026-11-01", "old-call"))
        before = self.file.read_bytes()
        real, calls = decisions.parse_add_line, []

        def fake(text):
            calls.append(1)
            if len(calls) >= 2:
                raise RuntimeError("boom")
            return real(text)
        argv = ["--slug", "new-call", "--applies", "one", "--from", "project", "--who", "Sam", "--time", "09:12",
                "--words", "yes", "--call", "c", "--why", "w", "--date", "2026-11-13", "--session", "12345678",
                "--file", str(self.file), "--supersedes", "old-call"]
        with unittest.mock.patch.object(decisions, "parse_add_line", side_effect=fake):
            rc = decisions.main(["add", *argv])
        self.assertEqual(rc, 1)
        self.assertEqual(self.file.read_bytes(), before)

    def test_open_slice_drops_superseded_decision(self):
        self.write(line("2026-11-01", "old-call"))
        self.add("new-call", "--supersedes", "old-call")
        records = work_map.parse_decision(self.file.read_text().splitlines()[2], ("f", 3)), \
            work_map.parse_decision(self.file.read_text().splitlines()[3], ("f", 4))
        open_ids = [r["id"] for r in records if r["status"] in work_map.OPEN_STATUSES]
        self.assertEqual(open_ids, ["decision:new-call"])


class QueryOrder(Base):
    def test_newest_date_first_then_later_line_first(self):
        self.write(line("2026-11-01", "a-one"), line("2026-11-05", "b-two"), line("2026-11-05", "c-three"), line("2026-11-03", "d-four"))
        out = self.query("because", "--file", str(self.file))
        self.assertEqual([o.split("  ")[0] for o in out], ["DECISIONS.md:5", "DECISIONS.md:4", "DECISIONS.md:6", "DECISIONS.md:3"])

    def test_config_order_across_files_at_same_date_and_notes_last(self):
        a, b = self.root / "A.md", self.root / "B.md"
        a.write_text("---\n" + line("2026-11-05", "in-a") + "\n", encoding="utf-8")
        b.write_text("---\n" + line("2026-11-05", "in-b") + "\n", encoding="utf-8")
        notes = self.root / "notes.md"
        notes.write_text("we decided because of things\n", encoding="utf-8")
        out = self.query("because", "--file", str(a), "--file", str(b))
        self.assertEqual([o.split(":")[0] for o in out], ["A.md", "B.md"])
        out = self.query("because", "--file", str(a), "--notes", str(notes))
        self.assertEqual([o.split(":")[0] for o in out], ["A.md", "notes.md"])

    def test_cut_exact_list_prints_count_line(self):
        self.write(*[line("2026-10-%02d" % d, "slug-%d" % d) for d in range(1, 29)])
        out = self.query("because", "--file", str(self.file))
        self.assertEqual(len(out), 26)
        self.assertEqual(out[-1], "showing 25 of 28; add a term to narrow")
        self.assertIn("2026-10-28", out[0])

    def test_uncut_list_prints_no_count_line(self):
        self.write(line("2026-11-01", "a-one"))
        self.assertFalse(any(o.startswith("showing") for o in self.query("because", "--file", str(self.file))))

    def test_cut_closest_list_prints_count_line(self):
        self.write(*[line("2026-10-%02d" % d, "slug-%d" % d) for d in range(1, 21)])
        out = self.query("because", "nomatchword", "--file", str(self.file))
        self.assertEqual(out[0], "No line matches every term; closest matches:")
        self.assertEqual(len(out), 1 + 15 + 1)
        self.assertEqual(out[-1], "showing 15 of 20; add a term to narrow")
        self.assertIn("2026-10-20", out[1])


if __name__ == "__main__":
    unittest.main()
