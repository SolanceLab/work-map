# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# #!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "plugin", "scripts"))
import work_map  # noqa: E402

CONFIG = os.path.join(HERE, "fixtures", "config.json")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = work_map.main(["--config", CONFIG] + list(argv))
    return code, out.getvalue()


def graph():
    sources, base = work_map.load_config(CONFIG)
    records, files, excluded = work_map.load_all(sources, base)
    return records, work_map.build_graph(records)


def by_id(records, id_):
    return [r for r in records if r["id"] == id_]


class ParseTests(unittest.TestCase):
    def test_four_kinds(self):
        records, _ = graph()
        d = by_id(records, "decision:plain-words")[0]
        self.assertEqual((d["date"], d["session"], d["project"]), ("2026-03-05", "a1b2c3d4", "billing"))
        self.assertEqual(d["call"], "Write in plain words")
        self.assertEqual(d["why"], "readers are not engineers")
        p = by_id(records, "pipeline:reports/weekly-digest-email")[0]
        self.assertEqual((p["status"], p["spec"]), ("planned", "specs/digest.md"))
        t = by_id(records, "task:t-14")[0]
        self.assertEqual((t["project"], t["gist"]), ("reports", "Add digest template"))
        s = by_id(records, "ship:reports@v0.4.0")[0]
        self.assertEqual(s["sha"], "9f3c2ab")
        self.assertEqual(by_id(records, "ship:billing@1a2b3c4d5e")[0]["version"], "")

    def test_untagged_indexed_as_unknown(self):
        records, _ = graph()
        d = by_id(records, "decision:untagged-call")[0]
        self.assertEqual((d["project"], d["session"]), ("unknown", "unknown"))
        self.assertEqual(by_id(records, "pipeline:unknown/untagged-idea")[0]["session"], "unknown")


    def test_tasks_under_items_key(self):
        text = json.dumps({"items": [{"id": "7", "title": "t", "decisions": ["unknown"]}]})
        out = work_map.parse_tasks(text, "now.json")
        self.assertEqual([r["id"] for r in out], ["task:7"])

    def test_unknown_in_list_gives_no_link(self):
        self.assertEqual(work_map.csv("[unknown]"), []); self.assertEqual(work_map.csv("a, none"), ["a"])


    def test_from_unknown_gives_no_link_and_kind_is_read(self):
        r = work_map.parse_decision("- 2026-11-09 · session: unknown · applies: [billing] · from: unknown · kind: one-time · bajo-x · Sam (10:00 \"ok\") → done", "D.md")
        self.assertEqual(r["from"], "")
        self.assertNotIn("project:unknown", json.dumps(r))
        self.assertEqual(r["weight"], "one-time")


class LinkTests(unittest.TestCase):
    def links(self, id_):
        records, _ = graph()
        return set(by_id(records, id_)[0]["links"])

    def test_six_links(self):
        self.assertIn(("in-session", "session:a1b2c3d4"), self.links("decision:plain-words"))
        self.assertIn(("applies-to", "project:house"), self.links("decision:plain-words"))
        self.assertIn(("from", "project:billing"), self.links("decision:plain-words"))
        self.assertIn(("belongs-to", "project:reports"), self.links("task:t-14"))
        self.assertIn(("belongs-to", "project:billing"), self.links("pipeline:billing/old-importer"))
        self.assertIn(("depends-on", "decision:keep-csv-export"), self.links("task:t-14"))
        ship = self.links("ship:reports@v0.4.0")
        self.assertIn(("depends-on", "decision:keep-csv-export"), ship)
        self.assertIn(("done-by", "task:t-14"), ship)

    def test_unresolved_kept(self):
        self.assertIn(("depends-on", "unresolved:decision:missing-decision"), self.links("task:t-14"))
        self.assertIn(("done-by", "unresolved:task:t-99"), self.links("ship:reports@v0.4.0"))

    def test_collision_kept(self):
        records, g = graph()
        self.assertEqual(len(by_id(records, "decision:keep-csv-export")), 2)
        self.assertEqual(g[3], {"decision:keep-csv-export": 2})


