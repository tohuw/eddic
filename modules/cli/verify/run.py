# /// script
# requires-python = ">=3.9"
# ///
"""Verify the cli module end to end in a throwaway campaign:
stamp → doctor → manifest record/check → vendor lint verb → lint a
planted wiki through the dispatcher. Exits 0 on success."""

import json
import os
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
        vdir = tmp / "campaign" / "bot"
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "variables.txt").write_text(
            "TOKEN_A=\nKEEP=asis\n", encoding="utf-8")
        sp = subprocess.run(
            [sys.executable,
             str(MODULES / "cli" / "scripts" / "secrets_fill.py"),
             str(tmp / "campaign")],
            input="sekrit-value-123\n", capture_output=True, text=True)
        filled = (vdir / "variables.txt").read_text(encoding="utf-8")
        ok = ("TOKEN_A=sekrit-value-123" in filled
              and "sekrit-value-123" not in sp.stdout
              and "sekrit-v" in sp.stdout)
        print(("ok  " if ok else "FAIL"),
              "secrets fills slots, echoes fingerprint only")
        if not ok:
            return 1
        import importlib.util as _u
        _spec = _u.spec_from_file_location(
            "eddic_disp", MODULES / "cli" / "templates" / "eddic.py")
        _disp = _u.module_from_spec(_spec)
        _spec.loader.exec_module(_disp)
        cmd = _disp.service_command(
            {"python": "3.14", "with": ["py-cord[voice]==2.8.0", "davey"],
             "entry": "bot.py"})
        ok_svc = (cmd == ["uv", "run", "--python", "3.14",
                          "--with", "py-cord[voice]==2.8.0",
                          "--with", "davey", "bot.py"])
        print(("ok  " if ok_svc else "FAIL"),
              "run: service_command builds the pinned uv invocation")
        if not ok_svc:
            return 1
        cmd2 = _disp.service_command({})
        print(("ok  " if cmd2 == ["uv", "run", "bot.py"] else "FAIL"),
              "run: service_command defaults to bot.py, no pins")
        if cmd2 != ["uv", "run", "bot.py"]:
            return 1

        # doctor degrades (warns, exit 0) when git is not on PATH,
        # instead of crashing on FileNotFoundError from `git --version`.
        nogit = tmp / "nogit-path"
        nogit.mkdir()
        dproc = subprocess.run(
            [sys.executable, str(cli), "doctor"],
            capture_output=True, text=True,
            env={**os.environ, "PATH": str(nogit)})
        ok_git = dproc.returncode == 0 and "git not found" in dproc.stdout
        print(("ok  " if ok_git else "FAIL"),
              "doctor degrades gracefully when git is absent")
        if not ok_git:
            print(dproc.stdout, dproc.stderr, sep="\n")
            return 1

        # manifest record with malformed --params errors cleanly (exit
        # 2) rather than raising an uncaught JSONDecodeError.
        jproc = subprocess.run(
            [sys.executable, str(cli), "manifest", "record",
             "--module", "x", "--version", "1", "--params", "{not json"],
            capture_output=True, text=True)
        ok_json = jproc.returncode == 2 and "not valid JSON" in jproc.stderr
        print(("ok  " if ok_json else "FAIL"),
              "manifest record rejects malformed --params cleanly")
        if not ok_json:
            print(jproc.stdout, jproc.stderr, sep="\n")
            return 1

        # secrets_fill --file with no positional dir (root via
        # EDDIC_CONFIG): the flag value must not land among positionals.
        secrets_fill = MODULES / "cli" / "scripts" / "secrets_fill.py"
        onefile = camp / "loose-vars.txt"
        onefile.write_text("SOLO=\n", encoding="utf-8")
        fproc = subprocess.run(
            [sys.executable, str(secrets_fill), "--file", str(onefile)],
            input="from-file-1234\n", capture_output=True, text=True,
            env={**os.environ,
                 "EDDIC_CONFIG": str(camp / ".eddic" / "config.json")})
        ok_file = (fproc.returncode == 0 and "SOLO=from-file-1234"
                   in onefile.read_text(encoding="utf-8"))
        print(("ok  " if ok_file else "FAIL"),
              "secrets_fill --file fills with no positional dir")
        if not ok_file:
            print(fproc.stdout, fproc.stderr, sep="\n")
            return 1

        # secrets_fill scans variables.txt two directories deep, as its
        # docstring promises (one-level glob missed the deeper file).
        deep = camp / "one" / "two"
        deep.mkdir(parents=True, exist_ok=True)
        (deep / "variables.txt").write_text("DEEP=\n", encoding="utf-8")
        gproc = subprocess.run(
            [sys.executable, str(secrets_fill), str(camp)],
            input="deep-secret-9876\n", capture_output=True, text=True)
        ok_deep = (gproc.returncode == 0 and "DEEP=deep-secret-9876"
                   in (deep / "variables.txt").read_text(encoding="utf-8"))
        print(("ok  " if ok_deep else "FAIL"),
              "secrets_fill scans variables.txt two directories deep")
        if not ok_deep:
            print(gproc.stdout, gproc.stderr, sep="\n")
            return 1

        print("verify ok: cli module")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
