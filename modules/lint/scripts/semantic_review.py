# /// script
# requires-python = ">=3.9"
# ///
"""eddic semantic-review — assemble a review packet for the agentic
(semantic) wiki lint, and validate the findings it produces.

Usage:
    uv run semantic_review.py <wiki_dir> [--projection DIR] [--out FILE]
                              [--log NAME]
        Build the review packet (JSON) and print it (or write --out).
    uv run semantic_review.py --validate [FILE]
        Validate a findings document (from FILE or stdin) against the
        finding schema. Exit 0 all valid, 1 schema violations, 2 usage.
    (bare, as a vendored eddic verb: wiki_dir and the projection dir
     come from EDDIC_CONFIG.)

This is the deterministic half of the model-triage seam's *semantic*
pass — the complement to eddic_lint.py's structural pass. It never
edits anything and it makes no judgments: it gathers the material a
model needs (the DM master pages, and SEPARATELY the built player
projection for the firewall-in-prose check), bundles the semantic
checklist, and pins the findings output schema. The LLM judgment stays
the agent's; setup and aggregation are scriptable, reproducible, and
testable, so a run is a pure function of the wiki tree.

What the semantic pass catches is exactly what regex cannot, and it is
scoped to NOT re-litigate what the deterministic floor already
guarantees (see `not_in_scope` in the packet). Everything it produces
is advisory: the agent proposes, the human disposes; nothing is ever
auto-applied and human-authored prose is never rewritten.

Exit codes: 0 ok, 1 schema violations (validate) / runtime error,
2 usage error.
"""

import json
import os
import re
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
STUB_WORD_LIMIT = 150

# The semantic checklist: what a careful maintainer catches by reading,
# that a structural reporter cannot. Each item names the deterministic
# check it complements so the pass never duplicates the floor.
CHECKLIST = [
    {
        "category": "firewall-prose",
        "severity": "error",
        "surface": "projection",
        "check": "Player-visible prose that reveals or strongly implies "
                 "DM-only knowledge — a secret identity, a hidden twist, a "
                 "trap, an NPC's true motive — even though the page links no "
                 "DM-only page. Read the projection as a player would and "
                 "ask what it gives away.",
        "complements": "firewall-breach: the structural lint catches a "
                       "player page that *links* a DM-only page; it cannot "
                       "read prose. Judge the projection text itself, never "
                       "the master.",
    },
    {
        "category": "tonal-drift",
        "severity": "warning",
        "surface": "master",
        "check": "Encyclopedic/tonal drift: a page that has slid out of the "
                 "wiki's self-contained, third-person encyclopedia register "
                 "— session-log narration, second-person table talk, "
                 "unresolved authorial notes, or meta-commentary — where a "
                 "retrieval-substrate fact page is intended.",
        "complements": "Nothing structural covers tone; this is judgment "
                       "the reporter has no signal for.",
    },
    {
        "category": "contradiction",
        "severity": "warning",
        "surface": "master",
        "check": "A fact asserted on one page that another page contradicts "
                 "— a date, a death, a location, a relationship, an "
                 "allegiance. Cite both pages in the finding.",
        "complements": "Links resolve structurally; the facts they carry do "
                       "not. Only reading catches a contradiction.",
    },
    {
        "category": "dangling-reference",
        "severity": "warning",
        "surface": "master",
        "check": "A narrative reference to a person, place, item, or event "
                 "that the wiki mentions but never establishes — named as if "
                 "known, with no page and no defining prose anywhere. The "
                 "reader is left with a name and nothing behind it.",
        "complements": "broken-link / orphan / unreachable are about the "
                       "link graph. This is about prose that references "
                       "something never written up at all — no link exists "
                       "to be broken.",
    },
    {
        "category": "naming-inconsistency",
        "severity": "warning",
        "surface": "master",
        "check": "One entity written more than one way — spelling variants, "
                 "an old name a rename missed, inconsistent titles or "
                 "epithets — that a reader would not reliably recognize as "
                 "the same thing (and a retrieval agent would miss).",
        "complements": "A mechanical rename propagates exact strings; it "
                       "cannot judge that two different strings mean the "
                       "same entity. Propose the canonical form; the owner "
                       "directs any propagation (authorship doctrine).",
    },
    {
        "category": "stub-overgrown-prose",
        "severity": "info",
        "surface": "master",
        "check": "A page still marked STUB that in fact reads as a complete, "
                 "promotable page — coherent, self-contained, done — "
                 "regardless of its word count.",
        "complements": "stub-overgrown fires only past the "
                       f"{STUB_WORD_LIMIT}-word threshold. This is the "
                       "judgment the threshold cannot make: a short page "
                       "that is nonetheless finished.",
    },
]

