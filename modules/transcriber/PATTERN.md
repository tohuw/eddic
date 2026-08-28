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
- **Check the queue at the start of a working session.** The recorder
  stages audio and logs a `witness` entry, then stops; nothing
  transcribes itself. List `sessions/raw/` and compare the newest dated
  folder against the highest `sources/session-N_transcript.md` — a
  folder with no transcript is a session the table has not been given
  back, and it is the first thing to do, ahead of whatever the owner
  opened the campaign to ask about.
- **Probe before the long run.** A multi-hour, multi-track recording
  is hours of compute, and a recorder fault — a failed decrypt, the
  wrong input device, a track that is silence end to end — produces
  that many hours of garbage just as willingly. Cut a three-minute
  slice from the middle of the largest track and transcribe only
  that, then read it:

      ffmpeg -ss 3600 -t 180 -i <largest-track> -ar 16000 -ac 1 probe.wav
      whisper-cli -f probe.wav -m <model> -nt

  Recognisable table talk means the recording is sound and the full
  run is worth starting. Noise, silence, or a looping hallucination
  means repair the recording — or accept it is lost — before spending
  the afternoon on it. `ffprobe -show_entries format=duration` on each
  track is the cheaper half of the same check: tracks that should
  differ in length and do not, or a duration nothing like the
  session's, are the fault showing up before whisper ever runs.

## Procedure

1. Seed the recognizer with the campaign's own names first. Invented
   proper nouns are where recognition fails hardest, and the campaign
   already knows every one of them:

       uv run <campaign>/.eddic/eddic.py ingest --glossary

   That prints a short prompt built from the wiki's page titles and
   every correction previously recorded under "Known mishearings", so
   accuracy improves each session instead of the same name being
   mangled forever. Pass it as `--prompt` below. (The glossary verb
   ships with the ingest module; without it, write the prompt by hand
   from the names the session will use — it is the same idea, done
   worse.)

2. Transcribe:

       uv run modules/transcriber/scripts/transcribe.py <audio-or-dir> \
           --out <campaign>/sources/session-N_transcript.md \
           --session "Session N" [--model <path>] [--whisper <bin>] \
           [--prompt "<glossary output>" | --prompt-file <file>]

   A directory input transcribes each track and merges by timestamp;
   long silences break paragraphs; consecutive same-speaker segments
   coalesce.

3. Skim the result for systematic mishearings (proper nouns fare
   worst: "suntan" for Sunton) and record them in the transcript's
   "Known mishearings" section — never edit the body; the transcript
   is a source, and corrections are annotations on it. That section is
   read back by `ingest --glossary`, so a correction recorded once
   stops the same mishearing recurring.

4. Compiling the transcript into the wiki is the **ingest** module's
   job — recap, page updates, and the citations that make a claim
   traceable to the line that produced it. Log its `ingest` entry
   there, not here.

5. The whisper working directory (`.<name>-whisper/` beside the
   output) holds the raw per-track JSON; keep or delete at the
   owner's preference.

### Speaker labels

A track is named for whoever Discord thought was speaking — a username,
a display name, sometimes a display name with a real first name glued
on. With a campaign roster present (the cli module's `roster` verb),
those resolve to the table's own terms before they reach the transcript:
`1-Niðrerir_Ron.wav` becomes `Niðrerir`, `5-theseous` becomes `DM`.
Pass `--roster FILE` to override; without a roster, labels pass through
exactly as they always did.

This is a firewall matter as much as a legibility one. The roster is
DM-tier and holds real names; the transcript is a source file the whole
pipeline reads, and it should speak in character terms.

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
