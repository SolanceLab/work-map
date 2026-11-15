# Changelog

## Unreleased

- `decisions.py query` never cuts a match silently: when more lines match than it prints in full (25 exact, 15 closest), it names every remaining one as `<file>:<line> <slug>` under `also matching (N more):`, before the `showing N of M` line. Live standing decisions that apply to `house` print first among exact matches.

## 0.5.1

- `ships.py yes`: a publish yes is a DEVLOG line. `ships.py yes --project P --tag T --who NAME --time HH:MM --words W [--repo R] [--note N]` writes `- <date> · session: <id> · project: <P> · publish-yes <R> <T> · yes: <NAME> (<HH:MM> "<W>")[ · <N>]` under the anchor (`--repo` defaults to the project), refuses a second yes for the same repo and tag, and the reader never reads a yes line as a ship nor shows it in why.

## 0.5.0

- `ships.py checkpoint` and `ships.py deviation` write the DEVLOG's two other line kinds under the one anchor, with proof (a commit sha, a ship version, or the user's words with who and time) and refuse a missing proof, bad sha or time, empty field, newline or " · " in a field, and a file with no anchor or two (file untouched). `why` finds a checkpoint by its commit sha. A work item's `devlog:` date that is not a real date (2026-02-31) no longer matches any DEVLOG line.
- Root (map) lines take a pointer tag: `pipeline: <path>` (a project's own PIPELINE) or `spec: <path>` (an idea's spec or plan page); `open project:<id>` prints it.
- A root line carries two tags. `access:` is `public` (others have it), `going-public` (private now, meant for the public), `house` (ours only) or `none` (not built). `status:` is `workbench` (being worked on now), `waiting` (known work, not on the bench), `idea` (not started), `settled` (finished, nothing open) or `dropped`. Older statuses (`live`, `building`, `later`, `closed`...) and lines with no `access:` still read as written. `workbench` and `waiting` count as open; `settled` does not. `open project:<id>` prints `access:`.
- At most `workbench_limit` (config key, default 3) root lines may be on the workbench. Pointer rule: `workbench`, `waiting` and `settled` need `pipeline:`; `idea` needs `spec:` or `pipeline:`; `dropped` needs none. `inventory` reports `workbench-over-limit`, `pointer-missing`, `pointer-target-missing`, `access-missing` and `access-invalid` under problems.
- `pipeline.py root add|update` writes root lines (`add` requires `--access`, `update` takes it) and refuses a wrong access or status, a full workbench, a missing pointer or a pointer to a file that does not exist; `pipeline.py check` also checks root lines. The skill tells the AI to write root lines only this way.
- `why` reads the DEVLOG first: every commit shows, before its work item and decisions, the lines of the configured `ships` files that name its exact 7-character or full sha (`devlog: <file>:L<n> · <text>`), and up to 3 lines dated the day of a work item's `devlog: <YYYY-MM-DD>` tag, found in the DEVLOG.md beside that item's PIPELINE file (`devlog (work item <id>): ...`). A commit with only DEVLOG hits is shown and not counted as "without a Work line or DEVLOG mention"; `--json` carries a `devlog` list (each hit has `source`, `line`, `text`, `via`) on each commit.
- Docs: `git config notes.rewriteRef refs/notes/work-map` keeps local notes through amend and rebase.

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
