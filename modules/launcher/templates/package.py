# /// script
# requires-python = ">=3.9"
# ///
"""package.py — stamp a native, double-clickable launcher for a
campaign's local service (the recorder bot, or a locally-run lore bot).

Reads the service from <campaign>/.eddic/config.json and stamps a
platform-native launcher that *delegates* to the campaign's run verb —
`uv run .eddic/eddic.py run <service>` — so the launcher never
duplicates the run command, only wraps it so the owner can double-click:

  macOS   -> <Name>.app bundle, a real signed app that owns its identity
  Windows -> <Name>.cmd launcher

The macOS app is hand-built (its own Info.plist, a compiled Swift AppKit
supervisor as Contents/MacOS/<Name>, ad-hoc code-signed) rather than an
osacompile "applet", and it is fully self-contained — it drives no other
app. That matters for the reasons the owner hit:

  1. Its own window. The supervisor is a real windowed AppKit app: a menu
     bar with a Quit item on Cmd-Q, and a read-only, monospaced,
     auto-scrolling text view showing the service's stdout+stderr live.
     No Terminal, no osascript, no tail — nothing else to leave running.
  2. Clean lifecycle. It launches the run verb as its own child in a new
     session/process group. Quitting the app (Cmd-Q / menu), closing the
     window, or the bot exiting on its own terminates the whole child
     process group — no orphaned python/recorder, and no third app left
     behind.
  3. Identity. Because the bundle carries its own reverse-DNS
     CFBundleIdentifier (quest.eddic.launcher.<slug>), its own name, and
     an ad-hoc code signature, macOS TCC pins the service's permissions
     (microphone, etc.) to *this app*. And because the bot is the app's
     own child (in its own session via setsid), TCC attributes it to the
     app.

Building the macOS app requires macOS with `swiftc` and `codesign` (both
ship with the Xcode command-line tools / macOS). The pure text builders
(swift_source_text, info_plist_text, cmd_launcher_text, launcher_name,
bundle_identifier) do no I/O and golden-test cleanly on any OS;
build_macos_app / write_cmd do the platform work.

Usage:
    uv run package.py --service NAME [--campaign DIR] [--config PATH]
        [--target macos|windows|both|auto] [--dest DIR]
        [--name LABEL] [--icon PATH.icns] [--headless]
"""

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The launcher wraps exactly this — the campaign's own run verb. The two
# forms differ only in path separator; the verb and service are shared.
EDDIC_POSIX = ".eddic/eddic.py"
EDDIC_WIN = ".eddic\\eddic.py"


def launcher_name(service, explicit=None):
    """Filesystem-safe launcher label. Default: the service name
    title-cased with separators removed (recorder -> Recorder, lore-bot
    -> LoreBot)."""
    if explicit:
        return explicit
    words = re.sub(r"[-_]+", " ", service).title()
    return re.sub(r"\s+", "", words) or "Launcher"


def bundle_identifier(name):
    """A per-app, stable reverse-DNS id derived from the launcher name.
    This is the identity macOS TCC pins the service's permissions to, so
    it must be unique per app and never the shared osacompile default."""
    slug = re.sub(r"[^a-z0-9]", "", name.lower()) or "launcher"
    return f"quest.eddic.launcher.{slug}"


