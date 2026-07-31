# /// script
# requires-python = ">=3.9"
# ///
"""Stamp the shared wiki primitives from tools/wikilib.py into every script
that carries them, and prove no copy has drifted.

    uv run tools/sync_shared.py            # rewrite the stamped blocks
    uv run tools/sync_shared.py --check    # exit 1 if any copy is stale

A consumer opts in with a marker naming exactly what it wants:

    # --- BEGIN SHARED wikilib: consts, split_frontmatter, page_ref ---
    ...generated...
    # --- END SHARED wikilib ---

Two failures are caught. **Drift**: a stamped block that differs from what
wikilib.py would produce — someone hand-edited a copy. **Forking**: a
rostered name defined anywhere outside a stamped block — someone added an
eighth implementation instead of extending the canonical one. The second is
the one that actually bit us: the pen axis went into the projection and not
into the lint or the graph, so a clean lint meant a projection that refused.

The floor runs --check on every push.
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "tools" / "wikilib.py"
BEGIN = re.compile(
    r"^([ \t]*)# --- BEGIN SHARED wikilib: (.+?) ---[ \t]*$", re.M)
END = "# --- END SHARED wikilib ---"


def chunks():
    """Named blocks of wikilib.py, delimited by `# >>> name` / `# <<<`."""
    out, name, buf = {}, None, []
    for line in LIB.read_text(encoding="utf-8").splitlines():
        if line.startswith("# >>> "):
            name, buf = line[6:].strip(), []
        elif line.strip() == "# <<<" and name:
            out[name] = "\n".join(buf).strip("\n")
            name = None
        elif name is not None:
            buf.append(line)
    return out


def rostered_names(available):
    """Every top-level name wikilib.py defines, function or constant."""
    names = set()
    for body in available.values():
        for node in ast.parse(body).body:
            if isinstance(node, ast.FunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names


def scannable():
    """Every module script that could carry or fork a primitive. Vendored
    templates count: the lore bot parses frontmatter on its own host, and a
    fork hiding there would serve the difference to players."""
    seen = []
    for pattern in ("modules/*/scripts/*.py", "modules/*/templates/*.py"):
        seen.extend(sorted(ROOT.glob(pattern)))
    return sorted(set(seen))


def consumers():
    for path in scannable():
        text = path.read_text(encoding="utf-8")
        if BEGIN.search(text):
            yield path, text


def render(text, available, path):
    """Rewrite every stamped block in `text`. Returns (new_text, errors)."""
    errors = []
    out, pos = [], 0
    for m in BEGIN.finditer(text):
        indent, wanted = m.group(1), [w.strip() for w in m.group(2).split(",")]
        end = text.find(f"{indent}{END}", m.end())
        if end == -1:
            errors.append(f"{path}: BEGIN marker with no matching END")
            return text, errors
        missing = [w for w in wanted if w not in available]
        if missing:
            errors.append(
                f"{path}: marker names {missing} which wikilib.py does not "
                f"define (have: {sorted(available)})")
            return text, errors
        body = "\n\n\n".join(available[w] for w in wanted)
        if indent:
            body = "\n".join(indent + ln if ln.strip() else ln
                             for ln in body.splitlines())
        out.append(text[pos:m.end()])
        out.append("\n" + body + "\n")
        pos = end
    out.append(text[pos:])
    return "".join(out), errors


def stamped_spans(text):
    spans = []
    for m in BEGIN.finditer(text):
        end = text.find(f"{m.group(1)}{END}", m.end())
        if end != -1:
            spans.append((m.start(), end + len(END)))
    return spans


def forks(names):
    """Rostered names defined outside a stamped block, anywhere in modules/."""
    found = []
    for path in scannable():
        text = path.read_text(encoding="utf-8")
        spans = stamped_spans(text)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        lines = text.splitlines(keepends=True)
        offsets, run = [], 0
        for ln in lines:
            offsets.append(run)
            run += len(ln)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                who = node.name
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                who = node.targets[0].id
            else:
                continue
            if who not in names:
                continue
            at = offsets[node.lineno - 1]
            if not any(a <= at < b for a, b in spans):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}: "
                             f"'{who}' is defined outside a stamped block — "
                             f"extend tools/wikilib.py instead of forking it")
    return found


def main(argv):
    check = "--check" in argv
    available = chunks()
    if not available:
        print("sync_shared: wikilib.py exposes no blocks", file=sys.stderr)
        return 2
    names = rostered_names(available)

    stale, errors = [], []
    for path, text in consumers():
        new, errs = render(text, available, path.relative_to(ROOT))
        errors.extend(errs)
        if new != text:
            stale.append(path.relative_to(ROOT))
            if not check:
                path.write_text(new, encoding="utf-8")
    errors.extend(forks(names))

    for e in errors:
        print(f"sync_shared: {e}", file=sys.stderr)
    if errors:
        return 1
    if check:
        if stale:
            for p in stale:
                print(f"sync_shared: {p} has drifted from tools/wikilib.py",
                      file=sys.stderr)
            print("sync_shared: run `uv run tools/sync_shared.py` to restamp",
                  file=sys.stderr)
            return 1
        print(f"sync_shared: ok ({len(list(consumers()))} consumers, "
              f"{len(names)} rostered names, no drift, no forks)")
        return 0
    print(f"sync_shared: stamped {len(stale)} file(s); "
          f"{len(names)} rostered names")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
