# work-map commands

Every command and flag of the reader and the writers. The work-map skill runs these for you; this page is for running them by hand.

```
python3 plugin/scripts/work_map.py --config <file> <command> [--json]
```

- `index`: parse everything, print counts.
- `query <text>`: items whose id, project or words match all the given words, one line each: `<kind> <id> · <project> · <status or date> · <gist> · links: … · source: <file>:L<n>`.
- `open <id>`: one item with its links, what links to it, and its source line.
- `slice --project <p>|--house [--status open|any|<status>] [--limit N]`: newest first, the same one-line form, for a lean session start. `open` means pipeline items not done, tasks not done, and decisions; ships are left out. Undated items sort after dated ones, later lines first.
- `inventory`: counts per kind and per file, unresolved links, collisions, problems and files excluded with the reason. Problems include the root-line ones: `workbench-over-limit` (more root lines on the workbench than the config's `workbench_limit`, default 3), `pointer-missing`, `pointer-target-missing`, `access-missing` and `access-invalid`.
- `why <commit|file|file:LINE> [--limit N]`: from a commit back to the reasons it exists. The target is resolved in this order: an existing file, then `file:LINE` (through `git blame`), then a folder (refused), then a commit-ish read in the current folder. git is anchored at the file's own folder, so the current folder does not matter for a path. A file shows its history newest first (`git log --follow`, up to `--limit`, default 20). Each commit prints `commit <sha7> · <date> · <subject>`, then any direct `decision:` line from a `Decision:` trailer, then each `Work:` item (`pipeline:<project>/<id> · <title> · <status>`, its `why:`, the decisions it rests on with their `why:`, its `spec:`), then `session:` (the commit's `Session:` trailer, else the item's). Approvals (`publish-yes...`) are skipped. A work item already printed for an earlier commit shows `work: <id> (above)`; an id not in the record shows `(not in the record)`; a bare id shared by two projects shows `(ambiguous: <ids>; write <project>/<id>)`. DEVLOG lines show first, under the commit line, from two paths: lines of a configured `ships` (DEVLOG) file that name the commit's 7-character or full sha as a whole hex token (`devlog: <file>:L<line> · <text>`), and up to 3 lines dated the day in a work item's `devlog: <YYYY-MM-DD>` tag, taken from the DEVLOG.md in the same folder as the item's PIPELINE file (`devlog (work item <id>): ...`; a line the sha path already showed is not repeated). A commit with only DEVLOG hits is shown and not counted. The last line counts commits without a Work line or DEVLOG mention. `--json` gives one object per commit that has a link: `commit`, `date`, `subject`, `work[]` (`id`, `found`, `title`, `status`, `why`, `spec`, `decisions[]`, and `ambiguous[]` only when ambiguous), `decisions[]` (direct Decision trailers) and `session`, `devlog[]` (`source`, `line`, `text`, `via`: `sha` or `work item <id>`; empty when nothing was found). Read-only.

Exit codes: 0 success; 1 `open` found nothing, or `why` found no committed history for its target (untracked or staged file, uncommitted line); 2 bad config, or for `why` a git refusal (git missing, not a repository, unknown commit, no commits yet, folder target, line out of range) or --limit below 1.

### Writers

The same folder holds the writers, so the lines cannot drift from what the reader parses. Both take `--config` (else `WORK_MAP_CONFIG`, else `./work-map.json`) and `--file`; both refuse bad input, restore the file byte for byte if the written line does not parse back, and take `--dry-run` (`decisions.py add`, `pipeline.py add`).

```
python3 plugin/scripts/decisions.py add --slug S --applies a,b|house --from PROJECT --who NAME --time HH:MM --words "..." --call "..." --why "..." [--kind standing|one-time] [--session ID8] [--supersedes OLD-SLUG]
python3 plugin/scripts/decisions.py query <terms>... [--notes <file-or-folder>]... [--decision-words <regex>]...
python3 plugin/scripts/pipeline.py add --project P --item TITLE --id SLUG --status S --why W [--spec P] [--decisions a,b] [--detail L]...
python3 plugin/scripts/pipeline.py update (--project P | --file F) --id SLUG [--status S] [--devlog YYYY-MM-DD] [--add-detail L]
python3 plugin/scripts/pipeline.py check [--config C] FILE...
python3 plugin/scripts/pipeline.py root add --name N --id ID --access public|going-public|house|none --status workbench|waiting|idea|settled|dropped --why W [--aka a,b] [--pipeline PATH | --spec PATH] [--file F] [--dry-run]
python3 plugin/scripts/pipeline.py root update --id ID [--access A] [--status S] [--pipeline PATH] [--spec PATH] [--why W] [--file F] [--dry-run]
python3 plugin/scripts/ships.py add --project P --version V --sha SHA [--decisions a,b|none] [--tasks t1,t2|none] [--date YYYY-MM-DD] [--session ID8] [--file F]
```

`--supersedes OLD-SLUG` marks the old decision `SUPERSEDED by <slug>` in the same file as the new line, in one atomic write. It refuses (exit 2, nothing written) when the old slug is missing, appears more than once, is already superseded, lives only in another of the config's decision files, or equals `--slug`; `--dry-run` prints both lines.

`decisions.py query` lists exact matches newest date first (later line first within a file, config order across files at the same date, undated `--notes` lines last). A superseded decision keeps its place with a `[superseded by <slug>]` prefix. Live standing decisions that apply to `house` (`kind: standing`, `applies: [house]`, not superseded) print before all other exact matches. At most 25 exact matches, or 15 closest matches, print in full; when the list is cut, every remaining match is still named as `<file>:<line> <slug>` under `also matching (N more):`, and the last line reads `showing N of M; add a term to narrow`.

`--decision-words` (repeatable) adds a Python regex for the lines of `--notes` files that mark a decision, on top of the built-in words; the config key `decision_words` does the same, and a regex that does not compile is refused with exit 2.

`ships.py add` writes one ship line to the config's `ships` file (the one in a folder named like the project, else the only one; `./DEVLOG.md` with no config), and refuses a second line for the same project and version. The line goes directly under the anchor `<!-- work-map: newest first -->` when the file has exactly one; with no anchor it is appended; with two or more the command is refused (exit 2) and the file is left alone. A file the command creates starts with the heading, a blank line and the anchor. A plugin hook (`plugin/hooks/ship_reminder.py`) reminds the AI to run it after `gh release create`, `git tag vX.Y.Z` or a tag push; it never blocks, and `WORK_MAP_SHIP_REMINDER=0` turns it off.

`ships.py checkpoint`, `ships.py deviation` and `ships.py yes` write the other DEVLOG line kinds (checkpoints with proof, approved deviations, publish yeses):

```
python3 plugin/scripts/ships.py checkpoint --project P --text T (--commit SHA [--commit SHA2 ...] | --ship VERSION | --who NAME --time HH:MM --words W) [--date YYYY-MM-DD] [--session ID8] [--file F] [--config C] [--dry-run]
python3 plugin/scripts/ships.py deviation --project P --step S --who NAME --time HH:MM --words W --what D --why Y [--date YYYY-MM-DD] [--session ID8] [--file F] [--config C] [--dry-run]
python3 plugin/scripts/ships.py yes --project P --tag T --who NAME --time HH:MM --words W [--repo R] [--note N] [--date YYYY-MM-DD] [--session ID8] [--file F] [--config C] [--dry-run]
```

They pick the target file like `add`, but the file must already hold exactly one anchor: no anchor, two or more anchors, or a missing file is refused (exit 2, one line, nothing written). Only `--file` naming a path that does not exist yet creates a file (heading, blank line, anchor, line). The line goes directly under the anchor, is read back, and the file is restored byte for byte if that fails. A commit sha (7 to 40 hex characters) is written as its first 7, which is what `why` matches. Refused with the file untouched: no proof or more than one kind, a bad sha, a time that is not HH:MM, an empty field, a newline or the separator ` · ` in a field, a double quote in the words, an impossible date. `--dry-run` prints the line and writes nothing.

`pipeline.py root add|update` writes the root (map) line, in the first `map` file of the config (or `--file`; `add` goes after the last root line). It refuses, in one line with nothing written: an access outside public/going-public/house/none; a status outside workbench/waiting/idea/settled/dropped; `workbench` when the workbench already holds `workbench_limit` lines (the message names them); `workbench`, `waiting` or `settled` without `--pipeline` (unless the line already has one; `none` is not enough); `idea` without `--spec` or `--pipeline` (write `none` when there is none); both `--pipeline` and `--spec`; a pointer path that does not exist (read from the config's folder; `none` is exempt); a duplicate id; an unknown id. A new `--pipeline` on `update` replaces the line's `spec` (and the reverse), so an idea can be promoted in one command. A line that still carries an old status (or no `access:` tag) can change its why or pointer without being forced onto the new statuses. `check` also reports the root-line problems of a map file.

`pipeline.py` keeps the sections `Now` (building, waiting), `Next` (planned), `Later` (idea, parked) and `Done` (done, dropped), and stamps `touched:` on every change. Set `WORK_MAP_SESSION` to the first 8 characters of your session id instead of passing `--session`.
