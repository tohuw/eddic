# /// script
# requires-python = ">=3.9"
# ///
"""Verify the launcher packager against a planted service spec.

Golden tests, no network, no third-party deps. The cross-platform checks
exercise the pure text builders and the Windows .cmd; the macOS build
(swiftc + codesign) is asserted only on macOS with the toolchain present.

  - The Swift supervisor source delegates to the run verb for the
    service, launches it as the app's own child in a new process group
    (setsid), and terminates that group on quit.
  - The Info.plist carries a per-app reverse-DNS identifier
    (quest.eddic.launcher.<slug>), the app's name as executable/display
    name, and a microphone usage string; --headless adds LSUIElement.
  - macOS (toolchain present): the stamped .app has a Mach-O executable
    at Contents/MacOS/<Name>, an Info.plist whose CFBundleIdentifier is
    the per-app id, and an ad-hoc code signature keyed on that id
    (codesign --verify passes). The app is never launched.
  - Windows target emits a .cmd invoking `.eddic\\eddic.py run <service>`
    with CRLF line endings.
  - An unknown service refuses (nonzero, no artifact).
"""

import importlib.util
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "templates" / "package.py"


def load_pkg():
    spec = importlib.util.spec_from_file_location("package", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    pkg = load_pkg()
    tmp = Path(tempfile.mkdtemp(prefix="eddic-launcher-verify-"))
    camp = make_campaign(tmp)
    checks = []

    def check(cond, msg):
        checks.append((bool(cond), msg))

    # --- pure builders (cross-platform) ---
    name = pkg.launcher_name("recorder")
    check(name == "Recorder", "launcher_name defaults to the title-cased "
          "service")
    ident = pkg.bundle_identifier(name)
    check(ident == "quest.eddic.launcher.recorder",
          f"bundle_identifier is a per-app reverse-DNS id (got {ident})")
    check(ident != "com.apple.ScriptEditor.id.Applet",
          "identifier is not the shared osacompile default")

    swift = pkg.swift_source_text(name, "recorder", str(camp), False)
    check("uv run .eddic/eddic.py run" in swift
          and 'let service = "recorder"' in swift,
          "supervisor delegates to the run verb for the service")
    check(str(camp) in swift, "supervisor bakes the campaign directory")
    check("setsid" in swift,
          "supervisor puts the child in a new session/process group")
    check("SIGTERM" in swift and "SIGKILL" in swift and "kill(-" in swift,
          "supervisor kills the child's whole process group")
    check("NSApplicationDelegate" in swift,
          "supervisor is a real Cocoa app (event loop for Cmd-Q)")
    # A self-contained, native log window — no Terminal, no osascript.
    check("NSTextView" in swift and "NSScrollView" in swift,
          "supervisor shows logs in its own NSTextView/NSScrollView")
    check("monospacedSystemFont" in swift, "the log view is monospaced")
    check("readabilityHandler" in swift,
          "supervisor streams the child's stdout+stderr live")
    check("PYTHONUNBUFFERED" in swift,
          "supervisor runs the child unbuffered so logs stream")
    check('"Quit "' in swift and 'keyEquivalent: "q"' in swift,
          "supervisor has a Quit menu item bound to Cmd-Q")
    check("applicationShouldTerminate" in swift
          and "windowWillClose" in swift,
          "quit and window-close both route to teardown")
    for banned in ("osascript", "Terminal", "do script", "tail -f",
                   "/usr/bin/osascript"):
        check(banned not in swift,
              f"supervisor drives no Terminal machinery ({banned!r})")
    h_swift = pkg.swift_source_text(name, "recorder", str(camp), True)
    check("let headless = true" in h_swift,
          "--headless bakes the headless flag into the supervisor")

    plist = plistlib.loads(
        pkg.info_plist_text(name, "recorder", False).encode("utf-8"))
    check(plist.get("CFBundleIdentifier") == "quest.eddic.launcher.recorder",
          "Info.plist declares the per-app identifier")
    check(plist.get("CFBundleName") == "Recorder"
          and plist.get("CFBundleDisplayName") == "Recorder",
          "Info.plist names the app (not a generic Applet)")
    check(plist.get("CFBundleExecutable") == "Recorder",
          "Info.plist executable is the app name")
    check(plist.get("CFBundlePackageType") == "APPL",
          "Info.plist declares an APPL bundle")
    check("NSMicrophoneUsageDescription" in plist,
          "Info.plist declares a microphone usage string")
    check("LSUIElement" not in plist,
          "visible app is not an LSUIElement agent")
    h_plist = plistlib.loads(
        pkg.info_plist_text(name, "recorder", True).encode("utf-8"))
    check(h_plist.get("LSUIElement") is True,
          "headless app declares LSUIElement")
    icon_plist = plistlib.loads(
        pkg.info_plist_text(name, "recorder", False,
                            "Recorder.icns").encode("utf-8"))
    check(icon_plist.get("CFBundleIconFile") == "Recorder.icns",
          "an icon, when given, is declared in Info.plist")

    # --- bug 6: adversarial escaping in generated artifacts ---
    # A name with XML metacharacters must yield a well-formed plist whose
    # parsed values equal the raw name (raw `&`/`<`/`>` would be malformed
    # XML that plistlib rejects).
    evil_name = "Ampersand & <Angle> Bot"
    evil_plist_xml = pkg.info_plist_text(evil_name, "recorder", False)
    parsed_ok = True
    try:
        ep = plistlib.loads(evil_plist_xml.encode("utf-8"))
    except Exception:
        parsed_ok = False
        ep = {}
    check(parsed_ok and ep.get("CFBundleName") == evil_name
          and ep.get("CFBundleDisplayName") == evil_name
          and ep.get("CFBundleExecutable") == evil_name,
          "plist XML-escapes a name with & < > (parses back to the raw name)")
    check(parsed_ok and evil_name in ep.get("NSMicrophoneUsageDescription", ""),
          "plist XML-escapes the name in the mic usage string too")

    # _swift_str escapes backslash, quote, and newline/CR so a value can
    # never terminate or inject into the one-line Swift literal.
    check(pkg._swift_str('a"b\nc\\d\re') == 'a\\"b\\nc\\\\d\\re',
          "swift string escaping covers quote, newline, CR, and backslash")
    # A campaign dir with a newline stays on one Swift literal line.
    nl_swift = pkg.swift_source_text(name, "recorder", "/tmp/x\ny", False)
    check('let campaignDir = "/tmp/x\\ny"' in nl_swift,
          "a newline in the campaign dir is escaped inside the Swift literal")

    # The shell `cd` bash-single-quotes the campaign dir, so a path with `"`,
    # `$`, or backticks cannot break out of the cd or inject a command.
    evil_dir = '/tmp/x"; rm -rf ~; $(id) `whoami` #'
    ed_swift = pkg.swift_source_text(name, "recorder", evil_dir, False)
    baked_shell = pkg._swift_str(pkg._bash_squote(evil_dir))
    check(f'let campaignShell = "{baked_shell}"' in ed_swift,
          "the campaign dir is bash-single-quoted for the shell cd")
    check('"cd \\"" + campaignDir' not in ed_swift
          and 'let script = "cd " + campaignShell' in ed_swift,
          "the cd uses the bash-quoted campaignShell, not a raw quoted path")
    check(pkg._bash_squote("a'b") == "'a'\\''b'",
          "bash single-quoting closes/escapes/reopens an embedded quote")

    # --- bug 7: bundle_identifier does not collide near-duplicate names ---
    check(pkg.bundle_identifier("LoreBot") != pkg.bundle_identifier("Lore-Bot"),
          "'LoreBot' and 'Lore-Bot' get distinct bundle identifiers")
    check(pkg.bundle_identifier("lorebot") != pkg.bundle_identifier("lore bot"),
          "'lorebot' and 'lore bot' get distinct bundle identifiers")
    check(pkg.bundle_identifier("Lore-Bot") == "quest.eddic.launcher.lore-bot",
          "a separator in the name is preserved as '-' in the identifier")
    check(pkg.bundle_identifier("!!!") == "quest.eddic.launcher.launcher",
          "a punctuation-only name falls back to the 'launcher' id")

    # --- Windows .cmd (cross-platform) ---
    out_win = tmp / "win"
    p = run("--service", "recorder", "--campaign", str(camp),
            "--target", "windows", "--dest", str(out_win))
    check(p.returncode == 0,
          f"windows stamp exits 0 (got {p.returncode}: "
          f"{p.stderr.strip()[:120]})")
    cmd = out_win / "Recorder.cmd"
    check(cmd.is_file(), "Recorder.cmd created")
    if cmd.is_file():
        raw = cmd.read_bytes()
        check(b"\r\n" in raw, "cmd uses CRLF line endings")
        text = raw.decode("utf-8")
        check("uv run .eddic\\eddic.py run recorder" in text,
              "cmd invokes the run verb for the service")
        check(text.startswith("@echo off"), "cmd is a batch launcher")

    # --- unknown service refuses (cross-platform) ---
    p = run("--service", "ghost", "--campaign", str(camp),
            "--target", "windows", "--dest", str(tmp / "ghost"))
    check(p.returncode != 0, f"unknown service refuses (got {p.returncode})")
    check(not (tmp / "ghost" / "Ghost.cmd").exists(),
          "no launcher stamped for an unknown service")

    # --- macOS build (only where the toolchain exists) ---
    have_mac = (sys.platform == "darwin" and shutil.which("swiftc")
                and shutil.which("codesign"))
    if have_mac:
        out_mac = tmp / "mac"
        p = run("--service", "recorder", "--campaign", str(camp),
                "--target", "macos", "--dest", str(out_mac))
        check(p.returncode == 0,
              f"macos build exits 0 (got {p.returncode}: "
              f"{p.stderr.strip()[:200]})")
        app = out_mac / "Recorder.app"
        exe = app / "Contents" / "MacOS" / "Recorder"
        plist_path = app / "Contents" / "Info.plist"
        check(app.is_dir(), "Recorder.app bundle built")
        check(exe.is_file(), "MacOS/Recorder executable present")
        if exe.is_file():
            magic = exe.read_bytes()[:4]
            check(magic in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                            b"\xca\xfe\xba\xbe"),
                  "MacOS/Recorder is a compiled Mach-O binary")
            check(os.access(exe, os.X_OK), "executable has the exec bit")
        if plist_path.is_file():
            pl = plistlib.loads(plist_path.read_bytes())
            check(pl.get("CFBundleIdentifier")
                  == "quest.eddic.launcher.recorder",
                  "built Info.plist carries the per-app identifier")
        # ad-hoc signature keyed on the per-app identifier
        cs = subprocess.run(["codesign", "-dvvv", str(app)],
                            capture_output=True, text=True)
        combined = cs.stdout + cs.stderr
        check("Identifier=quest.eddic.launcher.recorder" in combined,
              "signature is keyed on the per-app identifier")
        check("adhoc" in combined or "Signature=adhoc" in combined,
              "bundle is ad-hoc signed")
        v = subprocess.run(["codesign", "--verify", "--strict", str(app)],
                          capture_output=True, text=True)
        check(v.returncode == 0,
              f"codesign --verify passes (got {v.returncode}: "
              f"{v.stderr.strip()[:120]})")
    else:
        print("note: skipping macOS build checks "
              "(not on macOS or swiftc/codesign missing)")

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
