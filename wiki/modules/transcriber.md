# transcriber

The transcriber module turns a recorded session into a `sources/`
transcript the wiki ingest can later compile from. It runs whisper.cpp
entirely on the local machine: no accounts, no uploads, audio never
leaves the host. This is deliberately the free path that replaces paid
transcript services — the audio is already given away by the recording
bot, so there is no reason to pay a second party to transcribe it. The
module touches only `sources/` and depends on no other module. Its
sole deterministic script is
[`scripts/transcribe.py`](../../modules/transcriber/scripts/transcribe.py),
invoked through the [cli](cli.md).

## Input: mixed file or per-speaker tracks

The transcriber accepts either a single mixed recording or a directory
of per-speaker tracks. A directory is treated as a Craig-style export —
one file per voice, named like `1-username.flac` — and this is the
preferred form, because per-speaker tracks make attribution exact in a
way a single microphone never can. Each track is transcribed
separately, then all segments are merged into one timeline. A single
mixed file still transcribes, but its lines carry no speaker label. The
speaker label is derived from the track filename by stripping a leading
number and separator, so `1-username` and `01_username` both become
`username`. Recognized audio extensions are FLAC, WAV, MP3, M4A, OGG,
AAC, and Opus. The recording itself is produced upstream by the
[recorder](recorder.md) module.

## Merge behaviour

Segments from every track are sorted by their whisper start offset into
a single ordered timeline, so speakers interleave correctly across
tracks. Two rules then shape the prose. Consecutive segments from the
same speaker are coalesced into one paragraph as long as the gap
between them stays under thirty seconds. A silence of thirty seconds or
more breaks the paragraph even for the same speaker, so long pauses in
play become paragraph boundaries. Each rendered line is stamped
`[H:MM:SS] speaker: text`, the timestamp computed from the segment's
millisecond offset.

## Output: a sources transcript

The written file is a `sources/` document, not a wiki page. It opens
with frontmatter marking `authorship: transcript` and an `origin`
field naming the input, carries a standing "Known mishearings" section,
and then the timestamped transcript body under a "Transcript" heading.
The `authorship: transcript` marker tells the ingest routine that this
is a raw source and not human-authored prose, which governs how it may
be transformed. Compiling the transcript into actual wiki pages is the
[wiki](wiki.md) module's job, not this one's; the transcriber stops at
producing the source. That compilation step is what earns an `ingest`
entry in the operation log.

## Mishearings are annotations, never edits

whisper mishears systematically, and proper nouns fare worst — a place
called Sunton is heard as "suntan" consistently across a session.
Corrections are never applied by editing the transcript body. The
transcript is a source, and a source is not rewritten; corrections
accumulate in the "Known mishearings" section as annotations on it.
This keeps the raw machine output intact and auditable while still
letting the ingest apply the accumulated fixes downstream. Respecting
that authorship boundary is a
[firewall](../concepts/the-firewall.md)-adjacent instance of Eddic's
broader rule against stylistically rewriting non-agent content.

## The model ladder

Which whisper.cpp model to use is the module's main decision point. The
model file must already be on disk; the recommendation weighs host
hardware, disk, session length, and how much the table cares about
exact words.

| model | size | character |
|---|---|---|
| `base.en` | ~148 MB | fast draft; misses crosstalk |
| `small.en` | ~466 MB | good on clear single voices |
| `medium.en` | ~1.5 GB | the quality floor for session audio |
| `large-v3-turbo` | ~1.6 GB | near-best quality, much faster |
| `large-v3` | ~3.1 GB | best transcription available |

When the owner declines to choose, the default is `large-v3-turbo` on
capable hardware and `medium.en` otherwise. Models are fetched from the
whisper.cpp model repository into a cache directory and passed with
`--model`.

## Invocation, working directory, exit codes

The script is run through uv:

```
uv run modules/transcriber/scripts/transcribe.py <audio-or-dir> \
    --out <campaign>/sources/session-N_transcript.md \
    --session "Session N" [--model <path>] [--whisper <bin>]
```

The `--whisper` flag overrides the whisper binary, which defaults to
`whisper-cli`. During a real transcription the script creates a working
directory named `.<out-stem>-whisper/` beside the output file, holding
the raw per-track whisper JSON; by default this is kept until the
session's wiki ingest is done, then deleted at the owner's discretion.
A separate `--from-json` mode skips whisper entirely and merges
existing whisper JSON output, which is both a way to re-merge without
re-transcribing and the mechanism the module's verify uses to run
without any audio. The script exits 0 when the transcript is written, 1
when a track fails to transcribe, and 2 on a usage error.

## Verification

The module's [deterministic](../concepts/deterministic-core.md) check,
[`verify/run.py`](../../modules/transcriber/verify/run.py), plants two
speakers' whisper JSON and runs the `--from-json` merge, then asserts
that segments interleave in timestamp order across tracks, that
same-speaker runs coalesce, that a long gap breaks a paragraph, that
speaker labels are recovered from the track filenames, and that the
sources frontmatter and mishearings section are present.

See the full [module index](index.md) for how the transcriber sits
beside the [recorder](recorder.md) that feeds it and the [wiki](wiki.md)
that consumes its output.
