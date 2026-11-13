# work-map record format

The exact line shapes work-map reads, the ids it gives each record and the links it derives. The work-map skill writes these lines for you; this page is for anyone writing them by hand or building on the parser.

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

A decision that a later one replaces carries the field `SUPERSEDED by <new-slug>` directly after its own slug (`… · <old-slug> · SUPERSEDED by <new-slug> · <who> (…`). The reader gives it the status `superseded`, which is not open, and keeps `superseded_by` in `--json`. `decisions.py add --supersedes <old-slug>` writes the mark and the new line in one step.

A log file (a ships file such as `DEVLOG.md`) can opt in to newest first by holding one anchor line, exactly `<!-- work-map: newest first -->` (surrounding spaces ignored). `ships.py add` then puts each new line directly below the anchor; a file with no anchor is appended to, and a file with two or more anchors is refused. A log `ships.py` creates starts `# <project> DEVLOG`, a blank line, the anchor, then the line. Decision files keep their append order and take no anchor.

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
