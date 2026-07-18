# /// script
# requires-python = ">=3.9"
# ///
"""Verify Craig staging: per-speaker tracks land in the dated layout,
the folder-named-.flac quirk flattens to a real file, non-audio
extras are reported untouched, and an audio-free download refuses."""

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "stage_craig.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-capture-verify-"))
    dl = tmp / "craig-session.zip"
    with zipfile.ZipFile(dl, "w") as z:
        z.writestr("craig-123/1-alice.flac", "fake-flac-bytes")
        # the quirk: a directory named like a flac, audio inside
        z.writestr("craig-123/2-bob.flac/data", "fake-flac-bytes-bob")
        z.writestr("craig-123/info.txt", "craig metadata")
        z.writestr("craig-123/transcript-craig.txt", "premium words")
    out = tmp / "raw"

    p = run(str(dl), "--out", str(out), "--date", "2026-01-01")
    day = out / "2026-01-01"
    checks = [
        (p.returncode == 0, f"staging exits 0 (got {p.returncode}: "
                            f"{p.stderr.strip()[:120]})"),
        ((day / "1-alice.flac").is_file(), "plain track staged"),
        ((day / "2-bob.flac").is_file(),
         "folder-named-.flac quirk flattened to a file"),
        ((day / "2-bob.flac").read_text(encoding="utf-8")
         == "fake-flac-bytes-bob", "quirk file carries the real audio"),
        (not (day / "info.txt").exists(),
         "non-audio extras not staged"),
        ("transcript-craig.txt" in p.stdout,
         "extras reported for the agent's judgment"),
    ]

    empty = tmp / "empty.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "no audio here")
    p = run(str(empty), "--out", str(out))
    checks.append((p.returncode == 1,
                   f"audio-free download refuses (got {p.returncode})"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: capture module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
