# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# #!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "scripts"))
import pipeline


FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "writers", "PIPELINE.md")
STAMP = "2026-11-10 20:57"


class PipelineTouchedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pipeline_file = os.path.join(self.tmp, "PIPELINE.md")
        shutil.copy(FIXTURE, self.pipeline_file)

    def run_cmd(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                mock.patch.object(pipeline, "now_stamp", return_value=STAMP):
            result = pipeline.main(list(argv))
        return result, stdout.getvalue(), stderr.getvalue()

    def item_line(self, slug):
        with open(self.pipeline_file, encoding="utf-8") as handle:
            return next(line for line in handle.read().splitlines() if "id: %s " % slug in line)

    def test_add_writes_touched_last_with_patched_time(self):
        result, _, error = self.run_cmd(
            "add", "--project", "demo", "--file", self.pipeline_file,
            "--item", "New", "--id", "new", "--status", "planned", "--why", "needed",
        )
        self.assertEqual(result, 0, error)
        self.assertTrue(self.item_line("new").endswith(" · touched: " + STAMP))

    def test_update_without_touched_adds_it(self):
        result, _, error = self.run_cmd(
            "update", "--file", self.pipeline_file, "--id", "idea-thing", "--status", "parked",
        )
        self.assertEqual(result, 0, error)
        self.assertTrue(self.item_line("idea-thing").endswith(" · touched: " + STAMP))

    def test_update_replaces_existing_touched_once(self):
        with open(self.pipeline_file, encoding="utf-8") as handle:
            text = handle.read()
        text = text.replace(
            " · decisions: none\n  - first detail",
            " · decisions: none · touched: 2026-01-01 01:02\n  - first detail",
            1,
        )
        with open(self.pipeline_file, "w", encoding="utf-8") as handle:
            handle.write(text)
        result, _, error = self.run_cmd(
            "update", "--file", self.pipeline_file, "--id", "building-thing", "--devlog", "2026-11-10",
        )
        self.assertEqual(result, 0, error)
        line = self.item_line("building-thing")
        self.assertEqual(line.count("touched:"), 1)
        self.assertTrue(line.endswith(" · touched: " + STAMP))

    def test_add_detail_alone_refreshes_touched(self):
        with open(self.pipeline_file, encoding="utf-8") as handle:
            text = handle.read()
        text = text.replace(
            " · decisions: none\n  - first detail",
            " · decisions: none · touched: 2026-01-01 01:02\n  - first detail",
            1,
        )
        with open(self.pipeline_file, "w", encoding="utf-8") as handle:
            handle.write(text)
        result, _, error = self.run_cmd(
            "update", "--file", self.pipeline_file, "--id", "building-thing", "--add-detail", "new detail",
        )
        self.assertEqual(result, 0, error)
        self.assertTrue(self.item_line("building-thing").endswith(" · touched: " + STAMP))
        with open(self.pipeline_file, encoding="utf-8") as handle:
            self.assertIn("  - new detail\n", handle.read())

    def test_check_rejects_malformed_touched_and_accepts_good_value(self):
        with open(self.pipeline_file, encoding="utf-8") as handle:
            good = handle.read().replace(" · decisions: none", " · decisions: none · touched: " + STAMP)
        with open(self.pipeline_file, "w", encoding="utf-8") as handle:
            handle.write(good)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(pipeline.check([self.pipeline_file]), 0)
        with open(self.pipeline_file, "w", encoding="utf-8") as handle:
            handle.write(good.replace(STAMP, "2026/11/10 20:57", 1))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(pipeline.check([self.pipeline_file]), 1)
        self.assertIn("malformed touched", output.getvalue())


if __name__ == "__main__":
    unittest.main()
