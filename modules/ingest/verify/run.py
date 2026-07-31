# /// script
# requires-python = ">=3.9"
# ///
"""Verify the ingest module's deterministic floor: the glossary draws on
the campaign's own names, the anchor index reports exactly what the
transcript contains, scaffolding writes honest frontmatter and refuses to
clobber, and redaction cuts off-the-record passages (including an
unclosed one) while leaving a visible marker."""

import subprocess
import sys
import tempfile
from pathlib import Path

INGEST = Path(__file__).resolve().parent.parent / "scripts" / "ingest.py"

TRANSCRIPT = """---
authorship: transcript
---

# Session 4 — transcript

## Known mishearings

- warden's gate -> Warden's Gate
- sunk in city -> the Sunken City

## Transcript

[0:00:10] kestrel: We came by the low road.

[0:41:07] vagrant: The Warden would not speak of it.

[OTR]

[0:52:00] kestrel: unrelated personal aside

[/OTR]

[1:14:22] kestrel: The oath was sworn at the water line.
"""


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def run(*args):
    return subprocess.run([sys.executable, str(INGEST), *args],
                          capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-ingest-verify-"))
    wiki = tmp / "wiki"
    write(wiki, "index.md", "# The Realm\n\nThe catalog.\n")
    write(wiki, "places/sunken-city.md", "# The Sunken City\n\nDrowned.\n")
    write(wiki, "characters/warden.md", "# The Warden\n\nIts keeper.\n")
    write(wiki, "sessions/session-3.md", "# Session 3 — the low road\n\nOld.\n")
    tpath = write(wiki, "sessions/session-4-transcript.md", TRANSCRIPT)

    checks = []

    g = run("--glossary", "--wiki", str(wiki))
    checks += [
        (g.returncode == 0, f"glossary exits 0 (got {g.returncode})"),
        ("sunken city" in g.stdout.lower() and "warden" in g.stdout.lower(),
         "glossary carries the campaign's page titles"),
        (g.stdout.lower().count("sunken city") == 1,
         "a name recorded as a correction is not repeated from its page "
         "title"),
        ("Warden's Gate" in g.stdout,
         "glossary carries corrections from Known mishearings"),
        ("Session 3" not in g.stdout,
         "glossary skips recap titles (they teach the recognizer nothing)"),
    ]

    i = run("--index", str(tpath))
    checks += [
        (i.returncode == 0, f"index exits 0 (got {i.returncode})"),
        ("#t=0:41:07" in i.stdout and "#t=1:14:22" in i.stdout,
         "index reports the transcript's real anchors"),
        ("#t=9:99:99" not in i.stdout, "index invents no anchors"),
        ("vagrant" in i.stdout, "index carries the speaker"),
    ]

    r = run("--redact", str(tpath))
    checks += [
        (r.returncode == 0, f"redact exits 0 (got {r.returncode})"),
        ("unrelated personal aside" not in r.stdout,
         "redaction cuts the off-the-record passage"),
        ("off the record" in r.stdout,
         "redaction leaves a visible marker, not a silent gap"),
        ("[0:41:07]" in r.stdout and "[1:14:22]" in r.stdout,
         "redaction keeps everything outside the marked region"),
    ]

    # An unclosed [OTR] runs to end of file: if someone said stop and
    # nobody said start again, the safe reading is that they meant it.
    unclosed = write(wiki, "sessions/session-5-transcript.md",
                     "[0:00:01] a: on the record\n\n[OTR]\n\n"
                     "[0:00:02] a: everything after this is private\n")
    u = run("--redact", str(unclosed))
    checks += [
        ("on the record" in u.stdout and "private" not in u.stdout,
         "an unclosed off-the-record marker runs to the end of the file"),
    ]

    w = run("--redact", str(tpath), "--write")
    again = run("--redact", str(tpath), "--write")
    checks += [
        (w.returncode == 0 and "unrelated personal aside"
         not in tpath.read_text(encoding="utf-8"),
         "--write cuts the passage in place"),
        (again.returncode == 0,
         "redacting an already-redacted transcript is safe"),
    ]

    s = run("--scaffold", str(tpath), "--session", "4", "--wiki", str(wiki))
    recap = wiki / "sessions" / "session-4.md"
    body = recap.read_text(encoding="utf-8") if recap.exists() else ""
    checks += [
        (s.returncode == 0, f"scaffold exits 0 (got {s.returncode})"),
        ("authorship: machine" in body,
         "scaffold marks the recap machine-authored"),
        ("sources: sessions/session-4-transcript.md" in body,
         "scaffold names the transcript in sources:"),
        ("visibility:" not in body,
         "scaffold leaves the recap DM-only — marking it player is a "
         "decision, not a default"),
    ]
    again_s = run("--scaffold", str(tpath), "--session", "4",
                  "--wiki", str(wiki))
    checks.append((again_s.returncode == 1,
                   "scaffold refuses to overwrite an existing recap"))

    failed = [m for ok, m in checks if not ok]
    for ok, m in checks:
        print(("ok  " if ok else "FAIL"), m)
    if failed:
        return 1
    print("verify ok: ingest module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
