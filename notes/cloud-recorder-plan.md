# Cloud recorder plan — session recording from a worker host, sinking to R2

Planning note, 2026-07-18. Design for running the recorder capability
(module 9) when the campaign bot runs in lore-bot cloud mode, with
recordings landing in Cloudflare R2 instead of the campaign's local
disk. The local-disk path stays the baseline-build default; this is
the upgrade for tables whose bot already lives on a worker host
because no machine is reliably awake during play. Web-verified claims
below are dated 2026-07; the recorder brief itself (one bot, consent
in the sink, per-speaker tracks, transcriber layout, consent-to-record
≠ consent-to-sell) is unchanged from ROADMAP.

## Architecture sketch

    worker host (Railway / Fly.io — the lore-bot cloud-mode process)
      bot.py + recorder capability
        Discord voice gateway ──> voice_recv reader/decoder threads
              │ (WSS to *.discord.media + outbound UDP 50000–65535)
              v
        ConsentSink.write()  — consent gate, unchanged, per-user
              │ (only consented users' frames pass; runs on the
              │  extension's decoder thread, never the event loop)
              v
        per-user TrackWriter — Ogg/Opus (default) or FLAC encoder
              │ bounded queue, spill to ephemeral disk on stall
              v
        uploader thread — S3 multipart, 5 MiB uniform parts
              │ boto3 low-level API, bucket-scoped write token
              v
    R2 bucket  sessions/raw/<date>/N-name.ogg  (+ session.json manifest)
              │ lifecycle rules: delete after retention window,
              │ abort incomplete multipart after 7 days
              v
    DM's local machine
        `eddic sessions pull` (reader token) ──> <campaign>/sessions/raw/<date>/…
        writes the witness log entry locally, then transcriber runs
        as the deliberate maintenance step it already is

Nothing gains an inbound port. The bot stays one process with two
outbound needs: the gateway it already has, plus voice (WSS to
`*.discord.media` and outbound UDP to Discord's media servers, ports
50000–65535). Railway officially supports unrestricted outbound UDP
(inbound UDP is not supported, which a voice bot does not need — the
bot initiates, return traffic rides the established flow). One caveat
verified 2026-07: an unresolved Railway help thread (March 2026)
reports Discord voice UDP failing to reach ready state there, so the
host choice carries a mandatory preflight spike — join a voice
channel from the deployed bot and confirm `VoiceRecvClient` reaches
ready before the table depends on it. Fly.io is the named fallback:
outbound UDP works, community Discord music bots run there without a
dedicated IPv4 (their strict `fly-global-services` binding rules
apply to inbound UDP services only).

Bucket keys mirror the campaign layout exactly: object key
`sessions/raw/<date>/N-name.ogg` equals the repo-relative path the
transcriber already expects, so the pull verb is a straight prefix
download with no mapping table. A small `session.json` per date
records track list, byte counts, and sink stats — it is what lets the
pull verb write an honest witness log entry, since the cloud host
cannot append to `wiki/log.md` (the campaign repo is a read-only
tarball in cloud mode; the log write moves to pull time, which is
also where provenance doctrine wants it: a field write reconciled on
the DM's machine, not hot-edited from a remote host).

## Upload strategy: streaming multipart, not upload-on-stop

Upload-on-stop is disqualified by its failure mode: worker-host disks
are ephemeral, so a crashed or redeployed host mid-session loses the
entire recording — four hours of a table's one weekly night, gone.
Unacceptable regardless of simplicity.

Recommended: S3-compatible multipart upload per speaker track,
streamed during the session. R2 specifics that shape it (verified
2026-07 against Cloudflare docs):

- One multipart upload per track, created at first consented frame.
  Parts flush at exactly 5 MiB — R2 requires **uniform part sizes**
  (except the final part), an R2 quirk AWS does not share, so use the
  low-level boto3 multipart calls, not the transfer manager, and
  buffer to exactly the part size. 5 MiB is the minimum, which
  minimizes the loss window.
- Uploaded parts persist server-side immediately. After a crash,
  `ListMultipartUploads` + `ListParts` recover the upload ID and part
  ETags, so a deterministic **recovery sweep** — run at bot startup
  and available as an `eddic` verb — can `CompleteMultipartUpload` on
  anything left open under `sessions/raw/`. Everything already
  uploaded survives; recovery is idempotent and free (abort, if the
  owner prefers discarding a fragment, deletes all parts at no
  charge).
- Loss bound: only the not-yet-flushed tail buffer, < 5 MiB per
  track. At Opus rates that is up to ~10 minutes of *speech* per
  speaker (wall-clock longer, since silence is not transmitted). If a
  table wants a tighter time bound, the escape hatch is rolling
  segment objects (close and PUT a fresh object every N minutes;
  time-bounded loss, no multipart state, at the cost of a stitch step
  at pull time) — but the multipart default yields exactly one
  seamless file per track in the transcriber's layout, no stitching.
- Incomplete uploads auto-abort after 7 days by default; keep that
  rule so a session nobody recovers cannot silently accrue storage.

Backpressure: the uploader consumes a bounded queue; if R2 stalls,
spill to the host's ephemeral disk rather than grow memory or drop
frames (frames dropped by upload plumbing would be a silent hole in a
consented recording — the sink's stats discipline extends to the
uploader: parts written, parts pending, spill depth, reported at
`/record stop`).

## Audio format: Opus passthrough by default

Raw decoded PCM-WAV (48 kHz, 16-bit stereo) runs ~11.25 MiB per
minute per speaker — a four-hour, six-speaker session brushes 16 GB,
past the entire R2 free tier in one night. WAV is out for cloud.

The decisive fact: audio *arrives* Opus-encoded. Discord delivers
~64 kbps Opus per speaker; the local draft decodes it to PCM in the
sink. Re-encoding that decoded PCM to FLAC produces a file ~10×
larger than the Opus it came from while adding **zero fidelity** —
lossless-of-lossy. So the cloud default is passthrough:
`wants_opus() = True`, write `data.opus` packets into an Ogg
container (`.ogg`, RFC 7845 Ogg-Opus). ~0.5 MB per minute of speech
per speaker; a realistic session lands around 250–500 MB total. No
transcode CPU on the host — the encoder is Discord's. The transcriber
already accepts ogg/opus, so nothing downstream changes.

Containering options, in preference order: PyOgg's `OggOpusWriter`
(handles paging and pre-skip, but needs libogg/libopus shared libs on
the host and the project's maintenance is thin); a vendored minimal
Ogg-Opus muxer (the encapsulation is small and deterministic —
attractive under the no-bash, runs-anywhere rule); ffmpeg subprocess
(heaviest, but nixpacks/apt can provide it). Decide at implementation
with a live spike.

FLAC stays available as the archival option for owners who want
maximum tool compatibility and don't mind ~5.5 MB/min/speaker:
pyflac's `StreamEncoder` is a real-time streaming encoder (16-bit in,
bytes out via callback — feeds the part buffer directly), proven for
exactly this capture-thread pattern. It is a storage/compatibility
choice, not a fidelity one, and the pattern should say so plainly.

## Fetching: a small eddic verb, not a new tool

The transcriber runs on the DM's local machine; sessions must come
down before it runs. Recommended: `eddic sessions pull` — uv-run
Python with boto3 (PEP 723), reads the reader token from the
campaign's `variables.txt`/env, lists `sessions/raw/` prefixes newer
than what exists locally, downloads into the campaign tree, writes
the witness log entry from `session.json`, and (optionally, off by
default) deletes pulled objects. This fits principle 3 (the DM
installs nothing new — uv is already the bootstrap) and keeps the
deterministic core in the CLI where patterns can point at it.

Alternatives, documented not defaulted: rclone (works against R2 at
v1.59+; object-scoped tokens need `no_check_bucket = true`) for
owners who already live in rclone; presigned URLs (GET, max 7-day
expiry, SigV4 cap — not extendable) only for the one-off case of
handing a single track to someone without credentials. Egress is free
either way.

## Credentials, per data-controls doctrine

Two bucket-scoped R2 API tokens, mirroring the retrieval module's
two-token shape:

- **Writer** — Object Read & Write, scoped to the one sessions
  bucket, held only as worker-host env vars (the S3 credential pair:
  access key ID = token ID, secret = SHA-256 of the token value,
  endpoint `https://<account_id>.r2.cloudflarestorage.com`).
- **Reader** — Object Read only, same single-bucket scope, held in
  the campaign's gitignored `variables.txt` on the DM's machine for
  the pull verb.

Minting is the Cloudflare dashboard (R2 → API Tokens → Object Read &
Write → scope to bucket) or the Cloudflare API; **wrangler cannot
mint R2 S3 credentials** (verified 2026-07 — wrangler manages buckets
and objects, not token issuance), so the pattern's preflight walks
the dashboard flow the way the lore-bot pattern walks the Discord
portal, and when the agent drives the browser it reads the secret
straight into the env/config, never into chat. Standard doctrine
applies unchanged: tokens never in repos, URLs, or transcripts;
fingerprints (first 8) for later reference; exposure means rotation —
revoke in the dashboard, re-mint, update the two homes, seconds. The
writer token can write and read audio but nothing else in the
account; the blast radius of a leak is one bucket of consented
session audio, and rotation plus the retention window bounds it in
time too.

## Cost posture

Free path first (principle 4): the baseline build records to local
disk with the local-mode bot and touches no cloud storage — this
whole document is the *upgrade*, and its stated reason is "the bot
already runs on a worker host because no machine is awake during
play." The upgrade adds **no new host cost** (same process, same
dyno) and, at Opus rates, stays inside the R2 free tier with room:
10 GB-month storage / 1M Class A / 10M Class B per month, zero
egress. Four sessions a month at ~500 MB each with a 60-day retention
window sits around 2–4 GB-months; Class A usage (parts + manifests,
a few hundred per session) is noise against 1M; pulls are Class B
noise. FLAC-format tables should do the arithmetic in the pattern's
verify step — several GB per session makes the free tier a real
ceiling, which is itself an argument for the Opus default. The only
unavoidable paid element is the worker host the table already pays
for; Railway's hobby tier and Fly's small machines are the reference
points, named as posture, not dollars.

## Consent — unchanged — and retention

The consent gate does not move: it lives in the sink, structurally
upstream of every writer and uploader, so unconsented audio never
reaches an encoder, a disk, or a socket. React to be captured;
un-react and capture stops from that moment; fail-closed means the
un-reacted are simply absent from the tracks. The cloud path changes
where consented bytes land, not what is consented to — and the
consent post's privacy link (`PRIVACY_URL`, the Eddic site posture
page) should say recordings are stored in the campaign's own private
bucket, retained N days, then deleted.

