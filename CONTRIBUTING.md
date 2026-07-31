# Contributing to Eddic

## First, once

    uv run tools/dev_setup.py

That activates this clone's git hooks, so your pushes run the gate. Git
will not let a repository do this to itself — a clone that configured
its own hooks could run code on checkout — so it is one command somebody
has to type, and it is the only setup step there is.

## The gate

    uv run tools/gate.py

The contract floor, every module's verifier, and the end-to-end
composition check. Your pre-push hook runs it, a maintainer runs it on
your branch before merging, and a manual workflow runs it on Linux,
macOS, and Windows when portability is in question. Same command every
time, which is the point — the gate cannot mean one thing for you and
another at merge.

There is no automatic CI, deliberately. The floor is cheap, local, and
cross-platform by construction; metered minutes on every push buy
nothing the hook does not already give.

`--quick` runs the floor alone, without uv, when you only touched docs.

## What to read before writing a module

`AGENTS.md` routes you. `modules/CONTRACT.md` is what a module must be —
the anatomy, the four-part pattern shape, the floor, and the rubric a
maintainer reads for. `wiki/design/principles.md` holds the tiebreakers,
and they decide close calls, so skimming them saves a rewrite.

The bar that catches most submissions: a pattern must contain nothing a
competent agent would produce unaided. Contracts, invariants, proven
procedure, and hard-won heuristics belong; vendor how-tos do not.

## What a maintainer will do with your PR

Run the gate on your branch, then read the pattern with a critical eye
for the things no command can check — whether the prose earns its place,
whether the defaults are right, whether the firewall and authorship
invariants are respected. The gate is what makes that reading short.
