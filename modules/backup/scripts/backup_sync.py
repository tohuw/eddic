# /// script
# requires-python = ">=3.9"
# ///
"""Pre-push worker for the Eddic tier-2 backup: rclone-sync the configured
blob dirs to object storage (Cloudflare R2 by default, or any S3/B2 remote)
before a push. Warn-and-continue if rclone is missing, the remote isn't
configured, or a sync fails, so a push of tier-1 text is NEVER blocked.
Reads .eddic/backup.json. Cross-platform; shells out to rclone only, no
third-party Python deps.

Vendored into a campaign as .eddic/lib/backup/backup_sync.py and called by
the pre-push hook; `--dry-run` prints the rclone commands (no rclone, no
network needed) for inspection and CI."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


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


def warn(msg):
    print(f"eddic backup: {msg}", file=sys.stderr)


def rclone_has_remote(remote):
    """rclone listremotes prints one 'name:' per line."""
    try:
        out = subprocess.run(["rclone", "listremotes"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return f"{remote}:" in [ln.strip() for ln in out.stdout.splitlines()]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=None,
                    help="repo root (default: discover via .eddic/backup.json)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the rclone commands instead of running them")
    args = ap.parse_args()

    root = resolve_root(args.root)
    if root is None:
        return 0  # not a backup-configured repo: nothing to do, never block

    cfg = json.loads(
        (root / ".eddic" / "backup.json").read_text(encoding="utf-8"))
    remote = cfg.get("rclone_remote")
    bucket = cfg.get("bucket")
    blob_dirs = cfg.get("blob_dirs", [])

    if not remote or not bucket:
        warn("backup.json missing rclone_remote or bucket — sync skipped, "
             "push continues.")
        return 0

    if not args.dry_run:
        if shutil.which("rclone") is None:
            warn("rclone not installed — object-store sync skipped, push "
                 "continues. Install rclone (see the backup README), then "
                 "the next push backs up.")
            return 0
        if not rclone_has_remote(remote):
            warn(f"rclone remote '{remote}' not configured — sync skipped, "
                 f"push continues. See the backup README to create it.")
            return 0

    for d in blob_dirs:
        src = root / d
        if not src.is_dir():
            continue
        dst = f"{remote}:{bucket}/{d}"
        cmd = ["rclone", "sync", str(src), dst,
               "--transfers", "4", "--s3-no-check-bucket"]
        if args.dry_run:
            print(" ".join(cmd))
            continue
        warn(f"rclone sync {d} -> {dst}")
        try:
            r = subprocess.run(cmd)
        except (OSError, subprocess.SubprocessError) as e:
            warn(f"sync of {d} errored ({e}) — push continues.")
            continue
        if r.returncode != 0:
            warn(f"sync of {d} failed (rc {r.returncode}) — push continues; "
                 f"re-run by hand: rclone sync {src} {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