Retention is an owner decision point because it is a promise made to
the table, not a tuning knob. Default: an R2 lifecycle rule deletes
objects under `sessions/raw/` after **60 days**, plus the 7-day
abort-incomplete rule. Rationale: raw audio is an intermediate — the
transcript and wiki are the durable artifacts — and 60 days
comfortably covers "transcription is a deliberate maintenance step"
without making the bucket a shadow archive nobody consented to.
Set once at bucket setup (dashboard or S3
`PutBucketLifecycleConfiguration`); the platform is the janitor, not
a cron. Consent-to-record ≠ consent-to-sell holds with no new
machinery: session audio is multi-author by nature, transactability
already defaults `local-only`, and raw tracks never enter any corpus
or projection — the sale fence never sees them.

## Decision points

- **Sink destination.** Default: local disk when the bot runs
  locally (baseline build); R2 when the bot runs cloud mode. The
  capability reads one config switch; everything upstream of the
  track writers is identical.
- **Host.** Default: wherever the lore bot already runs (Railway in
  its pattern). Mandatory voice-connectivity spike before first real
  session; Fly.io is the tested-in-community fallback if Railway's
  voice UDP path misbehaves.
- **Bucket.** Default: one private bucket per campaign
  (`<campaign>-sessions`), no public access, no custom domain.
