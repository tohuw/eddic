# capture

The capture module gets each session's audio into the campaign by
whichever recording route fits the table, and hands that audio off to the
rest of the pipeline without the owner ever navigating folders. Its
premise is that the capture source is a genuine choice rather than
doctrine: the irreplaceable Eddic part lives downstream, in deterministic
staging into the [transcriber](transcriber.md)'s layout followed by local
transcription. All the pipeline truly needs is the audio file, so the
table records however it likes and only the staging step is fixed. The
module depends on [cli](cli.md) and touches [transcriber](transcriber.md),
whose dated directory layout it writes into.

## Routes

Three routes cover recording, and none is wrong; they differ only in
consent machinery and cost. The default is free Craig (craig.chat), a
Discord recording bot proven over years that yields per-speaker tracks
with zero hosting — enough, because transcription happens locally. The
second is the Eddic [recorder](recorder.md) bot: a structural,
react-gated consent flow with no third party in the audio path, running
locally only at session time; it is live-proven but rides pinned py-cord
patches until upstream voice-receive lands. The third is premium Craig
using Craig's own cloud transcripts, which skips the transcriber module
entirely. The free route plus local transcription costs nothing; premium
Craig is paid convenience and is never required.

## Preflight

The transcriber pattern is applied first, unless the table uses premium
Craig's own transcripts, in which case the transcriber is simply unused.
For either Craig route, Craig must be invited to the server through its
browser invite flow, driven the same way the [lore-bot](lore-bot.md)
pattern drives OAuth flows. Because vendor tiers move, the free tier is
re-checked at setup time to confirm it still provides the per-speaker
tracks the pipeline expects.

## Staging and the handoff

The module vendors one deterministic verb, `stage-craig`, copied into the
campaign's library and recorded in the manifest at version 0.1.0. The verb
takes the zip — or an already-unpacked folder — that Craig hands the owner
and stages the per-speaker tracks into `sessions/raw/<date>/`, the layout
the transcriber reads. Output goes to a `--out` directory or, run as an
eddic verb, to the campaign's `sessions/raw` derived from `EDDIC_CONFIG`;
the date defaults to today. It recognizes the common audio extensions
(flac, wav, mp3, m4a, ogg, aac, opus) and flattens the known Craig quirk
where a track arrives as a *directory* named like `1-name.flac` with the
real audio file inside, copying that inner file out to the name it should
have been. Non-audio files — Craig's `info.txt`, premium transcripts — are
left untouched and listed so the agent can judge them. It exits zero when
tracks were staged, one when the download held no stageable audio, and two
on a usage error.

The handoff principle is that the owner never navigates folders. When the
owner has downloaded a session from Craig — or one simply appears in
downloads — the agent runs `eddic stage-craig <download>`, then runs
transcription per the transcriber pattern; on premium Craig the ready
transcript is placed as the session source directly. Either way an
`ingest` entry is logged. This deterministic staging is the fixed core;
route selection is the surrounding judgment, per
[Deterministic core, agent shell](../concepts/deterministic-core.md). On
macOS, Safari auto-extracts Craig's zip into a top-level folder *named*
`craig-*.flac`; the verb stages that case as well, and the occasional
"recording damaged" complaint is a quarantine attribute to strip.

## Decision points and verification

Two decisions are marked. The capture source defaults to free Craig; the
recorder bot and premium Craig are the alternatives, and the real trade
between them is consent machinery, not audio quality. Raw audio retention
defaults to keeping the source until the session's wiki ingest is done,
but is the owner's call. Verification stages a planted Craig zip and
confirms that per-speaker tracks land in the dated layout, the
folder-named-`.flac` quirk flattens to a real file carrying the true
audio, non-audio extras are reported untouched, the Safari-mangled
top-level folder stages, and an audio-free download refuses. The live
check is that after the first real session the staged tracks transcribe
clean and the owner never once opened a file manager.

Recording sits with this module rather than with the server bots the
[discord-setup](discord-setup.md) pattern invites. See also the
[module index](index.md).
