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
- `why <commit|file|file:LINE> [--limit N]`: from a commit back to the reasons it exists. The target is resolved in this order: an existing file, then `file:LINE` (through `git blame`), then a folder (refused), then a commit-ish read in the current folder. git is anchored at the file's own folder, so the current folder does not matter for a path. A file shows its history newest first (`git log --follow`, up to `--limit`, default 20). Each commit prints `commit <sha7> · <date> · <subject>`, then any direct `decision:` line from a `Decision:` trailer, then each `Work:` item (`pipeline:<project>/<id> · <title> · <status>`, its `why:`, the decisions it rests on with their `why:`, its `spec:`), then `session:` (the commit's `Session:` trailer, else the item's). Approvals (`publish-yes...`) are skipped. A work item already printed for an earlier commit shows `work: <id> (above)`; an id not in the record shows `(not in the record)`; a bare id shared by two projects shows `(ambiguous: <ids>; write <project>/<id>)`. The last line counts commits without a Work line. `--json` gives one object per commit that has a link: `commit`, `date`, `subject`, `work[]` (`id`, `found`, `title`, `status`, `why`, `spec`, `decisions[]`, and `ambiguous[]` only when ambiguous), `decisions[]` (direct Decision trailers) and `session`. Read-only.

Exit codes: 0 success; 1 `open` found nothing, or `why` found no committed history for its target (untracked or staged file, uncommitted line); 2 bad config, or for `why` a git refusal (git missing, not a repository, unknown commit, no commits yet, folder target, line out of range) or --limit below 1.

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
