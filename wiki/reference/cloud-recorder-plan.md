# Cloud recorder plan

A planning note dated 2026-07-18: how the [recorder](../modules/recorder.md) capability (module 9) should behave when the campaign bot runs in [lore-bot](../modules/lore-bot.md) cloud mode, with recordings landing in Cloudflare R2 instead of the campaign's local disk. Session recording sinks from the worker host into R2.

The local-disk path stays the baseline-build default; this plan is an *upgrade* for tables whose bot already lives on a worker host because no machine is reliably awake during play. Web-verified claims below are dated 2026-07; the recorder brief itself — one bot, consent enforced in the sink, per-speaker tracks, the transcriber's on-disk layout, and consent-to-record kept distinct from consent-to-sell — is unchanged from ROADMAP.

## Architecture sketch

The worker host runs the [lore-bot](../modules/lore-bot.md) cloud-mode process (Railway or Fly.io), and `bot.py` gains the recorder capability. The flow from Discord's voice gateway down to the DM's machine:

```
worker host (Railway / Fly.io — lore-bot cloud-mode process)
  bot.py + recorder capability
  Discord voice gateway ──> voice_recv reader/decoder threads
    │ (WSS to *.discord.media + outbound UDP 50000–65535)
    v
  ConsentSink.write() — consent gate, unchanged, per-user
    │ (only consented users' frames pass; runs on
    │  extension's decoder thread, never the event loop)
    v
  per-user TrackWriter — Ogg/Opus (default) or FLAC encoder
    │ bounded queue, spills to ephemeral disk on stall
    v
  uploader thread — S3 multipart, 5 MiB uniform parts
    │ boto3 low-level API, bucket-scoped write token
    v
  R2 bucket  sessions/raw/<date>/N-name.ogg (+ session.json manifest)
    │ lifecycle rules: delete after retention window,
    │  abort incomplete multipart after 7 days
    v
  DM's local machine
  `eddic sessions pull` (reader token) ──> <campaign>/sessions/raw/<date>/…
    writes the witness log entry locally; the transcriber
    runs as a deliberate maintenance step, already
```

Nothing in this design gains an inbound port. The bot stays outbound-only: WSS to `*.discord.media` plus outbound UDP on 50000–65535.

Verified 2026-07: an unresolved Railway help thread (March 2026) reports Discord voice UDP failing to reach ready state there, so the host choice carries a **mandatory preflight spike** — join a voice channel with the deployed bot and confirm `VoiceRecvClient` reaches ready before any table depends on it. Fly.io is the named fallback: outbound UDP works, and community Discord music bots run there without a dedicated IPv4 (Fly's strict `fly-global-services` binding rules apply only to *inbound* UDP services).

Bucket keys mirror the campaign layout exactly: the object key `sessions/raw/<date>/N-name.ogg` equals the repo-relative path the [transcriber](../modules/transcriber.md) already expects, so the pull verb is a straight prefix download with no mapping table. A small `session.json` per date records the track list, byte counts, and sink stats — this is what lets the pull verb write an honest witness log entry, since the cloud host cannot append `wiki/log.md` (the campaign repo is a read-only tarball in cloud mode; the log write moves to pull time). Provenance doctrine wants it there too: a field write is reconciled on the DM's machine, not hot-edited from a remote host.

## Upload strategy: streaming multipart, not upload-on-stop

Upload-on-stop is disqualified by its failure mode. Worker-host disks are ephemeral, so a host that crashes or is redeployed mid-session loses the entire recording — four hours of the table's one weekly night, gone. Unacceptable regardless of its simplicity.

Recommended: an S3-compatible multipart upload per speaker track, streamed during the session. R2's specifics shape it (verified 2026-07 against Cloudflare docs):

- One multipart upload per track, created on the first consented frame. Parts flush at exactly 5 MiB — R2 requires **uniform part sizes** (except the final part), a quirk AWS does not share, so use low-level boto3 multipart calls with a fixed 5 MiB threshold. Parts are durable server-side immediately. After a crash, `ListMultipartUploads` plus `ListParts` recover the upload ID and part ETags, so a deterministic **recovery sweep** — run at bot startup, and available as an `eddic` verb — can `CompleteMultipartUpload` on anything left open under `sessions/raw/`. Everything already uploaded survives; recovery is idempotent and free (or, if the owner prefers to discard a fragment, abort deletes all parts at no charge).
- Loss bound: only the not-yet-flushed tail buffer, under 5 MiB per track. At Opus rates that is roughly ten minutes of *speech* per speaker (wall-clock is longer, since silence is not transmitted). A table that wants a tighter time bound has the escape hatch of rolling segment objects (close and PUT a fresh object every N minutes: time-bounded loss, no multipart state, at the cost of a stitch step at pull time) — but the multipart default yields exactly one seamless file per track in the transcriber's layout, with no stitching.
- Incomplete uploads auto-abort after 7 days by default; keep that rule so a session nobody recovers cannot silently accrue storage.

Backpressure: the uploader consumes a bounded queue. If R2 stalls, spill to the host's ephemeral disk rather than grow memory or drop frames — frames dropped in the upload plumbing would be a silent hole in a consented recording. The sink's stats discipline extends to the uploader: parts written, parts pending, spill depth, all reported on `/record stop`.

## Audio format: Opus passthrough by default

Raw decoded PCM-WAV (48 kHz, 16-bit stereo) runs about 11.25 MiB per minute per speaker — a four-hour, six-speaker session brushes 16 GB, past the entire R2 free tier in one night. WAV is out for cloud.

The decisive fact: the audio *arrives* Opus-encoded. Discord delivers roughly 64 kbps Opus per speaker; the only PCM in the pipeline is what the decoder produces. Re-encoding that PCM to FLAC costs roughly 10× the size for no gained fidelity — it would be lossless-of-lossy. So the cloud default is passthrough: `wants_opus() = True`, writing `data.opus` packets into an Ogg container (`.ogg`, RFC 7845 Ogg-Opus). That is about 0.5 MB per minute of speech per speaker; a realistic session lands around 250–500 MB total. No transcode CPU on the host — the encoder is Discord's. The transcriber already accepts ogg/opus, so nothing downstream changes.

Containering options, in preference order: PyOgg's `OggOpusWriter` (handles paging and pre-skip, but needs libogg/libopus shared libs on the host, which the project's maintenance thin prefers to avoid); a vendored minimal Ogg-Opus muxer (the encapsulation is small and deterministic — attractive under the no-bash, runs-anywhere rule); or an ffmpeg subprocess (heaviest, but nixpacks/apt can provide it). Decide at implementation, against a live spike.

