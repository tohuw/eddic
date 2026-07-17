# ChatGPT web MCP — live acceptance record

The ChatGPT route stays `unverified` in module.yaml and
`docs/compatibility.md` until this checklist is completed against a
real ChatGPT on a real campaign. Mirror of the Claude cold-context
test that promoted the Claude rows. Fill it in, then promote the
statuses (with this file as the evidence pointer) in the same commit.

## Setup under test

- ChatGPT plan: ______ (Pro developer-mode / Business-Enterprise-Edu
  managed workspace — record which; they gate different MCP scopes)
- Date: ______
- Auth style used: bearer app auth / capability URL (record which;
  prefer bearer so the token stays out of the endpoint URL)
- Connector add route: user click-through / consented agent-driven

## Checks

1. **Cold context.** New chat, no instructions, no prior mention of
   the campaign. Ask a lore question about a term only the wiki
   defines. Pass: the model reaches for the connector's tools
   unprompted and answers from canon. Record the question shape (not
   campaign specifics), which tools it called, and time-to-answer.
2. **Tier isolation, consumer side.** With the player-tier connector,
   ask for a secret the projection withholds. Pass: the gap reads as
   the campaign's intended mystery; no refusal language, no leak. Ask
   directly for a DM-only page by path. Pass: indistinguishable from
   a page that never existed.
3. **Tool scan.** Confirm all four tools appear and are usable;
   confirm the client respects the read-only annotations (no write
   affordances surface).
4. **Surface limits.** Confirm mobile app and Voice behavior matches
   the documented limits (web-only MCP; Voice unsupported) and note
   any drift — vendor surfaces move.

## Result

- Verdict: ______ (pass → promote chatgpt to verified with this file
  and the date as evidence; fail → record what broke, keep
  unverified, file the fix)
- Latency felt: ______
- Drift from documented behavior: ______
