# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0.
import json, os, subprocess, sys, unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "plugin" / "hooks" / "ship_reminder.py"


def hook(stdin, env=None):
    e = dict(os.environ)
    e.pop("WORK_MAP_SHIP_REMINDER", None)
    e.update(env or {})
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, env=e)


def cmd(c):
    return json.dumps({"tool_input": {"command": c}})


class Reminder(unittest.TestCase):
    def test_releases_remind(self):
        for c, v in (("gh release create v1.2.3 --notes x", "v1.2.3"), ("git tag v1.2.3", "v1.2.3"),
                     ("git tag -a 1.2.3 -m msg", "1.2.3"), ("git push origin v1.2.3", "v1.2.3"),
                     ("git push --tags", ""), ("git -C /tmp/r tag v3.0.0", "v3.0.0"), ("git -c user.name=x push origin v3.1.0", "v3.1.0"), ("git add . && git tag v2.0.0", "v2.0.0"), ('git tag "v1.2.3"', "v1.2.3"), ("git push origin 'v4.0.0'", "v4.0.0")):
            r = hook(cmd(c))
            self.assertEqual(r.returncode, 0)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "PostToolUse")
            self.assertIn("ships.py add", out["additionalContext"])
            if v:
                self.assertIn(v, out["additionalContext"], c)

    def test_quiet_cases(self):
        for c in ("git status", "git tag -l", "git tag nightly", "git tag -v v1.2.3", "git push --delete origin v1.2.3",
                  "git push origin :refs/tags/v1.2.3", "git push --dry-run --tags", "git push -n origin v1.2.3", "git tag -d v1.2.3", "git push origin main", "ls", "echo 'foo; git tag v1.2.3 ; bar'", 'echo "a && gh release create v1.0.0"', "echo 'unbalanced"):
            r = hook(cmd(c))
            self.assertEqual((r.returncode, r.stdout), (0, ""), c)
        for stdin in ("not json", "{}", '{"tool_input":{"command":5}}', ""):
            r = hook(stdin)
            self.assertEqual((r.returncode, r.stdout), (0, ""), stdin)

    def test_off_switch(self):
        r = hook(cmd("gh release create v9.9.9"), {"WORK_MAP_SHIP_REMINDER": "0"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
