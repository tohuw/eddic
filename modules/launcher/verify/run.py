# /// script
# requires-python = ">=3.9"
# ///
"""Verify the launcher packager against a planted service spec.

Golden tests, no network, no third-party deps:
  - macOS target stamps a valid .app: Info.plist parses (plistlib) and
    names the executable, the MacOS executable is present (and, on
    POSIX, marked executable) and references the service, and run.sh
    delegates to the campaign's run verb for that service.
  - Windows target emits a .cmd invoking `.eddic\\eddic.py run <service>`
    with CRLF line endings.
  - An unknown service refuses (nonzero, no artifact).
  - --headless flips both launchers to the logfile/detached shape.
"""

import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "templates" / "package.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def make_campaign(tmp):
    camp = tmp / "campaign"
    (camp / ".eddic").mkdir(parents=True)
    cfg = ('{"services": {"recorder": {"dir": ".", "entry": "bot.py", '
           '"with": ["py-cord"]}}}')
    (camp / ".eddic" / "config.json").write_text(cfg, encoding="utf-8")
    return camp


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-launcher-verify-"))
    camp = make_campaign(tmp)
    checks = []

    def check(cond, msg):
        checks.append((bool(cond), msg))

    # --- macOS .app, visible ---
    out = tmp / "mac"
    p = run("--service", "recorder", "--campaign", str(camp),
            "--target", "macos", "--dest", str(out))
    check(p.returncode == 0,
          f"macos stamp exits 0 (got {p.returncode}: {p.stderr.strip()[:120]})")
    app = out / "Recorder.app"
    plist_path = app / "Contents" / "Info.plist"
    macos_exec = app / "Contents" / "MacOS" / "Recorder"
    run_sh = app / "Contents" / "Resources" / "run.sh"
    check(app.is_dir(), "Recorder.app bundle created")
    check(plist_path.is_file(), "Info.plist present")
    if plist_path.is_file():
        pl = plistlib.loads(plist_path.read_bytes())
        check(pl.get("CFBundleExecutable") == "Recorder",
              "Info.plist CFBundleExecutable names the executable")
        check(pl.get("CFBundlePackageType") == "APPL",
              "Info.plist declares an APPL bundle")
        check(pl.get("CFBundleName") == "Recorder",
              "Info.plist CFBundleName set")
    check(macos_exec.is_file(), "MacOS/Recorder executable present")
    if macos_exec.is_file():
        if os.name == "posix":
            check(os.access(macos_exec, os.X_OK),
                  "MacOS/Recorder has the executable bit")
        exec_text = macos_exec.read_text(encoding="utf-8")
        check("recorder" in exec_text,
              "MacOS executable references the recorder service")
        check("run.sh" in exec_text,
              "MacOS executable delegates to run.sh")
        check("osascript" in exec_text and "Terminal" in exec_text,
              "visible launcher opens Terminal")
    check(run_sh.is_file(), "Resources/run.sh present")
    if run_sh.is_file():
        sh = run_sh.read_text(encoding="utf-8")
        check("uv run .eddic/eddic.py run recorder" in sh,
              "run.sh delegates to the run verb for the service")
        check(str(camp) in sh, "run.sh cd's into the campaign directory")
        if os.name == "posix":
            check(os.access(run_sh, os.X_OK), "run.sh has the executable bit")

    # --- Windows .cmd ---
    out_win = tmp / "win"
    p = run("--service", "recorder", "--campaign", str(camp),
            "--target", "windows", "--dest", str(out_win))
    check(p.returncode == 0,
          f"windows stamp exits 0 (got {p.returncode}: {p.stderr.strip()[:120]})")
    cmd = out_win / "Recorder.cmd"
    check(cmd.is_file(), "Recorder.cmd created")
    if cmd.is_file():
        raw = cmd.read_bytes()
        check(b"\r\n" in raw, "cmd uses CRLF line endings")
        text = raw.decode("utf-8")
        check("uv run .eddic\\eddic.py run recorder" in text,
              "cmd invokes the run verb for the service")
        check(text.startswith("@echo off"), "cmd is a batch launcher")

    # --- unknown service refuses ---
    p = run("--service", "ghost", "--campaign", str(camp),
            "--target", "macos", "--dest", str(tmp / "ghost"))
    check(p.returncode != 0, f"unknown service refuses (got {p.returncode})")
    check(not (tmp / "ghost" / "Ghost.app").exists(),
          "no bundle stamped for an unknown service")

    # --- headless variant ---
    out_h = tmp / "headless"
    p = run("--service", "recorder", "--campaign", str(camp), "--headless",
            "--target", "both", "--dest", str(out_h))
    check(p.returncode == 0,
          f"headless both stamp exits 0 (got {p.returncode})")
    h_plist = out_h / "Recorder.app" / "Contents" / "Info.plist"
    if h_plist.is_file():
        pl = plistlib.loads(h_plist.read_bytes())
        check(pl.get("LSUIElement") is True,
              "headless .app declares LSUIElement")
    h_sh = out_h / "Recorder.app" / "Contents" / "Resources" / "run.sh"
    if h_sh.is_file():
        check(".eddic/recorder.log" in h_sh.read_text(encoding="utf-8"),
              "headless run.sh redirects to the service logfile")
    h_cmd = out_h / "Recorder.cmd"
    if h_cmd.is_file():
        check("start" in h_cmd.read_text(encoding="utf-8"),
              "headless cmd starts detached")

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        print(f"verify FAILED: launcher module ({len(failed)} check(s))")
        return 1
    print("verify ok: launcher module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
