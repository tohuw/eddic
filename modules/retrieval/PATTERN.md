# Pattern: agentic retrieval (the Worker MCP)

Gives the campaign a retrieval surface any MCP-capable agent can use
— including the DM's phone in the car: "what do I know about the
Reavers' patron?" becomes a tool call against the DM tier, no login
flow anywhere in the chain. One Worker, two tokens: TOKEN_DM serves
the master wiki, TOKEN_PLAYER serves the projection. Deterministic
auth in infrastructure; no agent ever decides what a tier may see.

## Preflight

- cli and wiki patterns applied; `eddic project` succeeds.
- A Cloudflare account with wrangler authenticated (`wrangler
  whoami`); node available. Account login is the user's interactive
  step — direct them, don't drive it.

## Procedure

1. Vendor the staging verb:

       cp scripts/stage.py <campaign>/.eddic/lib/stage.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module retrieval --version 0.1.0 --verbs stage

2. Create `<campaign>/worker/`: copy `templates/worker.js` and
   `templates/wrangler.toml` (fill `{{WORKER_NAME}}`; it becomes the
   `<name>.workers.dev` subdomain). Run `eddic.py stage` — it writes
   the two corpora beside worker.js, refusing if the projection is
   missing (the player tier only ever comes from `eddic project`).

3. Generate two tokens and set them as secrets (never in files, never
   in the repo):

       python3 -c "import secrets; print(secrets.token_urlsafe(24))"
       wrangler secret put TOKEN_DM      # paste one
       wrangler secret put TOKEN_PLAYER  # paste the other

4. Deploy: `wrangler deploy` from `worker/`. Re-publish cadence: any
   time the wiki changes, `eddic.py project && eddic.py stage &&
   wrangler deploy` — fold this into the publish/routine flow so the
   corpus tracks the wiki (freshness contract).

5. Connect an agent. Two auth styles, both live:
   - `Authorization: Bearer <token>` against `https://<worker>/mcp`
     — for clients that support headers.
   - Capability URL: `https://<worker>/<token>/mcp` — for connector
     UIs that only accept a URL (this is what the phone app's custom
     connector settings take). The DM configures the DM-token URL on
     their own devices only; the player URL can be shared with the
     table.

6. **Rotation is the panic procedure**: `wrangler secret put
   TOKEN_DM` with a fresh value, update the connector config, done —
   old token dead in seconds, no republish. If a DM-token leak is
   suspected, rotate first and investigate second.

## Decision points

- **Player tier.** Default: enabled — players asking their own agent
  questions is half the point. A table that only wants the DM tier
  just never sets TOKEN_PLAYER (unset token = tier off).
- **Auth style.** Default: capability URL for phone connectors,
  header auth for desktop agents. Same tokens either way.
- **Voice mode.** Default: spike before relying — configure the
  connector, then actually ask a question in voice mode before the
  DM depends on car-voice retrieval. Connector availability in voice
  contexts varies by app version; if it fails there, retrieval still
  works in normal app chat. Report what you find to the owner.

## Verify

- `uv run modules/retrieval/verify/run.py` — stages a planted
  campaign and drives the worker's fetch handler in node: 401s, both
  auth styles, initialize/tools-list shape, notification handling,
  and tier isolation (DM page and DM-only search terms invisible to
  the player token).
- After a real deploy: from an MCP client (or curl), initialize with
  each token; `search` for a DM-only term with the player token and
  confirm blindness; rotate a token and confirm the old one dies.
