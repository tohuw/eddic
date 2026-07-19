# Releases and versioning

Eddic has no single version number. It is a set of independently
shippable modules, and versioning is applied at three seams that move on
different clocks: each module carries its own semver, each campaign pins
the versions it has actually applied, and every claim about an outside
vendor carries a dated evidence state that decays. Nothing in the system
declares "Eddic 1.0"; the meaningful questions are always which module,
at what version, applied to which campaign, verified against which
vendor on what date.

## Modules version independently

Each module declares a `version` in its `module.yaml` and advances it on
its own semver track, decoupled from every other module. A tree at one
moment mixes maturities freely — a foundational module several minor
versions along while a newer one sits at its first release — because a
module's version answers only for that module's pattern, scripts, and
verify. Community contributions arrive as modules by pull request and
enter the same scheme; there is no global release train they must catch.
This independence is what lets the [module contract](the-module-contract.md)
treat each module as a self-contained shippable unit rather than a
component of a monolith.

## The manifest pins what was applied

A campaign is not a checkout of Eddic; it is a repository that has had
patterns stamped into it. What records that history is
`.eddic/manifest.json`, written and maintained by the
[cli](../modules/cli.md) module: for every module applied it holds the
version, the date applied, and the parameters used. The manifest is the
package-manager ledger for a distribution whose install step is an agent
following a runbook — it is what makes pattern application idempotent
(re-applying the same version is a no-op), auditable (every applied
version and date is on record), and upgradable (a newer pattern re-runs
against the recorded prior state and states its changes on
re-application). Vendoring is the distribution model behind this: a
campaign carries a pinned copy of the machinery it uses and works
offline with no Eddic checkout, and an upgrade re-stamps a newer version
against the manifest rather than tracking a live dependency.

## The CLI is a stable interface over changing implementation

`eddic` is the contractual locus for deterministic workflows — the
stable surface patterns are written against — precisely so its
implementation can be versioned underneath without breaking them. It is
uv-run Python today and may become per-OS binaries later; because
patterns invoke verbs and not an implementation, that change is a
release detail the patterns never see. Verbs themselves are versioned by
arrival: each lands with the module that needs it and none exists before
its module does, so the CLI's capability surface grows monotonically
with the modules that vendor into it. This is the [deterministic
core](deterministic-core.md) posture applied to releases — the
repeatable machinery has a versioned, testable interface, while the
agent shell above it reads [patterns](patterns-not-code.md) that stay
pinned to that interface.

## Vendor claims are dated and decay

Alongside module semver runs a second versioning discipline aimed at the
outside world. Any module whose pattern names a vendor must back the
claim with a `compatibility:` entry in `module.yaml` carrying the vendor
role, a status drawn from the evidence states in `docs/compatibility.md`,
and a date. These claims are treated as perishable: truth decays, so a
claim is re-dated when re-tested and demoted when the vendor moves, and
nothing below `verified` may be a decision point's default path.
Behavioral promises about how an answer client will conduct itself are
versioned the same way — verified adversarially, per client, before
being claimed. This keeps the compatibility ledger honest as an
independently moving version axis rather than a one-time assertion.

## Reference targets

Two named constructs act as versioned targets that releases aim at. The
baseline build is a named reference architecture — a complete campaign
running on nothing above a single low-tier subscription plus free
tiers — against which every module states its cost posture, so "does
this still fit the baseline" is a checkable release property. And the
deterministic floor enforced in CI is the mechanical gate a module
release must clear on macOS and Windows runners before it merges,
keeping every version increment behind a proven contract.

## See also

[The module contract](the-module-contract.md) governs what a shippable
module version must contain. [Deterministic core, agent
shell](deterministic-core.md) explains why the versioned interface sits
in scripts and the CLI. [Patterns, not code](patterns-not-code.md)
covers the instructional layer that pins itself to the CLI's stable
surface. The [cli module](../modules/cli.md) implements the manifest and
the vendoring model. The full [concepts index](index.md) and the
[modules index](../modules/index.md) list the rest.
