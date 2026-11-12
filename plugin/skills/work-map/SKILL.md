---
name: work-map
description: Write decisions, pipeline items, tasks and ship lines in the tagged shapes work-map can read. Use when the user makes a decision, has a new idea or plan, opens or closes a task, or ships something, and when starting a session that should load what is open.
---

# work-map

work-map links your work from plain lines. Write each line in exactly one of the four shapes below, separated by ` · ` (space, middle dot, space). Use the writer commands below for decisions, pipeline items and ship lines: they refuse bad input, never duplicate, and check what they wrote. Any tag may be left out: the line is still indexed, with project and session shown as `unknown`. Tags only link things when they are filled in, so fill in what you know.

## Session id

Use the first 8 characters of your own session id as `<id>`. Use the same one on every line you write in that session.

## Update, do not duplicate

When the line already exists (same decision slug, same pipeline title and project, same task id, same repo and version), change that line in place. Two lines with the same id are reported as a collision.

## How: the writer commands

Run them with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>`. The config is `--config <file>`, else `$WORK_MAP_CONFIG`, else `./work-map.json`. Set `WORK_MAP_SESSION` to your 8-character session id once, or pass `--session`.

Add a decision (appends one line to the first decision file in the config, or `--file`; `--dry-run` shows the line without writing):

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/decisions.py add --slug keep-csv-export --applies billing,reports --from billing --who Sam --time 14:05 --words "keep the CSV" --call "CSV export stays in v2" --why "three clients import it" [--kind standing|one-time]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/decisions.py query keep csv
```

`query` checks what is already decided before you ask the user again.

Add or change a pipeline item in a project's `PIPELINE.md` (the project is the folder name; the config's `map` aka list resolves old names). `add` stamps `touched:`; `update` moves the item to the right section (`Now` for building and any waiting status, `Next` for planned, `Later` for idea and parked, `Done` for done and dropped):

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline.py add --project reports --item "Weekly digest email" --id weekly-digest --status planned --why "clients ask for a Monday summary" [--spec specs/digest.md] [--decisions keep-csv-export] [--detail "a note"]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline.py update --project reports --id weekly-digest --status building
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline.py update --project reports --id weekly-digest --status done --devlog 2026-03-09
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline.py check reports/PIPELINE.md
```

Statuses: idea, planned, building, waiting (or `waiting-on-<name>`), parked, done, dropped. `done` needs `--devlog <date>`; `dropped` needs `--add-detail` saying why. `--decisions` slugs must already exist in the decision files.

Write a ship line (appends to the project's ships file, or `--file`; `--dry-run` shows the line without writing):

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ships.py add --project reports --version v0.4.0 --sha 9f3c2ab --decisions keep-csv-export --tasks t-14,t-15
```

Tasks have no writer: write them by hand in the shape below.

## 1. Decision

Write one when the user makes a call. Keep their words and the reason.

Template (a markdown list line):

`- <YYYY-MM-DD> · session: <id> · applies: [<project>, …|house] · from: <project> · <slug> · <who> (<HH:MM> "<words>") → <the call> · Why: <reason>`

Example:

`- 2026-03-02 · session: a1b2c3d4 · applies: [billing, reports] · from: billing · keep-csv-export · Sam (14:05 "keep the CSV, people use it") → CSV export stays in v2 · Why: three clients import it into their sheets`

Use `applies: [house]` for a decision that holds across every project. The slug is short, lowercase, with hyphens.

## 2. Pipeline item

Write one for an idea, a plan or a build in progress.

Template:

`- **<title>** · project: <project> · session: <id> · status: idea|planned|building|done · <text> · spec: <path|none>`

Example:

`- **Weekly digest email** · project: reports · session: a1b2c3d4 · status: planned · Send a Monday summary of last week's exports · spec: specs/digest.md`

Move the same line through the statuses as the work moves.

## 3. Task

Tasks are JSON objects in a list (a file like `now.json`). Required: `id`, `title`. Optional: `project`, `session`, `decisions` (slugs this task rests on), `status` (`open` unless you write `done`).

Example:

`{"id": "t-14", "title": "Add digest template", "project": "reports", "session": "a1b2c3d4", "decisions": ["keep-csv-export"]}`

## 4. Ship line

Write one each time something is released.

Template:

`<YYYY-MM-DD> · session: <id> · project: <repo> · shipped <version> <sha> · decisions: <slugs> · tasks closed: <ids>`

Example:

`2026-03-09 · session: a1b2c3d4 · project: reports · shipped v0.4.0 9f3c2ab · decisions: keep-csv-export · tasks closed: t-14, t-15`

Write it with `ships.py add` (above): it checks the shape and refuses a second line for the same project and version. A quiet hook reminds you after a release command; turn it off with `WORK_MAP_SHIP_REMINDER=0`.

Separate several slugs or ids with commas.

## Reading it back

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/work_map.py --config <config> slice --project <p> --limit 10` shows the newest open items for one project (use `--house` for house-wide decisions) so a session can start lean. `query <text>` finds items by id, project or words; `open <id>` shows one item with all its links.
