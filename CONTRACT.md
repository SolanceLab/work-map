# work-map contract

## Doors it offers

| Door | What it answers |
|---|---|
| `python3 plugin/scripts/work_map.py --config <file> index [--json]` | Counts of what was parsed |
| `... query <text> [--json]` | Items matching all the words, with links and source |
| `... open <id> [--json]` | One item, its links, what links to it, its source line |
| `... slice --project <p>\|--house [--status open\|any\|<status>] [--limit N] [--house-limit N] [--json]` | Newest-first open work for one project, or house-wide |
| `... inventory [--json]` | Counts per kind and file, unresolved links, collisions, excluded files |
| `... why <commit\|file\|file:LINE> [--limit N] [--json]` | The reasons behind a commit or file: each commit's Work items, their why, the decisions they rest on (approvals left out), spec and session; DEVLOG lines show first: lines of a configured ships (DEVLOG) file naming the commit's exact short or full sha, and up to 3 lines dated the day of a work item's `devlog:` tag from the DEVLOG.md beside its PIPELINE file |

| `python3 plugin/scripts/decisions.py add ...` | Appends one decision line, parses it back, restores the file on failure |
| `python3 plugin/scripts/decisions.py query <terms>` | Decision lines matching all terms, else the closest |
| `python3 plugin/scripts/ships.py checkpoint\|deviation ...` | Writes one DEVLOG checkpoint (with proof: `--commit` sha, `--ship` version, or `--who/--time/--words`) or one approved deviation directly under the file's one anchor; refuses missing proof, a bad sha or time, an empty field, a newline or " · " in a field, no anchor or two anchors, with the file untouched; reads the line back and restores the file on failure; `--dry-run` writes nothing |
| `python3 plugin/scripts/pipeline.py add\|update\|check ...` | Writes and checks pipeline item lines, stamps `touched:` |
| `python3 plugin/scripts/pipeline.py root add\|update ...` | Writes one root (map) line: `- **<name>** · id: <id> · access: public\|going-public\|house\|none · status: workbench\|waiting\|idea\|settled\|dropped · aka: <old names\|none> · pipeline: <path>\|spec: <path> · why: <reason>`; refuses an unknown access or status, a full workbench, a missing pointer and a pointer to a file that does not exist |

Exit codes: 0 success; 1 `open` found nothing, or `why` found no committed history for its target (untracked or staged file, uncommitted line); 2 bad config, or for `why` a git refusal (git missing, not a repository, unknown commit, no commits yet, folder target, line out of range) or --limit below 1.

## Root lines

A root (map) line is one project or idea. Two tags. `access:` is `public` (others have it), `going-public` (private now, meant for the public), `house` (ours only) or `none` (not built). `status:` is `workbench` (being worked on now, at most `workbench_limit`), `waiting` (known work, not on the bench), `idea` (not started), `settled` (finished, nothing open) or `dropped`. Pointer rule: `workbench`, `waiting` and `settled` carry `pipeline: <path>` (the project's own PIPELINE), `idea` carries `spec: <path>` or `pipeline: <path>`, `none` when there is none, `dropped` needs none; a path is read from the config's folder and must exist. Limit: at most `workbench_limit` (config key, default 3) lines on the workbench, enforced by `pipeline.py root`; `inventory` reports `workbench-over-limit`, `pointer-missing`, `pointer-target-missing`, `access-missing`, `access-invalid`. `workbench` and `waiting` are open, `settled` is not. Older root statuses and lines with no `access:` still read as written.

## Data it owns

The reader writes nothing; `why` only reads git history (log, blame, rev-parse). The writers change only the decision file, `PIPELINE.md` or (for `pipeline.py root`) the root map file they are pointed at (a short lock file goes in the system temp folder).

## Settings and secrets it needs

Named here, never valued.

| Name | What it is |
|---|---|
| `WORK_MAP_CONFIG` | Optional. Path to the config file (else `--config`) |

| `WORK_MAP_SESSION` | Optional. The 8-character session id the decision writer stamps |

No keys, no network, no secrets.

## Commit trailers it reads

Put the links in a LOCAL git note by default: `git notes --ref=work-map add -m "Work: <id>" -m "Session: <id>" <sha>`. Notes stay on this computer; a normal `git push` does not send them; never push `refs/notes/work-map`. `why` reads the note lines `Work:`, `Session:` and `Decision:` (comma separated values, keys in any case) together with any trailers and merges them without duplicates; a trailer `Session` wins over the note's. Put the links in the commit message as trailers ONLY in a repository you know is private. Never in a public repository's commit messages: work names and session ids are private, and a pushed commit message is permanent.

`Work: <pipeline id>` is the main trailer (trailer form, private repositories only). It may appear once or several times, or be comma separated. An id is `<item-id>` or `<project>/<item-id>`, optionally prefixed `pipeline:`. A bare id that two projects share is reported as ambiguous with every candidate, never guessed. `Decision: <slug>` is optional and shows that decision directly under the commit. `Session: <session id>` is optional; the first one is used. Approvals (`publish-yes...`) are never shown, whether an item lists them or a `Decision:` trailer names them. Commits with no Work line (and no non-approval Decision) are counted. This needs git 2.22 or newer.
