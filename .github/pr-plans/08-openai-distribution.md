# distribution: add an optional Codex/ChatGPT plugin and app template

Tracking issue: #1

## Objective

Package Eddic for OpenAI discovery while keeping AGENTS.md, patterns, and CLI canonical.

## Planned files

- `.codex-plugin/plugin.json`
- `skills/*`
- `apps/*`
- `docs/compatibility.md`
- `README.md`

## Scope

- Add an optional Codex skill routing to current modules.
- Add an app template for an existing Worker.
- Reference canonical patterns instead of copying them.
- Expose compatibility and setup requirements in metadata.
- Verify clean install and removal.

## Acceptance criteria

- [ ] Eddic works without the plugin.
- [ ] Plugin defers to AGENTS.md and PATTERN.md.
- [ ] Claude setup is unchanged.
- [ ] Plugin shortens adoption instead of creating another architecture.

## Non-goals

- No Apps SDK UI without need.
- No provider fork.
- No marketplace submission.

## Implementation status

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
