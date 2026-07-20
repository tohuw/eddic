# /// script
# requires-python = ">=3.9"
# ///
"""Verify the Stream Deck pack generator: the template compiles, the
pure builders emit the right curl per endpoint (with and without a
token), a full pack materializes on disk with exactly the four control
keys and nothing else, the Windows target emits CRLF `.cmd` files, and
the `.streamDeckProfile` is a valid zip whose manifest maps keys to
System ▸ Open on the stamped scripts."""

import io
import json
import py_compile
import sys
import tempfile
import zipfile
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def main():
    checks = []
    try:
        py_compile.compile(str(TEMPLATES / "deckpack.py"), doraise=True)
        checks.append((True, "deckpack.py compiles"))
    except py_compile.PyCompileError as e:
        checks.append((False, f"deckpack.py compile error: {e}"))
        _report(checks)
        return 1

    sys.path.insert(0, str(TEMPLATES))
    import deckpack

    # --- pure builders ---------------------------------------------------
    fn, text = deckpack.control_script(
        "Start Recording", "POST", "/record/start",
        "http://127.0.0.1:8776", "s3cr3t", "macos")
    checks.append((fn == "start-recording.command",
                   "core script filename is slugified"))
    checks.append(('-X POST "$BASE/record/start"' in text
                   and 'X-Muninn-Token: $TOKEN' in text
                   and 'TOKEN=s3cr3t' in text,
                   "start script curls POST /record/start with the token"))

    _, notok = deckpack.control_script(
        "Recording Status", "GET", "/status",
        "http://127.0.0.1:8776", "", "macos")
    checks.append(("TOKEN=''" in notok and "AUTH=()" in notok,
                   "no token -> no auth header sent"))

    winfn, wintext = deckpack.control_script(
        "Stop Recording", "POST", "/record/stop",
        "http://127.0.0.1:8776", "s3cr3t", "windows")
    checks.append((winfn.endswith(".cmd") and "\r\n" in wintext
                   and "%BASE%/record/stop" in wintext,
                   "windows target emits a CRLF .cmd hitting the endpoint"))

    # --- bug 6: adversarial base_url/token are shell-quoted, not injected ---
    import shlex
    evil_base = 'http://x`whoami`$(id)"; rm -rf ~ #/'
    evil_token = 's3`cr`3t"$(evil)\''
    _, mtext = deckpack.control_script(
        "Start Recording", "POST", "/record/start",
        evil_base, evil_token, "macos")
    checks.append((f"BASE={shlex.quote(evil_base)}" in mtext
                   and f"TOKEN={shlex.quote(evil_token)}" in mtext,
                   "macos: crafted base_url/token are single-quoted "
                   "(no shell injection)"))
    # The dangerous run of characters never appears unquoted (outside the
    # single-quoted assignment) — a raw `rm -rf ~` reaching the shell would.
    checks.append(('BASE="' + evil_base not in mtext
                   and 'TOKEN="' + evil_token not in mtext,
                   "macos: crafted values are never left in a breakable "
                   "double-quoted assignment"))
    evil_wbase = 'http://x&calc<nul|more%USERPROFILE%'
    _, wtext = deckpack.control_script(
        "Start Recording", "POST", "/record/start",
        evil_wbase, "tok&z", "windows")
    checks.append((f"set BASE={deckpack._cmd_quote(evil_wbase)}" in wtext
                   and "^&calc" in wtext and "%%USERPROFILE%%" in wtext,
                   "windows: crafted base_url is caret/percent-escaped in "
                   "the set assignment"))
    checks.append(("set TOKEN=tok^&z" in wtext,
                   "windows: crafted token is caret-escaped in its set "
                   "assignment"))

    # --- profile bytes ---------------------------------------------------
    pb = deckpack.profile_bytes("Muninn", [
        ("Start Recording", "/x/start-recording.command"),
        ("Stop Recording", "/x/stop-recording.command")])
    with zipfile.ZipFile(io.BytesIO(pb)) as z:
        names = z.namelist()
        man = json.loads(z.read("Muninn.sdProfile/manifest.json"))
    checks.append((any(n.endswith("manifest.json") for n in names),
                   "profile is a valid zip containing manifest.json"))
    a00 = man["Actions"].get("0,0", {})
    checks.append((a00.get("UUID") == "com.elgato.streamdeck.system.open"
                   and a00["Settings"]["path"].endswith(
                       "start-recording.command"),
                   "profile key 0,0 opens the start script via System Open"))

    # --- full pack on disk ----------------------------------------------
    dst = Path(tempfile.mkdtemp(prefix="eddic-deck-verify-"))
    written = deckpack.build_pack(dst, "Muninn", "http://127.0.0.1:8776",
                                  "s3cr3t", "macos")
    names = {p.name for p in written}
    core = {"start-recording.command", "stop-recording.command",
            "recording-status.command", "muninn-help.command",
            "README.md", "muninn.streamDeckProfile"}
    checks.append((core <= names, "core pack has the four keys, README, "
                                  "and profile"))
    # the pack stamps ONLY the four control keys — no extras, no other
    # scripts. Exactly the four .command scripts and nothing else.
    scripts = {p.name for p in written if p.suffix == ".command"}
    checks.append((scripts == {"start-recording.command",
                               "stop-recording.command",
                               "recording-status.command",
                               "muninn-help.command"},
                   "exactly the four control keys are stamped, no extras"))
    checks.append(((dst / "start-recording.command").stat().st_mode & 0o111,
                   "stamped .command scripts are executable"))
    checks.append((not (dst / "extras").exists(),
                   "no extras/ directory is ever created"))
    readme = (dst / "README.md").read_text(encoding="utf-8")
    checks.append(("System ▸ Open" in readme
                   and "/record/start" in readme,
                   "README documents the System-Open bind and endpoints"))
    checks.append(("extras" not in readme.lower()
                   and "suggestions" not in readme.lower()
                   and "convene" not in readme.lower(),
                   "README mentions no extras or aspirational verb buttons"))

    # --- both targets ---------------------------------------------------
    dst2 = Path(tempfile.mkdtemp(prefix="eddic-deck-verify2-"))
    deckpack.build_pack(dst2, "Muninn", "http://127.0.0.1:8776", "", "both")
    checks.append(((dst2 / "start-recording.cmd").exists()
                   and (dst2 / "start-recording.command").exists(),
                   "target=both stamps macOS and Windows scripts"))
    checks.append((not (dst2 / "extras").exists(),
                   "target=both stamps no extras/ directory either"))

    return _report(checks)


def _report(checks):
    failed = [m for ok, m in checks if not ok]
    for ok, m in checks:
        print(("ok  " if ok else "FAIL"), m)
    if failed:
        return 1
    print("verify ok: streamdeck module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
