# work-map settings

The settings file in full: where work-map finds it, which paths it trusts, and what the writers may change.

A small JSON (or TOML, Python 3.11+) file listing source files by kind. Globs are allowed; relative paths are read from the config file's folder. Pass it with `--config` or set `WORK_MAP_CONFIG`. A `work-map.json` picked up from the current folder (neither flag nor variable given) is implicit: the writers only write `.md` files that resolve, symlinks included, to inside that folder, and refuse otherwise; pass `--config` to trust a config that points elsewhere. `--file` is always trusted.

## Writer safety limits

- The writers lock a file by the system's advisory lock where there is one (macOS and Linux); on other systems two writers at once are not protected.
- An implicit config can only write inside its own folder, checked once before the write. Someone who can change files in that folder *while* a writer runs (swapping a folder for a link at that moment) could still redirect it; such a person can already edit your files directly, so that case is out of scope.
