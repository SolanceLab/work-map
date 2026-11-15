# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# decisions.py query: house-wide standing rules first, and no match is ever cut silently.
import importlib.util, io, json, subprocess, sys, tempfile, unittest, unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugin" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import work_map
spec = importlib.util.spec_from_file_location("decisions", SCRIPTS / "decisions.py")
decisions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decisions)


def plain(date, slug):
    return '- %s · session: 12345678 · applies: [demo] · from: demo · %s · Sam (09:12 "yes") → the call · Why: because' % (date, slug)


def house(date, slug, kind="standing", applies="house", superseded=None):
    mark = " · SUPERSEDED by %s" % superseded if superseded else ""
    return '- %s · session: 12345678 · applies: [%s] · from: demo · kind: %s · %s%s · Sam (09:12 "yes") → the rule · Why: because' % (date, applies, kind, slug, mark)


class Base(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.file = self.root / "DECISIONS.md"

    def write(self, *rows):
        self.file.write_text("# Register\n---\n" + "\n".join(rows) + "\n", encoding="utf-8")

    def query(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            decisions.main(["query", *args])
        return out.getvalue().splitlines()


class NoCut(Base):
    def test_old_house_standing_rules_come_first(self):
        self.write(*[plain("2026-10-%02d" % d, "demo-%02d" % d) for d in range(1, 29)],
                   house("2026-01-01", "house-rule-a"), house("2026-01-02", "house-rule-b"))
        out = self.query("because", "--file", str(self.file))
        self.assertIn("house-rule-b", out[0])
        self.assertIn("house-rule-a", out[1])
        self.assertIn("2026-10-28", out[2])
        self.assertIn("also matching (5 more):", out)
        self.assertEqual(out[-1], "showing 25 of 30; add a term to narrow")

    def test_every_match_named_when_40_match(self):
        dates = ["2026-09-%02d" % d for d in range(1, 31)] + ["2026-10-%02d" % d for d in range(1, 11)]
        self.write(*[plain(d, "item-%02d" % (n + 1)) for n, d in enumerate(dates)])
        out = self.query("because", "--file", str(self.file))
        text = "\n".join(out)
        for n in range(1, 41):
            self.assertIn("item-%02d" % n, text)
        self.assertIn("also matching (15 more):", out)
        self.assertEqual(out[-1], "showing 25 of 40; add a term to narrow")
        h = out.index("also matching (15 more):")
        for l in out[h + 1:-1]:
            self.assertTrue(l.startswith("  "))
            self.assertLessEqual(len(l), 120)

    def test_superseded_house_rule_not_promoted(self):
        self.write(*[plain("2026-10-%02d" % d, "demo-%02d" % d) for d in range(1, 29)],
                   house("2026-01-02", "house-live"), house("2026-01-01", "house-old", superseded="house-live"))
        out = self.query("because", "--file", str(self.file))
        self.assertIn("house-live", out[0])
        self.assertNotIn("house-old", out[0])
        idx_new = next(i for i, l in enumerate(out) if "2026-10-28" in l)
        idx_old = next(i for i, l in enumerate(out) if "house-old" in l)
        self.assertGreater(idx_old, idx_new)

    def test_superseded_house_rule_keeps_date_place_uncut(self):
        self.write(plain("2026-10-01", "demo-new"), house("2026-01-01", "house-old", superseded="house-live"))
        out = self.query("because", "--file", str(self.file))
        self.assertIn("demo-new", out[0])
        self.assertIn("house-old", out[1])
        self.assertIn("[superseded by house-live]", out[1])
        self.assertFalse(any(l.startswith("also matching") for l in out))

    def test_only_standing_and_house_promoted(self):
        self.write(plain("2026-10-05", "demo-new"), house("2026-01-01", "one-time-rule", kind="one-time"),
                   house("2026-01-02", "demo-standing", applies="demo"),
                   house("2026-01-03", "boat-standing", applies="houseboat"))
        out = self.query("because", "--file", str(self.file))
        self.assertIn("demo-new", out[0])

    def test_closest_matches_list_all_remaining(self):
        self.write(*[plain("2026-10-%02d" % d, "slug-%d" % d) for d in range(1, 21)])
        out = self.query("because", "nomatchword", "--file", str(self.file))
        self.assertEqual(out[0], "No line matches every term; closest matches:")
        self.assertIn("also matching (5 more):", out)
        rest = "\n".join(out[out.index("also matching (5 more):") + 1:])
        for n in range(1, 6):
            self.assertIn("slug-%d" % n, rest)
        self.assertEqual(out[-1], "showing 15 of 20; add a term to narrow")
        self.assertIn("2026-10-20", out[1])

    def test_notes_line_without_record_does_not_crash(self):
        self.write(plain("2026-10-01", "demo-new"))
        notes = self.root / "notes.md"
        notes.write_text("\n".join("we decided because reason %d" % n for n in range(30)) + "\n", encoding="utf-8")
        out = self.query("because", "--file", str(self.file), "--notes", str(notes))
        self.assertEqual(out[-1], "showing 25 of 31; add a term to narrow")
        self.assertIn("also matching (6 more):", out)


if __name__ == "__main__":
    unittest.main()
