# backup

The backup module gives a campaign a second data tier. Tier-1 is text —
the [wiki](wiki.md), the manifest, the operation log — and it lives in git,
versioned and diffable. Tier-2 is the large binary assets that would wreck
a text repo if committed: session audio above all, plus map exports and
handout PDFs. Those live in object storage while git tracks only an
inventory, so the repo always knows what exists and can prove integrity
without ever carrying the bytes. The module depends on [cli](cli.md) and is
the natural downstream home for the audio that [capture](capture.md) and
the [recorder](recorder.md) land in `sessions/raw/`.

## The two tiers and the inventory

The bytes never enter git history; the blob directories are gitignored and
the only tracked artifact is `.eddic/assets.json`, an inventory recording
each blob's repo-relative path, byte count, and sha256. That inventory is
what makes the split safe: a fresh clone knows the full set of assets and
can verify every restored file against its recorded hash, even though the
clone carries none of the audio. Text stays diffable in git; blobs stay out
of it; the inventory is the bridge that keeps the two consistent.

## Hands-off by two hooks over one worker

The automation is a pre-commit hook and a pre-push hook, both thin POSIX-sh
shims that locate the repo root and exec a single cross-platform Python
worker vendored into `.eddic/lib/backup/`. Pre-commit refreshes the
inventory so a commit always records the current asset set; pre-push
rclone-syncs the blob directories to the bucket. Git ships the `sh` that
runs the shims on macOS, Windows, and Linux alike, and all real logic lives
in the worker, so nothing platform-specific hides in the hooks. The
inventory and the `.githooks/` plus `.eddic/backup.json` config are
committed so every clone inherits the setup — a fresh clone only re-runs the
one `core.hooksPath` command the template's note names, since git will not
set that automatically.

## The hard rule: tier-2 never blocks tier-1

A tier-2 concern — a missing sync tool, an unreachable bucket, absent
credentials — must never block a tier-1 push. The worker guarantees this by
warning and continuing on any tier-2 failure rather than failing the hook,
and the module's verifier proves it: the sync path is a safe no-op that
warns when rclone is absent, when the repo is not backup-configured, and on
placeholder config, so setup can proceed before rclone or the bucket even
exist. Restore is the inverse of sync — `rclone sync <remote>:<bucket>/<dir>
<dir>` — checked against the tracked sha256s.

## Provider posture

The default object store is Cloudflare R2, whose free tier (10 GB-month,
zero egress) swallows a table's session-audio archive and whose
S3-compatible API rclone speaks natively; any S3/B2 remote (Backblaze B2,
AWS S3, self-hosted MinIO) is a drop-in by changing the provider, endpoint,
and rclone remote and nothing else. Credentials live only in rclone's own
config, never in the repo, a URL, or a chat transcript, following the same
token doctrine the [retrieval](retrieval.md) and [recorder](recorder.md)
patterns use — an exposed key is revoked and reminted, not patched.

## Verify

The module's verifier is offline and dependency-free. It confirms that the
inventory worker records a planted blob with the correct repo-relative posix
path, byte count, and sha256, carries the bucket through, and ignores OS
cruft like `.DS_Store`; that the sync worker is a safe no-op that warns and
continues when rclone is absent and when the repo is not configured; and
that a dry-run composes the correct `remote:bucket/dir` command from config
with no rclone and no network. The live check, after the one-time bucket
setup, is a full loop: drop a file into a blob dir, commit and confirm the
inventory gained the entry, push and watch the object appear in the bucket,
then rename rclone off `PATH` and push again to prove the text push still
completes.

See the [module index](index.md), the [module contract](../concepts/the-module-contract.md)
for how services and manifests fit together, and [data controls](../reference/data-controls.md)
for retention policy on the archived bytes.
