# /// script
# requires-python = ">=3.9"
# ///
"""Verify the transcriber's merge path (--from-json): two speakers'
whisper JSON interleave by timestamp, coalesce within a speaker,
break on long gaps, and land in a proper sources file."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "transcribe.py"


def whisper_json(items):
    return json.dumps({"transcription": [
        {"offsets": {"from": start, "to": start + 1500},
         "text": text} for start, text in items]})


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-transcriber-verify-"))
    jdir = tmp / "json"
    jdir.mkdir()
    (jdir / "1-dungeon_master.json").write_text(whisper_json([
        (0, "The gates of Sunton rise before you."),
        (2000, "A guard hails the party."),
        (95_000, "Night falls over the harbor."),
    ]), encoding="utf-8")
    (jdir / "2-warden_player.json").write_text(whisper_json([
        (4000, "I hail the guard right back."),
        (6000, "And I ask about the harbor."),
    ]), encoding="utf-8")

    out = tmp / "sources" / "session-1_transcript.md"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--from-json", str(jdir),
         "--out", str(out), "--session", "Session 1"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"FAIL: transcribe exit {proc.returncode}\n{proc.stderr}")
        return 1
    text = out.read_text(encoding="utf-8")
    body = text.partition("## Transcript")[2]
    lines = [ln for ln in body.splitlines() if ln.startswith("[")]

    checks = [
        ("authorship: transcript" in text, "sources frontmatter present"),
        ("## Known mishearings" in text, "mishearings section present"),
        (len(lines) == 3, f"3 merged segments (got {len(lines)}): "
                          "coalesce + gap break"),
        (lines[0].startswith("[0:00:00] dungeon_master:")
         and "guard hails" in lines[0],
         "same-speaker segments coalesced with label from track name"),
        (lines[1].startswith("[0:00:04] warden_player:"),
         "interleaved by timestamp across tracks"),
        (lines[2].startswith("[0:01:35] dungeon_master:"),
         "long gap breaks the paragraph"),
    ]
    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        print("\n" + body)
        return 1
    print("verify ok: transcriber module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
