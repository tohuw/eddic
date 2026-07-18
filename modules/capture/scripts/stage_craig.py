# /// script
# requires-python = ">=3.9"
# ///
"""eddic stage-craig — stage a Craig download into the campaign.

Usage:
    uv run stage_craig.py <craig-zip-or-dir> [--date YYYY-MM-DD]
        [--out <sessions/raw>]
    (bare, as a vendored eddic verb: the campaign root comes from
     EDDIC_CONFIG and output defaults to <campaign>/sessions/raw)

Takes the zip (or already-unpacked folder) Craig hands the owner and
stages the per-speaker tracks into sessions/raw/<date>/, the layout
the transcriber reads. Handles the known Craig quirk where a track
arrives as a *directory* named like `1-name.flac` with the real
audio inside: it is flattened to the file it should have been.
Non-audio files in the download (info.txt, Craig's own transcripts
on premium) are left alone and listed so the agent can judge them.

Exit codes: 0 staged, 1 nothing stageable, 2 usage error.
"""

import os
import shutil
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

AUDIO_EXTS = {".flac", ".wav", ".mp3", ".m4a", ".ogg", ".aac", ".opus"}


def main(argv):
    args, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i]] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        else:
            args.append(argv[i])
            i += 1
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    src = Path(args[0])
    if not src.exists():
        print(f"no such download: {src}", file=sys.stderr)
        return 2

    out = None
    if os.environ.get("EDDIC_CONFIG"):
        root = Path(os.environ["EDDIC_CONFIG"]).parent.parent
        out = root / "sessions" / "raw"
    if "--out" in opts:
        out = Path(opts["--out"])
    if out is None:
        print("no output dir: set --out or run as an eddic verb",
              file=sys.stderr)
        return 2
    day = opts.get("--date", date.today().isoformat())
    dest = out / day

    tmp = None
    if src.is_file() and src.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="eddic-craig-"))
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        src = tmp

    staged, other = [], []
    try:
        for p in sorted(src.rglob("*")):
            name = p.name
            if p.is_dir() and Path(name).suffix.lower() in AUDIO_EXTS:
                # the folder-named-.flac quirk: real audio is inside
                inner = [f for f in sorted(p.iterdir()) if f.is_file()]
                if inner:
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(inner[0], dest / name)
                    staged.append(name)
                continue
            if not p.is_file() or any(part.suffix.lower() in AUDIO_EXTS
                                      for part in p.parents):
                continue
            if Path(name).suffix.lower() in AUDIO_EXTS:
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dest / name)
                staged.append(name)
            else:
                other.append(p.name)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    if not staged:
        print("no audio tracks found in the download", file=sys.stderr)
        if other:
            print("non-audio files present: " + ", ".join(sorted(other)),
                  file=sys.stderr)
        return 1
    print(f"staged {len(staged)} track(s) to {dest}:")
    for name in staged:
        print(f"  {name}")
    if other:
        print("also in the download (left for your judgment): "
              + ", ".join(sorted(other)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
