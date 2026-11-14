# work-map contract

## Doors it offers

| Door | What it answers |
|---|---|
| `python3 plugin/scripts/work_map.py --config <file> index [--json]` | Counts of what was parsed |
| `... query <text> [--json]` | Items matching all the words, with links and source |
| `... open <id> [--json]` | One item, its links, what links to it, its source line |
| `... slice --project <p>\|--house [--status open\|any\|<status>] [--limit N] [--house-limit N] [--json]` | Newest-first open work for one project, or house-wide |
| `... inventory [--json]` | Counts per kind and file, unresolved links, collisions, excluded files |
| `... why <commit\|file\|file:LINE> [--limit N] [--json]` | The reasons behind a commit or file: each commit's Work items, their why, the decisions they rest on (approvals left out), spec and session |

| `python3 plugin/scripts/decisions.py add ...` | Appends one decision line, parses it back, restores the file on failure |
| `python3 plugin/scripts/decisions.py query <terms>` | Decision lines matching all terms, else the closest |
| `python3 plugin/scripts/pipeline.py add\|update\|check ...` | Writes and checks pipeline item lines, stamps `touched:` |

Exit codes: 0 success; 1 `open` found nothing, or `why` found no committed history for its target (untracked or staged file, uncommitted line); 2 bad config, or for `why` a git refusal (git missing, not a repository, unknown commit, no commits yet, folder target, line out of range) or --limit below 1.

## Data it owns

The reader writes nothing; `why` only reads git history (log, blame, rev-parse). The writers change only the decision file or `PIPELINE.md` they are pointed at (a short lock file goes in the system temp folder).

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
