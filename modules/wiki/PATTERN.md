# Pattern: the campaign wiki

Gives a campaign its knowledge architecture: sources, the DM-master
wiki, visibility, twin pages, the operation log, and the player
projection. This is the substrate every player-facing surface builds
on — and the schema you (the agent) maintain across sessions.

## Preflight

- The cli pattern is applied (`.eddic/` exists; `eddic.py doctor`
  passes) and the lint module is vendored.
- Identify which case you are in: a **new campaign** (empty wiki dir)
  or **adopting an existing wiki** (a tree of pages that predates
  Eddic). Adoption has extra steps below.

## Procedure

1. Stamp the schema and seeds (replace `{{SITE_NAME}}` and `{{LOG}}`
   with the config values as you copy):

       templates/AGENTS-campaign.md -> <campaign>/AGENTS.md
       templates/CLAUDE-stub.md     -> <campaign>/CLAUDE.md
       templates/index-seed.md      -> <wiki>/index.md      (if absent)
       templates/index-dm-seed.md   -> <wiki>/index.dm.md   (if absent)
       templates/log-seed.md        -> <wiki>/<log>         (if absent)

2. Vendor the projection verb:

       cp scripts/project.py <campaign>/.eddic/lib/project.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module wiki --version 0.1.0 --verbs project

3. Create `sources/` and move raw material there, adding
   `authorship:` frontmatter (a contributor id for each person's own
   prose — set up the DM-only roster per the stamped schema —
   `transcript` for session captures). Read the authorship rules in
   the stamped AGENTS.md — they bind you from now on. Attribution is
   captured at write time or lost; adopting an existing wiki is the
   last cheap moment to ask "who wrote this?" page by page.

4. **Adoption only.** If the campaign's old pipeline had a static
   asset directory (maps, images, standalone HTML), migrate the
   player-safe assets into `<wiki>/assets/` (DM-only assets under a
   path containing `.dm`, which never projects) and rewrite the
   pages' site-rooted links (`/maps/...`) to page-relative ones —
   lint flags these as `absolute-link`; they resolve on no Eddic
   surface. Check migrated HTML for internal absolute references
   too. Site chrome (stylesheets, templates) stays behind: the
   render module brings its own.

5. **Adoption only.** Walk the existing pages and mark visibility.
   Fail closed: mark `visibility: player` only on pages whose entire
   content the table has seen in play; leave everything else
   unmarked (DM-only). Where a page mixes revealed and secret
   material, split it into twins (player page under the canonical
   name, `.dm.md` for the rest). This marking is judgment about
   spoilers — do it page by page with the owner, never in bulk.

6. Project and check the loop:

       uv run <campaign>/.eddic/eddic.py lint
       uv run <campaign>/.eddic/eddic.py project

   Projection refuses all-or-nothing on any firewall breach; fix
   breaches by fixing pages (or splitting twins), never by weakening
   a marker without the owner's say.

7. Log a `schema` entry (new campaign) or `ingest` entry (adoption)
   and commit.

## Decision points

- **Taxonomy.** Default: the stock categories (characters, places,
  story, concepts, eras, species, sessions, systems). Trim or extend
  only for a campaign that clearly needs it; log deviations as
  `schema`.
- **Twin granularity.** Default: twin pages only for topics that
  actually reveal progressively; wholly-safe pages just get
  `visibility: player`, wholly-secret pages get nothing. Do not
  pre-create empty twins.
- **Adoption bulk-marking.** Default: no. Visibility marking on an
  existing wiki is per-page judgment with the owner (step 5); the
  only safe bulk operation is leaving pages unmarked (DM-only).

## Verify

- `uv run modules/wiki/verify/run.py` — projects a planted campaign:
  player pages and assets arrive, DM pages and `.dm` assets are
  withheld, and a planted breach (player page linking a DM page)
  refuses the whole projection without writing.
- In the real campaign: `eddic.py lint` clean or triaged;
  `eddic.py project` exits 0; eyeball `dist/player/` and confirm
  nothing DM-only is present; the log carries the entry.
