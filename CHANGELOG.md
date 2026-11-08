# Changelog

## 0.1.0 - 2026-11-11

- First version: `work_map.py` reads tagged decision, pipeline, task and ship lines from plain files and links them (in-session, applies-to, from, belongs-to, done-by, depends-on).
- Commands: `index`, `query`, `open`, `slice`, `inventory`; `--json` on each. Reads files only.
- Skill `work-map` teaches an agent to write the lines.
- Status `waiting` and `waiting-on-<name>` both count as waiting.
- Writers: `decisions.py` (add, query) and `pipeline.py` (add, update, check) ship with the reader so the line format cannot drift.
