# /// script
# requires-python = ">=3.9"
# ///
"""eddic reconcile — fork-first, validated writes to an Ørlǫg story.

Usage:
    uv run reconcile.py <story-dir> <mutations.json> [--name NAME]
    (bare, as a vendored eddic verb: story dir may come from
     EDDIC_CONFIG key "orlog_story"; then the first arg is just the
     mutations file)

ORLOG_CMD names the Ørlǫg CLI (default "orlog"; a repo checkout works
as "node <repo>/packages/cli/src/cli.ts"). Flow, unconditionally:
fork → apply --branch → validate --branch. The trunk and the story
head are never written by this script; a refused mutation means
nothing landed anywhere but an isolated fork you can inspect and
delete. Merging (setting head to the fork) is the owner's act in
Ørlǫg, never this script's.

Exit codes: 0 reconciled onto a fork, 1 refused, 2 usage error.
"""

import json
import os
import shlex
import subprocess
import sys
from datetime import date
from pathlib import Path

# Windows consoles default to legacy codepages that lack Ø and ǫ —
# and this script says Ørlǫg out loud. UTF-8, everywhere, always.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def orlog(args):
    raw = os.environ.get("ORLOG_CMD", "orlog")
    # posix=False on Windows keeps backslashed paths intact; it also
    # keeps quotes on tokens, so strip them
    parts = [t.strip('"') for t in shlex.split(raw,
                                               posix=(os.name != "nt"))]
    cmd = parts + args
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        body = json.loads(p.stdout)
    except ValueError:
        body = {}
    return p.returncode, body, (p.stderr or p.stdout).strip()


def main(argv):
    args, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i]] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        else:
            args.append(argv[i])
            i += 1
    story = None
    if os.environ.get("EDDIC_CONFIG"):
        cfg = json.loads(Path(os.environ["EDDIC_CONFIG"])
                         .read_text(encoding="utf-8"))
        story = cfg.get("orlog_story")
    if len(args) == 2:
        story, muts = args
    elif len(args) == 1 and story:
        muts = args[0]
    else:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not Path(muts).is_file():
        print(f"no such mutations file: {muts}", file=sys.stderr)
        return 2

    name = opts.get("--name", f"reconcile-{date.today().isoformat()}")
    rc, body, msg = orlog(["fork", story, "--name", name])
    if rc or not body.get("ok"):
        print(f"reconcile REFUSED at fork: {msg}", file=sys.stderr)
        return 1
    branch = body["branch"]["id"]

    rc, body, msg = orlog(["apply", story, muts, "--branch", branch])
    if rc or not body.get("ok"):
        print(f"reconcile REFUSED at apply — nothing landed; the story "
              f"head is untouched and fork '{branch}' holds nothing "
              f"new. Reason: {msg}", file=sys.stderr)
        return 1

    rc, body, msg = orlog(["validate", story, "--branch", branch])
    if rc or not body.get("ok"):
        print(f"reconcile REFUSED at validate — fork '{branch}' holds "
              f"the applied mutations for inspection; the story head "
              f"is untouched. Reason: {msg}", file=sys.stderr)
        return 1

    print(f"reconciled onto fork '{branch}' (head untouched). Review: "
          f"orlog dump {story} --branch {branch} — merging is the "
          f"owner's act in Ørlǫg.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
