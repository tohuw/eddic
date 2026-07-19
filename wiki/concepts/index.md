# Concepts

The load-bearing ideas behind Eddic: the principles and invariants that its [modules](../modules/index.md) manifest and that every pattern assumes. They restate, in encyclopedia form, the tiebreakers set out in the [design principles](../design/principles.md); each page settles one idea. Return to the [wiki index](../index.md).

- [Patterns, not code](patterns-not-code.md) — why Eddic ships facilities as agent-applied patterns rather than installable applications.
- [Deterministic core, agent shell](deterministic-core.md) — the division of labor between machinery and judgment: scripts do the repeatable, agents decide only at marked points.
- [The module contract](the-module-contract.md) — the agreement every module keeps so strangers' contributions merge on a small deterministic floor plus good-faith semantics.
- [The capability seam](the-capability-seam.md) — the fail-safe attachment surface that lets optional capability modules ride an existing long-lived service instead of standing up their own.
- [Projection and visibility](projection-and-visibility.md) — how one maintained body of campaign knowledge yields a narrower, player-safe copy computed by deterministic script rather than curated by hand.
- [The firewall](the-firewall.md) — Eddic's guarantee that material a game master keeps secret never reaches people it would spoil, asserted at build time and audited mechanically.
- [Releases and versioning](releases-and-versioning.md) — why Eddic has no single version number: each module carries its own semver, campaigns pin what they applied, and vendor claims carry dated evidence.
