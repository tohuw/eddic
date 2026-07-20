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

## Runner: the Claude Code Routine (hosted agent rung)

This is the top rung of the routines module's preference chain — a
hosted agent routine — for the semantic pass. A Claude Code Routine runs
a scheduled Claude Code session on Anthropic's cloud, so the pass fires
between sessions with the owner's laptop off, on the agent subscription
already paid for (no new service). The config lives in the owner's cloud
account, not the repo; what the repo supplies is the recipe (the
campaign's vendored `/semantic-review` command and its `.mcp.json`
witness declaration), which the cloud loads automatically on checkout.

**Prerequisites in the campaign repo** (apply the lint and retrieval
patterns first): the `semantic-review` verb vendored in `.eddic/lib/`;
the retrieval **witness write path** enabled (an `INBOX` KV namespace) so
`suggest_edit` has somewhere to land; a root **`.mcp.json`** declaring
the witness server with its token pulled from an env var, never
hardcoded —

    {
      "mcpServers": {
        "witness": {
          "type": "http",
          "url": "https://<worker-host>/mcp",
          "headers": { "Authorization": "Bearer ${EDDIC_WITNESS_TOKEN}" }
        }
      }
    }

Use the **player-tier** token here: it is low-sensitivity (the same
content as the public wiki), safe to store as a cloud env var, and
`suggest_edit` accepts any tier, so findings still reach the DM's inbox
without exposing the DM secret to the cloud.

**Create it at claude.ai/code/routines** (or `/schedule` from the CLI, or
the desktop app). Fill the routine's fields:

- **Repository** — the campaign repo. The routine checks out its default
  branch; GitHub auth is automatic, so the PR fallback needs no extra
  token.
- **Environment variable** — `EDDIC_WITNESS_TOKEN` = the campaign's
  **player-tier** retrieval token. Stored plaintext in the routine
  environment; that is acceptable precisely because it is the
  player-tier, public-content token. Never paste the DM token here.
- **Schedule** — weekly is the recommended cadence (between-sessions, per
  the default-cadence clause above); the platform floor is a **1 hour**
  minimum interval, so weekly sits well inside it. Pin a specific day and
  time — the morning after game night is ideal — with `/schedule update`
  (cron).
- **Prompt** — paste the block below.

### Routine Prompt (paste-ready)

```
Run this campaign's semantic wiki lint and file the findings.

Execute the /semantic-review command. It runs the deterministic floor
(eddic lint --strict), builds the player projection (eddic project) and
the review packet (eddic semantic-review --out packet.json), then has you
work the six-category checklist over the packet, write findings.json,
validate it (eddic semantic-review --validate findings.json), and file
each finding as a suggest_edit into the DM's witness inbox via the
`witness` MCP server.

Every finding is advisory: never edit a wiki file, never rewrite
human-authored prose, never apply anything to canon. Stop and report if
any deterministic step (lint, project, packet build, validate) refuses.

If the `witness` MCP server is unreachable (its host is not in this
environment's Allowed domains, or EDDIC_WITNESS_TOKEN is unset), do not
drop the findings: write them under suggestions/ and open a PR, per the
command's fallback. Report the finding count and which path you took.
```

**Allowed-domains gotcha.** The default "Trusted" cloud environment
`403`s requests to arbitrary custom domains, so the witness MCP handshake
to a custom host (e.g. `<campaign>.eddic.quest`) fails silently and the
routine takes the PR fallback every run. Add the worker host to the
routine **environment's Allowed domains** so the `witness` server
connects and findings reach the inbox. A `*.workers.dev` host may already
be permitted; a custom domain almost never is.

**PR fallback.** When the witness path is off or its host stays blocked,
the `/semantic-review` command writes the findings under `suggestions/`
and opens a PR against the default branch instead — so the owner triages
the same advisory findings through review rather than the inbox. GitHub
auth is automatic in the routine, so no token is needed for this path.
Nothing about the fallback reaches canon automatically; it is a proposal
like every other finding.

**Interactive auth does not work in the cloud.** getpass, OAuth popups,
and browser device flows all fail in a headless routine — this is exactly
why the witness token is a static env var and GitHub auth is the
platform's, not an interactive login.
