# /// script
# requires-python = ">=3.9"
# ///
"""package.py — stamp a native, double-clickable launcher for a
campaign's local service (the recorder bot, or a locally-run lore bot).

It reads the service from <campaign>/.eddic/config.json and generates a
platform-native launcher that *delegates* to the campaign's run verb —
`uv run .eddic/eddic.py run <service>` — so this file never duplicates
the run command, it only wraps it in something the owner can
double-click:

  macOS   -> a <Name>.app bundle
             (Contents/Info.plist, Contents/MacOS/<Name>, Contents/Resources/run.sh)
  Windows -> a <Name>.cmd launcher

A real Windows .exe would need a packager (pyinstaller, WinSW); the
.cmd is the dependency-free equivalent and is what this stamps.

By default both open a *visible* terminal so the service's console
output (consent posts, logs) shows and Ctrl-C stops it; --headless
redirects output to a logfile in .eddic/ instead.

The builders (app_bundle_files, cmd_launcher_text, run_sh_text,
launcher_name, info_plist_text) are pure — no filesystem, no exec — so
they golden-test cleanly. write_app_bundle / write_cmd do the I/O.

Usage:
    uv run package.py --service NAME [--campaign DIR] [--config PATH]
        [--target macos|windows|both|auto] [--dest DIR]
        [--name LABEL] [--headless]
"""

import argparse
import json
import platform
import re
import sys
from pathlib import Path

# The launcher wraps exactly this — the campaign's own run verb. The two
# forms differ only in path separator; the verb and service are shared.
EDDIC_POSIX = ".eddic/eddic.py"
EDDIC_WIN = ".eddic\\eddic.py"


def launcher_name(service, explicit=None):
    """Filesystem-safe launcher label. Default: the service name
    title-cased with separators removed (recorder -> Recorder,
    lore-bot -> LoreBot)."""
    if explicit:
        return explicit
    words = re.sub(r"[-_]+", " ", service).title()
    return re.sub(r"\s+", "", words) or "Launcher"


def bundle_identifier(name):
    slug = re.sub(r"[^a-z0-9]", "", name.lower()) or "launcher"
    return f"net.eddic.launcher.{slug}"


def run_sh_text(service, campaign_dir, headless):
    """The runner the .app executes: cd into the campaign, then hand off
    to the run verb. Mirrors the proven Muninn.app/Resources/run.sh."""
    invoke = f"uv run {EDDIC_POSIX} run {service}"
    lines = [
        "#!/bin/bash",
        f"# Start {service} through eddic's run verb, which builds the",
        "# pinned uv invocation from the campaign's service config.",
        f'cd "{campaign_dir}" || {{ echo "campaign dir not found: '
        f'{campaign_dir}"; exit 1; }}',
    ]
    if headless:
        log = f".eddic/{service}.log"
        lines += [
            f'echo "Starting {service} (headless) — output to {log}"',
            f'exec {invoke} >> "{log}" 2>&1',
        ]
    else:
        lines += [
            f'echo "Starting {service}…  Ctrl-C to stop."',
            f"exec {invoke}",
        ]
    return "\n".join(lines) + "\n"


def macos_exec_text(name, service, headless):
    """The .app's CFBundleExecutable. Visible: open Terminal on run.sh so
    the console is real and Ctrl-C reaches the process. Headless: exec
    run.sh directly (it redirects to the logfile)."""
    lines = [
        "#!/bin/bash",
        f"# {name} launcher for the {service} service. Delegates to",
        "# Resources/run.sh, which calls the campaign's run verb.",
        'contents="$(cd "$(dirname "$0")/.." && pwd)"',
        'run="$contents/Resources/run.sh"',
    ]
    if headless:
        lines += ['exec "$run"']
    else:
        lines += [
            "# Open Terminal so output is visible and Ctrl-C stops it.",
            "osascript >/dev/null 2>&1 <<OSA",
            'tell application "Terminal"',
            "  activate",
            "  do script \"exec '$run'\"",
            "end tell",
            "OSA",
        ]
    return "\n".join(lines) + "\n"


def info_plist_text(name, headless):
    ident = bundle_identifier(name)
    ui_element = ("  <key>LSUIElement</key><true/>\n" if headless else "")
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
        f"{ui_element}"
        "</dict>\n"
        "</plist>\n"
    )


def app_bundle_files(name, service, campaign_dir, headless):
    """Relative-path -> {text, exec} map of the whole .app bundle. Pure;
    write_app_bundle materializes it."""
    return {
        "Contents/Info.plist":
            {"text": info_plist_text(name, headless), "exec": False},
        f"Contents/MacOS/{name}":
            {"text": macos_exec_text(name, service, headless), "exec": True},
        "Contents/Resources/run.sh":
            {"text": run_sh_text(service, campaign_dir, headless),
             "exec": True},
    }


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
            f"echo Starting {service}...  Ctrl-C to stop.",
            invoke,
            "pause",
        ]
    # Windows batch expects CRLF.
    return "\r\n".join(lines) + "\r\n"


def write_app_bundle(dest_dir, name, files):
    app = Path(dest_dir) / f"{name}.app"
    for rel, spec in files.items():
        target = app / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(spec["text"], encoding="utf-8")
        if spec["exec"]:
            target.chmod(target.stat().st_mode | 0o111)
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
    ap = argparse.ArgumentParser(description="Stamp a native launcher for "
                                 "a campaign's local service.")
    ap.add_argument("--service", required=True,
                    help="service name as configured in .eddic/config.json")
    ap.add_argument("--campaign", help="campaign directory (default: cwd)")
    ap.add_argument("--config", help="path to config.json "
                    "(default: <campaign>/.eddic/config.json)")
    ap.add_argument("--target", default="auto",
                    choices=["macos", "windows", "both", "auto"],
                    help="which OS launcher(s) to stamp (default: auto)")
    ap.add_argument("--dest", help="where to place the launcher "
                    "(default: the campaign directory)")
    ap.add_argument("--name", help="launcher label "
                    "(default: title-cased service name)")
    ap.add_argument("--headless", action="store_true",
                    help="run detached, output to .eddic/<service>.log "
                    "(default: visible terminal)")
    args = ap.parse_args(argv)

    campaign = Path(args.campaign).expanduser().resolve() if args.campaign \
        else Path.cwd()
    config_path = Path(args.config).expanduser() if args.config \
        else campaign / ".eddic" / "config.json"
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"error: {config_path} is not valid JSON: {e}", file=sys.stderr)
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

    for tgt in resolve_targets(args.target):
        if tgt == "macos":
            files = app_bundle_files(name, args.service, str(campaign),
                                     args.headless)
            app = write_app_bundle(dest, name, files)
            print(f"stamped {app}")
        else:
            text = cmd_launcher_text(name, args.service, str(campaign),
                                     args.headless)
            cmd = write_cmd(dest, name, text)
            print(f"stamped {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
