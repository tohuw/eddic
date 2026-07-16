# /// script
# requires-python = ">=3.9"
# ///
"""Run every module's verify (modules/*/verify/run.py), preferring uv
so declared dependencies resolve. Cross-platform; exits nonzero if
any verify fails."""

import shutil
import subprocess
import sys
from pathlib import Path

MODULES = Path(__file__).resolve().parent.parent / "modules"


def main():
    runner = (["uv", "run"] if shutil.which("uv") else [sys.executable])
    failed = []
    for run in sorted(MODULES.glob("*/verify/run.py")):
        name = run.parent.parent.name
        print(f"=== {name} ===", flush=True)
        if subprocess.run(runner + [str(run)]).returncode != 0:
            failed.append(name)
    print("\nverify_all:", "ok" if not failed else
          f"FAILED ({', '.join(failed)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
