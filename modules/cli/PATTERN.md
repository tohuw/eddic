# Pattern: the vendored eddic CLI

Gives a campaign its deterministic core: a self-contained `.eddic/`
directory holding the dispatcher, the campaign config, the
applied-patterns manifest, and the `lib/` directory that other modules
vendor verbs into. After this pattern, every other Eddic pattern has a
place to put its machinery and a manifest to record itself in — apply
this one first.

Vendoring is the distribution model: the campaign carries a pinned
copy and works offline with no Eddic checkout; upgrades re-stamp at a
newer version against the manifest.

## Preflight

- uv is installed, or any Python ≥ 3.9 is on PATH. If neither: install
  uv (single binary; one-line official installer on Windows PowerShell
  and macOS/Linux — you know how).
- You know the campaign directory. It may be empty, new, or an
  existing wiki being adopted.
- If the campaign is not yet a git repository, initialize one; the
  provenance discipline assumes version control.

## Procedure

1. Stamp:

       uv run modules/cli/scripts/stamp.py <campaign_dir> --site-name "NAME" \
           [--wiki-dir wiki] [--projection-dir dist/player] \
           [--site-dir dist/site] [--log log.md]

   Idempotent: re-running refreshes the dispatcher, never overwrites
   an existing config.json, never touches other modules' manifest
   entries.

2. Run `uv run <campaign>/.eddic/eddic.py doctor` and resolve anything
   it flags.

   When the campaign needs a secret only the owner holds (a bot
   token, an API key), never take it through the conversation: vendor
   `scripts/secrets_fill.py` as `lib/secrets.py`, prepare the target
   variables file with an empty `KEY=` slot, and have the owner run
   `eddic secrets` in their own terminal — it prompts locally with
   no-echo input, writes the value into place, and reports only a
   fingerprint. That is intake route 3 with the folder navigation
   and the editor removed (`wiki/reference/data-controls.md`).

3. Vendoring a verb (done by *other* modules' patterns, recorded here
   for reference): copy the module's lib script into `.eddic/lib/`,
   then record it —

       cp modules/<m>/scripts/<verb>.py <campaign>/.eddic/lib/<verb>.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module <m> --version <V> --verbs <verb>

   Lib verbs receive `EDDIC_CONFIG` and `EDDIC_ROOT` in the
   environment and the remaining argv. The lint module's reporter is
   already lib-compatible: vendored as `lib/lint.py`, bare
   `eddic.py lint` lints the configured wiki.

4. Ensure the campaign ignores derived output: add the configured
   `dist/` (or equivalent) to `.gitignore`. `.eddic/` itself is
   committed — the campaign carries its tooling.

5. Whenever you return to a campaign with an Eddic checkout to hand,
   start by diffing the manifest against it —

       uv run <campaign>/.eddic/eddic.py upgrade <eddic_checkout>

   It reports each recorded module as up to date, upgradable (with the
   version delta), renamed (resolved through the checkout module's
   `renamed_from:`), or recorded-but-gone, and flags vendored
   `lib/<verb>.py` files no manifest entry claims. It never touches the
   campaign: it prints the `PATTERN.md` files to re-apply and the
   `manifest record` line to run afterwards, because applying a pattern
   is your job — you read the campaign, ask at its decision points, and
   write files a script cannot reason about. Exit 1 means something
   needs attention, so a routine can run it unattended. Work the list,
   then re-run until it exits 0; delete a stale entry (the renamed
   case) from `manifest.json` by hand once its successor is recorded.

### The roster

`scripts/roster.py` is stamped in beside the CLI as the `roster` verb.
It answers one question the whole campaign keeps re-deriving and never
keeping: who a Discord user is.

    uv run .eddic/eddic.py roster                       list
    uv run .eddic/eddic.py roster --seed-craig info.txt  seed ids+handles
    uv run .eddic/eddic.py roster --set <id> --character "Niðrerir"
    uv run .eddic/eddic.py roster --resolve 5-theseous   map any label
    uv run .eddic/eddic.py roster --check                validate

It is keyed by the numeric Discord user id, the one identifier that does
not change: usernames change, display names change, a player retires a
character. Every consumer maps whatever identifier it happens to hold —
a Craig track stem, a display name, a raw id — through `resolve()` to
one canonical `label`.

**It is DM-tier and it stays there.** It holds real first names and
Discord handles; it lives in `.eddic/`, which the projection never
reads, and consumers resolve *through* it rather than copying it
forward. That is the point of the `label` field: a transcript says
"Niðrerir", not "Niðrerir_Ron" and not "tohuw". An unknown speaker
resolves to itself rather than to the nearest guess, because a wrong
attribution is worse than an unresolved one.

## Decision points

- **Site name.** Default: the campaign directory's name, titleized.
  Worth asking when the user is present — it is the campaign's public
  name — but never a blocker.
- **Directory layout.** Default: `wiki/` for the DM master,
  `dist/player` for the projection, `dist/site` for rendered HTML,
  `log.md` inside the wiki. Deviate only for an existing campaign
  whose layout is already loved.
- **Where the Eddic checkout lives.** Default: pass its path to
  `upgrade` as an argument each time; nothing is stored, so the
  committed campaign stays portable. Set `"eddic_checkout"` in
  `config.json` (or `EDDIC_HOME` in the environment) only for a
  single-machine campaign where an unattended routine runs the verb.
- **Runtime.** Default: uv (`uv run .eddic/eddic.py …`). Bare
  `python3` works everywhere the stdlib-only verbs are concerned;
  verbs with declared dependencies need uv.

## Verify

- `uv run modules/cli/verify/run.py` — stamps a throwaway campaign,
  runs doctor, records and checks a manifest entry, vendors the lint
  verb, and lints a planted wiki through the dispatcher, asserting
  exit codes at each step. It also drives `upgrade` against a synthetic
  checkout holding a current, an upgradable, a renamed and a vanished
  module, asserting each verdict, the unclaimed-verb flag, exit 1 then
  exit 0, and that the manifest is unchanged by the report.
- In the real campaign: `eddic.py doctor` exits 0; `eddic.py manifest
  show` lists cli; `eddic.py upgrade <checkout>` exits 0 once you have
  worked its list; `.eddic/` is committed.
