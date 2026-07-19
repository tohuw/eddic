# Roadmap

The roadmap records the order in which Eddic's modules were built and the
decisions deliberately held open. The ordering principle is that each step
exercises what the previous one built: the first module proves the
[module contract](concepts/the-module-contract.md), and the CLI grows verbs
only as later modules demand them. As of the overnight and transaction arcs
of mid-2026, all fifteen planned queue items are built, twelve modules stand
in the tree, and repository CI enforces the contract floor while running
every module's verify suite on Ubuntu, macOS, and Windows.

## Build sequence and rationale

The queue was sequenced deliberately rather than by feature priority. Lint
came first because it is self-contained, high-value, and exercises the entire
contract; the CLI skeleton followed as the locus everything else hangs off.
The wiki schema, the static renderer, and Cloudflare Pages publishing
established the authoring-to-published-site path. Retrieval — the
bearer-token-gated Worker that serves the master corpus to a DM token and the
projection to a player token — was proven live end-to-end, including a voice
spike in which push-to-talk phone dictation reached connector tools and
answered from a cold context in about ten seconds. The lore bot, transcriber,
and capture modules closed the session-knowledge loop, and orlog and routines
completed the twelve-module tree. The transaction arc landed last, extending
wiki, lint, and publish with contributor overlays and the sale-build fence.

Windows CI repeatedly earned its place: it caught two real portability bugs
in orlog — path mangling under shell splitting and a codepage unable to print
the module's own name — before any user could hit them.

## Modules that shipped

Lint, the CLI, the wiki schema, the renderer, publish, retrieval, the lore
bot, and the transcriber form the first eight, shipped together and CI-gated.
Provider parity work added a compatibility ledger of evidence-backed vendor
claims, cross-client MCP hardening with a REST facade, and a provider seam in
the lore bot that admits a second vendor while leaving the default unchanged.

Capture and the [recorder](modules/recorder.md) address session audio by two
routes. Capture defaults to a free third-party recording path with
deterministic staging, because all Eddic truly needs is the audio and
transcription runs locally. The recorder is the consent-gated
no-third-party option: it receives audio over the Discord voice gateway
without an operating-system microphone permission, writes per-speaker FLAC
straight to disk on its own thread so answer latency can never drop frames,
and stages files with a log entry on stop. End-to-end voice receive was
solved against a broadly-broken ecosystem baseline by a patch set shared with
the upstream project; the patch module retires when that upstream change
lands. The recorder is its own bot rather than a mode of the always-on lore
bot: the two have different lifecycles and hosts — one always-on and
cloud-cheap, the other session-time-only, voice-heavy, and wanting to run
beside the disk the transcriber reads.

Discord-setup reconciles a live server to a standing spec versioned in the
campaign repository, reporting drift in the manner of a linter and ships a
curated third-party bot set with agent-driven invite flows. Routines defines
the maintenance-routine contract — idempotent, safe to miss, safe to
double-run — with a preference chain from hosted agent routines through
GitHub Actions to local scheduling. Orlog documents driving a headless
timeline CLI as a reconciler that turns wiki facts into validated,
all-or-nothing mutations on a fork.

The transaction arc shipped [contribs](modules/contribs.md) and the companion
family together. Contribs carries contributor overlays with shadowing and a
derivation graph, the pure-corpus projection with its full-equals-pure-plus-
attribution-log invariant, and consent receipts; attribution capture ships
earlier, in the wiki schema, because attribution is unrecoverable after the
fact. Companions run on their respective retrieval tiers under a
knowledge-parity conduct doctrine, with conduct claims verified adversarially
per answering client before any default is set.

## Items awaiting a live or human gate

Some work is designed and deferred to a session that supplies what only a
person can. The recorder brief was refined with the owner awake because voice
capture wants live testing. The marketplace module — transactable campaigns
as products, with an author role that is declared configuration and may
differ from the DM — is built as rights machinery but waits on the payment
gateway decision before it becomes commerce. Companion conduct claims remain
unverified until live adversarial passes. Beyond the planned queue, virtual
tabletop integrations are left to community contribution under the contract.

## Deferred decisions

Each deferred decision names a trigger that converts it from open to settled.

Signed binaries: CI already builds unsigned per-OS binaries as release
artifacts to prove the pipeline early, since agent-driven installs mostly
dodge the operating-system reputation gates that key on browser-download
provenance. The trigger to buy code signing is a human browser-download path
or a module needing a stable operating-system permission identity.

Licensing was resolved to a permissive license with a patent grant, chosen so
that vendored and stamped copies inside campaign repositories stay clean and
inbound contributions are self-licensing without a separate agreement.

Compression accelerators are handled as decision points with heuristics
inside the routines and transcriber modules, never as hard dependencies. The
Eddic website's first trigger has fired — it is live, rendered by the render
module, and carries the privacy posture the recorder's consent post links;
the remaining owner calls are a real domain and whether the site grows a
docs or marketplace face.

The payment gateway is chosen when the marketplace module starts: a gateway
offering checkout-and-download with no inventory overhead, under the project's
cost posture. Until then the transaction arc is rights machinery, not sales.

Multi-tenant operation of the scheduling bot is the newest open decision.
Today one bot serves one campaign, and [convene](modules/convene.md) counts
every scheduled event on the guild toward that campaign's quorum, so two
campaigns sharing a server would cross-contaminate events, reminders, and
quorum counts. The seam is already cut correctly — players are scoped by a
per-campaign role — so the missing piece is scoping events the same way, by
tagging each event to a campaign and filtering the event fetch by it. The
trigger is a real second tenant; the module deliberately stays unbuilt until
then so the single-tenant path remains zero-configuration.

## Related pages

The roadmap sits alongside the full [module index](modules/index.md) and the
[concepts index](concepts/index.md). Its versioning discipline is described
under [releases and versioning](concepts/releases-and-versioning.md), and the
floor every queued item had to clear is the
[module contract](concepts/the-module-contract.md). Return to the
[Eddic overview](index.md) for the project as a whole.
