# Pattern: transcribe a session

Turns session audio into a sources/ transcript the ingest routine can
compile from: speaker-labeled when the recording has per-speaker
tracks (a Craig export gives one file per voice, which makes
attribution exact — something a single mic can never do), timestamped
throughout, marked `authorship: transcript`, with a standing
mishearings section so corrections accumulate without ever editing
the transcript body.

## Preflight

- whisper.cpp's CLI (`whisper-cli`) is installed and a model file is
  on disk. You know how to install both for this host (package
  manager or a release binary; models from the whisper.cpp model
  repository). Nothing else is needed — no accounts, no uploads,
  audio never leaves the machine.
- The session audio exists locally: one mixed file, or a directory
  of per-speaker tracks named like `1-username.flac`.

## Procedure

1. Transcribe:

       uv run modules/transcriber/scripts/transcribe.py <audio-or-dir> \
           --out <campaign>/sources/session-N_transcript.md \
           --session "Session N" [--model <path>] [--whisper <bin>]

   A directory input transcribes each track and merges by timestamp;
   long silences break paragraphs; consecutive same-speaker segments
   coalesce.

2. Skim the result for systematic mishearings (proper nouns fare
   worst: "suntan" for Sunton) and record them in the transcript's
   "Known mishearings" section — never edit the body; the transcript
   is a source, and corrections are annotations on it.

3. Log an `ingest` entry when the transcript is compiled into the
   wiki (that compilation is the wiki pattern's job, not this one's).

4. The whisper working directory (`.<name>-whisper/` beside the
   output) holds the raw per-track JSON; keep or delete at the
   owner's preference.

## Decision points

- **Model.** Default: **ask the owner interactively** — present the
  ladder with sizes and your recommendation for their machine and
  patience, then download their pick to a cache dir (e.g.
  `~/.cache/whisper-cpp/`) from the whisper.cpp model repository:

  | model | download | character |
  |---|---|---|
  | `base.en` | ~148 MB | fast draft; misses crosstalk |
  | `small.en` | ~466 MB | good on clear single voices |
  | `medium.en` | ~1.5 GB | the quality floor for session audio |
  | `large-v3-turbo` | ~1.6 GB | near-best quality, much faster |
  | `large-v3` | ~3.1 GB | best transcription available |

  Recommend from what you can see — hardware, disk, session length,
  how much the table cares about exact words. You know how to weigh
  these; the table's answer is the decision. When the owner says
  "just pick," take `large-v3-turbo` on capable hardware, `medium.en`
  otherwise.
- **Mixed vs per-speaker.** Default: per-speaker tracks whenever the
  recording offers them; exact attribution is the difference between
  a transcript and a guess. Mixed audio still transcribes, unlabeled.
- **Raw JSON retention.** Default: keep until the session's wiki
  ingest is done, then delete.

## Verify

- `uv run modules/transcriber/verify/run.py` — merges planted
  whisper JSON for two speakers via `--from-json` and asserts
  timestamp ordering across tracks, same-speaker coalescing,
  paragraph breaks at long gaps, speaker labels from track names,
  and the sources frontmatter.
- With real audio: transcribe a short clip and read it; timestamps
  sane, speakers right, mishearings section present.
