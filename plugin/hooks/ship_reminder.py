#!/usr/bin/env python3
# work-map — Copyright (c) 2026 House of Solance. PolyForm Noncommercial 1.0.0. Required Notice: Copyright (c) 2026 House of Solance (https://github.com/SolanceLab)
"""PostToolUse hook: after a release command, remind the AI to write the ship line.

Reads the hook JSON on stdin. When tool_input.command creates a release (gh release create, git tag with a
version-looking name, git push of --tags or a version-looking ref) it prints one additionalContext sentence.
Anything else, bad JSON, or WORK_MAP_SHIP_REMINDER=0: prints nothing. Always exits 0; reads no files, no network.
"""
import json, os, re, shlex, sys

SEPARATORS = ";&|\n"
VERSION = re.compile(r"^v?\d+\.\d+(\.\d+)?([-+][0-9A-Za-z.-]+)?$")


def split_commands(command):
    """Split a shell line into word lists at ; && || | and newlines; quoted text stays whole and unquoted."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=SEPARATORS)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    parts, cur = [], []
    for tok in lex:
        if tok and all(c in SEPARATORS for c in tok):
            parts.append(cur)
            cur = []
        else:
            cur.append(tok)
    parts.append(cur)
    return parts


def git_sub(words):
    """Skip git's global options (-C path, -c k=v, --git-dir=..., --no-pager); return (subcommand, args)."""
    i = 1
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    return (words[i], words[i + 1:]) if i < len(words) else ("", [])


# Flags that mean the command does not create a release (verify, delete, list, dry run, show).
NOT_A_RELEASE = {"-v", "--verify", "-d", "--delete", "-l", "--list", "-n", "--dry-run", "--contains", "--points-at"}


def release_version(command):
    """Return (is_release, version or '')."""
    try:
        parts = split_commands(command)
    except ValueError:  # unbalanced quote: unreadable, stay quiet
        return False, ""
    for words in parts:
        if len(words) >= 3 and words[0] == "gh" and words[1] == "release" and words[2] == "create":
            rest = [w for w in words[3:] if not w.startswith("-")]
            return True, next((w for w in rest if VERSION.match(w)), "")
        if not words or words[0] != "git":
            continue
        sub, args = git_sub(words)
        if sub not in ("tag", "push") or any(w in NOT_A_RELEASE for w in args):
            continue
        refs = [w for w in args if not w.startswith("-")]
        if any(w.startswith(":") for w in refs):  # git push origin :refs/tags/v1 deletes the ref
            continue
        tags = [w.split(":")[-1].replace("refs/tags/", "") for w in refs]
        found = next((t for t in tags if VERSION.match(t)), "")
        if sub == "tag" and found:
            return True, found
        if sub == "push" and (found or "--tags" in args):
            return True, found
    return False, ""


def main():
    if os.environ.get("WORK_MAP_SHIP_REMINDER") == "0":
        return
    try:
        command = json.load(sys.stdin)["tool_input"]["command"]
        hit, version = release_version(command if isinstance(command, str) else "")
    except Exception:
        return
    if not hit:
        return
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or "<plugin>"
    what = "a release (%s)" % version if version else "a release"
    msg = ("work-map: you just ran %s, so write its ship line with `python3 %s/scripts/ships.py add --project <repo> "
           "--version %s --sha <sha> --decisions <slugs> --tasks <ids>` and mark the shipped pipeline items done with "
           "`pipeline.py update --status done --devlog <date>`." % (what, root, version or "<version>"))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