CATEGORIES = tuple(c["category"] for c in CHECKLIST)
SEVERITIES = ("error", "warning", "info")
FINDING_REQUIRED = ("page", "anchor_or_line", "category", "severity",
                    "finding", "suggested_fix")

# The deterministic floor already guarantees these; the semantic pass
# must NOT re-report them (no-egg-sucking; keep judgment off the floor).
NOT_IN_SCOPE = [
    "broken-link", "broken-anchor", "absolute-link", "missing-h1",
    "firewall-breach", "log-malformed", "orphan", "unreachable",
    "tiny-unstubbed", "stub-overgrown", "contrib-conflict",
    "contrib-collision", "contrib-replaces-missing", "contrib-unattributed",
    "invalid-transactability", "derived-from-missing",
]

OUTPUT_SCHEMA = {
    "shape": "a JSON array of finding objects (or {\"findings\": [...]})",
    "finding": {
        "page": "wiki-relative path of the page the finding concerns",
        "anchor_or_line": "a GitHub-style heading anchor locating it "
                          "(preferred), or 'L<n>' for a line reference",
        "category": "one of: " + ", ".join(CATEGORIES),
        "severity": "one of: " + ", ".join(SEVERITIES),
        "finding": "what is wrong, in one or two sentences; cite other "
                   "pages by path where the finding spans pages",
        "suggested_fix": "a remedy for the human to consider — a proposal "
                        "only, never applied automatically",
    },
    "example": {
        "page": "sunken-city.md",
        "anchor_or_line": "the-drowned-court",
        "category": "firewall-prose",
        "severity": "error",
        "finding": "The player-visible section states the Warden drowned "
                   "the court himself, which the DM notes mark as the "
                   "campaign's central hidden twist.",
        "suggested_fix": "Move the culpability sentence to the .dm twin, or "
                        "reword to the in-world rumor players actually hold.",
    },
}

SAFETY_RAILS = [
    "Advisory only: every finding is a suggestion, never an applied edit.",
    "The agent proposes; the human disposes. Nothing here reaches canon or "
    "any player-visible surface without the owner's explicit action.",
    "Never auto-rewrite human-authored prose. Mechanical, owner-directed "
    "transforms only; stylistic rewrites are out of bounds (authorship "
    "preservation).",
    "The firewall-prose check reads only the player PROJECTION, never the "
    "master — it judges what players actually see.",
    "Do not report anything in not_in_scope: the deterministic lint already "
    "guarantees it.",
]


def split_frontmatter(text):
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


def word_count(body):
    return len(re.sub(r"[^\w\s]", " ", body).split())


def is_stub(body):
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return bool(lines) and lines[-1] == "STUB"


def gather_master(root, log_name):
    pages = []
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        fm, body = split_frontmatter(
            p.read_text(encoding="utf-8", errors="replace"))
        pages.append({
            "path": p.relative_to(root).as_posix(),
            "visibility": (fm.get("visibility") or "dm").strip(),
            "words": word_count(body),
            "is_stub": is_stub(body),
            "body": body,
        })
    return pages