class TaskRobustnessTests(unittest.TestCase):
    def test_non_list_decisions_excluded_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "t.json"), "w") as fh:
                json.dump([{"id": "a", "title": "x", "decisions": 7}], fh)
            records, files, excluded = work_map.load_all({"decisions": [], "pipeline": [], "tasks": ["t.json"], "ships": []}, d)
        self.assertEqual(records, [])
        self.assertIn("bad content", excluded[0]["reason"])

    def test_duplicate_ids_get_own_lines(self):
        text = '[\n{"id": "dup", "title": "one"},\n{"id": "dup", "title": "two"}\n]'
        recs = work_map.parse_tasks(text, "t.json")
        self.assertEqual([r["source"][1] for r in recs], [2, 3])


class CommandTests(unittest.TestCase):
    def test_index_counts(self):
        code, out = run("index")
        self.assertEqual(code, 0)
        for line in ("decisions: 5", "pipeline: 3", "tasks: 3", "ships: 2"):
            self.assertIn(line, out)

    def test_query(self):
        code, out = run("query", "digest")
        lines = out.strip().splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 2)  # pipeline item and task
        self.assertTrue(lines[0].startswith("pipeline pipeline:reports/weekly-digest-email · reports · planned · "))
        self.assertIn(" · links: ", lines[0])
        self.assertTrue(lines[0].endswith("source: pipeline.md:L1"))

    def test_open(self):
        code, out = run("open", "task:t-14")
        self.assertEqual(code, 0)
        self.assertIn("depends-on -> unresolved:decision:missing-decision", out)
        self.assertIn("linked-from: ship:reports@v0.4.0 (done-by)", out)
        self.assertIn("source: tasks.json:L2", out)
        self.assertEqual(run("open", "task:nope")[0], 1)

    def test_slice_order_and_limit(self):
        _, out = run("slice", "--project", "reports", "--json")
        ids = [i["id"] for i in json.loads(out)]
        self.assertEqual(ids[0], "task:t-14")
        self.assertIn("ship:reports@v0.4.0", ids)
        self.assertNotIn("task:t-16", ids)
        _, out = run("slice", "--project", "reports", "--limit", "2", "--json")
        self.assertEqual(len(json.loads(out)), 4)  # two OWN records, the ship, and one house-wide record
        _, out = run("slice", "--house", "--json")
        self.assertEqual([i["id"] for i in json.loads(out)], ["decision:plain-words"])

    def test_inventory(self):
        code, out = run("inventory")
        self.assertEqual(code, 0)
        self.assertIn("ships: 2 indexed", out)
        self.assertIn("decision:keep-csv-export (2 records)", out)
        self.assertIn("missing-*.md (ships): no file matches", out)
        self.assertIn("unresolved links: 2", out)

    def test_json_shape(self):
        _, out = run("query", "t-14", "--json")
        item = json.loads(out)[0]
        self.assertEqual(set(item), {"kind", "id", "project", "session", "status", "date", "gist", "source", "links"})
        self.assertEqual(item["source"], {"file": "tasks.json", "line": 2})
        inv = json.loads(run("inventory", "--json")[1])
        self.assertEqual(inv["counts"]["task"], 3)

    def test_bad_config_exits_2(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(work_map.main(["--config", f.name, "index"]), 2)
                self.assertEqual(work_map.main(["--config", "/nonexistent.json", "index"]), 2)
        finally:
            os.unlink(f.name)


V2_CONFIG = os.path.join(HERE, "fixtures", "v2", "config.json")


def run_v2(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = work_map.main(["--config", V2_CONFIG] + list(argv))
    return code, out.getvalue()


def graph_v2():
    sources, base = work_map.load_config(V2_CONFIG)
    records, files, excluded = work_map.load_all(sources, base)
    return records, work_map.build_graph(records)


def map_only(text):
    """Load a temporary config that has only a map key; return (records, graph)."""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "m.md"), "w") as fh:
            fh.write(text)
        with open(os.path.join(d, "c.json"), "w") as fh:
            json.dump({"map": ["m.md"]}, fh)
        sources, base = work_map.load_config(os.path.join(d, "c.json"))
        records, _, _ = work_map.load_all(sources, base)
    return records, work_map.build_graph(records)


