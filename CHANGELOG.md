# Changelog

## 0.4.0

- `work_map.py why <commit|file|file:LINE>` follows a commit back to the reasons it exists: the pipeline item in its `Work:` trailer, that item's why, the decisions it rests on (approvals such as `publish-yes...` are left out), its spec and session. An optional `Decision: <slug>` trailer shows that decision directly. A bare id shared by two projects is reported as ambiguous. Read-only; a git refusal exits 2, a target with no committed history exits 1.
- `why` also reads the same links from a local git note (`refs/notes/work-map`, `git notes --ref=work-map add -m "Work: <id>" <sha>`), so public repositories never put them in commit messages; trailer and note values merge.
- Commit trailers `Work:`, `Decision:` and `Session:` documented in the contract, the record format and the skill.

## 0.3.0

- `ships.py add` puts the new line directly under the anchor line `<!-- work-map: newest first -->` when the file has one (appends when it has none; refuses a file with two). A ships file it creates starts with the anchor.
- `decisions.py add --supersedes <old-slug>` marks the replaced decision `SUPERSEDED by <slug>` and writes the new line in one atomic step; the reader gives the old one the status `superseded` (not open) and `--json` carries `superseded_by`.
- `decisions.py query` lists newest first, shows a `[superseded by <slug>]` prefix, and prints `showing N of M; add a term to narrow` whenever it cuts the list.

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
