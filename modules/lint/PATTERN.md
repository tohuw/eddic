# Pattern: wiki lint

Gives a campaign a repeatable health check for its wiki: a
deterministic reporter that finds structural rot, and a triage
discipline for what you (the agent) may fix and what you must
escalate. This is the reporter half of a reporter/model seam — the
script never edits anything; judgment about findings is your half.

## Preflight

- The target is a wiki directory: a tree of `.md` pages connected by
  relative links, with an optional `index.md` root and an optional
  operation log (`log.md` by default).
- Python ≥ 3.9 is reachable — `uv run scripts/eddic_lint.py` (uv
  bootstraps Python) or any system `python3`. The reporter is
  stdlib-only; there is nothing else to install.
- If the wiki lives in git, confirm a clean working tree before any
  fixes, so lint fixes land as their own reviewable change.

## Procedure

1. Run the reporter:

       uv run scripts/eddic_lint.py <wiki_dir> [--json] [--strict] [--log NAME]

   Exit 0 is clean, 1 means errors (or warnings under `--strict`),
   2 is a usage problem. Use `--json` when you are consuming the
   findings rather than showing them.

2. Triage every finding into *fix* or *escalate*:

   **You may fix without asking** (mechanical, art-free, reversible):
   - `broken-link` / `broken-anchor` where the target plainly moved or
     was renamed — repoint the link. If the target never existed,
     create a stub page (H1, any known facts, final line `STUB`)
     rather than deleting the link.
   - `absolute-link` — a site-rooted path (`/maps/...`) resolving on
     no Eddic surface. If the target is a static asset, migrate it
     under `wiki/assets/` and rewrite the link page-relative (see the
     wiki pattern's adoption steps); if it names a wiki page, make
     the link relative.
   - `missing-h1` — add the title the filename and content imply.
   - `unreachable` / `orphan` — weave the page in: add it to the
     catalog/index and link it from at least one related page.
   - `tiny-unstubbed` — append the `STUB` marker.

   **You must escalate, never fix silently**:
   - `firewall-breach` — a player-visible page references DM-only
     material. Visibility is a safety property; changing either side
     is the owner's call.
   - `orphan`/`unreachable` on pages that look *deliberately* hidden
     (spoiler material, unlinked by design). Weaving those in is a
     leak. When in doubt, ask; wikis predating visibility frontmatter
     rely on being unlinked as their only firewall.
   - `stub-overgrown` — promotion from stub to page is editorial.
   - `log-malformed` — never rewrite history in an append-only log;
     report it and let the owner decide whether to annotate.
   - Anything whose fix would delete a page or alter human-authored
     prose (authorship preservation; see DESIGN.md).

3. Record a `lint` entry in the campaign's operation log: date, what
   was found, what was fixed, what was escalated.

4. If the campaign has a manifest, record this module and version.

## Decision points

- **Strictness.** Default: plain mode interactively; `--strict` inside
  routines and CI, where a warning nobody reads is a warning that
  never gets fixed.
- **Firewall scope.** Wikis with no visibility frontmatter get the
  check skipped (reported as info). Default: leave it skipped and note
  that the wiki module introduces visibility; do not invent
  frontmatter yourself.
- **Cadence.** Default: on demand now; when the routines module is
  applied, lint runs inside every maintenance pass.

## Verify

- `uv run verify/run.py` (or `python3 verify/run.py`) — runs the
  reporter against the planted fixture and requires exactly the
  expected findings and exit code.
- Run the reporter against the live wiki; confirm the report reads
  sensibly and exit codes match the summary line.
- After any fixes: re-run; previously-reported findings are gone, no
  new ones appeared, and the log carries the `lint` entry.