def gather_projection(proj, log_name):
    pages = []
    for p in sorted(proj.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        _, body = split_frontmatter(
            p.read_text(encoding="utf-8", errors="replace"))
        pages.append({"path": p.relative_to(proj).as_posix(), "body": body})
    return pages


def build_packet(root, projection, log_name):
    if projection and projection.is_dir():
        proj = {"status": "present", "dir": str(projection),
                "pages": gather_projection(projection, log_name)}
    else:
        proj = {"status": "absent",
                "note": "Run `eddic project` first: the firewall-prose "
                        "check needs the exact built player surface and is "
                        "BLOCKED without it. Every other check still runs "
                        "over the master."}
    return {
        "eddic_semantic_review": "1",
        "wiki_dir": str(root),
        "instructions": "Perform Eddic's semantic wiki lint. Work every "
                        "checklist item; read the master for all but "
                        "firewall-prose, which you judge on the projection "
                        "alone. Emit findings as a JSON array matching "
                        "output_schema. Respect every entry in safety_rails "
                        "and report nothing in not_in_scope.",
        "safety_rails": SAFETY_RAILS,
        "checklist": CHECKLIST,
        "output_schema": OUTPUT_SCHEMA,
        "not_in_scope": {
            "note": "The deterministic lint (eddic_lint.py) already "
                    "guarantees these; do NOT re-report them.",
            "codes": NOT_IN_SCOPE,
        },
        "projection": proj,
        "master_pages": gather_master(root, log_name),
    }


def validate_findings(doc):
    """Return a list of human-readable schema violations (empty == valid)."""
    if isinstance(doc, dict) and "findings" in doc:
        doc = doc["findings"]
    if not isinstance(doc, list):
        return ["top level must be a JSON array of findings "
                "(or an object with a 'findings' array)"]
    problems = []
    for i, f in enumerate(doc):
        where = f"finding[{i}]"
        if not isinstance(f, dict):
            problems.append(f"{where}: not an object")
            continue
        for key in FINDING_REQUIRED:
            if key not in f:
                problems.append(f"{where}: missing required key '{key}'")
        if f.get("severity") not in SEVERITIES:
            problems.append(f"{where}: severity {f.get('severity')!r} not "
                            f"one of {SEVERITIES}")
        if f.get("category") not in CATEGORIES:
            problems.append(f"{where}: category {f.get('category')!r} not "
                            f"one of {CATEGORIES}")
        for key in ("page", "anchor_or_line", "finding"):
            v = f.get(key)
            if key in f and (not isinstance(v, str) or not v.strip()):
                problems.append(f"{where}: '{key}' must be a non-empty string")
        if "suggested_fix" in f and not isinstance(f["suggested_fix"], str):
            problems.append(f"{where}: 'suggested_fix' must be a string")
    return problems


def do_validate(argv):
    src = next((a for a in argv if not a.startswith("--")), None)
    try:
        raw = (Path(src).read_text(encoding="utf-8") if src
               else sys.stdin.read())
    except OSError as e:
        print(f"semantic-review: cannot read {src}: {e}", file=sys.stderr)
        return 2
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"semantic-review: not valid JSON: {e}", file=sys.stderr)
        return 2
    problems = validate_findings(doc)
    if problems:
        for p in problems:
            print(f"INVALID {p}", file=sys.stderr)
        print(f"semantic-review: {len(problems)} schema violation(s)",
              file=sys.stderr)
        return 1
    n = len(doc["findings"] if isinstance(doc, dict) else doc)
    print(f"semantic-review: {n} finding(s), all schema-valid")
    return 0


def main(argv):
    if "--validate" in argv:
        return do_validate([a for a in argv if a != "--validate"])

    opts, positional = {}, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            opts[a] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        else:
            positional.append(a)
            i += 1

    log_name = opts.get("--log", "log.md")
    root = projection = None
    if not positional and os.environ.get("EDDIC_CONFIG"):
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        campaign = cfg_path.parent.parent
        root = campaign / cfg.get("wiki_dir", "wiki")
        projection = campaign / cfg.get("projection_dir", "dist/player")
        log_name = opts.get("--log", cfg.get("log", "log.md"))
    if positional:
        root = Path(positional[0])
    if "--projection" in opts:
        projection = Path(opts["--projection"])
    if root is None:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    packet = build_packet(root, projection, log_name)
    out = json.dumps(packet, indent=2, ensure_ascii=False)
    if opts.get("--out"):
        Path(opts["--out"]).write_text(out + "\n", encoding="utf-8")
        print(f"semantic-review: packet written to {opts['--out']} "
              f"({len(packet['master_pages'])} master page(s), "
              f"projection {packet['projection']['status']})",
              file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
