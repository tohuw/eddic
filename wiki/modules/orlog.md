# orlog

The orlog module connects a campaign to its Ørlǫg story, the external timeline tool in which chronology is authored. It exists so that time is stated one way in each place: the Ørlǫg story holds the machine chronology, the campaign wiki states time in plain prose, and facts cross between them only when the owner directs it. The module adds two things upstream Ørlǫg does not: the fork-first reconcile discipline for moving settled facts into the timeline, and a query cookbook for answering time questions from the timeline rather than inventing a date syntax in prose. It touches the [wiki](wiki.md) and depends on the [cli](cli.md); it is entirely local and free, requiring only Ørlǫg's headless CLI on Node 24 or later, driven by a standard-library Python wrapper.

## Preflight

Three conditions must hold before the module applies. The campaign already uses Ørlǫg — a story folder exists, by default under the owner's documents in the app's stories directory. The module never creates a story; the story is the owner's, born in the app. Ørlǫg's headless CLI must be reachable, whether as an installed `orlog` or a repo checkout run as `node <repo>/packages/cli/src/cli.ts`; the invocation is recorded in `.eddic/config.json` as `orlog_cmd` and the story path as `orlog_story`. The [cli](cli.md) pattern must already be applied.

## The reconcile discipline

Reconciliation moves settled facts from the wiki into the timeline, and it runs only when the owner directs it — never as ambient maintenance, never scheduled. Chronology mutations are canon surgery. The default fact direction is wiki to timeline, because the wiki is where play lands first; the reverse flow passes through the same owner-directed gate and is phrased as prose, never as machine dates.

The verb `reconcile` is fork-first, unconditionally. Its flow is fork, then apply to that fork's branch, then validate that branch — all-or-nothing. The trunk and the story head are never written by the script. A refusal at any stage means nothing landed anywhere but an isolated fork the owner can inspect and delete. Refusal at apply leaves the fork holding nothing new; refusal at validate leaves the fork holding the applied mutations for inspection. In every case the exit is loud and names the untouched head. Exit codes are zero when reconciled onto a fork, one when refused, two on usage error.

Setting the head — merging the fork — is the owner's act in Ørlǫg, and the script never performs it. Nor does the verb delete anything: refused or unmerged forks are left in place for the owner to inspect and remove in the app. After a successful reconcile the operator hands the owner the review (`orlog dump --branch <fork>` and targeted queries) and appends a `reconcile` entry to the wiki's operation log recording what moved, from which pages, onto which fork.

Drafting the mutations is judgment work: gather settled events from session recaps and the wiki's log since the last reconcile, draft conservatively, and keep each fact traceable to its page. The current mutation vocabulary comes from `orlog schema`, which emits the JSON Schema of the mutation union; a shipped template shows the shape of a single `event.create` mutation with a floating anchor. This fork-then-validate, all-or-nothing posture is the [deterministic core](../concepts/deterministic-core.md) applied to chronology, and the owner-only merge follows directly from Eddic's [design principles](../design/principles.md) on human authority over canon.

## Query cookbook

When a time question arrives — how old a character is at a given event, what era a scene falls in — the answer comes from the timeline, not from arithmetic in prose. The queries are `age`, `era-at`, `time-between`, `anniversaries`, and `alive`. Where a query takes a moment in time, an anchored event's label is preferred over a literal date, because a label stays true when the timeline shifts beneath it.

## Verify

The module's verifier drives the reconciler against a fake Ørlǫg CLI and proves the discipline without a real Ørlǫg present: fork happens before apply before validate, the fork's branch id threads through the later calls, a refused apply aborts before validate with the head untouched, success names the fork, and a missing mutations file is a usage error. Run it with `uv run modules/orlog/verify/run.py`. Live verification, when Ørlǫg is installed, runs the example mutations against a copy of the story — never the original — and confirms the fork appears, the head is unmoved, and a malformed mutation refuses loudly.

See the full [module index](index.md) for related patterns.
