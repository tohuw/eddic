# /// script
# requires-python = ">=3.9"
# ///
"""eddic ingest — the deterministic half of turning a session into canon.

Usage:
    uv run ingest.py --glossary [--wiki DIR]
    uv run ingest.py --index <transcript>
    uv run ingest.py --scaffold <transcript> --session N [--wiki DIR]
    uv run ingest.py --redact <transcript> [--write]
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG)

Writing the recap is the agent's job and always will be — that is the
one step in Eddic where prose has to be composed rather than computed.
What this script does is everything around it that must not be
improvised: seeding the transcriber with the campaign's invented names,
listing the anchors a claim can cite, scaffolding the page with honest
frontmatter, and stripping what the table said off the record before any
of it reaches a model.

  --glossary  A whisper initial prompt built from the wiki's own page
              titles plus every correction recorded in a transcript's
              "Known mishearings" section. Invented proper nouns are
              exactly what wrecks speech recognition, and the campaign
              already knows all of them; feeding them forward is the
              cheapest accuracy win available.

  --index     The citable anchors in a transcript: every timestamp, its
              speaker, and the opening words. An agent writing a recap
              cites from this rather than inventing a plausible time.

  --scaffold  The recap page, stamped with `sources:` naming the
              transcript, `authorship: machine`, and no visibility
              marker — a recap starts DM-only like every other page and
              is marked player-visible deliberately, after someone has
              read it.

  --redact    Removes every `[OTR] ... [/OTR]` region. Anything a table
              wants off the record is cut here, before the transcript is
              read by anything. Prints to stdout; `--write` edits in
              place, leaving a marker recording that a cut was made so
              the gap is honest rather than invisible.

Exit codes: 0 ok, 1 refused, 2 usage error.
"""

import json
import os
import re
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
TIMESTAMP = re.compile(r"^\[(\d+:\d{2}:\d{2})\](?:\s*([^:]{1,40}):)?\s*(.*)$")
H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
OTR_OPEN = re.compile(r"^\s*\[OTR\]\s*$", re.I)
OTR_CLOSE = re.compile(r"^\s*\[/OTR\]\s*$", re.I)
MISHEARD = re.compile(r"^-\s*(.+?)\s*(?:->|→)\s*(.+?)\s*$")
GLOSSARY_CAP = 60


# --- BEGIN SHARED wikilib: split_frontmatter ---
def split_frontmatter(text):
    """(frontmatter dict, body) — flat `key: value` pairs only, top level
    only, no YAML dependency. A page with no frontmatter yields ({}, text),
    which is what makes every visibility judgment fail closed."""
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm = {}
                for ln in lines[1:i]:
                    if ":" in ln and not ln.startswith((" ", "\t")):
                        k, _, v = ln.partition(":")
                        fm[k.strip()] = v.strip()
                return fm, "\n".join(lines[i + 1:])
    return {}, text
# --- END SHARED wikilib ---


def page_titles(wiki):
    """Every page's H1 — the campaign's proper nouns, already curated by
    the fact that someone made a page for them."""
    out = []
    for p in sorted(wiki.rglob("*.md")):
        if p.name in NON_CONTENT:
            continue
        _, body = split_frontmatter(p.read_text(encoding="utf-8",
                                                errors="replace"))
        m = H1.search(body)
        if m:
            title = m.group(1).strip()
            # a recap's "Session 4 — ..." title teaches whisper nothing
            if title and not title.lower().startswith("session "):
                out.append(title)
    return out


def corrections(wiki, sources):
    """Every `- misheard -> correct` line under a Known mishearings
    heading, from transcripts wherever they live."""
    out = []
    for root in (wiki, sources):
        if not root or not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            if "Known mishearings" not in text:
                continue
            section = text.partition("Known mishearings")[2].partition("\n## ")[0]
            for line in section.splitlines():
                m = MISHEARD.match(line.strip())
                if m:
                    out.append(m.group(2).strip())
    return out


