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
   and the editor removed (`docs/data-controls.md`).

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

## Decision points

- **Site name.** Default: the campaign directory's name, titleized.
  Worth asking when the user is present — it is the campaign's public
  name — but never a blocker.
- **Directory layout.** Default: `wiki/` for the DM master,
  `dist/player` for the projection, `dist/site` for rendered HTML,
  `log.md` inside the wiki. Deviate only for an existing campaign
  whose layout is already loved.
- **Runtime.** Default: uv (`uv run .eddic/eddic.py …`). Bare
  `python3` works everywhere the stdlib-only verbs are concerned;
  verbs with declared dependencies need uv.

## Verify

- `uv run modules/cli/verify/run.py` — stamps a throwaway campaign,
  runs doctor, records and checks a manifest entry, vendors the lint
  verb, and lints a planted wiki through the dispatcher, asserting
  exit codes at each step.
- In the real campaign: `eddic.py doctor` exits 0; `eddic.py manifest
  show` lists cli; `.eddic/` is committed.
