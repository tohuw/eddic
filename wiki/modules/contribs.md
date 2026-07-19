# contribs

The contribs module supplies the machinery and operating discipline of
Eddic's transaction arc: the means by which a campaign that has absorbed
material from many hands can later be packaged for sale without shipping
anything whose rights are unclear. It treats contributed material as
overlays that shadow rather than replace base pages, computes rights
status from a derivation graph, records consent as hash-pinned entries in
the operation log, and provides `eddic bundle` — a deterministic fence
that packages what is cleared and refuses everything else,
all-or-nothing. The module is entirely local and free, stdlib Python run
through uv; the fence is a build refusal, not a service. It touches the
[wiki](wiki.md) and [lint](lint.md) surfaces and depends on
[cli](cli.md), wiki, and lint. The schema side —
the contribs directory layout, the `replaces:` and `derived-from:` keys,
the transactability axis, the log types — is defined in the wiki module's
stamped instructions; contribs provides the verb that enforces it.

## The overlay model

Contributions are routed through `contribs/<contributor-id>/` rather than
edited into base pages. A contribution is either a new page, placed at its
wiki-relative path, or a rewrite of an existing base page, marked with
`replaces:` frontmatter naming the base page it shadows. Every contrib
file carries an `authorship:` id identifying its contributor. Building the
effective wiki overlays these files onto the base tree: a contrib page's
`replaces:` target, or its path relative to the contributor directory,
names the slot it occupies. Two contributions claiming the same slot are a
conflict, and the build refuses rather than guessing which wins. Because
overlays shadow rather than overwrite, the base page remains on disk and
the original authorship is never lost — the transaction can always be
reconstructed.

## Rights are computed, not judged

The fence never makes an editorial call about whether material is clear.
It computes clearance from ancestry. A page is clear if and only if
nothing in its ancestry — its own declared authorship, the contributor of
any overlay occupying its slot, and the chain of pages it declares itself
`derived-from:` — traces to a contributor, other than the campaign's
declared author, who lacks a valid consent entry. The computation is
fail-closed: unresolvable or unknown ancestry counts as taint, not as
clearance. Generic authorship values (`human`, `agent`, `machine`,
`transcript`) are not treated as personal contributors requiring
clearance, with one exception below. Taint propagates: a page derived from
an uncleared base is itself uncleared until the base clears.

## Transactability and consent

Whether a page may be sold at all is a separate axis from whether its
rights are clear, and it is the author's to set, page by page. A page
marked `transactability: transactable` is cleared original work.
`transactable-with-attribution`, carrying the required credit text in an
`attribution:` frontmatter key, is licensed material that must ship with
credit. Anything unmarked is `local-only` and the fence excludes it
silently — that exclusion is the fence working, not an error, so material
taught to a campaign but not owned by it simply never leaves.

Consent is recorded in the operation log as `consent` entries whose body
lists each cleared fragment as a line pinning its path to a sixteen-hex
`sha256:` prefix. A contributor is cleared when their latest consent entry
covers every one of their current files at their current hashes. The
pinning is what makes clearance honest: if a contributor's file changes
after they signed off, the recorded hash no longer matches, the clearance
goes stale, and the fence refuses until a fresh sign-off is logged. Pages
whose authorship is `transcript` are multi-author by nature — the table's
own recorded words — and clear only under a table-wide consent entry whose
summary begins with `table`, never through any single contributor's
sign-off.

## The verb

`eddic bundle` drives the module. Run bare as a vendored verb it reads its
paths from `EDDIC_CONFIG` (the wiki directory, the contribs directory, the
log name, and the declared author, writing to `dist/bundle/`); run
directly it takes `--src`, `--contribs`, `--out`, `--log`, and `--author`.
Its exit codes are 0 for a clean build, 1 for a refusal with reasons
listed, and 2 for a usage error.

`eddic bundle --receipts <contributor>` prints that contributor's current
fragments with their hashes together with a ready-to-append consent entry
dated today — the concrete artifact shown to a contributor for sign-off,
appended to the log verbatim only on their approval. `eddic bundle
--check` verifies the attribution log against the tree without building:
it confirms that every contributed file is accounted for by an
`attribution` entry at its current hash, so the invariant that the full
corpus equals the pure corpus plus its attribution log is checked
continuously rather than discovered as silent rot. A contribution lands
with an `attribution` log entry recording its fragments and hashes; a
`consent` entry clears it for sale; a `sever` entry, made only by the
author and only deliberately, asserts clean-room status by removing a
`derived-from:` link.

## What a clean build ships

`eddic bundle` refuses, writing nothing at all, when no author is
declared, when overlays conflict, when a page marked transactable has
ancestry reaching an uncleared contributor, when a clearance is stale, or
when nothing is marked transactable. A clean run writes `dist/bundle/`:
the cleared wiki pages, DM-only pages included — visibility never filters
a sale, because the buyer becomes their own table's DM and a sale ships
the full truth — plus any assets, the campaign's agent instructions,
and a generated `CREDITS.md` listing every attribution-bearing page's
required credit. The operation log itself never ships, nor do sources or
`.eddic` state; sources travel only in a deluxe offering where every
transcript already carries table consent.

## Preflight and discipline

The module presumes cli, wiki, and lint already applied at versions whose
lint knows the contrib checks and whose wiki applies overlays, and a
declared author — the holder of transaction rights, who need not be the
DM. When author and DM differ, the DM's own writing is itself a
contribution needing clearance like anyone else's, and the transactability
marks belong to the author, not the DM. Severing a derivation defaults to
never; `derived-from:` is removed only by owner directive with a `sever`
entry stating why clean-room status is asserted. Attribution is logged at
file granularity — one entry per contribution event, fragments listed per
file — because the file is the unit the overlay system moves.

This module embodies the transaction arc described in the
[design principles](../design/principles.md) and honors the
[firewall](../concepts/the-firewall.md) without deferring to it: a sale
crosses the DM/player boundary deliberately, shipping DM pages while the
firewall keeps them from players day to day. See the
[modules index](index.md) for the surrounding toolkit and
[Eddic](../index.md) for the whole.
