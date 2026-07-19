# The capability seam

The capability seam is the fail-safe attachment surface a long-lived
Eddic service exposes so that optional capability modules ride the same
process rather than standing up their own. Its worked instance is the
always-on [lore bot](../modules/lore-bot.md): a resident Q&A service that
already holds a Discord connection, a corpus built from the player
projection, and a freshness poll. A capability such as
[convene](../modules/convene.md) — session lifecycle: scheduled events,
quorum, recap announcements — is not a second bot but a rider on that one
process, gaining the client, the credentials, the corpus, and the refresh
cycle for nothing new. The seam is what makes the difference between an
extension and another host a matter of a file copied beside `bot.py`.

## The contract

The host carries the seam whether or not anything rides it. At import it
attempts `import convene` and calls `setup(client)`; an `ImportError`
means no capability is present and the host runs unchanged, while any
other exception during setup is logged and the host continues without it.
Two further touchpoints hand the capability the host's live state: after
the Discord connection is ready the host calls `capability.ready(corpus)`,
and after every freshness reload it calls
`capability.on_corpus_refresh(corpus)`, so a rider observes exactly what
the host observes without re-reading disk — the pure corpus helpers the
host exposes let a capability notice which pages exist from the passed-in
corpus alone. Each call is individually guarded: a capability that fails
to load, or throws in any touchpoint, is logged and skipped, and can
never break the host's core answering or wedge its poll loop. That guard
is the seam's safety property, and it is structural, an instance of
[deterministic core, agent shell](deterministic-core.md) — the host's
obligation to survive its riders is fixed infrastructure, not a rider's
good behavior.

## Why it earns its place

A capability that rides the seam declares it in the ordinary
[module contract](the-module-contract.md) terms: convene lists
`depends: lore-bot` and `touches: lore-bot`, and its cost posture names no
paid path at all, because it adds no host and no spend to the process it
extends. This is the installation-friction principle working through
composition: the table that already pays to keep one archivist awake gets
session orchestration in its rightful always-on home instead of a second
service to deploy, credential, and remember. The seam generalizes: any
resident Eddic surface can expose the same shape — a guarded optional
import and a handful of state-handoff touchpoints — and let dependent
modules extend it without new infrastructure.

See the [concepts index](index.md), the [lore bot](../modules/lore-bot.md)
that hosts the seam, and [convene](../modules/convene.md) that rides it.
