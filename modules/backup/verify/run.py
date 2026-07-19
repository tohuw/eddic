# /// script
# requires-python = ">=3.9"
# ///
"""Golden tests for the backup module's deterministic core — offline,
dep-free, no network:

  - assets.py inventories a blob dir into .eddic/assets.json with the right
    repo-relative path, byte count, and sha256, carries the bucket through,
    and ignores OS cruft (.DS_Store);
  - backup_sync.py is a safe no-op that warns-and-continues when rclone is
    absent (a text push must never block) and when the repo isn't
    backup-configured;
  - backup_sync.py --dry-run composes the correct rclone sync command
    (remote:bucket/dir, excluding .DS_Store) from config, no rclone and no
    network needed;
  - backup_setup.py's pure build_rclone_argv composes the correct
    `rclone config create` argv from a sample config and sample keys, no
    rclone, no network, no prompt.

Exit 0 on success, nonzero on any failure."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
ASSETS = MOD / "scripts" / "assets.py"
SYNC = MOD / "scripts" / "backup_sync.py"
SETUP = MOD / "templates" / "backup_setup.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(script, *args, env=None):
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, env=env)


def make_campaign(root, bucket="warden-sunken-city",
                  blob_dirs=("sessions/raw",)):
    (root / ".eddic").mkdir(parents=True, exist_ok=True)
    (root / ".eddic" / "backup.json").write_text(json.dumps({
        "provider": "cloudflare-r2",
        "rclone_remote": "r2",
        "bucket": bucket,
        "endpoint": "https://EXAMPLE.r2.cloudflarestorage.com",
        "blob_dirs": list(blob_dirs),
    }), encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-backup-verify-"))
    checks = []

    # --- assets.py: manifest generation golden ---
    make_campaign(tmp)
    blobdir = tmp / "sessions" / "raw" / "2026-01-01"
    blobdir.mkdir(parents=True)
    audio = b"fake-opus-bytes-" * 1000
    (blobdir / "1-warden.ogg").write_bytes(audio)
    (blobdir / ".DS_Store").write_bytes(b"macos cruft")  # must be ignored

    p = run(ASSETS, "--root", str(tmp))
    checks.append((p.returncode == 0,
                   f"assets exits 0 ({p.stderr.strip()[:120]})"))
    manifest = json.loads((tmp / ".eddic" / "assets.json").read_text())
    blobs = manifest.get("blobs", [])
    checks.append((len(blobs) == 1, f"exactly one blob inventoried "
                                    f"(got {len(blobs)})"))
    if blobs:
        b = blobs[0]
        checks.append((b.get("path") == "sessions/raw/2026-01-01/1-warden.ogg",
                       f"repo-relative posix path recorded "
                       f"(got {b.get('path')})"))
        checks.append((b.get("bytes") == len(audio),
                       f"byte count recorded (got {b.get('bytes')})"))
        checks.append((b.get("sha256") == hashlib.sha256(audio).hexdigest(),
                       "sha256 recorded and correct"))
    checks.append((manifest.get("bucket") == "warden-sunken-city",
                   "bucket carried into the inventory"))
    checks.append((all(".DS_Store" not in bb.get("path", "") for bb in blobs),
                   ".DS_Store ignored"))

    # --- backup_sync.py: safe no-op when rclone is absent ---
    empty = tmp / "empty-path"
    empty.mkdir()
    env = {**os.environ, "PATH": str(empty)}  # rclone unreachable on PATH
    p = run(SYNC, "--root", str(tmp), env=env)
    checks.append((p.returncode == 0,
                   f"sync exits 0 with rclone absent (got {p.returncode})"))
    checks.append(("rclone not installed" in p.stderr,
                   "sync warns that rclone is absent"))
    checks.append((not any("->" in ln for ln in p.stderr.splitlines()),
                   "no rclone sync attempted when rclone is absent"))

    # --- backup_sync.py: no-op in a non-backup-configured repo ---
    bare = Path(tempfile.mkdtemp(prefix="eddic-backup-bare-"))
    p = run(SYNC, "--root", str(bare))
    checks.append((p.returncode == 0,
                   f"sync no-ops on a non-backup repo (got {p.returncode})"))

    # --- backup_sync.py --dry-run: command composition, no rclone/network ---
    p = run(SYNC, "--root", str(tmp), "--dry-run")
    checks.append((p.returncode == 0, f"dry-run exits 0 (got {p.returncode})"))
    checks.append(("r2:warden-sunken-city/sessions/raw" in p.stdout,
                   f"dry-run composes remote:bucket/dir "
                   f"(got {p.stdout.strip()[:160]})"))
    checks.append(("rclone sync" in p.stdout,
                   "dry-run emits an rclone sync command"))
    checks.append(("--exclude .DS_Store" in p.stdout,
                   f"dry-run excludes .DS_Store from the sync "
                   f"(got {p.stdout.strip()[:160]})"))

    # --- backup_setup.py: build_rclone_argv golden (pure, no rclone) ---
    setup = load_module(SETUP, "backup_setup")
    sample_cfg = {
        "provider": "cloudflare-r2",
        "rclone_remote": "r2",
        "bucket": "warden-sunken-city",
        "endpoint": "https://ACCT.r2.cloudflarestorage.com",
        "blob_dirs": ["sessions/raw"],
    }
    argv = setup.build_rclone_argv(sample_cfg, "AKIDEXAMPLE", "s3cr3t-key")
    expected = [
        "rclone", "config", "create", "r2", "s3",
        "provider", "Cloudflare",
        "endpoint", "https://ACCT.r2.cloudflarestorage.com",
        "access_key_id", "AKIDEXAMPLE",
        "secret_access_key", "s3cr3t-key",
        "acl", "private",
    ]
    checks.append((argv == expected,
                   f"build_rclone_argv composes the correct config-create "
                   f"argv (got {argv})"))

    failed = [m for ok, m in checks if not ok]
    for ok, m in checks:
        print(("ok  " if ok else "FAIL"), m)
    if failed:
        return 1
    print("verify ok: backup module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