def _swift_str(value):
    """Escape a Python string for embedding in a Swift string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def swift_source_text(name, service, campaign_dir, headless):
    """The Swift source for Contents/MacOS/<Name> — the AppKit
    supervisor. Pure: values are baked as escaped Swift string literals;
    build_macos_app compiles it. Delegates to the run verb (never
    duplicates the run command); runs it as the app's own child in a new
    session/process group (perl setsid) so the whole tree dies with one
    signal and TCC pins the mic to this app; streams the child's
    stdout+stderr into an in-window text view."""
    n = _swift_str(name)
    svc = _swift_str(service)
    camp = _swift_str(campaign_dir)
    headless_flag = "true" if headless else "false"
    # Baked values, in order: displayName, service, campaignDir, headless.
    return _SWIFT_TEMPLATE % (n, svc, camp, headless_flag)


# The AppKit supervisor. Self-contained: it owns a window with a
# monospaced, auto-scrolling NSTextView (in an NSScrollView) that shows
# the child's stdout+stderr live, a menu bar with Quit on Cmd-Q, and a
# standard Edit menu so the log is selectable/copyable. It launches
# `uv run .eddic/eddic.py run <service>` as its own child, in a new
# session/process group (perl setsid), with PYTHONUNBUFFERED=1 so logs
# stream. It kills the child's whole process group (TERM then KILL) on
# quit (Cmd-Q / menu), on the window closing, and when the child exits.
# It spawns no Terminal and drives no other app.
_SWIFT_TEMPLATE = r'''import AppKit
import Foundation

let displayName = "%s"
let service = "%s"
let campaignDir = "%s"
let headless = %s
let logPath = campaignDir + "/.eddic/" + service + ".log"

final class Controller: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var childPGID: pid_t = -1
    var process: Process?
    var pipe: Pipe?
    var logHandle: FileHandle?
    var window: NSWindow?
    var textView: NSTextView?
    var quitting = false

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        if !headless { buildWindow() }
        startChild()
    }

    // App menu (Quit on Cmd-Q) + a standard Edit menu so the log text is
    // selectable and copyable.
    func buildMenu() {
        let mainMenu = NSMenu()

        let appItem = NSMenuItem()
        mainMenu.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Hide " + displayName,
            action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit " + displayName,
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q")
        appItem.submenu = appMenu

        let editItem = NSMenuItem()
        mainMenu.addItem(editItem)
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Cut",
            action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy",
            action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste",
            action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All",
            action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = editMenu

        NSApp.mainMenu = mainMenu
    }

    func buildWindow() {
        let frame = NSRect(x: 0, y: 0, width: 760, height: 480)
        let win = NSWindow(contentRect: frame,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        win.title = displayName + " \u{2014} live log"
        win.delegate = self
        win.center()

        let scroll = NSScrollView(frame: frame)
        scroll.hasVerticalScroller = true
        scroll.autoresizingMask = [.width, .height]
        scroll.borderType = .noBorder

        let tv = NSTextView(frame: frame)
        tv.isEditable = false
        tv.isSelectable = true
        tv.isRichText = false
        tv.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
        tv.textColor = NSColor.textColor
        tv.backgroundColor = NSColor.textBackgroundColor
        tv.isVerticallyResizable = true
        tv.isHorizontallyResizable = false
        tv.autoresizingMask = [.width]
        tv.textContainerInset = NSSize(width: 6, height: 6)
        tv.textContainer?.widthTracksTextView = true

        scroll.documentView = tv
        win.contentView = scroll
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        self.window = win
        self.textView = tv
    }

    // Append on the main queue, cap backlog, keep pinned to the bottom.
    func append(_ s: String) {
        guard let tv = textView, let ts = tv.textStorage else { return }
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 12, weight: .regular),
            .foregroundColor: NSColor.textColor,
        ]
        ts.append(NSAttributedString(string: s, attributes: attrs))
        let cap = 400000
        if ts.length > cap {
            ts.deleteCharacters(
                in: NSRange(location: 0, length: ts.length - cap))
        }
        tv.scrollToEndOfDocument(nil)
    }

    func startChild() {
        let logDir = campaignDir + "/.eddic"
        try? FileManager.default.createDirectory(
            atPath: logDir, withIntermediateDirectories: true)
        FileManager.default.createFile(atPath: logPath, contents: Data())
        logHandle = FileHandle(forWritingAtPath: logPath)

        // Delegate to the run verb, as our own child, in a new
        // session/process group (setsid) so one signal fells the tree.
        let invoke = "uv run .eddic/eddic.py run " + service
        let script = "cd \"" + campaignDir + "\" && exec perl -e "
            + "'use POSIX qw(setsid); setsid(); exec @ARGV' "
            + "/bin/bash -lc '" + invoke + "'"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = ["-c", script]
        var env = ProcessInfo.processInfo.environment
        env["PYTHONUNBUFFERED"] = "1"   // stream, don't buffer into silence
        p.environment = env

        let pp = Pipe()
        p.standardOutput = pp
        p.standardError = pp
        p.standardInput = FileHandle.nullDevice
        pp.fileHandleForReading.readabilityHandler = { [weak self] fh in
            let data = fh.availableData
            if data.isEmpty { return }
            self?.logHandle?.write(data)   // tee for post-mortem
            let text = String(decoding: data, as: UTF8.self)
            DispatchQueue.main.async { self?.append(text) }
        }
        p.terminationHandler = { [weak self] proc in
            let status = proc.terminationStatus
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.append("\n[" + displayName
                    + " stopped (exit \(status))]\n")
                if !self.quitting {
                    self.childPGID = -1   // it is already gone
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
                        NSApp.terminate(nil)
                    }
                }
            }
        }
        do {
            try p.run()
        } catch {
            append("failed to launch " + displayName + ": "
                + error.localizedDescription + "\n")
            return
        }
        process = p
        pipe = pp
        childPGID = p.processIdentifier   // == pgid after setsid
        append("== " + displayName + " \u{2014} live log ==\n")
    }

    func killChild() {
        guard childPGID > 0 else { return }
        kill(-childPGID, SIGTERM)
        usleep(500000)
        kill(-childPGID, SIGKILL)
        childPGID = -1
    }

    // Cmd-Q / the Quit menu item.
    func applicationShouldTerminate(
        _ sender: NSApplication) -> NSApplication.TerminateReply {
        quitting = true
        pipe?.fileHandleForReading.readabilityHandler = nil
        killChild()
        return .terminateNow
    }

    // The window's red close button.
    func windowWillClose(_ notification: Notification) {
        quitting = true
        pipe?.fileHandleForReading.readabilityHandler = nil
        killChild()
        NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(
        _ app: NSApplication) -> Bool { return true }
}

let app = NSApplication.shared
let controller = Controller()
app.delegate = controller
app.setActivationPolicy(headless ? .accessory : .regular)
app.run()
'''


def info_plist_text(name, service, headless, icon_file=None):
    """The bundle's Info.plist. Carries a per-app reverse-DNS identifier
    and the app's own name/display name so macOS TCC pins the service's
    permissions to THIS app. NSMicrophoneUsageDescription is declared so
    a recorder's mic prompt attributes to the app with a sane string."""
    ident = bundle_identifier(name)
    ui_element = "  <key>LSUIElement</key><true/>\n" if headless else ""
    icon = (f"  <key>CFBundleIconFile</key><string>{icon_file}</string>\n"
            if icon_file else "")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        f"  <key>CFBundleName</key><string>{name}</string>\n"
        f"  <key>CFBundleDisplayName</key><string>{name}</string>\n"
        f"  <key>CFBundleIdentifier</key><string>{ident}</string>\n"
        "  <key>CFBundleVersion</key><string>1.0</string>\n"
        "  <key>CFBundleShortVersionString</key><string>1.0</string>\n"
        "  <key>CFBundlePackageType</key><string>APPL</string>\n"
        f"  <key>CFBundleExecutable</key><string>{name}</string>\n"
        "  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>\n"
        "  <key>LSMinimumSystemVersion</key><string>10.13</string>\n"
        "  <key>NSHighResolutionCapable</key><true/>\n"
        "  <key>NSMicrophoneUsageDescription</key>"
        f"<string>{name} records session audio for transcription."
        "</string>\n"
        f"{icon}"
        f"{ui_element}"
        "</dict>\n"
        "</plist>\n"
    )


