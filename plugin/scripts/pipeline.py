#!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""pipeline.py add|update|check — the writer for project PIPELINE.md item lines (the shape work_map.py reads).

Refuses bad input in one line, supports --dry-run, writes, parses the written line back, and restores
the file byte-for-byte on any failure. Python 3.9+, standard library only.
  add    --project ID --item T --id SLUG --status S --why W [--spec P] [--decisions a,b]
         [--worker NAME] [--detail L]... [--file P] [--config C] [--decisions-file P]... [--dry-run]
  update (--file P | --project ID) --id SLUG [--status S] [--devlog YYYY-MM-DD] [--add-detail L] [--config C]
  check  FILE...
Status: idea, planned, building, waiting, waiting-on-<name>, parked, done, dropped.
Paths: --config, else $WORK_MAP_CONFIG, else ./work-map.json (its "pipeline", "map" and "decisions"
lists; globs allowed, relative paths read from the config's folder). Without a config, pass --file.
"""
import argparse, contextlib, datetime, glob, hashlib, json, os, re, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # the shared lock sits beside this script
import _writelock
from _writelock import locked, _private_lock_dir, confined
fcntl = _writelock.fcntl

WAITING = re.compile(r"waiting(-on-[a-z0-9][a-z0-9-]*)?")
FIXED = {"idea": "Later", "planned": "Next", "building": "Now", "parked": "Later", "done": "Done", "dropped": "Done"}
STATUSES = ["idea", "planned", "building", "waiting", "waiting-on-<name>", "parked", "done", "dropped"]


def status_ok(status):
    return status in FIXED or bool(WAITING.fullmatch(status or ""))


def section_of(status):
    return "Now" if WAITING.fullmatch(status or "") else FIXED[status]


def default_config():
    return os.environ.get("WORK_MAP_CONFIG") or "work-map.json"


def given_config(arg):
    """The config the user named (--config, else $WORK_MAP_CONFIG), else None."""
    return arg or os.environ.get("WORK_MAP_CONFIG") or None


def strict_decision_files(config):
    """Decision files a config names; refuses when it is unreadable, names none, or matches none."""
    try:
        with open(config, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, UnicodeError, ValueError) as exc:
        raise Refusal("config %s is unreadable or not valid JSON: %s" % (config, exc))
    vals = cfg.get("decisions") if isinstance(cfg, dict) else None
    vals = [vals] if isinstance(vals, str) else vals
    if not isinstance(vals, list) or not vals or not all(isinstance(v, str) for v in vals):
        raise Refusal("config %s names no decisions file (key \"decisions\")" % config)
    found = config_paths(config, "decisions")
    if not found:
        raise Refusal("config %s: no decisions file matches %s" % (config, ", ".join(vals)))
    return found


def config_paths(config, key):
    """Files the config lists under key, globs expanded, relative paths read from the config's folder."""
    try:
        with open(config, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return []
    base = os.path.dirname(os.path.abspath(config))
    vals = cfg.get(key, []) if isinstance(cfg, dict) else []
    vals = [vals] if isinstance(vals, str) else vals
    out = []
    for v in vals:
        pat = v if os.path.isabs(v) else os.path.join(base, v)
        out += sorted(glob.glob(pat, recursive=True))
    return out
HEADING = re.compile(r"^## (.*?)\s*$")
SECTIONS = ["Now", "Next", "Later", "Done"]
ITEM = re.compile(r"^- \*\*(?P<item>.+?)\*\* · (?P<rest>.*)$")
KEYS = ["id", "project", "worker", "status", "why", "spec", "decisions", "devlog", "touched"]


class Refusal(Exception):
    pass


def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def parse_item_line(line):
    """Item line -> {'item', <field>...} or None. A part without a known key continues the previous value."""
    m = ITEM.match(line)
    if not m:
        return None
    out, last = {"item": m.group("item")}, None
    for part in m.group("rest").split(" · "):
        km = re.match(r"^(%s): (.*)$" % "|".join(KEYS), part)
        if km and km.group(1) not in out:
            last = km.group(1)
            out[last] = km.group(2)
        elif last:
            out[last] += " · " + part
        else:
            return None
    return out


def format_line(f):
    parts = ["id: " + f["id"]] if f.get("id") else []
    if f.get("project"):
        parts.append("project: " + f["project"])
    if f.get("worker"):
        parts.append("worker: " + f["worker"])
    parts += ["%s: %s" % (k, f[k]) for k in ("status", "why", "spec", "decisions", "devlog", "touched") if k in f and f[k] != ""]
    return "- **%s** · %s" % (f["item"], " · ".join(parts))


def item_id(line):
    m = re.search(r" · id: ([^ ]+?)(?: · |$)", line) if ITEM.match(line) else None
    return m.group(1) if m else None


def find_block(lines, slug):
    """(start, end) of the item with this id: its line plus indented detail lines; None if absent."""
    for i, l in enumerate(lines):
        if item_id(l) == slug:
            j = i + 1
            while j < len(lines) and re.match(r"^\s+\S", lines[j]):  # any indented non-blank line belongs to the item
                j += 1
            return i, j
    return None


def section_at(lines, idx):
    cur = None
    for l in lines[:idx + 1]:
        m = HEADING.match(l)
        if m:
            cur = m.group(1)
    return cur


def insert_block(lines, section, block):
    """Insert at the end of the section; create the heading in order Now, Next, Later, Done if missing."""
    heads = {HEADING.match(l).group(1): i for i, l in enumerate(lines) if HEADING.match(l)}
    if section in heads:
        h = heads[section]
        e = next((i for i in range(h + 1, len(lines)) if HEADING.match(lines[i])), len(lines))
        last = max([i for i in range(h + 1, e) if lines[i].strip()] or [h])
        ins = block if last > h else [""] + block
        lines[last + 1:last + 1] = ins
        after = last + 1 + len(ins)
        if after < len(lines) and HEADING.match(lines[after]):
            lines.insert(after, "")
        return lines
    later = [heads[s] for s in SECTIONS[SECTIONS.index(section) + 1:] if s in heads]
    if later:
        lines[min(later):min(later)] = ["## " + section, ""] + block + [""]
        return lines
    while lines and lines[-1] == "":
        lines.pop()
    return lines + ["", "## " + section, ""] + block + [""]


def decision_slugs_ok(slugs, files):
    text = ""
    for p in files:
        try:
            text += open(p, encoding="utf-8").read() + "\n"
        except OSError:
            pass
    for s in slugs:
        if not re.search(r"^- \d{4}-\d{2}-\d{2} .* · " + re.escape(s) + r" · ", text, re.M):
            raise Refusal("decision slug not found in the decision files: " + s)


def implicit_base(arg):
    """The config's own folder when the config is implicit (neither --config nor $WORK_MAP_CONFIG), else None."""
    if given_config(arg):
        return None
    return os.path.dirname(os.path.abspath("work-map.json")) if os.path.isfile("work-map.json") else os.getcwd()


def confine_or_refuse(paths, base):
    if base is None:
        return
    for p in paths:
        problem = confined(p, base)
        if problem:
            raise Refusal(problem)


def resolve_file(project, config_path):
    if not os.path.isfile(config_path):
        raise Refusal("no PIPELINE for %s; pass --file (config unreadable: %s)" % (project, config_path))
    pid = project
    for mp in config_paths(config_path, "map"):
        try:
            with open(mp, encoding="utf-8") as fh:
                mlines = fh.readlines()
            for l in mlines:
                m = re.search(r" · id: ([^ ]+) · .*? · aka: (.*?) · ", l)
                if m and pid in [a.strip() for a in m.group(2).split(",")]:
                    pid = m.group(1)
        except OSError:
            pass
    for p in config_paths(config_path, "pipeline"):
        if os.path.basename(os.path.dirname(p)) == pid:
            return p, pid
    raise Refusal("no PIPELINE for %s; pass --file" % project)


def no_reserved(**fields):
    for k, v in fields.items():
        vals = v if isinstance(v, list) else [v]
        for x in vals:
            if isinstance(x, str) and ("\n" in x or "\r" in x or " · " in x):
                raise Refusal("%s contains a newline or reserved delimiter" % k)


def read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def to_text(original):
    """Bytes -> text with LF newlines (CRLF files are worked on as LF and written back as CRLF)."""
    return original.decode("utf-8").replace("\r\n", "\n")


def atomic_write(path, data):
    """Write data to a temp file in the same folder (0600, then the original's mode), fsync, os.replace onto path."""
    folder = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".work-map-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except FileNotFoundError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def restore_original(path, original):
    """Put the original bytes back atomically (or remove a file that did not exist); loud, with a backup, if even that fails."""
    try:
        if original is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            try:
                with open(path, "rb") as fh:
                    if fh.read() == original:
                        return True  # the write never reached the target: nothing to put back
            except FileNotFoundError:
                pass
            atomic_write(path, original)
        return True
    except OSError as exc:
        backup = path + ".work-map-backup"
        try:
            with open(backup, "wb") as fh:
                fh.write(original or b"")
            where = "the original is saved beside it as " + backup
        except OSError:
            where = "the original could NOT be saved; take it from your own backup"
        print("RESTORE FAILED (%s): %s is now the new content; %s" % (exc, path, where), file=sys.stderr)
        return False


def commit(path, original, new_text, expect):
    """Write atomically, parse back via expect(lines); restore the original atomically on any failure."""
    path = os.path.realpath(path)
    if original is not None and b"\r\n" in original:
        new_text = new_text.replace("\n", "\r\n")
    try:
        atomic_write(path, new_text.encode("utf-8"))
        with open(path, encoding="utf-8") as f:
            ok = expect(f.read().split("\n"))
        if not ok:
            raise ValueError("written line failed parse-back")
    except BaseException as exc:  # any failure after the write puts the original bytes back
        restored = restore_original(path, original)
        if not isinstance(exc, Exception):
            raise
        print("failed: %s" % exc, file=sys.stderr)
        return 1 if restored else 3
    return 0


def matches(lines, slug, want, details, section):
    b = find_block(lines, slug)
    if not b:
        return False
    got = parse_item_line(lines[b[0]])
    if got is None or any(got.get(k) != v for k, v in want.items()):
        return False
    if lines[b[0] + 1:b[1]] != details:
        return False
    return section_at(lines, b[0]) == section


def add(argv):
    p = argparse.ArgumentParser(prog="pipeline.py add")
    p.add_argument("--project", required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--spec", default="none")
    p.add_argument("--decisions", default="")
    p.add_argument("--worker")
    p.add_argument("--detail", action="append", default=[])
    p.add_argument("--file")
    p.add_argument("--config")
    p.add_argument("--decisions-file", action="append")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    no_reserved(project=a.project, item=a.item, id=a.id, status=a.status, why=a.why, spec=a.spec,
                decisions=a.decisions, detail=a.detail)
    if not a.why.strip():
        raise Refusal("why is required and cannot be empty")
    if not status_ok(a.status):
        raise Refusal("status must be one of: " + " ".join(STATUSES))
    if not re.fullmatch(r"[a-z0-9-]+", a.id):
        raise Refusal("invalid id (use a-z, 0-9, -)")
    if not a.item.strip() or not a.spec.strip():
        raise Refusal("item and spec cannot be empty")
    slugs = [s.strip() for s in a.decisions.split(",") if s.strip()]
    if slugs:
        cfg_given = given_config(a.config) or ("work-map.json" if os.path.isfile("work-map.json") else None)
        dfiles = a.decisions_file or (strict_decision_files(cfg_given) if cfg_given else ["DECISIONS.md"])
        if not a.decisions_file:
            confine_or_refuse(dfiles, implicit_base(a.config))
        decision_slugs_ok(slugs, dfiles)
    if a.file:
        path, pid = a.file, a.project
    else:
        path, pid = resolve_file(a.project, given_config(a.config) or "work-map.json")
    path = os.path.realpath(path)  # resolved once: the same path is checked, locked and written
    if not a.file:
        confine_or_refuse([path], implicit_base(a.config))
    with locked(path):
        original = read_bytes(path)
        if original is None and not a.file:
            raise Refusal("%s does not exist; pass --file to create it" % path)
        text = to_text(original) if original is not None else "# %s — PIPELINE\n" % pid
        lines = text.split("\n")
        if any(item_id(l) == a.id for l in lines):
            raise Refusal("duplicate id: " + a.id)
        f = dict(item=a.item, id=a.id, status=a.status, why=a.why, spec=a.spec,
                 decisions=", ".join(slugs) or "none", touched=now_stamp())
        if os.path.basename(os.path.dirname(os.path.abspath(path))) != pid:
            f["project"] = pid
        if a.worker:
            f["worker"] = a.worker
        section = section_of(a.status)
        block = [format_line(f)] + ["  - " + d for d in a.detail]
        if a.dry_run:
            print("\n".join(block))
            return 0
        new = "\n".join(insert_block(lines, section, block))
        return commit(path, original, new, lambda ls: matches(ls, a.id, f, block[1:], section))


def update(argv):
    p = argparse.ArgumentParser(prog="pipeline.py update")
    p.add_argument("--file")
    p.add_argument("--project")
    p.add_argument("--id", required=True)
    p.add_argument("--status")
    p.add_argument("--devlog")
    p.add_argument("--add-detail", action="append", default=[])
    p.add_argument("--config")
    a = p.parse_args(argv)
    no_reserved(id=a.id, devlog=a.devlog or "", add_detail=a.add_detail)
    if a.status and not status_ok(a.status):
        raise Refusal("status must be one of: " + " ".join(STATUSES))
    if a.status == "done" and not a.devlog:
        raise Refusal("--status done requires --devlog YYYY-MM-DD")
    if a.status == "dropped" and not a.add_detail:
        raise Refusal("--status dropped requires --add-detail (why it died)")
    if a.devlog:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.devlog):
                raise ValueError()
            datetime.date.fromisoformat(a.devlog)
        except ValueError:
            raise Refusal("devlog must be a valid YYYY-MM-DD")
    if a.file:
        path = a.file
    elif a.project:
        path, _ = resolve_file(a.project, given_config(a.config) or "work-map.json")
        confine_or_refuse([path], implicit_base(a.config))
    else:
        raise Refusal("pass --file or --project")
    with locked(path):
        original = read_bytes(path)
        if original is None:
            raise Refusal("no such file: " + path)
        lines = to_text(original).split("\n")
        b = find_block(lines, a.id)
        if not b:
            raise Refusal("unknown id: " + a.id)
        cur = parse_item_line(lines[b[0]])
        if cur is None:
            raise Refusal("item line for %s is not in item format" % a.id)
        if a.status:
            cur["status"] = a.status
        if a.devlog:
            cur["devlog"] = a.devlog
        cur["touched"] = now_stamp()
        want = {k: cur[k] for k in KEYS if k in cur}
        line = format_line(dict(cur))
        # keep the line's own field set; format_line only reorders fields into the house order
        # detail lines move verbatim (original indentation and text); new details append at two spaces
        details = lines[b[0] + 1:b[1]] + ["  - " + d for d in a.add_detail]
        block = [line] + details
        section = section_of(cur["status"])
        if section_at(lines, b[0]) == section:
            lines[b[0]:b[1]] = block
        else:
            del lines[b[0]:b[1]]
            lines = insert_block(lines, section, block)
        new = "\n".join(lines)
        want["item"] = cur["item"]
        return commit(path, original, new, lambda ls: matches(ls, a.id, want, details, section))


def check(files):
    bad = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().split("\n")
        except (OSError, UnicodeError) as exc:
            print("%s: unreadable: %s" % (path, exc))
            bad += 1
            continue
        seen = {}
        for n, l in enumerate(lines, 1):
            if not l.startswith("- **"):
                continue
            f = parse_item_line(l)
            if f is None:
                print("%s:%d: not an item line" % (path, n)); bad += 1; continue
            for k in ("id", "status", "why", "spec", "decisions"):
                if not f.get(k, "").strip():
                    print("%s:%d: missing %s" % (path, n, k)); bad += 1
            if f.get("status") and not status_ok(f["status"]):
                print("%s:%d: bad status %s" % (path, n, f["status"])); bad += 1
            if "touched" in f and not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", f["touched"]):
                print("%s:%d: malformed touched %s" % (path, n, f["touched"])); bad += 1
            if f.get("id"):
                if f["id"] in seen:
                    print("%s:%d: duplicate id %s (first at line %d)" % (path, n, f["id"], seen[f["id"]])); bad += 1
                seen.setdefault(f["id"], n)
    return 1 if bad else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("add", "update", "check"):
        print(__doc__)
        return 0
    try:
        if argv[0] == "check":
            return check(argv[1:])
        return (add if argv[0] == "add" else update)(argv[1:])
    except Refusal as r:
        print("refused: %s" % r, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
