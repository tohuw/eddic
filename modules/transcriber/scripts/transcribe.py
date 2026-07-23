# /// script
# requires-python = ">=3.9"
# ///
"""eddic transcribe — session audio to a sources/ transcript.

Usage:
    uv run transcribe.py <audio-file-or-dir> --out <sources/session-N.md>
        [--model PATH] [--whisper whisper-cli] [--session "Session 3"]
    uv run transcribe.py --from-json <dir-of-whisper-json> --out ... \
        [--session ...]

A directory input is treated as per-speaker tracks (a Craig export:
one file per voice, names like `1-username.flac`): each track is
transcribed separately with whisper.cpp, then the segments are merged
by timestamp into one readable transcript with speaker labels —
per-speaker tracks make attribution exact, which single-mic
recordings can never be. A single file transcribes without labels.

--from-json skips whisper and merges existing whisper.cpp JSON output
(`-oj`); this is also how the module verifies without audio.

Output is a sources file: `authorship: transcript` frontmatter, a
mishearings section for corrections discovered later, and
`[H:MM:SS] speaker: text` lines. Exit 0 written, 1 a track failed,
2 usage error.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

AUDIO_EXTS = {".flac", ".wav", ".mp3", ".m4a", ".ogg", ".aac", ".opus"}
GAP_BREAK_MS = 30_000


def speaker_from_name(stem):
    """Craig names tracks like `1-username` or `01_username`."""
    return re.sub(r"^\d+[-_]", "", stem) or stem


def run_whisper(audio, whisper, model, workdir):
    out_base = workdir / audio.stem
    cmd = [whisper, "-f", str(audio), "-oj", "-of", str(out_base)]
    # Per-speaker tracks (a Craig export) are mostly silence for any one
    # voice, and vanilla whisper hallucinates loops over the silence — the
    # same phrase repeated for minutes, which corrupts most of the file.
    # Drop the failed silent segments instead of looping: no context
    # carryover (-mc 0, so a loop can't feed itself), no temperature
    # fallback (-nf, the fallback is what hallucinates), and stricter
    # entropy/logprob fail thresholds so low-confidence silence is dropped.
    cmd += ["-mc", "0", "-nf", "-et", "2.8", "-lpt", "-1.0"]
    if model:
        cmd += ["-m", str(model)]
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    json_path = out_base.with_suffix(".json")
    if proc.returncode != 0 or not json_path.exists():
        print(f"whisper failed on {audio.name}:\n{proc.stderr[-2000:]}",
              file=sys.stderr)
        return None
    return json_path


def segments_from_json(json_path, speaker):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segs = []
    for item in data.get("transcription", []):
        text = item.get("text", "").strip()
        start = (item.get("offsets") or {}).get("from", 0)
        if text:
            segs.append((start, speaker, text))
    return segs


def merge(segments):
    """Sort across tracks, coalesce consecutive same-speaker runs,
    break paragraphs at long silences."""
    segments.sort(key=lambda s: s[0])
    merged = []
    for start, speaker, text in segments:
        if (merged and merged[-1][1] == speaker
                and start - merged[-1][2] < GAP_BREAK_MS):
            merged[-1] = (merged[-1][0], speaker, start,
                          merged[-1][3] + " " + text)
        else:
            merged.append((start, speaker, start, text))
    return [(s, sp, tx) for s, sp, _, tx in merged]


def stamp(ms):
    s = ms // 1000
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def render(merged, session, origin):
    lines = ["---", "authorship: transcript", f"origin: {origin}", "---",
             "", f"# {session} — transcript", "",
             "## Known mishearings", "",
             "(corrections land here as they are discovered; the",
             "transcript body is never edited)", "", "## Transcript", ""]
    for start, speaker, text in merged:
        who = f" {speaker}:" if speaker else ""
        lines.append(f"[{stamp(start)}]{who} {text}")
        lines.append("")
    return "\n".join(lines)


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    pos = []
    skip = False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = a not in ()
            continue
        pos.append(a)
    out = Path(opts["--out"]) if "--out" in opts else None
    session = opts.get("--session", "Session")
    if not out or (not pos and "--from-json" not in opts):
        print(__doc__.strip(), file=sys.stderr)
        return 2

    segments, origin = [], ""
    if "--from-json" in opts:
        jdir = Path(opts["--from-json"])
        origin = jdir.name
        for j in sorted(jdir.glob("*.json")):
            segments += segments_from_json(j, speaker_from_name(j.stem))
    else:
        src = Path(pos[0])
        origin = src.name
        whisper = opts.get("--whisper", "whisper-cli")
        model = opts.get("--model")
        workdir = out.parent / f".{out.stem}-whisper"
        workdir.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            tracks = sorted(p for p in src.iterdir()
                            if p.suffix.lower() in AUDIO_EXTS)
            if not tracks:
                print(f"no audio tracks in {src}", file=sys.stderr)
                return 2
            for t in tracks:
                j = run_whisper(t, whisper, model, workdir)
                if not j:
                    return 1
                segments += segments_from_json(j, speaker_from_name(t.stem))
        else:
            j = run_whisper(src, whisper, model, workdir)
            if not j:
                return 1
            segments += segments_from_json(j, "")

    merged = merge(segments)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(merged, session, origin), encoding="utf-8")
    print(f"wrote {out} ({len(merged)} merged segment(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
