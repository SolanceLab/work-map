#!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""ships.py add — write one ship line (the shape work_map.py reads), once per release.

  add --project P --version V --sha SHA [--decisions a,b|none] [--tasks t1,t2|none]
      [--date YYYY-MM-DD] [--session ID8] [--file F] [--config C] [--dry-run]

Line: <date> · session: <id> · project: <P> · shipped <V> <SHA> · decisions: <slugs> · tasks closed: <ids>
Target file: --file, else the config's "ships" list (--config, else $WORK_MAP_CONFIG, else ./work-map.json):
the one file with a folder named like the project, else the only file listed, else refused.
With no config and no --file: ./DEVLOG.md. A second line for the same project and version is refused.
The session id is --session or $WORK_MAP_SESSION, else "unknown". Python 3.9+, standard library only.
"""
import argparse, datetime, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _writelock import locked, confined
from decisions import atomic_write, restore_original, default_config, ConfigRefused
import work_map


def config_ship_files(config):
    try:
        with open(config, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConfigRefused("config %s is unreadable or not valid JSON: %s" % (config, exc))
    vals = cfg.get("ships") if isinstance(cfg, dict) else None
    vals = [vals] if isinstance(vals, str) else vals
    if not isinstance(vals, list) or not vals or not all(isinstance(v, str) for v in vals):
        raise ConfigRefused("config %s names no ships file (key \"ships\")" % config)
    base = os.path.dirname(os.path.abspath(config))
    out = []
    for v in vals:
        full = v if os.path.isabs(v) else os.path.join(base, v)
        if glob.has_magic(v):
            out += sorted(glob.glob(full, recursive=True))
        else:
            out.append(os.path.normpath(full))  # a literal path may not exist yet: add creates it
    out = list(dict.fromkeys(out))
    if not out:
        raise ConfigRefused("config %s: no ships file matches %s" % (config, ", ".join(vals)))
    return out


def pick_file(files, project, config):
    own = [f for f in files if project in os.path.normpath(f).split(os.sep)[:-1]]
    if len(own) == 1:
        return own[0]
    if len(files) == 1 and not own:
        return files[0]
    raise ConfigRefused("config %s lists several ships files and none (or several) sit in a folder named %s: %s; pass --file"
                        % (config, project, ", ".join(own or files)))


def split_list(value):
    return [p.strip() for p in value.split(",") if p.strip() and p.strip().lower() != "none"]


def bad_field(value):
    return any(c in value for c in "\r\n[]") or " · " in value


def add_command(argv):
    parser = argparse.ArgumentParser(prog="ships.py add")
    for flag in ("project", "version", "sha"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--decisions", default="none")
    parser.add_argument("--tasks", default="none")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    parser.add_argument("--session")
    parser.add_argument("--file")
    parser.add_argument("--config", default=default_config())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", args.sha):
        parser.error("sha must be 7 to 40 hex characters")
    if not args.version.strip() or re.search(r"\s", args.version) or bad_field(args.version):
        parser.error("version must be one word without reserved characters")
    if not args.project.strip() or bad_field(args.project) or args.project != args.project.strip():
        parser.error("project is empty or contains a newline, bracket or reserved delimiter")
    decisions, tasks = split_list(args.decisions), split_list(args.tasks)
    for item in decisions + tasks:
        if bad_field(item):
            parser.error("slug or id %r contains a newline, bracket or reserved delimiter" % item)
    try:
        datetime.date.fromisoformat(args.date)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
            raise ValueError()
    except ValueError:
        parser.error("date must be a valid YYYY-MM-DD")
    session = args.session or os.environ.get("WORK_MAP_SESSION") or "unknown"
    if bad_field(session) or not session.strip():
        parser.error("session contains a newline, bracket or reserved delimiter")
    try:
        implicit = not args.file and not args.config
        if args.file:
            target = args.file
        elif args.config:
            target = pick_file(config_ship_files(args.config), args.project, args.config)
        elif os.path.isfile("work-map.json"):
            target = pick_file(config_ship_files("work-map.json"), args.project, "work-map.json")
        else:
            target = "DEVLOG.md"
        target = os.path.realpath(target)
        if implicit:
            base = os.path.dirname(os.path.abspath("work-map.json")) if os.path.isfile("work-map.json") else os.getcwd()
            problem = confined(target, base)
            if problem:
                raise ConfigRefused(problem)
    except ConfigRefused as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    line = "%s · session: %s · project: %s · shipped %s %s · decisions: %s · tasks closed: %s" % (
        args.date, session, args.project, args.version, args.sha,
        ", ".join(decisions) or "none", ", ".join(tasks) or "none")
    with locked(target):
        wrote = False
        original = None
        try:
            if os.path.exists(target):
                with open(target, "rb") as fh:
                    original = fh.read()
                for n, old in enumerate(original.decode("utf-8").splitlines(), 1):
                    r = work_map.parse_ship(old, (target, n))
                    if r and r["project"] == args.project and r["version"] == args.version:
                        print("refused: %s %s is already logged at %s:%d: %s" % (args.project, args.version, target, n, old.strip()), file=sys.stderr)
                        return 2
            if args.dry_run:
                print(line)
                print(target)
                return 0
            head = b"" if original is not None else ("# %s DEVLOG\n\n" % args.project).encode("utf-8")
            body = (original or b"")
            sep = b"\n" if body and not body.endswith(b"\n") else b""
            os.makedirs(os.path.dirname(target), exist_ok=True)
            wrote = True
            atomic_write(target, head + body + sep + (line + "\n").encode("utf-8"))
            with open(target, encoding="utf-8") as fh:
                last = fh.read().splitlines()[-1]
            r = work_map.parse_ship(last, (target, 0))
            want = [("depends-on", "decision:" + work_map.slugify(d)) for d in decisions] + [("done-by", "task:" + t) for t in tasks]
            if not (r and r["kind"] == "ship" and r["project"] == args.project and r["version"] == args.version
                    and r["sha"] == args.sha and r["links"] == want):
                raise ValueError("written line failed parse-back")
        except BaseException as exc:  # any failure after the write (incl. Ctrl-C) puts the original back
            restored = restore_original(target, original) if wrote else True
            if not isinstance(exc, Exception):
                raise
            print("add failed: %s" % exc, file=sys.stderr)
            return 1 if restored else 3
    print(line)
    print(target)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != "add":
        print(__doc__)
        return 0
    return add_command(argv[1:])


if __name__ == "__main__":
    sys.exit(main())
