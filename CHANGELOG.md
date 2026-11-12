# Changelog

## 0.2.0

- `decisions.py query` takes `--decision-words REGEX` and a config key `decision_words`, so `--notes` lines can be recognised as decisions by your own marker (the built-in words still apply).
- `ships.py add` writes a ship line in the shape the reader parses, and refuses a second line for the same project and version.
- A quiet release reminder hook asks the AI to write the ship line after a release command; turn it off with `WORK_MAP_SHIP_REMINDER=0`.

## 0.1.1 - 2026-11-11

- `decisions.py query` follows the same folder rule as the writers: a `work-map.json` found in the current folder can only point at `.md` files inside that folder. Pass `--config` to trust one that points elsewhere.

## 0.1.0 - 2026-11-11

- First version: `work_map.py` reads tagged decision, pipeline, task and ship lines from plain files and links them (in-session, applies-to, from, belongs-to, done-by, depends-on).
- Commands: `index`, `query`, `open`, `slice`, `inventory`; `--json` on each. Reads files only.
- Skill `work-map` teaches an agent to write the lines.
- Status `waiting` and `waiting-on-<name>` both count as waiting.
- Writers: `decisions.py` (add, query) and `pipeline.py` (add, update, check) ship with the reader so the line format cannot drift.
