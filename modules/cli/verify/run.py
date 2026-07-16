# /// script
# requires-python = ">=3.9"
# ///
"""Verify the cli module end to end in a throwaway campaign:
stamp → doctor → manifest record/check → vendor lint verb → lint a
planted wiki through the dispatcher. Exits 0 on success."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULES = HERE.parent.parent
STAMP = MODULES / "cli" / "scripts" / "stamp.py"
LINT = MODULES / "lint" / "scripts" / "eddic_lint.py"


def run(args, expect, label, **kw):
    proc = subprocess.run([sys.executable] + [str(a) for a in args],
                          capture_output=True, text=True, **kw)
    if proc.returncode != expect:
        print(f"FAIL {label}: exit {proc.returncode}, expected {expect}")
        print(proc.stdout, proc.stderr, sep="\n")
        sys.exit(1)
    print(f"ok   {label}")
    return proc


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-cli-verify-"))
    try:
        camp = tmp / "campaign"
        run([STAMP, camp, "--site-name", "Verify Realm"], 0, "stamp")
        cli = camp / ".eddic" / "eddic.py"

        run([STAMP, camp, "--site-name", "Ignored On Restamp"], 0, "restamp")
        cfg = json.loads((camp / ".eddic" / "config.json").read_text())
        assert cfg["site_name"] == "Verify Realm", "restamp clobbered config"
        print("ok   restamp preserved config")

        (camp / "wiki" / "index.md").write_text(
            "# Verify Realm\n\nSee [the keep](keep.md).\n", encoding="utf-8")
        (camp / "wiki" / "keep.md").write_text(
            "# The Keep\n\nA sturdy keep above the [realm](index.md). "
            "It has stood for nine generations of wardens and will "
            "stand for nine more, or so the masons swear.\n",
            encoding="utf-8")

        run([cli, "doctor"], 0, "doctor")
        run([cli, "manifest", "record", "--module", "lint",
             "--version", "0.1.0", "--verbs", "lint"], 0, "manifest record")
        run([cli, "manifest", "check"], 1, "manifest check flags unvendored verb")
        shutil.copyfile(LINT, camp / ".eddic" / "lib" / "lint.py")
        run([cli, "manifest", "check"], 0, "manifest check after vendoring")
        run([cli, "lint"], 0, "vendored lint verb on clean wiki")

        (camp / "wiki" / "keep.md").write_text(
            "# The Keep\n\nSee [nowhere](missing.md).\n", encoding="utf-8")
        run([cli, "lint"], 1, "vendored lint verb flags broken link")
        run([cli, "nosuchverb"], 2, "unknown verb rejected")
        print("verify ok: cli module")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
