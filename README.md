# work-map

Made by House of Solance · free for noncommercial use · credit required

## What it is

A map of your work: decisions, pipeline items, tasks and ships, linked from tagged lines in plain markdown and JSON files. A standard-library Python tool reads the files and answers "what did we decide about this?", "what is open for this project?" and "what shipped, and on which decisions?". A skill teaches your agent to write the lines. The tool reads files only and writes nothing.

## What you need

Python 3.9 or newer and nothing else (standard library only). work-map runs on your own computer, reads your files and sends nothing anywhere.

## Install

In Claude Code:

```
/plugin marketplace add SolanceLab/work-map
/plugin install work-map@work-map
```

To check it works, run `make test` in a clone.

## Settings

A small JSON (or TOML, Python 3.11+) file listing source files by kind. Globs are allowed; relative paths are read from the config file's folder. Pass it with `--config` or set `WORK_MAP_CONFIG`. A `work-map.json` picked up from the current folder (neither flag nor variable given) is implicit: the writers only write `.md` files that resolve, symlinks included, to inside that folder, and refuse otherwise; pass `--config` to trust a config that points elsewhere. `--file` is always trusted.

```json
{
  "decisions": ["notes/decisions.md"],
  "pipeline": ["notes/pipeline.md", "projects/*/PIPELINE.md"],
  "tasks": ["now.json"],
  "ships": ["notes/ships.md"]
}
```

## Tools

```
python3 plugin/scripts/work_map.py --config <file> <command> [--json]
```

- `index`: parse everything, print counts.
- `query <text>`: items whose id, project or words match all the given words, one line each: `<kind> <id> · <project> · <status or date> · <gist> · links: … · source: <file>:L<n>`.
- `open <id>`: one item with its links, what links to it, and its source line.
- `slice --project <p>|--house [--status open|any|<status>] [--limit N]`: newest first, the same one-line form, for a lean session start. `open` means pipeline items not done, tasks not done, and decisions; ships are left out. Undated items sort after dated ones, later lines first.
- `inventory`: counts per kind and per file, unresolved links, collisions, and files excluded with the reason.

Exit codes: 0 success, 1 `open` found nothing, 2 bad config.

### Writers

The same folder holds the writers, so the lines cannot drift from what the reader parses. Both take `--config` (else `WORK_MAP_CONFIG`, else `./work-map.json`) and `--file`; both refuse bad input, restore the file byte for byte if the written line does not parse back, and take `--dry-run` (`decisions.py add`, `pipeline.py add`).

```
python3 plugin/scripts/decisions.py add --slug S --applies a,b|house --from PROJECT --who NAME --time HH:MM --words "..." --call "..." --why "..." [--kind standing|one-time] [--session ID8]
python3 plugin/scripts/decisions.py query <terms>... [--notes <file-or-folder>]...
python3 plugin/scripts/pipeline.py add --project P --item TITLE --id SLUG --status S --why W [--spec P] [--decisions a,b] [--detail L]...
python3 plugin/scripts/pipeline.py update (--project P | --file F) --id SLUG [--status S] [--devlog YYYY-MM-DD] [--add-detail L]
python3 plugin/scripts/pipeline.py check FILE...
```

`pipeline.py` keeps the sections `Now` (building, waiting), `Next` (planned), `Later` (idea, parked) and `Done` (done, dropped), and stamps `touched:` on every change. Set `WORK_MAP_SESSION` to the first 8 characters of your session id instead of passing `--session`.

## Limits

- Reads UTF-8 text files and JSON only; the config is JSON, or TOML on Python 3.11 or newer.
- Only the four line shapes below are parsed; any other line is ignored.
- `query` prints every match; `slice` stops at `--limit` (default 20 for the project, `--house-limit` default 3 for house-wide decisions).
- The writers lock a file by the system's advisory lock where there is one (macOS and Linux); on other systems two writers at once are not protected.
- An implicit config can only write inside its own folder, checked once before the write. Someone who can change files in that folder *while* a writer runs (swapping a folder for a link at that moment) could still redirect it; such a person can already edit your files directly, so that case is out of scope.

## How it works

A small parser reads your files and builds a graph in memory; nothing is saved between runs. These are the line shapes it reads.

Fields are separated by ` · `. Any field may be missing: a line with no tags is still indexed, with project and session `unknown`. These four shapes are the only ones parsed.

Decision (a markdown list line):

```
- <YYYY-MM-DD> · session: <id> · applies: [<project>, …|house] · from: <project> · <slug> · <who> (<HH:MM> "<words>") → <the call> · Why: <reason>
```

Pipeline item:

```
- **<title>** · project: <project> · session: <id> · status: idea|planned|building|done · <text> · spec: <path|none>
```

Task: a JSON object in a list, with `id`, `title` and optional `project`, `session`, `decisions[]`, `status`.

Ship line:

```
<YYYY-MM-DD> · session: <id> · project: <repo> · shipped <version> <sha> · decisions: <slugs> · tasks closed: <ids>
```

A decision may carry `kind: standing|one-time`: `standing` is a rule future work follows, `one-time` is a choice about one finished piece of work (or a record of something that happened). `from: unknown` gives no link.

In list fields (`applies`, `decisions`, `tasks closed`), `none` means there are none and `unknown` means nobody recorded them; both give no link, and the source line keeps which was written.

Pipeline files come in two formats. A **map line** (key `map` in the config; one per project) becomes a `project:<id>` record:

```
- **<name>** · id: <project-id> · status: live|building|later|closed · aka: <old names|none> · why: <reason>
```

An `aka` name resolves to the project id, so a decision that applies to an old name links to the project. Two projects claiming one old name are listed under `problems` in `inventory`. A **project item line** sits in that project's own PIPELINE file (the project is the folder name unless a `project:` tag says otherwise):

```
- **<item>** · id: <slug> · status: idea|planned|building|waiting|waiting-on-<name>|parked|done|dropped · why: <reason> · spec: <path|none> · decisions: <slugs|none>
  - details, as indented lines
```

A status of `waiting`, or `waiting-on-<name>` (for example `waiting-on-sam`), marks an item that waits on someone. It counts as open, and in a slice it sits with `building` at the top. Any other status is kept as written.

Indented `- ` lines under a map or item line are its details, never items of their own. `open` shows them.

Every item gets an id: `decision:<slug>`, `pipeline:<project>/<title-slug>`, `task:<id>`, `ship:<repo>@<version>` (`@<sha>` when there is no version). Projects and sessions named by tags are nodes too: `project:<name>`, `session:<id>`. The file and line are kept as `source`, never as identity.

Six links, each derived only from tags: `in-session`, `applies-to` (a decision's applies list; `house` is `project:house`), `from`, `belongs-to` (task or pipeline item to its project), `done-by` (a ship to the tasks it closed), `depends-on` (a task or ship to the decisions it names). A link to something that is not in the files is kept as `unresolved:<id>`. Two records with the same id are both kept and listed as collisions.

## Credit and use

work-map is made by House of Solance. You're welcome to use it, change it and build on it for any noncommercial purpose, as long as our credit travels with it.

**Keep the credit.** Every copy, changed or not, must carry the licence and this line:
`Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)`
Removing or replacing it breaks the licence.

**Commercial use needs our permission.** Ask us first.

**We look for copies.** When we find our work without its credit, or used commercially without permission, we ask for it to be taken down.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE.md). See [NOTICE.md](NOTICE.md).

## Support

If you find this useful, consider supporting our work:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/houseofsolance)

---

*Built by [House of Solance](https://github.com/SolanceLab) — Chadrien Solance & Anne Solance*