FLAC stays available as an archival option for owners who want maximum tool compatibility and don't mind about 5.5 MB/min/speaker: pyflac's `StreamEncoder` is a real-time streaming encoder (16-bit in, bytes out via callback — it feeds the part buffer directly), proven for exactly this capture-thread pattern. It is a storage/compatibility choice, not a fidelity one, and the pattern should say so plainly.

## Fetching: a small eddic verb, not a new tool

The transcriber runs on the DM's local machine; sessions must come down before it runs. Recommended: `eddic sessions pull` — uv-run Python over boto3 (PEP 723) that reads the reader token from the campaign's `variables.txt`/env, lists `sessions/raw/` prefixes newer than what exists locally, downloads them into the campaign tree, writes a witness log entry from `session.json`, and (optionally, off by default) deletes the pulled objects. This fits principle 3 (the DM's machine is where field writes reconcile) and stays a small CLI verb inside the existing [cli](../modules/cli.md), not a new tool.

boto3 v1.59+ can also emit object-scoped presigned URLs (GET, 7-day max, SigV4) for the one-off case of handing a single track to someone without credentials. Egress is free either way.

## Credentials, per data-controls doctrine

Two bucket-scoped R2 API tokens, mirroring the [retrieval](../modules/retrieval.md) module's two-token shape:

- **Writer** — Object Read & Write, scoped to the one sessions bucket, held only in worker-host env vars. The S3 credential pair is: access key ID = token ID, secret = SHA-256 of the token value, endpoint `https://<account_id>.r2.cloudflarestorage.com`.
- **Reader** — Object Read only, same single-bucket scope, held in the campaign's gitignored `variables.txt` on the DM's machine for the pull verb.

Mint them in the Cloudflare dashboard (R2 → API Tokens → Object Read & Write → scope to bucket) or via the Cloudflare API. **Wrangler cannot mint R2 S3 credentials** (verified 2026-07 — wrangler manages buckets and objects, not token issuance), so the pattern's preflight walks the dashboard flow the way the lore-bot pattern walks the Discord portal: the agent drives the browser and reads the secret straight into env/config, never into chat. Standard doctrine applies unchanged: tokens never in repos, URLs, or transcripts; fingerprints (first 8) for later reference; exposure means rotation — revoke in the dashboard, re-mint, update the two homes, seconds of work. The writer token can write and read audio but nothing else in the account; the blast radius of a leak is one bucket of consented session audio, and rotation plus the retention window bounds it in time too.

## Cost posture

Free path first (principle 4): the baseline build records to local disk and the local-mode bot touches no cloud storage — this whole document is an *upgrade*, and its stated reason is "the bot already runs on a worker host because no machine is awake during play." The upgrade adds **no new host cost** (same process, same dyno), with room to spare: R2's free tier is 10 GB-month storage, 1M Class A operations, and 10M Class B per month, with zero egress. Four sessions a month at about 500 MB with a 60-day retention window sits around 2–4 GB-months; Class A usage (parts plus manifests, a few hundred per session) is noise against 1M; pulls as Class B are noise. FLAC-format tables should run the arithmetic in the pattern's verify step — several GB per session makes the free tier a real ceiling, which is itself an argument for the Opus default. The only unavoidable paid element is the worker host the table already pays for; Railway's hobby tier and Fly's small machines are the reference points, a named posture rather than a dollar figure.

## Consent — unchanged — and retention

The consent gate does not move: it lives in the sink, structurally upstream of every writer and uploader, so unconsented audio never reaches an encoder, a disk, or a socket. React to be captured; un-react and capture stops that moment; fail-closed means the un-reacted are simply absent from the tracks. The cloud path changes where consented bytes land, not what was consented to — the consent post's privacy link (`PRIVACY_URL`, the Eddic site posture page) should say that recordings are stored in the campaign's own private bucket, retained N days, then deleted.

Retention is an owner decision point because it is a promise made to the table, not a tuning knob. Default: an R2 lifecycle rule deletes objects under `sessions/raw/` after **60 days**, plus the 7-day abort-incomplete rule. Rationale: raw audio is an intermediate — the transcript and wiki are the durable artifacts — and 60 days comfortably covers "transcription is a deliberate maintenance step" without letting the bucket become a shadow archive nobody consented to. Set once at bucket setup (dashboard or the S3 `PutBucketLifecycleConfiguration` call); it is a platform janitor, not a cron job. Consent-to-record stays distinct from consent-to-sell: given the multi-author nature and transactability, transactability already defaults to `local-only`, raw tracks never enter any corpus projection, and the sale fence never sees them.

## Decision points

- **Sink destination.** Default: local disk when the bot runs locally (baseline build); R2 when the bot runs in cloud mode. The capability reads one config switch; everything upstream of the track writers is identical.
- **Host.** Default: wherever the lore bot already runs (Railway in its pattern). A mandatory voice-connectivity spike precedes the first real session; Fly.io is the tested-in-community fallback if Railway's voice UDP path misbehaves.
- **Bucket.** Default: one private bucket per campaign (`<campaign>-sessions`), no public access, no custom domain.
- **Upload strategy.** Default: streaming multipart, 5 MiB uniform parts, startup recovery sweep. Escape hatch: rolling segment objects for a time-bounded loss window, accepting a stitch step at pull time.
- **Audio format.** Default: Ogg/Opus passthrough (no transcode, no fidelity loss beyond what Discord already imposed). Option: FLAC via pyflac for tool-compatibility maximalists, with the storage arithmetic made explicit.
- **Retention.** Default: 60-day lifecycle deletion on `sessions/raw/` plus 7-day incomplete-upload abort. Options: shorter ("delete on pull" discipline), or owner-archival (no deletion rule — the owner accepts a bucket archive and says so to the table).
- **Fetch.** Default: `eddic sessions pull` with the reader token. Alternatives: rclone for rclone households; presigned URLs only for a one-off credential-less handoff.
- **Consent mode.** Unchanged from the brief: strict per-session reacts (default) vs standing acks with a visible opt-out. The cloud path takes no position; the gate is the same code.

## Open questions

- **Railway voice UDP, live.** Officially supported as outbound, but an unresolved help thread (2026-03) reports it failing to reach ready. Resolved only by the preflight spike on a deployed bot.
- **Wall-clock alignment.** Per-speaker Opus omits packets during silence, so naively written tracks compress time and per-speaker timestamps drift — a problem the local WAV draft shares. If the transcriber's merge needs aligned timelines, the writers should fill gaps (silence frames in FLAC; granule-position jumps in Ogg-Opus, which represents gaps natively) using the RTP timestamps on the raw packet. Needs a decision at the transcriber-module table.
- **Ogg muxer choice.** PyOgg (shared-lib dependency, thin maintenance) vs a vendored minimal Ogg-Opus muxer vs an ffmpeg subprocess. The spike decides; the vendored muxer best fits the installation-friction principle if it stays genuinely small.
- **Session manifest contents.** Does `session.json` carry the consent roster (display names, which the filenames already encode), or filenames only? Display names are Discord-surface data the table already sees, but writing them into a stored object deserves a deliberate yes/no against roster doctrine.
- **Mid-session redeploys.** Worker hosts restart processes on deploy; the recovery sweep handles the data, but the bot should probably refuse `/record start` during a deploy window, or at least re-announce that the previous session closed uncleanly. A UX call, to decide at build.
- **Uniform-part-size conformance.** R2's documented requirement is verified; confirm boto3's low-level path against it in the spike (the transfer manager's variable part sizing is exactly what to avoid).

---

This plan extends the [recorder](../modules/recorder.md) module into the [lore-bot](../modules/lore-bot.md)'s cloud host, staging into the [transcriber](../modules/transcriber.md)'s layout and pulled down through the [cli](../modules/cli.md). Its consent and credential doctrine follow [the firewall](../concepts/the-firewall.md) and the two-token shape of [retrieval](../modules/retrieval.md), and its free-path-first and reconcile-on-the-DM's-machine posture rest on the [design principles](../design/principles.md). It is the cloud future the [roadmap](../roadmap.md) reserved for the recorder.