def cmd_launcher_text(name, service, campaign_dir, headless):
    """The Windows .cmd. Visible: run in this console and pause on exit so
    the window stays. Headless: start detached, output to logfile."""
    invoke = f"uv run {EDDIC_WIN} run {service}"
    lines = [
        "@echo off",
        f"REM {name} launcher for the {service} service. Delegates to the",
        "REM campaign's run verb; this file never duplicates it.",
        f'cd /d "{campaign_dir}"',
    ]
    if headless:
        log = f".eddic\\{service}.log"
        lines += [
            f"echo Starting {service} (headless) - output to {log}",
            f'start "" /b {invoke} >> "{log}" 2>&1',
        ]
    else:
        lines += [
            f"echo Starting {service}... Ctrl-C to stop.",
            invoke,
            "pause",
        ]
    # Windows batch expects CRLF.
    return "\r\n".join(lines) + "\r\n"


def build_macos_app(dest_dir, name, service, campaign_dir, headless,
                    icon_path=None):
    """Materialize and compile the .app bundle. Requires macOS with
    swiftc and codesign. Writes Info.plist, compiles the Swift supervisor
    into Contents/MacOS/<name>, copies an optional .icns, and ad-hoc
    code-signs LAST (any later edit breaks the signature). Returns the
    .app path. Raises RuntimeError if the toolchain is missing or a
    build step fails."""
    if platform.system() != "Darwin":
        raise RuntimeError("the macOS launcher must be built on macOS "
                           "(needs swiftc and codesign)")
    for tool in ("swiftc", "codesign"):
        if not shutil.which(tool):
            raise RuntimeError(f"required tool not found: {tool} "
                               "(install the Xcode command-line tools)")

    app = Path(dest_dir) / f"{name}.app"
    # Read the icon up front: a restamp may point --icon at the bundle's
    # own current icon, and we are about to remove the bundle.
    icon_file = None
    icon_data = None
    if icon_path:
        icon_file = f"{name}.icns"
        icon_data = Path(icon_path).read_bytes()

    # Rebuild from clean so a restamp never inherits stale payload (an
    # old executable, a dropped Resources file) or a stale signature.
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    if icon_data is not None:
        (resources / icon_file).write_bytes(icon_data)

    (app / "Contents" / "Info.plist").write_text(
        info_plist_text(name, service, headless, icon_file),
        encoding="utf-8")

    src = swift_source_text(name, service, campaign_dir, headless)
    with tempfile.TemporaryDirectory() as td:
        swift_path = Path(td) / "main.swift"
        swift_path.write_text(src, encoding="utf-8")
        exe = macos / name
        r = subprocess.run(
            ["swiftc", "-O", str(swift_path), "-o", str(exe)],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"swiftc failed:\n{r.stderr.strip()}")
        exe.chmod(exe.stat().st_mode | 0o111)

    # Sign LAST, after every payload byte is final.
    r = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"codesign failed:\n{r.stderr.strip()}")
    return app


