# Pattern: discord-setup

Gives the campaign's Discord server a **standing spec**: the shape of
the table's home — roles, channels, topics, role-privacy — versioned
in the campaign repo and reconciled by a deterministic verb. Server
shape stops being tribal memory; drift shows up like lint findings,
and creation is additive-only — the verb never deletes or renames
anything, because removal is a human act in the client.

## Preflight

- The campaign bot exists (lore-bot pattern) and its invite carries
  **Manage Roles** and **Manage Channels** — re-invite with an
  updated permissions URL if not; the driven portal flow applies.
- The guild id is known (the owner's client copies it with Developer
  Mode on; you know the path).

## Procedure

1. Vendor the verb and seed the spec:

       cp scripts/discord_setup.py <campaign>/.eddic/lib/discord-setup.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module discord-setup --version 0.1.0 --verbs discord-setup

   For an existing server, seed by **dumping reality**:
   `eddic discord-setup --dump > server-spec.json`, then trim it to
   what the table actually means to keep versioned. For a new
   server, start from `templates/server-spec.json` (the generalized
   scaffold: ask-the-archivist, threaded session-recaps, a botspam
   sandbox, a session voice channel, a DM-private channel, DM and
   Player roles) and fill the guild id.

2. **Plan first, always.** The bare verb IS the plan: what `--apply`
   would create, what already exists and will be **re-used as-is**,
   which mismatches wait on the owner, and which extras stay
   untouched. Walk the owner through that plan in their terms — what
   appears on their server, what of theirs is being kept — and only
   then run `eddic discord-setup --apply`, which creates exactly the
   planned items (private channels get their deny-@everyone/
   allow-role overwrites at birth) and changes nothing else.
   Never apply a plan the owner hasn't seen.

3. Third-party bots are invited, not specced — each is an OAuth
   flow on its own site (the agent-driven browser route). Curated
   set, per the owner: **Avrae** (dice and D&D Beyond),
   **Apollo** (session scheduling), **Jockie Music** (ambience).
   Recording is deliberately absent — the capture module covers it.

4. Commit `server-spec.json` and log a `schema` entry.

## Decision points

- **Adopt vs scaffold.** Default: adopt — dump the live server and
  trim; the spec should start as truth, not aspiration. Scaffold
  from the template only for a genuinely new server.
- **Curated bots.** Default: offer the curated three above; the
  table takes what it wants. A table with its own loadout keeps it —
  the spec doesn't govern bots.
- **Drift policy.** Default: report-only; `--apply` is a deliberate
  act, suited to a maintenance routine only as report (a routine
  that creates channels unasked violates least surprise).

## Verify

- `uv run modules/discord-setup/verify/run.py` — drives the verb
  against a mock API: drift detection (missing, extra, privacy and
  topic mismatches), additive apply with overwrites at creation,
  no auto-repair of existing channels, dump round-trip, managed
  roles excluded.
- Live: dump your real server and read the spec it prints — it
  should look like the server you know. Then `--apply` on a spec
  with one new test channel and watch exactly that channel appear.
