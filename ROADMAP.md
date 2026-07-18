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

**Provider parity 2026-07-17** (issue #1, PRs #2–#9 merged): the
compatibility ledger (`docs/compatibility.md`) with floor-enforced
evidence-backed vendor claims; worker 0.3.0 (cross-client MCP
hardening + Custom GPT Actions REST facade); lore-bot 0.2.0 (OpenAI
Responses adapter behind a provider seam, Anthropic default
unchanged); data-control profiles; Codex plugin routing to AGENTS.md.
Awaiting live vendor sessions: the ChatGPT acceptance rig
(`modules/retrieval/verify/chatgpt-acceptance.md`), a Codex
plugin-install test, an OpenAI-provider bot deployment.

**Lore bot live 2026-07-18:** full end-to-end on the test campaign —
Discord app created via driven browser (human: one captcha, one MFA,
one ToS, one Authorize), corpus answers with linked citations into the
live Pages site, projection blindness holding conversationally, and
the freshness poll observed reloading unprompted after a wiki edit.
Four live finds shipped back into the module during the test.

**Overnight 2026-07-18:** orlog (12) and routines (11) shipped at
0.1.0 — twelve modules in the tree, queue items 1–12 all built. The
Eddic site is live at eddic-site.pages.dev (pitch, how-it-works,
modules, principles, and the privacy posture the recorder's consent
post links — its trigger, fired), dogfooded through the render
module. Windows CI caught two real portability bugs in orlog before
any user could (shlex path mangling; cp1252 unable to print "Ørlǫg").
Recorder build deliberately deferred to a session with the owner
awake: voice capture needs live testing, lore-bot-style.

**Transaction arc 2026-07-18:** contribs (14) and companion (13)
shipped at 0.1.0; the author role is declared config (may differ from
the DM — DESIGN records the consequences); wiki 0.3.0 applies
contributor overlays across every surface, lint 0.3.0 checks them,
retrieval 0.4.0 stages the effective corpus; `eddic bundle` is the
sale-build fence (hash-pinned consent, derivation-graph rights,
stale-clearance refusal). `tools/verify_e2e.py` proves the full
composition in CI on all three OSes. Companion conduct claims are
unverified until live adversarial passes; marketplace (15) waits on
the payment-gateway decision.

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
9. **recorder** — **BLOCKED UPSTREAM (2026-07-18)**: Discord voice
   receive is broken Python-ecosystem-wide by DAVE E2EE enforcement;
   the module ships when Pycord-Development/pycord#3139 lands and a
   live capture passes. Everything human-facing was proven live
   (consent flow, commands, staging — see
   `notes/recorder-learnings.md`; cloud/R2 design in
   `notes/cloud-recorder-plan.md`); no module ships non-working
   capture, because modules hold only what is proven to work.
   The brief (owner, 2026-07-18; **revised same day: the recorder is
   its own bot**, reversing the earlier one-bot call): the lore bot
   is always-on and cloud-cheap; the recorder is session-time-only
   and voice-heavy, wants to run beside the disk the transcriber
   reads, and cloud voice-UDP is unverified — different lifecycles,
   different hosts, so separate applications and tokens. The
   capability code shape, consent machinery, and staging layout are
   unchanged; the driven portal flow makes the second app cheap.
   Local, session-time execution is the default; the R2/cloud design
   (notes/cloud-recorder-plan.md) becomes this bot's optional cloud
   mode. Audio arrives over the
   Discord voice gateway (no OS mic permission); the voice sink runs
   on its own thread writing straight to disk so answer latency can
   never drop frames. Summon/dismiss via slash commands
   (`/record start|stop|help`; invites need the
   `applications.commands` scope alongside `bot`). Output:
   per-speaker FLAC to the campaign's local disk in the transcriber's
   expected layout; on stop, files are staged and a log entry
   written — transcription stays a deliberate maintenance step.
   Consent: on start, the bot posts in the voice channel's text chat —
   announcement, privacy-posture link (hosted on the Eddic site), and
   per-member opt-in reacts; a member's audio is captured only after
   their react, nobody is gated on anyone else, and fail-closed means
   un-reacted members are simply never in the recording. Decision
   point: strict per-session reacts (default) vs standing acks
   remembered across sessions with visible opt-out. Doctrine:
   consent-to-record is not consent-to-sell — the transaction arc's
   full-table sign-off remains its own later act.
10. **discord-setup** — server scaffolding (owner's spec, 2026-07-18):
    a deterministic REST script as an eddic verb, using the campaign
    bot's existing token (no gateway, no second bot) against a
    **standing server spec** versioned in the campaign repo —
    re-running reconciles the live server to spec and reports drift,
    lint-style. Default scaffold generalizes the reference table's
    server: an ask-the-archivist channel, threaded session-recaps, a
    botspam sandbox, a session voice channel with its text chat, a
    DM-private channel, DM/player roles with sane overwrites. Ships a
    **curated third-party set** (drafted from the reference server,
    owner to confirm: dice = Avrae, scheduling = Apollo, music =
    Jockie; recording deliberately absent — the recorder capability
    replaces it) with the agent-driven invite-URL flow for each and
    per-bot config notes. Decision points: adopt-vs-scaffold on an
    existing server; which curated bots to take; spec-drift policy
    (report-only vs repair).
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

13. **companion** — the at-the-table module family under the
    knowledge-parity conduct doctrine (DESIGN: "Companions at the
    table"): player and DM companions on their respective retrieval
    tiers, and the backstory interviewer with its scribe/drafter
    authorship dial. Conduct claims verified adversarially per
    answer client before any default.
14. **contribs** — the transaction arc's machinery (DESIGN: "The
    transaction arc"), landing as wiki/lint/publish extensions:
    contributor overlays with `replaces:` shadowing, `derived-from:`
    derivation graph, the pure-corpus projection with its
    full = pure + attribution-log invariant, the transactability
    frontmatter axis and sale-build fence, consent receipts.
    Attribution *capture* ships earlier in the wiki schema — it
    cannot wait, because attribution is unrecoverable after the fact.
15. **marketplace** — transactable campaigns as products: the author
    role, base and deluxe (session-log) offerings, packaging and
    refusal machinery. Payment gateway is a deferred decision below.

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
- **License.** Resolved 2026-07-17: Apache-2.0 (see `LICENSE` and the
  "License and authorship" section of `README.md`). Permissive, so
  vendored and stamped copies inside campaign repos stay clean; carries
  a patent grant; §5 makes inbound contributions self-licensing with no
  CLA needed.
- **Compression accelerators.** headroom/thlibo guidance lands inside
  the routines and transcriber modules as decision points with
  heuristics, per DESIGN.md — never as dependencies.
- **Eddic website.** First trigger fired 2026-07-18: live at
  eddic-site.pages.dev (source in `site/`, rendered by the render
  module), carrying the privacy posture the recorder's consent post
  links. Remaining owner calls: a real domain, and whether the site
  grows a docs/marketplace face beyond the current five pages.
- **Payment gateway.** Choose when the marketplace module (15) starts:
  a gateway with checkout-and-download and no inventory overhead;
  cost posture per principle 4. Until then the transaction arc is
  rights machinery, not commerce.