def write_cmd(dest_dir, name, text):
    target = Path(dest_dir) / f"{name}.cmd"
    target.parent.mkdir(parents=True, exist_ok=True)
    # newline="" so the CRLFs in text survive verbatim on every OS.
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return target


def resolve_targets(target):
    if target == "both":
        return ["macos", "windows"]
    if target == "auto":
        return ["windows"] if platform.system() == "Windows" else ["macos"]
    return [target]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stamp a native launcher.")
    ap.add_argument("--service", required=True,
                    help="service key in .eddic/config.json")
    ap.add_argument("--campaign", help="campaign directory (default: cwd)")
    ap.add_argument("--config", help="config.json path (default: "
                    "<campaign>/.eddic/config.json)")
    ap.add_argument("--target", default="auto",
                    choices=["macos", "windows", "both", "auto"],
                    help="which launcher(s) to stamp (default: this OS)")
    ap.add_argument("--dest", help="output directory (default: campaign)")
    ap.add_argument("--name", help="launcher label (default: service, "
                    "title-cased)")
    ap.add_argument("--icon", help="path to a .icns to use as the app icon")
    ap.add_argument("--headless", action="store_true",
                    help="no window; output to .eddic/<service>.log")
    args = ap.parse_args(argv)

    campaign = (Path(args.campaign).expanduser().resolve() if args.campaign
                else Path.cwd())
    config_path = (Path(args.config).expanduser() if args.config
                   else campaign / ".eddic" / "config.json")
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"error: {config_path} is not valid JSON: {e}",
              file=sys.stderr)
        return 1

    services = cfg.get("services", {})
    if args.service not in services:
        print(f"error: unknown service '{args.service}' (configured: "
              f"{', '.join(services) or 'none'})", file=sys.stderr)
        return 2

    name = launcher_name(args.service, args.name)
    dest = (Path(args.dest).expanduser().resolve() if args.dest
            else campaign)
    dest.mkdir(parents=True, exist_ok=True)

    icon_path = None
    if args.icon:
        icon_path = Path(args.icon).expanduser()
        if not icon_path.is_file():
            print(f"error: icon not found: {icon_path}", file=sys.stderr)
            return 1

    for tgt in resolve_targets(args.target):
        if tgt == "macos":
            try:
                app = build_macos_app(dest, name, args.service,
                                      str(campaign), args.headless,
                                      icon_path)
            except RuntimeError as e:
                print(f"error: {e}", file=sys.stderr)
                return 3
            print(f"stamped {app}")
        else:
            text = cmd_launcher_text(name, args.service, str(campaign),
                                     args.headless)
            cmd = write_cmd(dest, name, text)
            print(f"stamped {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
