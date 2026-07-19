# Blob backup (tier-2 -> object storage)

Large binary assets — session audio, and anything else too big and binary
for git — live in a `blob_dirs` (default `sessions/raw/`), are
**gitignored**, and sync to object storage instead. The repo tracks only an
inventory (`.eddic/assets.json`: each blob's path, size, and sha256) so it
knows what exists and can verify integrity without ever storing the bytes.

Two git hooks (enabled with `git config core.hooksPath .githooks`) make it
hands-off:

- **pre-commit** refreshes `.eddic/assets.json` and stages it.
- **pre-push** `rclone sync`s the blob dirs to the object store. If rclone
  or the remote isn't set up, it warns and lets the push through — a
  text-only push is never blocked.

## One-time setup (then it's automatic)

Default provider is **Cloudflare R2** (free tier, zero egress). Any
S3-compatible store — Backblaze B2, AWS S3, MinIO — works the same way via
rclone; only the remote's `provider`/`endpoint` differ.

1. Install rclone: `rclone.org/install` (`brew install rclone` on macOS;
   `winget install Rclone.Rclone` on Windows; distro packages on Linux).
2. Create a private bucket in the provider's console. For R2:
   **R2 -> Create bucket** (name it, e.g. `warden-sunken-city`), then
   **R2 -> Manage R2 API Tokens -> Create** with **Object Read & Write**
   scoped to that bucket. Copy the Access Key ID and Secret Access Key.
   Note your account's S3 endpoint (`https://<account_id>.r2.cloudflarestorage.com`).
3. Create the rclone remote (name it to match `rclone_remote` in
   `.eddic/backup.json` — `r2` by default):

   ```
   rclone config create r2 s3 \
     provider=Cloudflare \
     endpoint=https://<ACCOUNT_ID>.r2.cloudflarestorage.com \
     access_key_id=<ACCESS_KEY_ID> \
     secret_access_key=<SECRET_ACCESS_KEY> \
     acl=private
   ```

4. Fill `bucket` and `endpoint` in `.eddic/backup.json`.

That's it — `git push` now backs up the blob dirs. The first push does the
initial upload.

Credentials live only in rclone's own config, never in the repo, a URL, or
a chat transcript. If a key is ever exposed, revoke it in the provider
console, mint a fresh one, and re-run the `rclone config create` above.

## On a fresh clone

Hooks aren't set automatically (git security). Once per clone:
`git config core.hooksPath .githooks`

## Restore blobs

`rclone sync r2:<bucket>/sessions/raw sessions/raw` (swap in each
`blob_dir`). Verify against the tracked inventory: the sha256 in
`.eddic/assets.json` must match the restored bytes.
