# discord-setup

The discord-setup module gives a campaign's Discord server a standing
spec: the shape of the table's home — roles, channels, channel topics,
and role-privacy — versioned as JSON in the campaign repo and reconciled
by a single deterministic verb. Server shape stops being tribal memory
held in one owner's head. Drift between the spec and the live server
surfaces the way [lint](lint.md) findings do, and reconciliation is
additive-only: the verb creates what is missing and never deletes or
renames anything, because removal is treated as a human act performed in
the Discord client, not something a script decides. The module depends
on [cli](cli.md) and touches [lore-bot](lore-bot.md), whose bot token and
invited permissions it reuses.

## The spec

A `server-spec.json` file names a `guild_id` and lists `roles` and
`channels`. Each role carries a name and optional `hoist` and
`mentionable` flags. Each channel carries a name, a `type` of `text` or
`voice`, an optional `topic`, and an optional `private_to` naming the one
role permitted to see it. The generalized scaffold template seeds a new
server with an ask-the-archivist channel, threaded session-recaps, a
botspam sandbox that is explicitly non-canon, a session voice channel, a
DM-private notes channel, and DM and Player roles. The spec governs only
this shape; it does not govern third-party bots.

## The verb

The verb runs against the Discord REST API using the campaign bot's
existing token, drawn from `DISCORD_TOKEN` in the environment or from the
bot's token file — no gateway connection and no hosting, so operation is
entirely free. The bot must hold Manage Roles and Manage Channels; a
permissions error instructs the operator to re-invite it with those bits
through the same portal flow, and reports that nothing was partially
applied beyond what was already printed. Managed roles (those owned by
bots) and the `@everyone` role are excluded from both reporting and
reconciliation.

Three modes cover the lifecycle. The bare run is a drift report and,
equivalently, a plan: it lists each spec item as create (missing on the
server), re-use (present and matching, kept as-is), or mismatch (present
but with differing topic or privacy), and lists extra channels that exist
on the server but not in the spec as left untouched. The report exits
nonzero when any drift exists and zero when the server is in sync. The
`--apply` mode creates exactly the items the plan marked for creation and
changes nothing else; private channels receive their overwrites at birth,
denying view to `@everyone` and allowing it to the named role, so a
private channel is never briefly public. Mismatches on channels that
already exist are reported but never auto-repaired — the owner decides
whether to reconcile an existing channel's topic or privacy by hand. The
`--dump` mode prints the live server as spec JSON, which is how an
existing server is adopted: dump reality, trim the result to what the
table means to keep, and commit it.

## Applying the pattern

For an existing server the default is to adopt rather than scaffold: dump
the live server so the spec begins as truth, then trim it. A genuinely
new server starts from the template with its guild id filled in. Planning
always precedes applying — the bare verb is the plan, and the operator
walks the owner through it in the owner's own terms (what will appear on
their server, what of theirs is being kept) before any `--apply` runs. A
plan the owner has not seen is never applied.

Third-party bots are invited, not specced: each is an OAuth flow on its
own site, driven through the browser. A curated set is offered — a dice
and character-sheet bot, a scheduling bot, and a music bot for ambience —
and the table takes what it wants; a table with its own loadout keeps it.
Recording is deliberately absent from that set, because the
[capture](capture.md) module covers session recording. Because an
unasked-for channel creation would violate least surprise, the drift
policy in any maintenance [routine](routines.md) is report-only; `--apply`
stays a deliberate, owner-approved act. Applying the pattern ends with the
committed spec and a `schema` entry in the operation log.

The module's determinism sits in the verb, its judgment at the marked
decision points — see [Deterministic core, agent shell](../concepts/deterministic-core.md).
See also the [module index](index.md).
