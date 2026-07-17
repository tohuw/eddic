# ROADMAP.md — module queue and deferred decisions

Order chosen so each step exercises what the previous one built. The
first module proves the contract; the CLI grows verbs only as modules
need them.

**Status 2026-07-16:** items 1–8 shipped at 0.1.0 (see
`modules/README.md`), plus repo CI enforcing the contract floor and
running every module verify on ubuntu/macos/windows. Retrieval is
proven live end-to-end on a Land of Song test absorption: Worker
deployed, tier isolation wire-verified, and the voice spike passed —
push-to-talk dictation on the phone app reached connector tools and
answered from a cold context in ~10 s. The Pages live deploy awaits
the owner. Remaining: recorder (9, needs the owner's brief),
discord-setup (10), routines (11), orlog (12).

## Module queue

1. **lint** — the wiki health check, generalized from the DitD
   discipline: broken links and anchors, orphans, catalog drift, STUB
   mismatches, malformed log headers, and the new firewall check
   (no player-visible page links DM-only). Deterministic reporter +
   model-triage seam. First because it is self-contained, high-value,
   and exercises the whole module contract.
2. **cli** — the `eddic` skeleton (uv-run Python, PEP 723): `doctor`,
   `lint`, `manifest`. The contractual locus everything else hangs off.
3. **wiki** — the campaign knowledge schema, generalized from the Land
   of Song kb: taxonomy, encyclopedia tone, stub convention, typed log,
   authorship frontmatter, visibility frontmatter, and the `project`
   verb (deterministic player projection).
4. **render** — the purpose-built static renderer, patterned on
   bolverk's wiki stage but Eddic-owned: markdown tree in, HTML mirror
   out, `.md`→`.html` link rewriting, one template. Held at exactly that
   scope — the moment it grows an index generator, we have rebuilt Hugo
   badly.
5. **publish** — Cloudflare Pages deployment for the projected sites
   (unlisted, noindex; DM and player sites).
6. **retrieval** — the Cloudflare Worker MCP: bearer-token-gated,
   DM token sees the master, player token sees the projection; token
   rotation as the panic procedure. Includes the spike: verify connector
   availability in phone voice mode before this becomes load-bearing.
   Later: the `witness` write tool and inbox (bidirectionality).
7. **lore-bot** — snorri absorbed and parameterized: corpus-in-cached-
   prompt Discord Q&A over the player projection, forum CLI, session
   announce. Must satisfy DESIGN.md's freshness contract from day one:
   the bot self-refreshes by watching the projection's version (HEAD
   poll) rather than relying on deploy chaining, webhooks, or an
   owner-gated reload command — the source stack's bot went stale on
   every wiki publish for lack of exactly this.
8. **transcriber** — local session transcription (whisper.cpp) from
   recorded audio; the free path that replaces paid transcript services.
   Likely the first binary-bearing module.
9. **recorder** — the local Discord voice-recording bot (Craig
   replacement; receives audio over the Discord voice gateway — no OS
   mic permission involved). Spec brief pending from the owner.
10. **discord-setup** — server scaffolding: Discord template for
    structure, deterministic setup bot for what templates can't do
    (integrations, webhooks, permissions).
11. **routines** — the maintenance routine contract (idempotent, safe
    to miss, safe to double-run) with the preference chain: hosted
    agent routines → GitHub Actions → local cron-esque. Adapters stated
    as contracts, not how-tos (no egg-sucking).
12. **orlog** — guidance for driving Ørlǫg's headless CLI (M5, shipped
    2026-07-16: `orlog apply/dump/query/fork/validate/schema`,
    constraint-checked all-or-nothing writes, JSON Schema of the
    Mutation union, zero build step on Node ≥ 24): the reconciler
    skill (wiki facts → validated mutations on a fork), and `validate`
    as the story's test suite. Unblocked.

**Contributable thereafter:** VTT modules (Roll20, Foundry, …) by
community PR under the contract.

## Deferred decisions, with triggers

- **Signed binaries.** Now: CI builds unsigned per-OS binaries as
  release artifacts (prove the pipeline early; agent-driven installs
  mostly dodge Gatekeeper/SmartScreen, which key on browser-download
  provenance). Trigger to buy signing (Apple Developer ~$99/yr +
  notarization; Azure Trusted Signing ~$10/mo for Windows): a human
  browser-download path, or a module needing stable OS-permission
  identity.
- **License.** Must be chosen before the repo goes public / first
  external PR.
- **Compression accelerators.** headroom/thlibo guidance lands inside
  the routines and transcriber modules as decision points with
  heuristics, per DESIGN.md — never as dependencies.
