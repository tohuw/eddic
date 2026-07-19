# Deterministic core, agent shell

Deterministic core, agent shell is the first and most frequently invoked
of Eddic's [design principles](../design/principles.md): the division of
labor between machinery and judgment that decides where every module puts
its weight. Scripts do everything repeatable. Agents read patterns, make
judgment calls at marked decision points, and run maintenance. The rule
that keeps the seam honest runs both ways: an agent never does
infrastructure's job — authentication, projection, cryptography,
firewalls — and infrastructure never does judgment's job. The intent is
to spend agentic capability where it is genuinely good and to stop
burning tokens and gambling on outcomes where a script would be exact,
cheap, and identical on every run.

## Why the split exists

An agent is a probabilistic reader whose strength is adapting a written
procedure to a messy environment and choosing well among options a human
would care about. Those strengths are wasted, and actively dangerous, on
work whose whole value is that it produces the same result every time.
Safety properties — that no hidden page reaches a player surface, that a
secret is never echoed, that a sale build refuses without a declared
author — must hold by construction, not by an agent remembering to make
them hold. So the properties that must never vary are pushed into
deterministic scripts and a lint that audits them, and the decisions that
genuinely need taste are surfaced explicitly, each with a default so that
an owner who wants none of them can have the agent take every default and
ask nothing.

## How a pattern encodes it

Every module's pattern is built on this division. Its four parts —
preflight, procedure, decision points, verify — put the agent's judgment
exactly where it belongs and nowhere else. Preflight and verify are
deterministic checks: can the environment accept the pattern, and did the
application observably succeed. The procedure is prose that invokes
scripts for everything repeatable; the agent adapts the procedure to the
environment but does not replace the scripts, and improvising a
substitute for a deterministic step is a contract violation. Decision
points are the only places the pattern consults the owner, and each one
ships a recommended default. The [module contract](the-module-contract.md)
enforces this mechanically: a decision point without a default fails CI,
and the semantic rubric's first line is "deterministic where possible."

## The seam in the modules

The core surfaces as concrete reporter/machine halves throughout Eddic.
The [cli](../modules/cli.md) module stamps a campaign's deterministic
core — a vendored dispatcher over swappable verbs — and holds the owner's
secrets locally rather than through conversation, because credential
handling is infrastructure's job. The [lint](../modules/lint.md) module
is the clearest expression: a reporter that only names structural rot and
never edits, leaving which findings to fix and which to escalate to the
agent and owner. Maintenance in the [routines](../modules/routines.md)
module runs the deterministic passes on a schedule so nothing that must
be exact depends on an agent choosing to run it. The same shape underlies
the [capability seam](the-capability-seam.md), which stabilizes the
interface an agent shells out to, and [patterns, not code](patterns-not-code.md),
which explains why the shell is written as instructions rather than
compiled in.

## Related

[Concepts index](index.md) · [Modules index](../modules/index.md) ·
[Design principles](../design/principles.md) · [The module contract](the-module-contract.md) ·
[The capability seam](the-capability-seam.md) · [Patterns, not code](patterns-not-code.md) ·
[The firewall](the-firewall.md) · [cli](../modules/cli.md) · [lint](../modules/lint.md)
