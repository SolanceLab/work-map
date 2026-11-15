# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""Root (map) lines: pointer tags, access and status tags, the workbench limit, and the writer `pipeline.py root`."""
import contextlib, io, json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "scripts"))
import pipeline
import work_map

MAP = """# Root

- **Alpha** · id: alpha · access: house · status: workbench · aka: none · pipeline: alpha/PIPELINE.md · why: first
- **Beta** · id: beta · access: public · status: waiting · aka: old-beta · pipeline: beta/PIPELINE.md · why: second
- **Gamma** · id: gamma · access: none · status: idea · aka: none · spec: specs/gamma.md · why: a thought
- **Old** · id: old · status: building · aka: none · why: old style line
  - a detail
- **Oldlive** · id: oldlive · status: live · aka: none · why: old live line, no access tag
"""


class RootBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel in ("alpha/PIPELINE.md", "beta/PIPELINE.md", "delta/PIPELINE.md", "specs/gamma.md", "specs/eps.md"):
            os.makedirs(os.path.dirname(os.path.join(self.tmp, rel)), exist_ok=True)
            with open(os.path.join(self.tmp, rel), "w") as fh:
                fh.write("x\n")
        self.map = os.path.join(self.tmp, "map.md")
        self.write_map(MAP)
        self.cfg = os.path.join(self.tmp, "work-map.json")
        self.set_config({"map": ["map.md"]})

    def write_map(self, text):
        with open(self.map, "w") as f:
            f.write(text)

    def set_config(self, cfg):
        with open(self.cfg, "w") as f:
            json.dump(cfg, f)

    def text(self):
        return self.raw().decode()

    def raw(self):
        with open(self.map, "rb") as f:
            return f.read()

    def root(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = pipeline.main(["root"] + list(argv) + ["--config", self.cfg])
        return rc, out.getvalue(), err.getvalue()

    def refused(self, *argv, needle=""):
        before = self.raw()
        rc, _, err = self.root(*argv)
        self.assertEqual(rc, 2, err)
        self.assertIn(needle, err)
        self.assertEqual(self.raw(), before)  # nothing written
        self.assertEqual(err.count("\n"), 1)  # one line

    def cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = work_map.main(["--config", self.cfg] + list(argv))
        return rc, out.getvalue()


class RootReader(RootBase):
    def records(self):
        sources, base = work_map.load_config(self.cfg)
        return {r["project"]: r for r in work_map.load_all(sources, base)[0]}

    def test_tags_and_old_statuses_are_read(self):
        r = self.records()
        self.assertEqual(r["alpha"]["pipeline"], "alpha/PIPELINE.md")
        self.assertEqual(r["gamma"]["spec"], "specs/gamma.md")
        self.assertNotIn("pipeline", r["old"])
        self.assertEqual(r["old"]["status"], "building")  # old values kept as written
        self.assertEqual(r["old"]["details"], ["a detail"])

    def test_workbench_is_open(self):
        _, out = self.cli("slice", "--house", "--status", "open")
        self.assertEqual(out.strip(), "nothing open")  # roots are project records; house slice only shows project:house
        self.write_map("- **House** · id: house · access: house · status: workbench · aka: none · pipeline: none · why: w\n")
        _, out = self.cli("slice", "--house")
        self.assertIn("project:house", out)

    def test_project_slice_opens_with_its_workbench_line(self):
        rc, out = self.cli("slice", "--project", "alpha")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("project project:alpha"))

    def test_open_prints_pointers(self):
        _, out = self.cli("open", "project:alpha")
        self.assertIn("  pipeline: alpha/PIPELINE.md", out)
        _, out = self.cli("open", "project:gamma")
        self.assertIn("  spec: specs/gamma.md", out)
        _, out = self.cli("open", "project:old")
        self.assertNotIn("pipeline:", out)

    def problems(self):
        _, out = self.cli("inventory", "--json")
        return json.loads(out)["problems"]

    def test_inventory_clean_and_old_lines_not_flagged(self):
        self.assertEqual(self.problems(), [])

    def test_inventory_over_limit_missing_pointer_missing_target(self):
        self.set_config({"map": ["map.md"], "workbench_limit": 1})
        self.write_map(MAP + "- **Dee** · id: dee · access: house · status: workbench · aka: none · pipeline: nope/PIPELINE.md · why: w\n"
                       "- **Eps** · id: eps · access: house · status: idea · aka: none · why: w\n"
                       "- **Zed** · id: zed · access: house · status: waiting · aka: none · why: w\n"
                       "- **Set** · id: set · access: public · status: settled · aka: none · pipeline: none · why: w\n"
                       "- **Nil** · id: nil · access: none · status: idea · aka: none · spec: none · why: w\n"
                       "- **Drp** · id: drp · access: none · status: dropped · aka: none · why: w\n")
        kinds = {(p["type"], p.get("id")) for p in self.problems()}
        self.assertIn(("workbench-over-limit", None), kinds)
        self.assertIn(("pointer-target-missing", "dee"), kinds)
        self.assertIn(("pointer-missing", "eps"), kinds)
        self.assertIn(("pointer-missing", "zed"), kinds)  # waiting needs a pipeline
        self.assertIn(("pointer-missing", "set"), kinds)  # settled needs a pipeline
        self.assertNotIn(("pointer-missing", "nil"), kinds)  # none is explicit
        self.assertNotIn(("pointer-missing", "drp"), kinds)  # dropped needs no pointer
        over = [p for p in self.problems() if p["type"] == "workbench-over-limit"][0]
        self.assertEqual(over["ids"], ["alpha", "dee"])
        _, text = self.cli("inventory")
        self.assertIn("workbench-over-limit: 2 on the workbench, limit 1 (alpha, dee)", text)

    def test_inventory_access_missing_and_invalid(self):
        self.write_map(MAP + "- **Nia** · id: nia · status: idea · aka: none · spec: none · why: w\n"
                       "- **Bad** · id: bad · access: secret · status: idea · aka: none · spec: none · why: w\n"
                       "- **Ok** · id: ok · access: going-public · status: dropped · aka: none · why: w\n")
        kinds = {(p["type"], p.get("id")) for p in self.problems()}
        self.assertIn(("access-missing", "nia"), kinds)
        self.assertIn(("access-invalid", "bad"), kinds)
        self.assertNotIn(("access-missing", "ok"), kinds)
        self.assertNotIn(("access-missing", "old"), kinds)  # old status: not asked
        self.assertNotIn(("access-missing", "oldlive"), kinds)
        _, text = self.cli("inventory")
        self.assertIn("access-missing: nia (status idea)", text)
        self.assertIn("access-invalid: bad access secret (status idea)", text)

    def test_settled_is_not_open_waiting_is(self):
        self.write_map("- **Set** · id: set · access: public · status: settled · aka: none · pipeline: alpha/PIPELINE.md · why: done\n"
                       "- **Wai** · id: wai · access: house · status: waiting · aka: none · pipeline: alpha/PIPELINE.md · why: later\n")
        records = {r["id"]: r for r in work_map.load_all(*work_map.load_config(self.cfg))[0]}
        self.assertEqual(records["project:set"]["access"], "public")
        self.assertNotIn("settled", work_map.OPEN_STATUSES)
        self.assertIn("waiting", work_map.OPEN_STATUSES)
        _, out = self.cli("open", "project:set")
        self.assertIn("  access: public", out)
        self.write_map("- **House** · id: house · access: house · status: settled · aka: none · pipeline: alpha/PIPELINE.md · why: done\n")
        _, out = self.cli("slice", "--house", "--status", "open")
        self.assertEqual(out.strip(), "nothing open")
        self.write_map("- **House** · id: house · access: house · status: waiting · aka: none · pipeline: alpha/PIPELINE.md · why: later\n")
        _, out = self.cli("slice", "--house", "--status", "open")
        self.assertIn("project:house", out)

    def test_limit_default_three_and_bad_limit(self):
        self.assertEqual(work_map.config_workbench_limit(self.cfg), 3)
        self.set_config({"map": ["map.md"], "workbench_limit": 5})
        self.assertEqual(work_map.config_workbench_limit(self.cfg), 5)
        self.set_config({"map": ["map.md"], "workbench_limit": 0})
        self.assertEqual(self.cli("inventory")[0], 2)

    def test_project_item_statuses_untouched(self):
        # an item line with status workbench is not a root: nothing about items changed
        recs = work_map.parse_pipeline_file("- **T** · id: t · status: building · why: w · spec: none · decisions: none\n", "P.md", "alpha")
        self.assertEqual(recs[0]["status"], "building")
        self.assertNotIn("workbench", pipeline.STATUSES)
        self.assertFalse(pipeline.status_ok("workbench"))


