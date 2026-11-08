# work-map contract

## Doors it offers

| Door | What it answers |
|---|---|
| `python3 plugin/scripts/work_map.py --config <file> index [--json]` | Counts of what was parsed |
| `... query <text> [--json]` | Items matching all the words, with links and source |
| `... open <id> [--json]` | One item, its links, what links to it, its source line |
| `... slice --project <p>\|--house [--status open\|any\|<status>] [--limit N] [--house-limit N] [--json]` | Newest-first open work for one project, or house-wide |
| `... inventory [--json]` | Counts per kind and file, unresolved links, collisions, excluded files |

| `python3 plugin/scripts/decisions.py add ...` | Appends one decision line, parses it back, restores the file on failure |
| `python3 plugin/scripts/decisions.py query <terms>` | Decision lines matching all terms, else the closest |
| `python3 plugin/scripts/pipeline.py add\|update\|check ...` | Writes and checks pipeline item lines, stamps `touched:` |

Exit codes: 0 success, 1 `open` found nothing, 2 bad config.

## Data it owns

The reader writes nothing. The writers change only the decision file or `PIPELINE.md` they are pointed at (a short lock file goes in the system temp folder).

## Settings and secrets it needs

Named here, never valued.

| Name | What it is |
|---|---|
| `WORK_MAP_CONFIG` | Optional. Path to the config file (else `--config`) |

| `WORK_MAP_SESSION` | Optional. The 8-character session id the decision writer stamps |

No keys, no network, no secrets.
