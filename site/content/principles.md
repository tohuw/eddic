# Principles

The short version of the doctrine that decides Eddic's close calls.
The full text lives in
[the design principles](https://github.com/tohuw/eddic/blob/master/wiki/design/principles.md).

**Deterministic core, agent shell.** Scripts do everything
repeatable; agents make judgment calls at marked decision points.
An agent never does infrastructure's job (auth, projection,
firewalls), and infrastructure never does judgment's.

**No egg-sucking.** Eddic never teaches an agent what it already
knows. Only proven procedures, hard-won heuristics, and contracts an
agent couldn't guess.

**Installation friction kills.** Players install nothing. The DM's
machine needs one bootstrap that works on Windows the same as
anywhere. No exceptions, because the average DM uses Windows and the
average table has zero patience for setup.

**Cost pragmatism.** The baseline build runs on a $20/month AI
subscription and free tiers. Paid anything must name its free
fallback and the reason it's worth it.

**Defaults everywhere.** Every decision ships a recommendation, so
"just do what you think is best" works mechanically.

**Authorship preservation.** No agent strips the human art out of
human prose. Mechanical, owner-directed transforms only, always
logged.

**The agent-answer surface is the product.** Players ask; agents
answer; the wiki exists to make the answers good. The hour-long
rabbithole is the delightful side effect.

**Two wikis, one truth.** One master, secrets included; the player
wiki is a build-time projection; a firewall proves nothing leaks.
Revealing is one marker — lifting the veil.

**Agent-agnostic.** Standard instruction forms, cross-vendor
protocols, and a dated compatibility ledger instead of promises.

**Provenance discipline.** A typed, append-only log records every
ingest, reveal, contribution, and consent. Attribution is captured
when words land, because it can't be reconstructed later.

**Personality lives at owned surfaces, never in the data layer.**
The table's bot may be a character; the data your own agent consumes
is plain content — because you tune your agent to respond the way
*you* need, and nothing Eddic serves should override that.
