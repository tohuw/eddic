# Pattern: wiki lint

Gives a campaign a repeatable health check for its wiki: a
deterministic reporter that finds structural rot, and a triage
discipline for what you (the agent) may fix and what you must
escalate. This is the reporter half of a reporter/model seam — the
script never edits anything; judgment about findings is your half.

The seam has two passes. The **structural** pass (`eddic_lint.py`) is
pure regex over the tree; it is Procedure steps 1–4. The **semantic**
pass (`semantic_review.py`) is the model half made concrete: a
deterministic script assembles a review packet — the pages, the player
projection kept separate, the semantic checklist, the findings schema —
and you, the reading model, work the checklist and emit findings. It is
Procedure step 5, and it catches only what regex cannot; it never
re-litigates what the structural floor already guarantees.

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
     prose (authorship preservation; see wiki/design/principles.md).

3. **Semantic pass (optional, model-run).** When the campaign is large
   enough that manual consistency review stops scaling, run the semantic
   lint — the reading-model complement to the regex reporter. It catches
   what structure cannot: DM-adjacent knowledge leaking through
   player-visible *prose* (not a link), encyclopedic/tonal drift,
   cross-page factual contradictions, dangling narrative references
   (named but never established), naming inconsistency, and stubs that
   read finished below the word threshold. It is scoped to NOT re-report
   any structural code — the packet's `not_in_scope` list names them.

   a. Build the player projection first (`eddic project`), so the
      firewall-in-prose check reads exactly what players see, never the
      master.

   b. Assemble the review packet:

          uv run scripts/semantic_review.py <wiki_dir> \
              --projection <projection_dir> [--out packet.json]

      It gathers the master pages and, *separately*, the projection
      pages; bundles the checklist; and pins the findings output schema
      (`{page, anchor_or_line, category, severity, finding,
      suggested_fix}`). The packet is a pure function of the tree.

   c. Work the checklist against the packet and emit findings as a JSON
      array matching that schema. Validate before you file:

          uv run scripts/semantic_review.py --validate findings.json

   d. File the findings. **Plain report (default):** write them to a
      review file or fold a summary into the `lint` log entry. **Filed
      to the DM's inbox (when the retrieval witness write path is
      enabled):** submit each finding through the retrieval MCP as a
      `suggest_edit` (`{path, suggestion, rationale}` — the finding's
      `suggested_fix` is the suggestion, its `finding` the rationale),
      so it lands as a pending suggestion the owner materializes with
      `eddic suggestions` and disposes by hand. Either way the output is
      advisory: findings are suggestions, never applied edits, and no
      human-authored prose is rewritten.

4. Record a `lint` entry in the campaign's operation log: date, what
   was found, what was fixed, what was escalated (a semantic pass notes
   how many findings it filed and by which path).

5. If the campaign has a manifest, record this module and version.

## Decision points

- **Strictness.** Default: plain mode interactively; `--strict` inside
  routines and CI, where a warning nobody reads is a warning that
  never gets fixed.
- **Firewall scope.** Wikis with no visibility frontmatter get the
  check skipped (reported as info). Default: leave it skipped and note
  that the wiki module introduces visibility; do not invent
  frontmatter yourself.
- **Cadence.** Default: on demand now; when the routines module is
  applied, the structural lint runs inside every maintenance pass. The
  semantic pass, being token-heavy, is its own routine
  (`routine-semantic-review`) on a slower cadence — between-sessions by
  default (see the routines module).
- **Semantic pass.** Default: off — the structural reporter is the
  whole health check for a small wiki, and a model pass on a handful of
  pages earns nothing. Turn it on when manual consistency review stops
  scaling (many pages, several contributors, spoilers threaded through
  prose). Worth it sooner if the campaign publishes a player surface,
  where firewall-in-prose leaks are costliest.
- **Finding delivery.** Default: file findings to the DM's review inbox
  as `suggest_edit` suggestions when the retrieval witness write path is
  enabled (they queue where the DM already triages), and fall back to a
  plain report — a review file plus the `lint` log entry — when it is
  not. Findings are advisory on either path; nothing is auto-applied.

## Verify

- `uv run verify/run.py` (or `python3 verify/run.py`) — runs the
  structural reporter against the planted fixture and requires exactly
  the expected findings and exit code, then drives `semantic_review.py`:
  the review packet builds from the fixture with the projection gathered
  separately, the checklist covers every category (firewall-prose
  included), the findings schema is pinned, `not_in_scope` names the
  deterministic codes, and the schema validator accepts a good findings
  document and rejects bad severity, bad category, and a missing key.
- Run the reporter against the live wiki; confirm the report reads
  sensibly and exit codes match the summary line.
- After any fixes: re-run; previously-reported findings are gone, no
  new ones appeared, and the log carries the `lint` entry.
- Semantic pass, live: build the packet against the projected wiki,
  work the checklist, validate the findings, and confirm each filed
  `suggest_edit` appears in `eddic suggestions` for the owner to
  dispose — with no wiki file altered by the pass itself.
