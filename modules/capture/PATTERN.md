# Pattern: session capture

Gets each session's audio into the campaign, by whichever route fits
the table. The irreplaceable Eddic parts are downstream — staging
into the transcriber's layout and the local transcription — so the
capture source is a genuine choice, not a doctrine.

Know what the choice is upstream of, and tell the table: the audio
becomes a written transcript locally, and the recap step downstream
then hands that transcript, entire and verbatim, to a model provider so
an agent can author the session's pages. Everything the microphones
caught goes with it, game or not. Being recorded and being sent to a
provider are two separate things to consent to; the recorder module's
consent post states both, and a table on the Craig route has no consent
post at all, so that route's owner owes the table the whole sentence
themselves.

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
           --module capture --version 0.1.1 --verbs stage-craig

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
  recorder bot** or **premium Craig with its own transcripts** (then
  skip the transcriber entirely). The consent-machinery difference is
  the real trade: only the recorder bot gates each microphone
  structurally and posts the disclosure the table reads, while only
  Craig keeps a third party in the audio path.

  The recorder bot is **experimental, and never a table's only
  recording.** It got a live capture through end to end once, on
  2026-07-18, on pinned py-cord patches plus a Rust DAVE library.
  Discord rotates a call's encryption keys mid-session, the receive
  path does not re-derive across the rotation, and every packet after
  it fails to decrypt — **permanently for that recording, and
  silently**: the bot stays connected, tracks keep being written, and
  nobody finds out until transcription returns nothing usable. There is
  no in-tree mitigation. So when a table picks the recorder bot, run
  **Craig in parallel every session** and treat the bot's tracks as the
  preferred output, not the relied-on one. Craig costs nothing, needs
  one summon, and turns a lost night into a redundant download. Stage
  whichever set survived; the transcriber neither knows nor cares which
  produced them.
- **Raw audio retention.** Default: **delete the session's raw audio 30
  days after that session's wiki ingest completes.** Thirty days
  outlives every reason to go back to the tape — a garbled line, a name
  nobody caught, a re-transcription with better prompting — while
  keeping the campaign from accumulating an indefinite archive of
  everyone's voices, which is the asset nobody consented to and nobody
  is guarding. Transcripts are kept: they are the campaign's source,
  they are already what the wiki cites, and they are text an owner can
  actually read and redact. To change it, the owner says a different
  number (or "keep nothing past ingest", or "archive it, I accept
  holding it") and the agent records that choice in the manifest
  alongside the module version, so a later run does not silently revert
  to this default.

  State the honest limit when you set this: **nothing enforces it.** No
  script sweeps `sessions/raw/`; the deletion is a step performed at
  ingest time, or a routine the table adds via the routines module.
  A retention default the owner never executes is a promise the table
  was given and did not receive, so tell them the number and tell them
  who runs it.

## Verify

- `uv run modules/capture/verify/run.py` — stages a planted Craig
  zip: per-speaker tracks land in the dated layout, the
  folder-named-`.flac` quirk is flattened to a real file, non-audio
  extras are reported untouched, and an audio-free download refuses.
- Live: after the first real session, the staged tracks transcribe
  clean and the owner never once opened a file manager.
