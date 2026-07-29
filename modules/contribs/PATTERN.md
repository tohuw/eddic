# Pattern: contributions and the sale-build fence

Gives a campaign the transaction arc (DESIGN: "The transaction arc"):
player material as overlays that shadow rather than replace, rights
status computed from a derivation graph, consent as hash-pinned log
entries, and `eddic bundle` — the deterministic fence that packages
what is cleared and refuses everything else. The schema side
(contribs layout, `replaces:`/`derived-from:`, the transactability
axis, log types) lives in the wiki module's stamped AGENTS.md; this
module supplies the machinery and the operating discipline.

## Preflight

- cli, wiki, and lint patterns applied at current versions (lint must
  know the contrib checks; project must apply overlays — wiki 0.3.0 /
  lint 0.3.0 or later).
- An **author** is known: the holder of transaction rights, who may
  not be the DM. When author and DM differ, understand what that
  means before proceeding: the DM's own writing is a contribution
  needing clearance like anyone else's, and transactability marks are
  the author's to make, not the DM's.

## Procedure

1. Vendor the verb and declare the author:

       cp scripts/bundle.py <campaign>/.eddic/lib/bundle.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module contribs --version 0.1.0 --verbs bundle

   then declare the author by re-running the cli module's stamp with
   `--author <id>` (idempotent; it only adds the config key).

2. Route contributions through `contribs/<contributor-id>/`: new
   pages at their wiki-relative paths, rewrites of base pages with
   `replaces:` frontmatter. Every contrib file carries the
   contributor's `authorship:` id. Lint and every build refuse
   conflicting or unattributed overlays — fix them when they appear,
   not later.

3. When a contribution lands, record it: an `attribution` log entry
   with the fragment paths and hashes (`--receipts <id>` prints the
   exact lines; swap `consent` for `attribution` in the header).
   `eddic bundle --check` verifies the invariant — full corpus =
   pure corpus + attribution log — and drift shows up as a red
   check, not silent rot.

4. Mark transactability as the author directs: `transactable` for
   cleared original work, `transactable-with-attribution` (with the
   credit text in `attribution:`) for licensed-with-credit material,
   nothing for everything else — unmarked is `local-only` and the
   fence excludes it silently.

5. To clear a contributor: `eddic bundle --receipts <id>`, show them
   their own fragments, and on their approval append the printed
   consent entry to the log verbatim. Hashes pin what was consented
   to: if their content changes afterward, the clearance goes stale
   and the fence refuses until a fresh sign-off. Session transcripts
   clear only via a table-wide entry (`consent | table ...`).

6. Build: `eddic bundle`. It refuses without an author, on any
   marked-but-uncleared ancestry, on a page marked for sale whose
   authorship is machine or unmarked, and when nothing is
   transactable; a clean run writes `dist/bundle/` — cleared wiki (DM
   pages included: a sale ships the full truth), assets, campaign
   instructions, injected credits, and no operation log.

7. **Walk the owner to clearable.** The fence tells the truth but it
   tells it all at once, and an owner who asked "can I sell this?"
   should not meet a wall of refusals in a schema they have never
   read. Run `eddic bundle --check`, then work the refusals *with*
   them, one page at a time, in their language — "this page is the
   one I wrote from your notes after session four; as it stands it
   is my writing, not yours."

   Every page ends in one of three places. It **ships**, because a
   person wrote it and the rights are clean. It gets **rewritten** —
   you interview them through it with the writing assistant until the
   page is theirs in their own words, which is what makes it honestly
   `mixed` and sellable; this is the path for material they care
   about and the only path that converts machine prose. Or it is
   **dropped** from the sale: unmark it and it stays in the campaign
   exactly as it is, still served, still linked, simply not sold. The
   projection already computes that exclusion, so dropping a page
   costs nothing and loses nothing.

   Say plainly, once, which of the three each page is heading for,
   and let them choose. Do not offer to "fix the marking" on machine
   prose, and do not accept the instruction if it comes: re-marking
   is the one move that turns an honest refusal into a false claim
   about who wrote the thing. There is no detector here and there
   never will be — the marks are their sworn word, and the whole
   arrangement runs on friction and honesty rather than forensics.

8. Deliver by private repository. The owner publishes the bundle to a
   private Git repository on their forge and adds each buyer as a
   collaborator; the buyer's own agent reads the campaign from there
   like any other. Access control, revocation, and delivery are the
   forge's job, which is what keeps Eddic out of the business of
   running a service, holding content, or asking anyone to make an
   account they do not already have. Warn once, and only once,
   because it is the one mistake that cannot be undone: a pull
   request against a *public* repository is publication. That is
   fine, even good, for a campaign given away — and fatal for one
   meant to be sold.

## Decision points

- **Severing a derivation.** Default: never. `derived-from:` is
  removed only by the author, only deliberately, only with a `sever`
  log entry stating why clean-room status is being asserted. An
  agent may draft disentangled prose, but the graph changes by owner
  directive alone.
- **What ships beyond the wiki.** Default: wiki pages, assets, the
  campaign's agent instructions (AGENTS.md and its stub), CREDITS.md
  — no sources, no operation log, no `.eddic` state. Include sources only for a
  deluxe offering where every transcript carries table consent.
- **Attribution granularity.** Default: one log entry per
  contribution event, fragments listed per file. Do not log below
  file granularity; the file is the unit the overlay system moves.
- **Machine-authored pages in a sale.** Default: drop them. Unmarking
  is instant, keeps the page in the campaign, and costs the seller a
  page nobody was entitled to sell anyway. Rewriting by interview is
  worth it only where the page carries something the buyer is
  actually paying for — a signature location, the through-line of an
  arc — and it is real work, so quote it honestly as such: an hour
  with the owner per substantial page, not a pass you can run for
  them. Never propose the third option, because there isn't one.
- **Where the sale bundle lives.** Default: a private repository per
  campaign on the owner's existing forge, buyers added as
  collaborators. Reach for anything heavier only when the buyer count
  makes collaborator management the bottleneck, and recognize that as
  the moment the owner is running a storefront rather than selling a
  campaign — a different undertaking, with a different appetite for
  infrastructure, and not one Eddic's machinery pretends to cover.

## Verify

- `uv run modules/contribs/verify/run.py` — plants a campaign and
  proves the fence: no-author refusal, uncleared and
  derived-from-tainted refusal, transcript-without-table-consent
  refusal, receipt/consent round-trip, correct bundle contents (DM
  page in, local-only out, credits injected, log withheld), the
  full = pure + log check, and stale-clearance refusal after
  post-sign-off drift.
- In a real campaign: `eddic bundle --check` green after every
  contribution lands; a deliberate dirty run (`--author` unset or a
  contributor uncleared) refuses loudly before you ever need it to.
