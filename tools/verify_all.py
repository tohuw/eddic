# /// script
# requires-python = ">=3.9"
# ///
"""Run every module's verify (modules/*/verify/run.py), preferring uv
so declared dependencies resolve. Cross-platform; exits nonzero if
any verify fails.

A verify is a leaf process, never interactive: it gets no stdin, and a
per-module wall-clock cap turns a hang into a reported failure instead
of a job that hangs the runner forever. (A single stuck verify once
wedged every Windows CI run silently; the cap makes that self-report.)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

MODULES = Path(__file__).resolve().parent.parent / "modules"
TIMEOUT = int(os.environ.get("VERIFY_TIMEOUT", "300"))   # seconds/module


def main():
    runner = (["uv", "run"] if shutil.which("uv") else [sys.executable])
    failed = []
    for run in sorted(MODULES.glob("*/verify/run.py")):
        name = run.parent.parent.name
        print(f"=== {name} ===", flush=True)
        try:
            rc = subprocess.run(runner + [str(run)],
                                stdin=subprocess.DEVNULL,
                                timeout=TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT after {TIMEOUT}s: {name} verify hung",
                  flush=True)
            rc = 1
        if rc != 0:
            failed.append(name)
    print("\nverify_all:", "ok" if not failed else
          f"FAILED ({', '.join(failed)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