def run_slice_fixture(*argv, extra_decisions=(), map_text=None):
    decisions = "\n".join(list(extra_decisions) + [
        "- 2026-11-01 · applies: [alpha] · from: alpha · own-call · Sam → Own decision",
        "- 2026-11-02 · applies: [house] · house-one · Sam → House one",
        "- 2026-11-03 · applies: [house] · house-two · Sam → House two",
        "- 2026-11-04 · applies: [house] · house-three · Sam → House three",
        "- 2026-11-05 · applies: [house] · house-four · Sam → House four",
    ]) + "\n"
    pipeline = "\n".join([
        "- **Planned** · project: alpha · status: planned · later",
        "- **Building** · project: alpha · status: building · now",
    ]) + "\n"
    tasks = [
        {"id": "open-task", "title": "Open task", "project": "alpha", "status": "open", "date": "2026-11-10"},
    ]
    ships = "\n".join([
        "2026-10-01 · shipped v1 aaaaaaa · project: alpha",
        "2026-11-09 · shipped v2 bbbbbbb · project: alpha",
    ]) + "\n"
    with tempfile.TemporaryDirectory() as d:
        paths = {"decisions": decisions, "pipeline": pipeline,
                 "tasks": json.dumps(tasks), "ships": ships}
        for kind, contents in paths.items():
            suffix = ".json" if kind == "tasks" else ".md"
            with open(os.path.join(d, kind + suffix), "w") as fh:
                fh.write(contents)
        config = {kind: [kind + (".json" if kind == "tasks" else ".md")] for kind in paths}
        if map_text is not None:
            with open(os.path.join(d, "map.md"), "w") as fh:
                fh.write(map_text)
            config["map"] = ["map.md"]
        config_path = os.path.join(d, "config.json")
        with open(config_path, "w") as fh:
            json.dump(config, fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = work_map.main(["--config", config_path, "slice"] + list(argv) + ["--json"])
    return code, json.loads(out.getvalue())


class SliceProjectTests(unittest.TestCase):
    def test_own_records_come_before_house_records(self):
        _, items = run_slice_fixture("--project", "alpha")
        ids = [item["id"] for item in items]
        first_house = ids.index("decision:house-four")
        self.assertTrue(all(item["project"] == "alpha" for item in items[:first_house]))

    def test_house_records_respect_default_and_explicit_caps(self):
        _, default = run_slice_fixture("--project", "alpha")
        self.assertEqual(len([i for i in default if i["project"] == "house"]), 3)
        _, limited = run_slice_fixture("--project", "alpha", "--house-limit", "1")
        self.assertEqual([i["id"] for i in limited if i["project"] == "house"],
                         ["decision:house-four"])

    def test_only_newest_project_ship_is_appended(self):
        _, items = run_slice_fixture("--project", "alpha")
        self.assertEqual([i["id"] for i in items if i["kind"] == "ship"], ["ship:alpha@v2"])

    def test_slice_opens_with_the_project_map_line(self):
        _, items = run_slice_fixture("--project", "alpha",
                                     map_text="- **Alpha** · id: alpha · status: live · aka: none · why: it runs\n")
        self.assertEqual(items[0]["id"], "project:alpha")
        self.assertEqual([i["id"] for i in items].count("project:alpha"), 1)

    def test_one_time_house_decisions_stay_out_of_project_slices(self):
        _, items = run_slice_fixture("--project", "alpha", extra_decisions=[
            "- 2026-11-09 · applies: [house] · kind: one-time · house-done · Sam → Done once"])
        ids = [i["id"] for i in items]
        self.assertNotIn("decision:house-done", ids)
        self.assertIn("decision:house-four", ids)

    def test_building_pipeline_precedes_planned_and_decision(self):
        _, items = run_slice_fixture("--project", "alpha")
        ids = [i["id"] for i in items]
        self.assertLess(ids.index("pipeline:alpha/building"), ids.index("pipeline:alpha/planned"))
        self.assertLess(ids.index("pipeline:alpha/planned"), ids.index("decision:own-call"))

    def test_house_slice_keeps_previous_newest_first_behavior(self):
        _, items = run_slice_fixture("--house")
        self.assertEqual([i["id"] for i in items], [
            "decision:house-four", "decision:house-three", "decision:house-two", "decision:house-one"])


class PipelineFormatTests(unittest.TestCase):
    def test_1_map_line_becomes_project(self):
        records, _ = graph_v2()
        p = by_id(records, "project:gazeta")[0]
        self.assertEqual((p["kind"], p["project"], p["status"], p["title"]), ("project", "gazeta", "live", "Gazeta daily front page"))
        self.assertEqual(p["aka"], ["wake-up", "daily-paper"])
        self.assertIn("first page she wakes to", p["why"])
        self.assertEqual(p["details"], ["runs every morning from the phone"])
        self.assertEqual(by_id(records, "project:work-map")[0]["aka"], [])

    def test_2_map_line_without_id_uses_name(self):
        records, _ = graph_v2()
        self.assertEqual(len(by_id(records, "project:open-notes-thing")), 1)

    def test_3_decision_alias_resolves_to_project_id(self):
        records, _ = graph_v2()
        links = by_id(records, "decision:paper-first")[0]["links"]
        self.assertIn(("applies-to", "project:gazeta"), links)
        self.assertFalse([t for _, t in links if t.startswith("unresolved:")])

    def test_4_alias_collision_reported_once(self):
        records, g = map_only(
            "- **A** · id: a · status: live · aka: old · why: x\n- **B** · id: b · status: live · aka: old · why: y\n")
        self.assertEqual(len(g[5]), 1)
        self.assertEqual((g[5][0]["type"], g[5][0]["alias"], g[5][0]["kept"]), ("alias-collision", "old", "project:a"))

    def test_5_folder_gives_project_and_id(self):
        records, _ = graph_v2()
        r = by_id(records, "pipeline:gazeta/layout")[0]
        self.assertEqual(r["project"], "gazeta")
        self.assertIn(("belongs-to", "project:gazeta"), r["links"])
        self.assertEqual(len(by_id(records, "pipeline:gazeta/no-id-item")), 1)

    def test_6_decisions_field_links_resolve(self):
        records, _ = graph_v2()
        links = by_id(records, "pipeline:gazeta/layout")[0]["links"]
        self.assertIn(("depends-on", "decision:front-page-rule"), links)
        self.assertIn(("depends-on", "decision:paper-first"), links)
        self.assertEqual(len([1 for t, x in links if t == "depends-on"]), 2)

    def test_7_indented_lines_are_details_not_items(self):
        records, _ = graph_v2()
        r = by_id(records, "pipeline:gazeta/layout")[0]
        self.assertEqual(r["details"], ["a plain detail line", "**bold detail** · with more words"])
        self.assertEqual(len([x for x in records if x["kind"] == "pipeline"]), 2)

    def test_8_old_format_line_unchanged(self):
        r = work_map.parse_pipeline_file(
            "- **Old importer** · project: billing · session: a1 · status: done · Replaced · spec: none\n", "p.md")[0]
        self.assertEqual((r["id"], r["session"], r["status"], r["gist"], r["spec"]),
                         ("pipeline:billing/old-importer", "a1", "done", "Replaced", "none"))

    def test_9_open_shows_why_details_and_items(self):
        code, out = run_v2("open", "pipeline:gazeta/layout")
        self.assertEqual(code, 0)
        self.assertIn("why: first draft of the page", out)
        self.assertIn("spec: specs/layout.md", out)
        self.assertIn("detail: a plain detail line", out)
        code, out = run_v2("open", "project:gazeta")
        self.assertIn("status: live", out)
        self.assertIn("aka: wake-up, daily-paper", out)
        self.assertIn("item: pipeline:gazeta/layout", out)

    def test_11_slice_through_alias(self):
        _, out = run_v2("slice", "--project", "gazeta", "--status", "any", "--json")
        self.assertIn("decision:paper-first", [x["id"] for x in json.loads(out)])

    def test_13_old_name_on_command_line_resolves(self):
        _, out = run_v2("slice", "--project", "wake-up", "--status", "any", "--json")
        self.assertIn("decision:paper-first", [x["id"] for x in json.loads(out)])
        _, out = run_v2("open", "project:wake-up")
        self.assertIn("item: pipeline:gazeta/layout", out)

    def test_10_config_with_only_map_loads(self):
        records, _ = map_only("- **Solo** · id: solo · status: later · aka: none · why: z\n")
        self.assertEqual([r["id"] for r in records], ["project:solo"])


    def test_12_pipeline_id_uses_canonical_project_after_alias(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "projects", "wake-up"))
            with open(os.path.join(d, "m.md"), "w") as fh:
                fh.write("- **Gazeta** · id: gazeta · status: live · aka: wake-up · why: x\n")
            with open(os.path.join(d, "projects", "wake-up", "PIPELINE.md"), "w") as fh:
                fh.write("- **Layout** · id: layout · status: now · Draft\n")
            with open(os.path.join(d, "c.json"), "w") as fh:
                json.dump({"map": ["m.md"], "pipeline": ["projects/*/PIPELINE.md"]}, fh)
            sources, base = work_map.load_config(os.path.join(d, "c.json"))
            records, _, _ = work_map.load_all(sources, base)
            nodes = work_map.build_graph(records)[0]
        self.assertIn("pipeline:gazeta/layout", nodes)
        self.assertNotIn("pipeline:wake-up/layout", nodes)
        self.assertEqual(nodes["pipeline:gazeta/layout"][0]["project"], "gazeta")