class RootWriter(RootBase):
    def test_add_happy_paths(self):
        rc, _, err = self.root("add", "--name", "Delta", "--id", "delta", "--access", "house", "--status", "workbench", "--why", "now",
                               "--aka", "d1, d2", "--pipeline", "delta/PIPELINE.md")
        self.assertEqual(rc, 0, err)
        lines = self.text().split("\n")
        i = lines.index("- **Delta** · id: delta · access: house · status: workbench · aka: d1, d2 · pipeline: delta/PIPELINE.md · why: now")
        self.assertTrue(lines[i - 1].startswith("- **Oldlive**"))  # after the last root line and its details
        rc, _, err = self.root("add", "--name", "Eps", "--id", "eps", "--access", "none", "--status", "idea", "--why", "w", "--spec", "specs/eps.md")
        self.assertEqual(rc, 0, err)
        rc, _, err = self.root("add", "--name", "Nil", "--id", "nil", "--access", "none", "--status", "idea", "--why", "w", "--spec", "none")
        self.assertEqual(rc, 0, err)
        self.assertIn("aka: none · spec: none · why: w", self.text())
        self.assertEqual(self.problems_none(), [])

    def problems_none(self):
        _, out = self.cli("inventory", "--json")
        return json.loads(out)["problems"]

    def test_dry_run_writes_nothing(self):
        before = self.raw()
        rc, out, _ = self.root("add", "--name", "E", "--id", "e", "--access", "public", "--status", "settled", "--why", "w",
                               "--pipeline", "beta/PIPELINE.md", "--dry-run")
        self.assertEqual((rc, self.raw()), (0, before))
        self.assertIn("id: e", out)

    def test_add_creates_map_with_file(self):
        new = os.path.join(self.tmp, "fresh.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = pipeline.main(["root", "add", "--name", "F", "--id", "f", "--access", "none", "--status", "idea", "--why", "w",
                                "--spec", "none", "--file", new])
        self.assertEqual(rc, 0)
        self.assertIn("- **F** · id: f · access: none · status: idea", Path(new).read_text())

    def test_update_happy_paths(self):
        rc, _, err = self.root("update", "--id", "gamma", "--status", "workbench", "--pipeline", "delta/PIPELINE.md")
        self.assertEqual(rc, 0, err)
        text = self.text()
        self.assertIn("- **Gamma** · id: gamma · access: none · status: workbench · aka: none · pipeline: delta/PIPELINE.md · why: a thought", text)
        self.assertNotIn("spec: specs/gamma.md", text)  # the promotion swaps the pointer kind
        rc, _, err = self.root("update", "--id", "alpha", "--why", "changed")
        self.assertEqual(rc, 0, err)
        self.assertIn("pipeline: alpha/PIPELINE.md · why: changed", self.text())
        rc, _, err = self.root("update", "--id", "alpha", "--status", "settled")
        self.assertEqual(rc, 0, err)

    def test_update_sets_aka_and_adds_details_after_existing_ones(self):
        rc, _, err = self.root("update", "--id", "old", "--aka", "first, second", "--add-detail", "new one")
        self.assertEqual(rc, 0, err)
        text = self.text()
        self.assertIn("status: building · aka: first, second", text)
        self.assertIn("aka: first, second · why: old style line\n  - a detail\n  - new one\n- **Oldlive**", text)
        self.refused("update", "--id", "old", "--aka", " ", needle="--aka cannot be empty")
        self.refused("update", "--id", "old", "--add-detail", " ", needle="--add-detail must be one non-empty line")

    def test_old_status_line_may_change_its_why(self):
        rc, _, err = self.root("update", "--id", "old", "--why", "still building")
        self.assertEqual(rc, 0, err)
        text = self.text()
        self.assertIn("status: building · aka: none · why: still building\n  - a detail\n", text)

    def test_typo_status_and_bad_access_are_refused_on_any_update(self):
        self.write_map("# Root\n\n- **Typo** · id: typo · access: house · status: workbenhc · aka: none · pipeline: alpha/PIPELINE.md · why: w\n"
                       "- **Secret** · id: secret · access: secret · status: waiting · aka: none · pipeline: alpha/PIPELINE.md · why: w\n")
        self.refused("update", "--id", "typo", "--why", "x", needle="status must be one of")
        self.refused("update", "--id", "secret", "--why", "x", needle="access must be one of")

    def test_why_only_update_cannot_resave_a_broken_line(self):
        self.write_map("# Root\n\n- **Bad** · id: bad · access: house · status: workbench · aka: none · why: no pointer\n")
        self.refused("update", "--id", "bad", "--why", "new words", needle="needs --pipeline")
        rc, _, err = self.root("update", "--id", "bad", "--why", "new words", "--pipeline", "alpha/PIPELINE.md")
        self.assertEqual(rc, 0, err)

    def test_every_refusal_leaves_the_file_identical(self):
        full = {"map": ["map.md"], "workbench_limit": 1}
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "building", "--why", "w", needle="status must be one of")
        self.refused("add", "--name", "X", "--id", "x", "--access", "private", "--status", "idea", "--why", "w", "--spec", "none",
                     needle="access must be one of: public going-public house none")
        self.refused("update", "--id", "alpha", "--access", "mine", needle="access must be one of")
        self.refused("update", "--id", "old", "--status", "idea", "--spec", "none", needle="needs --access")
        self.refused("update", "--id", "alpha", "--status", "later", needle="status must be one of")
        self.set_config(full)
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "workbench", "--why", "w", "--pipeline", "beta/PIPELINE.md",
                     needle="workbench is full (limit 1): alpha")
        self.refused("update", "--id", "beta", "--status", "workbench", needle="workbench is full")
        self.set_config({"map": ["map.md"]})
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "waiting", "--why", "w", needle="needs --pipeline")
        self.refused("update", "--id", "gamma", "--status", "workbench", needle="needs --pipeline")
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "idea", "--why", "w", needle="needs --spec")
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "idea", "--why", "w",
                     "--spec", "specs/eps.md", "--pipeline", "beta/PIPELINE.md", needle="not both")
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "idea", "--why", "w", "--spec", "specs/nope.md",
                     needle="path does not exist")
        self.refused("update", "--id", "beta", "--pipeline", "nope/PIPELINE.md", needle="path does not exist")
        self.refused("add", "--name", "X", "--id", "alpha", "--access", "house", "--status", "idea", "--why", "w", "--spec", "none",
                     needle="duplicate id")
        self.refused("update", "--id", "ghost", "--why", "w", needle="unknown id")

    def test_limit_applies_across_updates_and_ignores_own_line(self):
        self.set_config({"map": ["map.md"], "workbench_limit": 1})
        rc, _, err = self.root("update", "--id", "alpha", "--status", "workbench", "--why", "same")
        self.assertEqual(rc, 0, err)  # already on the bench: not counted against itself
        self.set_config({"map": ["map.md"], "workbench_limit": 2})
        rc, _, err = self.root("update", "--id", "beta", "--status", "workbench")
        self.assertEqual(rc, 0, err)
        self.refused("update", "--id", "gamma", "--status", "workbench", "--pipeline", "delta/PIPELINE.md", needle="alpha, beta")

    def test_item_writer_and_item_lines_untouched(self):
        pl = os.path.join(self.tmp, "alpha", "PIPELINE.md")
        Path(pl).write_text("# alpha — PIPELINE\n\n## Now\n\n- **T** · id: t · status: building · why: w · spec: none · decisions: none · touched: 2026-11-10 10:00\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = pipeline.main(["update", "--file", pl, "--id", "t", "--status", "waiting"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.raw().decode(), MAP)  # the map file was not touched

    def test_check_validates_root_lines(self):
        self.write_map(MAP + "- **Zed** · id: zed · access: house · status: waiting · aka: none · why: w\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = pipeline.main(["check", "--config", self.cfg, self.map])
        self.assertEqual(rc, 1)
        self.assertIn("pointer-missing: zed", out.getvalue())
        self.write_map(MAP)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.main(["check", "--config", self.cfg, self.map]), 0)

    def test_pointer_none_refused_for_workbench_waiting_settled(self):
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "waiting", "--why", "w", "--pipeline", "none", needle="needs --pipeline")
        self.refused("add", "--name", "X", "--id", "x", "--access", "house", "--status", "workbench", "--why", "w", "--pipeline", "none", needle="needs --pipeline")
        self.refused("update", "--id", "gamma", "--status", "settled", "--pipeline", "none", needle="needs --pipeline")
        rc, _, err = self.root("add", "--name", "X", "--id", "x", "--access", "house", "--status", "idea", "--why", "w", "--pipeline", "none")
        self.assertEqual(rc, 0, err)  # an idea may say none
        self.write_map(MAP + "- **Zed** · id: zed · access: house · status: settled · aka: none · pipeline: none · why: w\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = pipeline.main(["check", "--config", self.cfg, self.map])
        self.assertEqual(rc, 1)
        self.assertIn("pointer-missing: zed", out.getvalue())

    def test_dropped_needs_no_pointer_and_settled_needs_pipeline(self):
        rc, _, err = self.root("add", "--name", "X", "--id", "x", "--access", "none", "--status", "dropped", "--why", "w")
        self.assertEqual(rc, 0, err)
        self.refused("add", "--name", "Y", "--id", "y", "--access", "public", "--status", "settled", "--why", "w", needle="needs --pipeline")
        rc, _, err = self.root("add", "--name", "Y", "--id", "y", "--access", "public", "--status", "settled", "--why", "w",
                               "--pipeline", "beta/PIPELINE.md")
        self.assertEqual(rc, 0, err)

    def test_update_access(self):
        rc, _, err = self.root("update", "--id", "alpha", "--access", "going-public")
        self.assertEqual(rc, 0, err)
        self.assertIn("- **Alpha** · id: alpha · access: going-public · status: workbench", self.text())
        # an old line gains the tag in front of status
        rc, _, err = self.root("update", "--id", "old", "--access", "house")
        self.assertEqual(rc, 0, err)
        self.assertIn("- **Old** · id: old · access: house · status: building", self.text())

    def test_old_lines_stay_readable_and_inventory_clean(self):
        self.assertEqual(self.problems_none(), [])

    def test_check_counts_the_workbench_across_map_files(self):
        def mapfile(name, ids):
            path = os.path.join(self.tmp, name)
            Path(path).write_text("# Root\n\n" + "".join(
                "- **%s** · id: %s · access: house · status: workbench · aka: none · pipeline: alpha/PIPELINE.md · why: w\n" % (i, i) for i in ids))
            return path
        a, b = mapfile("a.md", ["a1", "a2"]), mapfile("b.md", ["b1", "b2"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = pipeline.main(["check", "--config", self.cfg, a, b])
        self.assertEqual(rc, 1)
        self.assertIn("workbench-over-limit: 4 on the workbench, limit 3", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.main(["check", "--config", self.cfg, a]), 0)


if __name__ == "__main__":
    unittest.main()
