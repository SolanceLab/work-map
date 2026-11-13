# work-map commands

Every command and flag of the reader and the writers. The work-map skill runs these for you; this page is for running them by hand.

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
python3 plugin/scripts/decisions.py add --slug S --applies a,b|house --from PROJECT --who NAME --time HH:MM --words "..." --call "..." --why "..." [--kind standing|one-time] [--session ID8] [--supersedes OLD-SLUG]
python3 plugin/scripts/decisions.py query <terms>... [--notes <file-or-folder>]... [--decision-words <regex>]...
python3 plugin/scripts/pipeline.py add --project P --item TITLE --id SLUG --status S --why W [--spec P] [--decisions a,b] [--detail L]...
python3 plugin/scripts/pipeline.py update (--project P | --file F) --id SLUG [--status S] [--devlog YYYY-MM-DD] [--add-detail L]
python3 plugin/scripts/pipeline.py check FILE...
python3 plugin/scripts/ships.py add --project P --version V --sha SHA [--decisions a,b|none] [--tasks t1,t2|none] [--date YYYY-MM-DD] [--session ID8] [--file F]
```

`--supersedes OLD-SLUG` marks the old decision `SUPERSEDED by <slug>` in the same file as the new line, in one atomic write. It refuses (exit 2, nothing written) when the old slug is missing, appears more than once, is already superseded, lives only in another of the config's decision files, or equals `--slug`; `--dry-run` prints both lines.

`decisions.py query` lists exact matches newest date first (later line first within a file, config order across files at the same date, undated `--notes` lines last). A superseded decision keeps its place with a `[superseded by <slug>]` prefix. At most 25 exact matches, or 15 closest matches, print; when the list is cut, the last line reads `showing N of M; add a term to narrow`.

`--decision-words` (repeatable) adds a Python regex for the lines of `--notes` files that mark a decision, on top of the built-in words; the config key `decision_words` does the same, and a regex that does not compile is refused with exit 2.

`ships.py add` writes one ship line to the config's `ships` file (the one in a folder named like the project, else the only one; `./DEVLOG.md` with no config), and refuses a second line for the same project and version. The line goes directly under the anchor `<!-- work-map: newest first -->` when the file has exactly one; with no anchor it is appended; with two or more the command is refused (exit 2) and the file is left alone. A file the command creates starts with the heading, a blank line and the anchor. A plugin hook (`plugin/hooks/ship_reminder.py`) reminds the AI to run it after `gh release create`, `git tag vX.Y.Z` or a tag push; it never blocks, and `WORK_MAP_SHIP_REMINDER=0` turns it off.

`pipeline.py` keeps the sections `Now` (building, waiting), `Next` (planned), `Later` (idea, parked) and `Done` (done, dropped), and stamps `touched:` on every change. Set `WORK_MAP_SESSION` to the first 8 characters of your session id instead of passing `--session`.