class WaitingStatusTests(unittest.TestCase):
    def test_waiting_forms_count(self):
        for status in ("waiting", "waiting-on-sam", "waiting-on-alex", "waiting-on-a-b"):
            self.assertTrue(work_map.is_waiting(status), status)

    def test_other_words_do_not(self):
        for status in ("waitingx", "waiting-", "waiting-on-", "waiting-onsam", "xwaiting", "building", "", None):
            self.assertFalse(work_map.is_waiting(status), status)

    def test_waiting_items_are_open_and_lead_the_slice(self):
        lines = ["- **A** · project: alpha · status: planned · a",
                 "- **B** · project: alpha · status: waiting · b",
                 "- **C** · project: alpha · status: waiting-on-sam · c",
                 "- **D** · project: alpha · status: waiting-on-alex · d",
                 "- **E** · project: alpha · status: waitingx · e"]
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "p.md"), "w") as fh:
                fh.write("\n".join(lines) + "\n")
            with open(os.path.join(d, "c.json"), "w") as fh:
                json.dump({"pipeline": ["p.md"]}, fh)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = work_map.main(["--config", os.path.join(d, "c.json"), "slice",
                                      "--project", "alpha", "--json"])
        ids = [i["id"] for i in json.loads(out.getvalue())]
        self.assertEqual(code, 0)
        self.assertEqual(set(ids[:3]), {"pipeline:alpha/b", "pipeline:alpha/c", "pipeline:alpha/d"})
        self.assertEqual(ids[3], "pipeline:alpha/a")
        self.assertNotIn("pipeline:alpha/e", ids)


if __name__ == "__main__":
    unittest.main()
