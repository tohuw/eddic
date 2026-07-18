# Pattern: driving Ørlǫg (the timeline)

Connects a campaign to its Ørlǫg story: chronology lives in the
timeline tool, the wiki states time in plain prose, and facts move
between them only by the owner's direction (DESIGN principle 10).
What this module adds is the **reconcile discipline** — timeline
writes happen on an isolated fork, validated, with merging reserved
to the owner — and the query cookbook for answering time questions
from the timeline instead of inventing a date syntax in prose.

## Preflight

- The campaign uses Ørlǫg (a story folder exists — by default under
  the owner's documents in the app's stories directory). No story,
  no module: do not create one from here; the story is the owner's,
  born in the app.
- Ørlǫg's headless CLI is reachable: an installed `orlog`, or a repo
  checkout run as `node <repo>/packages/cli/src/cli.ts` on Node 24+.
  Record the invocation in `.eddic/config.json` as `orlog_cmd` and
  the story path as `orlog_story`.
- The cli pattern is applied.

## Procedure

1. Vendor the verb and record it:

       cp scripts/reconcile.py <campaign>/.eddic/lib/reconcile.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module orlog --version 0.1.0 --verbs reconcile

2. **Reconcile flow** (only when the owner directs it — never as
   ambient maintenance):
   - Gather the facts to move: settled events from session recaps
     and the wiki's log since the last reconcile. This is judgment;
     draft conservatively and keep each fact traceable to its page.
   - Get the current vocabulary from `orlog schema` (JSON Schema of
     the mutation union; `templates/example-mutations.json` shows
     the shape) and draft the mutations file.
   - Run it: `eddic.py reconcile <mutations.json>` (story from
     config). The verb is fork-first, unconditionally: fork → apply
     → validate, all-or-nothing, and the story head is never
     touched. A refusal means nothing landed anywhere but an
     isolated fork.
   - Hand the owner the review: `orlog dump --branch <fork>` and
     targeted queries. **Merging — setting head — is the owner's
     act in Ørlǫg, never yours.**
   - Log a `reconcile` entry in the wiki's operation log: what
     moved, from which pages, onto which fork.

3. **Query cookbook** — when a time question arrives ("how old is
   the princess at the schism?", "what era is this scene in?"),
   answer from the timeline, not arithmetic in prose:
   `query age --character X --at <event|date>`, `era-at`,
   `time-between`, `anniversaries`, `alive`. `<when>` accepts an
   anchored event's label — prefer that over dates; it stays true
   when the timeline shifts.

## Decision points

- **When to reconcile.** Default: owner-directed only, typically
  after a session's recap lands. Never scheduled, never automatic:
  chronology mutations are canon surgery.
- **Fact direction.** Default: wiki → timeline (the wiki is where
  play lands first). Timeline → wiki flows through the same
  owner-directed gate, phrased in prose, never as machine dates.
- **Stale forks.** Default: leave refused or unmerged forks in
  place for the owner to inspect and delete in the app; the verb
  never deletes anything.

## Verify

- `uv run modules/orlog/verify/run.py` — drives the reconciler
  against a fake CLI and proves the discipline: fork before apply
  before validate, the fork id threading through, refusal aborting
  with no further calls and the head untouched, merging stated as
  the owner's act.
- Live, with Ørlǫg present: run the example mutations against a
  **copy** of the story (never the original) and confirm the fork
  appears, the head is unmoved, and a malformed mutation refuses
  loudly.
