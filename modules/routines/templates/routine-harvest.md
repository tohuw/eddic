# Routine contract: harvest

**Purpose.** Turn what the table said in Discord since the last run into
wiki work — rulings the DM dropped between sessions, questions the wiki
could not answer, and names the table spells correctly that the
transcripts mangle. It is the [harvest](../../harvest/PATTERN.md)
module's model half packaged as recurring maintenance, and it is
advisory only: every finding lands in the suggestion queue, and nothing
it produces reaches canon or a player surface on its own.

**Composed verbs, in order, stop on first failure:**

1. `eddic project` — the naming pass compares chat against the player
   projection, so a stale projection reports names the wiki already has.
   Deterministic; spends no tokens.
2. `eddic harvest --pull --out packet.json` — fetch everything after the
   watermark from the allow-listed channels, advance the watermarks, and
   write a pre-compressed packet. Deterministic; spends no tokens. A
   channel that fails is reported and keeps its place; a channel that
   hits the page cap says so.
3. *Model pass* — the maintaining agent reads the packet against its
   `checklist` and `not_in_scope` and emits findings matching the
   packet's schema. The one token-spending step and the only place
   judgment enters. It reports contradictions; it never adjudicates
   them, and it never treats a player's assertion as canon.
4. `eddic harvest --validate findings.json` — gate: malformed findings
   stop here rather than reaching the owner.
5. *File the findings* — as `suggest_edit` calls into the retrieval
   witness inbox where that path is enabled (the owner materializes them
   with `eddic suggestions`), else under `suggestions/` behind a PR.
   `naming` findings additionally belong in the transcript's mishearings
   table, where they stop the same mistake recurring.

**Idempotency.** Steps 1–2 are a pure function of the watermark and what
Discord holds: re-running immediately returns an empty packet, because
the watermarks moved. The model pass is not bit-identical, but its
output class is inert — suggestions, applied by nobody but the owner.

**Safe to miss.** A skipped night widens the next window; nothing is
lost, because Discord kept the messages, not this routine. The only
thing a long gap costs is the page cap, which truncates loudly and
resumes on the following run.

**Safe to double-run.** Two overlapping runs cannot double-file: the
first advances the watermarks, so the second finds nothing to report. If
they truly race, the worst case is duplicate suggestions the owner drops
in triage — there is no write path to canon to corrupt.

**Refusals.** A channel the bot cannot read, a missing token, or an
empty allow-list stops the chain and surfaces through the runner's
notification channel. The routine fixes nothing on its own.

**Cadence.** Nightly, off-session, so a night's play is harvested with
the following day's chatter. A quiet table can run weekly.

**Cost posture.** Steps 1, 2, 4 and 5 are free. Only the model pass
spends, and it reads a compressed packet — the table's questions and the
DM's substantive lines — rather than a day of raw chat. Its natural
runner is the top rung of the preference chain, a hosted agent routine,
for the same reason semantic review is: it wants to fire between
sessions with the owner's laptop shut.

**Privacy posture.** The routine reads an allow-list of channels, never
direct messages, and honors `optout_ids` before anything reaches the
packet. It persists no message text anywhere — the state file is
watermarks — so what it retains between runs is a set of ids. That claim
is enforced in code, and it is what the table should be told.
