# cli

The cli module stamps a campaign's deterministic core: a self-contained
`.eddic/` directory holding the dispatcher (`eddic.py`), the campaign
`config.json`, the applied-patterns `manifest.json`, and an empty `lib/`
directory into which every other module vendors its verbs. It is the
first pattern applied to any campaign, because every subsequent Eddic
pattern places its machinery there and records itself in the manifest.
As the contractual locus for all deterministic campaign workflows, the
dispatcher is the surface patterns are written against — patterns invoke
verbs, never internals. See [Deterministic core, agent shell](../concepts/deterministic-core.md)
and [The module contract](../concepts/the-module-contract.md).

## Vendoring distribution model

A campaign carries a pinned copy of the tooling and runs offline with no
Eddic checkout on the machine. The `.eddic/` directory is committed with
the campaign — the campaign owns its tooling — while derived output such
as `dist/` is gitignored. Upgrades are re-stamps: running the stamp
script again at a newer version refreshes the dispatcher and re-records
the cli module in the manifest, but never overwrites an existing
`config.json` and never touches another module's manifest entry. The
runtime is uv-run Python with PEP 723 inline script headers; uv
bootstraps Python itself as a single-binary install, so the only
preflight requirement is uv or any Python 3.9 or newer on PATH, plus a
git repository, since provenance discipline assumes version control.

## Stamping a campaign

The stamp script writes `.eddic/` into a campaign directory, which may
be empty, new, or an existing wiki being adopted. It takes the campaign
path and `--site-name`, with optional overrides for the directory layout:
`--wiki-dir`, `--projection-dir`, `--site-dir`, `--log`, and
`--contribs-dir`. The defaults are `wiki` for the DM master, `dist/player`
for the projection, `dist/site` for rendered HTML, `log.md`, and
`contribs`. An `--author` option declares the contributor who holds
transaction rights; a campaign runs without it, but a sale build refuses
until an author is declared, failing closed. After stamping, `doctor`
resolves anything it flags. The recommended defaults are the campaign
directory's titleized name for the site name and the standard layout
above; deviation is warranted only when an existing campaign already has
a loved layout.

## Built-in verbs

Three verbs ship in the dispatcher itself. `doctor` runs preflight
checks — Python at least 3.9, `config.json` and `manifest.json` present,
the configured wiki directory existing, every verb a manifest entry
records actually vendored in `lib/`, and git available (non-fatal, since
only versioning and provenance features degrade without it) — then lists
the vendored lib verbs and exits 0 when clean or 1 on failure. `manifest`
with no argument or `show` prints the manifest as JSON; `manifest check`
validates that each module records a version and applied date and that
every recorded verb is vendored; `manifest record --module M --version V`
writes or updates an entry, accepting `--params JSON` and a comma-joined
`--verbs` list. `run` launches a local session-time service, such as a
recorder bot, under a pinned runtime; bare `run` lists configured
services. A service runs in the foreground and is stopped with Ctrl-C,
and its launch command is built purely from the config entry —
`uv run` with `--python` and each `--with` dependency pin — so exactly
one copy runs during a session. See [recorder](recorder.md) for a
service that this verb launches.

## Dispatch and vendored verbs

Any verb that is not built in dispatches to `.eddic/lib/<verb>.py`. The
vendored script runs under the same interpreter with the remaining argv
passed through and `EDDIC_CONFIG` and `EDDIC_ROOT` set in the
environment, so a verb locates the campaign without argument plumbing;
the dispatcher prefers uv when available and otherwise falls back to the
current interpreter. A module contributes a verb by copying its script
to `lib/<verb>.py` and recording it with `manifest record`. The [lint](lint.md)
module's reporter is already lib-compatible: vendored as `lib/lint.py`,
a bare `eddic.py lint` lints the configured wiki. This seam — a stable
dispatcher over swappable vendored verbs — is what lets modules extend a
campaign without forking the core. See [The capability seam](../concepts/the-capability-seam.md).

## Secrets, held locally

When a campaign needs a secret only the owner holds — a bot token, an
API key — the cli module never takes it through conversation. Its
`secrets` verb, vendored from the secrets-fill script, scans the
campaign's gitignored `variables.txt` files (any such file up to two
directories deep, plus an explicit `--file`) for empty slots: lines like
`DISCORD_TOKEN=` with no value. It prompts for each with no-echo input,
writes the value straight into the file, and reports only a fingerprint —
the first eight characters and the length. Nothing typed is echoed,
printed, or logged. An interactive terminal uses hidden entry; piped
input is read line by line, which keeps fills scriptable and
cross-platform. Advisory shape checks warn when a value does not look
like a well-known token kind, but never refuse, since vendors change
formats.

## Related

[Modules index](index.md) · [lint](lint.md) · [recorder](recorder.md) ·
[Deterministic core, agent shell](../concepts/deterministic-core.md) ·
[The module contract](../concepts/the-module-contract.md) ·
[The capability seam](../concepts/the-capability-seam.md)
