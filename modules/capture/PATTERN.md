# Pattern: session capture

Gets each session's audio into the campaign, by whichever route fits
the table. The irreplaceable Eddic parts are downstream — staging
into the transcriber's layout and the local transcription — so the
capture source is a genuine choice, not a doctrine.

## Preflight

- The transcriber pattern is applied (unless the table uses premium
  Craig's own transcripts, in which case it is simply unused).
- For the Craig routes: Craig invited to the server (craig.chat; the
  driven-browser invite flow from the lore-bot pattern applies).
  Verify at setup time that the free tier still provides
  per-speaker tracks — vendor tiers move.

## Procedure

1. Vendor the staging verb:

       cp scripts/stage_craig.py <campaign>/.eddic/lib/stage-craig.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module capture --version 0.1.0 --verbs stage-craig

2. The table records sessions per its chosen route (decision point
   below). Craig's own docs cover summoning it; the Eddic recorder
   bot carries its own consent flow.

3. **The handoff — the owner never navigates folders.** When the
   owner has downloaded a session from Craig (or says so, or you
   simply notice a fresh Craig artifact in their downloads — you
   know their OS and where downloads land), take it from there:
   `eddic stage-craig <download>` does the deterministic staging
   into `sessions/raw/<date>/` (including flattening Craig's
   occasional folder-named-`.flac` quirk), then run the
   transcription per the transcriber pattern. If the download turns
   out to be Craig's own transcript (premium), place it as the
   session's source directly. Log an `ingest` entry either way.

   macOS recognition note: Safari auto-extracts Craig's zip into a
   folder *named* `craig-*.flac`, which macOS then treats as a
   quarantined package — Gatekeeper warnings, opens in an audio app
   instead of Finder. Staging handles it untouched (pass the folder
   as-is; copied files shed the quarantine attribute), so under
   this pattern the owner never meets the problem. If they arrive
   already bitten ("my Mac says the recording is damaged"), the
   cure is stripping the quarantine attribute and renaming the
   folder to drop the bogus extension — you know the commands.

## Decision points

- **Capture source.** Default: **free Craig** — proven for years,
  per-speaker tracks, zero hosting, and all we truly need is the
  audio since transcription is local. Alternatives: the **Eddic
  recorder bot** (the recorder module: structural react-gated
  consent, no third party in the audio path, runs locally at
  session time; live-proven, riding pinned py-cord patches until
  upstream lands voice receive) or **premium Craig with its own
  transcripts** (then skip the transcriber entirely). No wrong
  answer; the consent-machinery difference is the real trade.
- **Raw audio retention.** Default: keep until the session's wiki
  ingest is done, then the owner's call.

## Verify

- `uv run modules/capture/verify/run.py` — stages a planted Craig
  zip: per-speaker tracks land in the dated layout, the
  folder-named-`.flac` quirk is flattened to a real file, non-audio
  extras are reported untouched, and an audio-free download refuses.
- Live: after the first real session, the staged tracks transcribe
  clean and the owner never once opened a file manager.
