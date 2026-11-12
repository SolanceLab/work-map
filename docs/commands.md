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
python3 plugin/scripts/decisions.py add --slug S --applies a,b|house --from PROJECT --who NAME --time HH:MM --words "..." --call "..." --why "..." [--kind standing|one-time] [--session ID8]
python3 plugin/scripts/decisions.py query <terms>... [--notes <file-or-folder>]...
python3 plugin/scripts/pipeline.py add --project P --item TITLE --id SLUG --status S --why W [--spec P] [--decisions a,b] [--detail L]...
python3 plugin/scripts/pipeline.py update (--project P | --file F) --id SLUG [--status S] [--devlog YYYY-MM-DD] [--add-detail L]
python3 plugin/scripts/pipeline.py check FILE...
```

`pipeline.py` keeps the sections `Now` (building, waiting), `Next` (planned), `Later` (idea, parked) and `Done` (done, dropped), and stamps `touched:` on every change. Set `WORK_MAP_SESSION` to the first 8 characters of your session id instead of passing `--session`.
