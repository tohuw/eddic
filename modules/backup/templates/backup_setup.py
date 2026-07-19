# /// script
# requires-python = ">=3.9"
# ///
"""Guided one-time setup of the rclone remote for Eddic tier-2 backup.

Reads `rclone_remote`, `bucket`, and `endpoint` from `.eddic/backup.json`,
prompts for the object store's Access Key ID and Secret Access Key, and
runs `rclone config create` so the credentials land only in rclone's own
config — never in the repo, a URL, or a chat transcript. The owner runs one
command and answers a hidden prompt; no hand-editing of config files.

    uv run .eddic/lib/backup/backup_setup.py [--root <repo>]

The Access Key ID and Secret Access Key come from the provider console
(for Cloudflare R2: R2 -> Manage R2 API Tokens -> Create, Object Read &
Write scoped to the bucket). The secret is read with no echo on a TTY and
as a piped line otherwise, and is never printed, logged, or echoed back.

Exit codes: 0 remote created, 1 setup could not complete (rclone missing,
config not filled in, or rclone errored), 2 usage / no backup.json."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def read_secret(prompt):
    """One credential from the operator. Interactive: hidden entry via
    getpass. Non-interactive (piped stdin): read a line. getpass on
    Windows reads the console directly and ignores a pipe — so a scripted
    setup would hang forever waiting on a console that isn't there; the
    isatty gate makes setup scriptable and cross-platform. Copied from the
    cli module's secrets_fill pattern so this module stays self-contained."""
    import getpass
    if sys.stdin is not None and sys.stdin.isatty():
        return getpass.getpass(prompt)
    line = sys.stdin.readline()
    if not line:                       # EOF: nothing piped -> empty
        return ""
    return line.rstrip("\n")


def find_root(start):
    for d in [start, *start.parents]:
        if (d / ".eddic" / "backup.json").is_file():
            return d
    return None


def resolve_root(arg):
    if arg:
        root = Path(arg).resolve()
        return root if (root / ".eddic" / "backup.json").is_file() else None
    return find_root(Path.cwd().resolve())


def build_rclone_argv(cfg, access_key_id, secret_access_key):
    """Pure: the exact `rclone config create` argv for this config and
    credentials. No I/O, no rclone, no network — golden-tested in
    verify/run.py. `provider Cloudflare` is R2's rclone provider name; any
    S3/B2 remote overrides it via backup.json's own provider if adapted."""
    return [
        "rclone", "config", "create",
        cfg["rclone_remote"], "s3",
        "provider", "Cloudflare",
        "endpoint", cfg["endpoint"],
        "access_key_id", access_key_id,
        "secret_access_key", secret_access_key,
        "acl", "private",
    ]


def main():
    ap = argparse.ArgumentParser(description="Guided rclone remote setup "
                                 "for Eddic tier-2 backup.")
    ap.add_argument("--root", default=None,
                    help="repo root (default: discover via .eddic/backup.json)")
    args = ap.parse_args()

    root = resolve_root(args.root)
    if root is None:
        print("backup: no .eddic/backup.json found — apply the backup "
              "pattern first, then re-run this setup.", file=sys.stderr)
        return 2

    cfg = json.loads(
        (root / ".eddic" / "backup.json").read_text(encoding="utf-8"))
    remote = cfg.get("rclone_remote")
    endpoint = cfg.get("endpoint")
    bucket = cfg.get("bucket")

    if not remote or not endpoint or "{{" in endpoint:
        print("backup: fill rclone_remote, bucket, and endpoint in "
              ".eddic/backup.json before running setup (endpoint still "
              "looks like a placeholder).", file=sys.stderr)
        return 1

    if shutil.which("rclone") is None:
        print("backup: rclone is not installed. Install it, then re-run "
              "this setup:\n"
              "  macOS:   brew install rclone\n"
              "  Windows: winget install Rclone.Rclone\n"
              "  Linux:   your distro's package, or rclone.org/install",
              file=sys.stderr)
        return 1

    print(f"Creating rclone remote '{remote}' for {bucket} at {endpoint}.")
    print("Paste the credentials from your provider's API-token console "
          "(R2: Manage R2 API Tokens -> Create, Object Read & Write).")
    access_key_id = read_secret("Access Key ID: ").strip()
    secret_access_key = read_secret("Secret Access Key (hidden): ").strip()
    if not access_key_id or not secret_access_key:
        print("backup: no credentials entered — nothing created.",
              file=sys.stderr)
        return 1

    argv = build_rclone_argv(cfg, access_key_id, secret_access_key)
    # Capture output so the secret rclone echoes back into its config dump
    # never reaches the terminal or a log; report only our own redacted line.
    try:
        r = subprocess.run(argv, capture_output=True, text=True)
    except OSError as e:
        print(f"backup: could not run rclone ({e}).", file=sys.stderr)
        return 1
    if r.returncode != 0:
        print(f"backup: rclone config create failed (rc {r.returncode}). "
              f"Check the endpoint and that the key has Object Read & Write "
              f"on {bucket}.", file=sys.stderr)
        return 1

    print(f"backup: rclone remote '{remote}' created (Access Key ID "
          f"{access_key_id[:4]}…, secret stored in rclone config, not "
          f"echoed). Your next push backs up the blob dirs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