def glossary(wiki, sources):
    seen, terms = set(), []
    for t in corrections(wiki, sources) + page_titles(wiki):
        k = t.lower()
        if k not in seen and len(t) < 60:
            seen.add(k)
            terms.append(t)
    return terms[:GLOSSARY_CAP]


def anchors(transcript_text):
    out = []
    for line in transcript_text.splitlines():
        m = TIMESTAMP.match(line)
        if m:
            out.append((m.group(1), (m.group(2) or "").strip(),
                        m.group(3).strip()))
    return out


def redact(text):
    """Drop every [OTR]...[/OTR] region. Returns (text, cuts). An
    unclosed region runs to the end of the file: if a table said to stop
    recording and nobody said to start again, the safe reading is that
    they meant it."""
    out, cuts, skipping = [], 0, False
    for line in text.splitlines():
        if OTR_OPEN.match(line):
            skipping = True
            cuts += 1
            out.append("*(a passage was taken off the record here)*")
            continue
        if OTR_CLOSE.match(line):
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out) + "\n", cuts


def scaffold(session, transcript_rel):
    return (f"---\nauthorship: machine\ncuration: agent\ningest: derived\n"
            f"sources: {transcript_rel}\n---\n\n"
            f"# Session {session}\n\n"
            f"STUB\n")


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    flags = {a for a in argv if a.startswith("--")}
    wiki = Path(opts["--wiki"]) if "--wiki" in opts else None
    sources = Path(opts["--sources"]) if "--sources" in opts else None
    if wiki is None and os.environ.get("EDDIC_CONFIG"):
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        wiki = root / cfg.get("wiki_dir", "wiki")
        sources = root / cfg.get("sources_dir", "sources")

    if "--glossary" in flags:
        if not wiki or not wiki.is_dir():
            print("--glossary needs a wiki (--wiki DIR or EDDIC_CONFIG)",
                  file=sys.stderr)
            return 2
        terms = glossary(wiki, sources)
        if not terms:
            print("", end="")
            return 0
        # whisper takes a plain sentence; a bare comma list primes names
        # without teaching it a format it will then try to imitate.
        print("Names in this recording: " + ", ".join(terms) + ".")
        return 0

    target = opts.get("--index") or opts.get("--scaffold") or \
        opts.get("--redact")
    if not target:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    tpath = Path(target)
    if not tpath.is_file():
        print(f"not a file: {tpath}", file=sys.stderr)
        return 2
    text = tpath.read_text(encoding="utf-8", errors="replace")

    if "--index" in flags:
        found = anchors(text)
        for ts, who, said in found:
            label = f"{who}: " if who else ""
            print(f"#t={ts}  {label}{said[:70]}")
        print(f"\n{len(found)} anchor(s) — cite one as "
              f"<!-- src: {tpath.name}#t=H:MM:SS -->", file=sys.stderr)
        return 0

    if "--redact" in flags:
        cleaned, cuts = redact(text)
        if "--write" in flags:
            tpath.write_text(cleaned, encoding="utf-8")
            print(f"redacted {cuts} passage(s) in {tpath}")
        else:
            print(cleaned, end="")
            print(f"{cuts} passage(s) would be cut", file=sys.stderr)
        return 0

    if "--scaffold" in flags:
        session = opts.get("--session")
        if not session:
            print("--scaffold needs --session N", file=sys.stderr)
            return 2
        if not wiki or not wiki.is_dir():
            print("--scaffold needs a wiki (--wiki DIR or EDDIC_CONFIG)",
                  file=sys.stderr)
            return 2
        dest = wiki / "sessions" / f"session-{session}.md"
        if dest.exists():
            print(f"refusing to overwrite {dest}", file=sys.stderr)
            return 1
        try:
            rel = tpath.resolve().relative_to(wiki.resolve()).as_posix()
        except ValueError:
            rel = tpath.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(scaffold(session, rel), encoding="utf-8")
        print(f"scaffolded {dest} (sources: {rel})")
        return 0

    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
