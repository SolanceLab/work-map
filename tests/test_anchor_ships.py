# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# Ship lines go under the newest-first anchor when a file has one; otherwise they append as before.
import os, subprocess, sys, tempfile, unittest
from pathlib import Path

ANCHOR = "<!-- work-map: newest first -->"
SCRIPT = Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "ships.py"


def run(*args):
    e = {k: v for k, v in os.environ.items() if k not in ("WORK_MAP_CONFIG", "WORK_MAP_SESSION")}
    return subprocess.run([sys.executable, str(SCRIPT), "add", *args], capture_output=True, text=True, env=e)


class AnchoredShips(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.f = Path(t.name).resolve() / "DEVLOG.md"

    def ship(self, version, *extra):
        return run("--project", "demo", "--version", version, "--sha", "abc1234", "--date", "2026-11-13",
                   "--session", "a1b2c3d4", "--file", str(self.f), *extra)

    def test_new_file_starts_with_anchor_and_entry_under_it(self):
        self.assertEqual(self.ship("v1").returncode, 0)
        lines = self.f.read_text().splitlines()
        self.assertEqual(lines[:3], ["# demo DEVLOG", "", ANCHOR])
        self.assertIn("shipped v1 ", lines[3])

    def test_second_ship_goes_above_the_first(self):
        self.ship("v1")
        r = self.ship("v2")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = self.f.read_text().splitlines()
        self.assertIn("shipped v2 ", lines[3])
        self.assertIn("shipped v1 ", lines[4])

    def test_anchor_in_the_middle_is_never_moved(self):
        self.f.write_text("# x\nintro\n" + ANCHOR + "\nold note\n")
        self.assertEqual(self.ship("v1").returncode, 0)
        lines = self.f.read_text().splitlines()
        self.assertEqual(lines[:3], ["# x", "intro", ANCHOR])
        self.assertIn("shipped v1 ", lines[3])
        self.assertEqual(lines[4], "old note")

    def test_anchor_as_last_line_without_newline(self):
        self.f.write_text("# x\n  " + ANCHOR + "  ")
        self.assertEqual(self.ship("v1").returncode, 0)
        lines = self.f.read_text().splitlines()
        self.assertIn("shipped v1 ", lines[2])

    def test_no_anchor_appends_as_before(self):
        self.f.write_text("# x\nold note\n")
        self.assertEqual(self.ship("v1").returncode, 0)
        lines = self.f.read_text().splitlines()
        self.assertEqual(lines[:2], ["# x", "old note"])
        self.assertIn("shipped v1 ", lines[-1])

    def test_two_anchors_refused_and_file_untouched(self):
        text = ANCHOR + "\nmid\n" + ANCHOR + "\n"
        self.f.write_text(text)
        r = self.ship("v1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("line 1", r.stderr)
        self.assertIn("line 3", r.stderr)
        self.assertEqual(self.f.read_text(), text)

    def test_near_anchor_text_is_not_an_anchor(self):
        self.f.write_text("<!-- work-map: newest first --> extra\nold\n")
        self.assertEqual(self.ship("v1").returncode, 0)
        self.assertIn("shipped v1 ", self.f.read_text().splitlines()[-1])

    def test_duplicate_version_still_refused_with_anchor(self):
        self.ship("v1")
        before = self.f.read_bytes()
        self.assertEqual(self.ship("v1").returncode, 2)
        self.assertEqual(self.f.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
