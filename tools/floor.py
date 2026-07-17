# /// script
# requires-python = ">=3.9"
# ///
"""The contract's deterministic floor, mechanically enforced.

Checks every modules/<name>/ against CONTRACT.md's floor:
  - module.yaml present with required top-level keys
  - PATTERN.md present with the four parts, in order
  - every decision point ships a Default:
  - files the pattern references under scripts/ and templates/ exist
  - verify/run.py present
  - no symlinks anywhere in the module
  - no obvious committed secrets anywhere in the repo
  - vendor names in PATTERN.md are backed by compatibility metadata
    in module.yaml (status/date; verified additionally needs evidence)

Exit 0 clean, 1 violations (listed)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
YAML_KEYS = ("name:", "version:", "summary:", "touches:", "depends:",
             "cost_posture:")
PARTS = ("## Preflight", "## Procedure", "## Decision points", "## Verify")
SECRET_PATTERNS = re.compile(
    r"sk-ant-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
COMPAT_NAMES = ("claude", "chatgpt", "codex", "anthropic", "openai")
COMPAT_STATES = ("verified", "documented", "unverified", "unsupported")


def compat_entries(yaml_text):
    """Parse the flat compatibility: block — entry names at two-space
    indent, fields at four. Naive on purpose; module.yaml is ours."""
    entries, current, in_block = {}, None, False
    for ln in yaml_text.splitlines():
        if re.match(r"^compatibility:\s*$", ln):
            in_block = True
            continue
        if in_block:
            if ln.strip() and not ln.startswith(" "):
                break
            m = re.match(r"^  ([\w-]+):\s*$", ln)
            if m:
                current = m.group(1).lower()
                entries[current] = {}
                continue
            f = re.match(r"^    ([\w-]+):\s*(.+?)\s*$", ln)
            if f and current:
                entries[current][f.group(1)] = f.group(2)
    return entries


def main():
    problems = []

    def bad(msg):
        problems.append(msg)

    for mod in sorted(p for p in MODULES.iterdir() if p.is_dir()):
        name = mod.name
        yaml = mod / "module.yaml"
        if not yaml.is_file():
            bad(f"{name}: module.yaml missing")
        else:
            text = yaml.read_text(encoding="utf-8")
            for key in YAML_KEYS:
                if not re.search(rf"^{key}", text, re.M):
                    bad(f"{name}: module.yaml missing key '{key}'")
            m = re.search(r"^name:\s*(\S+)", text, re.M)
            if m and m.group(1) != name:
                bad(f"{name}: module.yaml name '{m.group(1)}' != dir name")

        pattern = mod / "PATTERN.md"
        if not pattern.is_file():
            bad(f"{name}: PATTERN.md missing")
        else:
            text = pattern.read_text(encoding="utf-8")
            idx = [text.find(part) for part in PARTS]
            if -1 in idx:
                missing = [p for p, i in zip(PARTS, idx) if i == -1]
                bad(f"{name}: PATTERN.md missing {', '.join(missing)}")
            elif idx != sorted(idx):
                bad(f"{name}: PATTERN.md parts out of order")
            dp = text.partition("## Decision points")[2].partition("## ")[0]
            for line in dp.splitlines():
                if line.startswith("- **") and "Default:" not in line:
                    # default may wrap to the following lines of the bullet
                    rest = dp[dp.find(line):]
                    bullet = rest.split("\n- **")[0]
                    if "Default:" not in bullet:
                        bad(f"{name}: decision point without a Default: "
                            f"{line.strip()[:60]}")
            for ref in re.findall(r"(?:scripts|templates|verify)/[\w.\-]+",
                                  text):
                if not (mod / ref).exists():
                    bad(f"{name}: PATTERN.md references missing file {ref}")

            # vendor claims need compatibility metadata (see CONTRACT.md)
            if yaml.is_file():
                entries = compat_entries(yaml.read_text(encoding="utf-8"))
                mentioned = {n for n in COMPAT_NAMES
                             if re.search(rf"\b{n}\b", text, re.I)}
                for n in sorted(mentioned - set(entries)):
                    bad(f"{name}: PATTERN.md mentions '{n}' but module.yaml "
                        f"has no compatibility entry for it")
                for n, fields in entries.items():
                    status = fields.get("status", "")
                    if status not in COMPAT_STATES:
                        bad(f"{name}: compatibility.{n} status "
                            f"'{status}' not one of {COMPAT_STATES}")
                    if "date" not in fields:
                        bad(f"{name}: compatibility.{n} missing date")
                    if status == "verified" and "evidence" not in fields:
                        bad(f"{name}: compatibility.{n} is verified "
                            f"but cites no evidence")

        if not (mod / "verify" / "run.py").is_file():
            bad(f"{name}: verify/run.py missing")
        for p in mod.rglob("*"):
            if p.is_symlink():
                bad(f"{name}: symlink at {p.relative_to(mod)}")

    for p in ROOT.rglob("*"):
        if (p.is_file() and ".git" not in p.parts
                and p.suffix not in (".png", ".webp", ".jpg")):
            try:
                if SECRET_PATTERNS.search(p.read_text(encoding="utf-8",
                                                      errors="ignore")):
                    bad(f"possible committed secret in "
                        f"{p.relative_to(ROOT)}")
            except OSError:
                pass

    for msg in problems:
        print(f"FLOOR: {msg}")
    count = sum(1 for p in MODULES.iterdir() if p.is_dir())
    print(f"floor: {'ok' if not problems else 'FAILED'} "
          f"({count} modules checked)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