- **Upload strategy.** Default: streaming multipart, 5 MiB uniform
  parts, startup recovery sweep. Escape hatch: rolling segment
  objects for a time-bounded loss window, accepting a stitch step at
  pull time.
- **Audio format.** Default: Ogg/Opus passthrough (no transcode, no
  fidelity loss beyond what Discord already imposed). Option: FLAC
  via pyflac for tool-compatibility maximalists, with the storage
  arithmetic made explicit.
- **Retention.** Default: 60-day lifecycle deletion on
  `sessions/raw/` + 7-day incomplete-upload abort. Options: shorter
  ("delete after pull" discipline), or owner-archival (no deletion
  rule — the owner accepts the bucket as an archive and says so to
  the table).
- **Fetch.** Default: `eddic sessions pull` with the reader token.
  Alternatives: rclone for rclone households; presigned URLs only
  for one-off credential-less handoff.
- **Consent mode.** Unchanged from the brief: strict per-session
  reacts (default) vs standing acks with visible opt-out. The cloud
  path takes no position; the gate is the same code.

## Open questions

- **Railway voice UDP, live.** Officially supported outbound, one
  unresolved contrary field report (2026-03). The recorder brief
  already defers the build to live testing; the cloud spike must be
  part of it, on the actual host, before the pattern claims Railway.
- **Wall-clock alignment of per-speaker tracks.** Discord sends no
  packets during silence, so naively written tracks compress time and
  per-speaker timestamps drift — a problem the local WAV draft
  shares. If the transcriber's merge needs aligned timelines, the
  writers should fill gaps (silence frames in FLAC; granule-position
  jumps in Ogg-Opus, which represent gaps natively) using RTP
  timestamps from the raw packet. Needs a decision with the
  transcriber module at the table.
- **Ogg muxer choice.** PyOgg (shared-lib dependency, thin
  maintenance) vs a vendored minimal Ogg-Opus muxer vs ffmpeg
  subprocess. Spike decides; the vendored muxer best fits the
  installation-friction principle if it stays genuinely small.
- **Session manifest contents.** Does `session.json` carry the
  consent roster (display names, as the filenames already do), or
  filenames only? Display names are Discord-surface data the table
  already sees, but writing them into a stored object deserves a
  deliberate yes/no against the roster doctrine.
- **Mid-session redeploys.** Worker hosts restart processes on
  deploy; the recovery sweep handles the data, but the bot should
  probably refuse `/record start` during a deploy window or at least
  re-announce that the previous session closed uncleanly. UX call,
  decide at build.
- **Uniform-part-size conformance.** Verified as an R2 documented
  requirement; confirm boto3's low-level path against it in the
  spike (the transfer manager's variable part sizing is exactly what
  to avoid).
