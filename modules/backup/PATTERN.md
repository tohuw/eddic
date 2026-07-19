# Pattern: tier-2 blob backup

Gives the campaign a second data tier. Tier-1 is text — the wiki, the
manifest, the log — and it lives in git, versioned and diffable. Tier-2 is
the large binary assets that would wreck a text repo if committed: session
audio above all, plus map exports and handout PDFs. Those live in object
storage; git tracks only an **inventory** (`.eddic/assets.json`: each
blob's repo-relative path, byte count, and sha256), so the repo always
knows what exists and can prove integrity without ever carrying the bytes.
Two git hooks over one Python worker keep it hands-off, and the hard rule
throughout is that a tier-2 concern — a missing sync tool, an unreachable
bucket — must never block a tier-1 push.

## Preflight

- The repo is a git working tree with a push remote (the sync rides
  `git push`). `git rev-parse --show-toplevel` succeeds.
- The blob dirs exist or have a natural home (default `sessions/raw/`),
  and are gitignored — tier-2 means the bytes never enter git history. If
  audio is arriving via the capture pattern, its `sessions/raw/` layout is
  already the blob dir.
- rclone is installable on the owner's machine (`rclone.org/install`). Its
  absence must degrade to warn-and-continue, never a blocked push — the
  worker guarantees this and `verify/run.py` proves it, so setup can
  proceed before rclone or the bucket exist.
- An object-storage bucket the owner controls, or willingness to create
  one; `templates/README.md` walks the one-time remote setup.

## Procedure

1. Vendor the deterministic core and stamp the config:

       mkdir -p <campaign>/.eddic/lib/backup
       cp scripts/assets.py       <campaign>/.eddic/lib/backup/assets.py
       cp scripts/backup_sync.py  <campaign>/.eddic/lib/backup/backup_sync.py
       cp templates/backup.json   <campaign>/.eddic/backup.json
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module backup --version 0.1.0 \
           --verbs backup-inventory,backup-sync

   Fill `bucket`, `endpoint`, and `blob_dirs` in `.eddic/backup.json`
   (leave `bucket`/`endpoint` as placeholders until the object-store
   setup step if the account doesn't exist yet — the worker no-ops
   cleanly on placeholders).

2. Install the hooks and point git at them:

       mkdir -p <campaign>/.githooks
       cp templates/pre-commit <campaign>/.githooks/pre-commit
       cp templates/pre-push   <campaign>/.githooks/pre-push
       git -C <campaign> config core.hooksPath .githooks

   The hooks are thin POSIX-sh shims that locate the repo root and exec
   the vendored Python worker; git ships the `sh` that runs them on
   macOS, Windows, and Linux alike, and all real logic is in the
   cross-platform worker. `core.hooksPath` isn't set on a fresh clone (git
   security) — the README's "fresh clone" note tells a new cloner the one
   command to re-run.

3. Gitignore the blob dirs so the bytes never enter history; the only
   tracked artifact is `.eddic/assets.json`. Commit that inventory and the
   `.githooks/` + `.eddic/backup.json` config so every clone inherits the
   setup.

4. Walk the one-time object-store setup from `templates/README.md`: create
   the private bucket, mint a bucket-scoped read-write token, and
   `rclone config create` the remote whose name matches `rclone_remote`.
   Credentials live only in rclone's own config — never in the repo, a
   URL, or a chat transcript; an exposed key is revoked-and-reminted, not
   patched. On exposure, follow the same doctrine the retrieval and
   recorder patterns use for their tokens.

5. Confirm the loop end to end (see Verify), then hand off. The first
   push does the initial upload; thereafter every commit refreshes the
   inventory and every push syncs the blobs, with no folder navigation and
   nothing for the owner to remember. Restore is `rclone sync
   <remote>:<bucket>/<dir> <dir>`, checked against the tracked sha256s.

## Decision points

- **Object-storage provider.** Default: **Cloudflare R2** — free tier
  (10 GB-month, zero egress) that swallows a table's audio archive, and an
  S3-compatible API rclone speaks natively. Alternatives: any S3/B2 store
  (Backblaze B2, AWS S3, self-hosted MinIO) is a drop-in — set `provider`,
  `endpoint`, and the rclone remote to match; nothing else in the pattern
  changes. Pick by where the owner already has an account or the cheapest
  egress terms; R2's free egress is the tie-breaker for a media archive.
- **Which dirs are blobs.** Default: `["sessions/raw"]` — session audio is
  the canonical tier-2 asset and the capture pattern already lands it
  there. Add a dir when a class of assets is large, binary, and
  regenerable-or-archival rather than authored (map exports, scanned
  handouts, rendered video). Keep authored text out: anything you'd want to
  diff or that a projection reads belongs in tier-1 git, not here.
- **Hooks vs. manual.** Default: **hooks** — the whole point is that
  backup happens without anyone remembering, and pre-push warn-and-continue
  means the automation can never cost a blocked push. Choose manual (skip
  `core.hooksPath`, run `uv run .eddic/lib/backup/assets.py` and `rclone
  sync` by hand, or fold both into a routine) only when the owner objects
  to repo-installed hooks or runs backup from a scheduler instead of at
  push time; the same worker serves both, so the choice is only *when* it
  runs.

## Verify

- `uv run modules/backup/verify/run.py` — golden tests, offline and
  dep-free: `assets.py` inventories a planted blob into `.eddic/assets.json`
  with the correct repo-relative path, byte count, and sha256, carries the
  bucket through, and ignores OS cruft (`.DS_Store`); `backup_sync.py` is a
  safe no-op that warns-and-continues when rclone is absent (the text-push
  guarantee) and when the repo isn't backup-configured; and
  `backup_sync.py --dry-run` composes the correct `remote:bucket/dir` sync
  command from config with no rclone and no network.
- Live, after the object-store setup: drop a small file into a blob dir,
  `git commit`, and confirm `.eddic/assets.json` gained the entry (path,
  size, sha256) and was staged. Then `git push` and watch the pre-push
  hook report `rclone sync ... -> <remote>:<bucket>/...`; confirm the
  object appears in the bucket. Finally, prove the guarantee that matters:
  temporarily rename rclone off `PATH` and push — the hook warns that sync
  was skipped and the push still completes.
