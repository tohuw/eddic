# /// script
# requires-python = ">=3.9"
# ///
"""Regenerate .eddic/assets.json — the tracked inventory of tier-2 blobs
(large binary assets: session audio, map exports, handout PDFs) that live
in object storage, not git. Records each blob's repo-relative path, size,
and sha256 so the repo knows what exists and can verify integrity without
storing the bytes. Reads blob_dirs and bucket from .eddic/backup.json.
Cross-platform, no third-party deps.

Vendored into a campaign as .eddic/lib/backup/assets.py and called by the
pre-commit hook; also runnable by hand (`--root <repo>`)."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

# OS cruft that must never enter the inventory or the object store.
IGNORE_NAMES = {".DS_Store", "Thumbs.db"}


def find_root(start):
    """Walk up from `start` to the first dir holding .eddic/backup.json."""
    for d in [start, *start.parents]:
        if (d / ".eddic" / "backup.json").is_file():
            return d
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(root):
    cfg = json.loads(
        (root / ".eddic" / "backup.json").read_text(encoding="utf-8"))
    blobs = []
    for d in cfg.get("blob_dirs", []):
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.is_symlink() and p.name not in IGNORE_NAMES:
                blobs.append({"path": p.relative_to(root).as_posix(),
                              "bytes": p.stat().st_size,
                              "sha256": sha256(p)})
    return {"bucket": cfg.get("bucket"), "blobs": blobs}


def resolve_root(arg):
    """A `--root` that isn't backup-configured is a clean no-op, not an
    error: the hook fires in every repo, only backup repos have work."""
    if arg:
        root = Path(arg).resolve()
        return root if (root / ".eddic" / "backup.json").is_file() else None
    return find_root(Path.cwd().resolve())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=None,
                    help="repo root (default: discover via .eddic/backup.json)")
    args = ap.parse_args()

    root = resolve_root(args.root)
    if root is None:
        print("backup: no .eddic/backup.json; nothing to inventory",
              file=sys.stderr)
        return 0

    manifest = build(root)
    out = root / ".eddic" / "assets.json"
    out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    total = sum(b["bytes"] for b in manifest["blobs"])
    print(f"assets: {len(manifest['blobs'])} blob(s), {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
