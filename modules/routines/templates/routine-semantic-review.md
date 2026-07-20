# Routine contract: semantic review

**Purpose.** Catch what the structural lint cannot — DM-adjacent
knowledge leaking through player-visible *prose*, encyclopedic/tonal
drift, cross-page factual contradictions, dangling narrative references,
naming inconsistency, and stubs that read finished below the word
threshold — and put the findings in front of the owner. This is the
model half of the lint module's reporter/model seam, packaged as a
recurring routine. It is advisory only: the agent proposes, the human
disposes; nothing it produces reaches canon or a player-visible surface
automatically.

**Composed verbs, in order, stop on first failure:**

1. `eddic lint --strict` — the deterministic floor must be green first;
   a semantic pass over a structurally broken wiki wastes tokens
   re-finding what regex already names.
2. `eddic project` — build the player projection, so the
   firewall-in-prose check reads exactly what players see.
3. `eddic semantic-review --projection <projection_dir> --out packet.json`
   — assemble the review packet (master pages, projection kept separate,
   checklist, findings schema). Deterministic; spends no tokens.
4. *Model pass* — the maintaining agent reads the packet, works the
   checklist, and emits findings as a JSON array matching the packet's
   schema. This is the one token-spending step, and the only place
   judgment enters; it is bounded by the checklist and kept away from
   every safety property (it reads the projection for firewall-in-prose,
   never decides visibility; it never edits a file).
5. `eddic semantic-review --validate findings.json` — gate: malformed
   findings stop here rather than reaching the inbox.
6. *File the findings* — as `suggest_edit` calls into the retrieval
   witness inbox when that path is enabled (the owner materializes them
   with `eddic suggestions`), else as a plain review report.

**Idempotency.** The packet (steps 1–3) is a pure function of the wiki
tree: same tree, same packet. The model pass is not bit-identical run to
run, but its *output class* is stable and, crucially, inert — findings
are suggestions, applied by no one but the owner, so a re-run cannot
change the campaign. Filing is keyed so a re-run updates the same
pending suggestions rather than forking canon.

**Safe to miss.** A missed run leaves the owner's advisory queue stale,
never the wiki wrong. Nothing this routine emits is load-bearing;
skipping it degrades only the freshness of advice.

**Safe to double-run.** Two overlapping runs can at worst file duplicate
suggestions into the inbox — noise the owner drops in triage — and can
corrupt nothing, because the routine has no write path to canon and the
projection it reads is itself rebuilt deterministically each run.

**Refusal behavior.** A nonzero deterministic step (1–3, 5) stops the
chain and surfaces that step's stderr through the runner's failure
channel; the model pass never "fixes" anything and never applies an
edit. Human-authored prose is never rewritten — mechanical,
owner-directed transforms only.

**Default cadence.** Between-sessions, not on every wiki push: the pass
is token-heavy and its findings are advisory, so it rides the rhythm of
play rather than the rhythm of edits. On-demand is the escape hatch.
Pre-compress the packet's page bodies (DESIGN: token economics) before
the model reads them on a large wiki.
