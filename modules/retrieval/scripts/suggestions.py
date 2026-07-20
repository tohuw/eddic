# /// script
# requires-python = ">=3.9"
# ///
"""eddic suggestions — materialize the retrieval worker's review inbox
into the repo for the owner to review, apply, and commit.

Usage:
    uv run suggestions.py [--url BASE] [--token DM_TOKEN]
                          [--status pending|accepted|all] [--out DIR]
    (bare, as a vendored eddic verb: the worker base URL comes from the
     campaign config's `worker_url` and the DM token from the
     environment; --url / --token override.)

This is the owner's side of the witness write path. The worker files
player and DM *suggestions* into a KV inbox; nothing an agent submits
ever reaches canon automatically. This verb reads that inbox over the
DM-tier MCP endpoint (`list_suggestions`) and writes one markdown file
per suggestion under `suggestions/` — metadata plus the proposed
content — so the owner can read it, apply it by hand, and commit. It
NEVER writes canon and never auto-applies: it only stages review files.

Resolution model:
  * pending and accepted suggestions are materialized (one file each,
    named <id>.md);
  * a suggestion that has been dropped (or has vanished from the inbox)
    has its stale review file removed, if present;
  * re-running updates files in place — idempotent, no duplicates.

Sources, in precedence order:
  * base URL:  --url  >  $EDDIC_WORKER_URL  >  config.json "worker_url"
  * DM token:  --token  >  $EDDIC_DM_TOKEN  >  $TOKEN_DM

Exit codes: 0 done, 1 runtime error (network/auth/config), 2 usage.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

VALID_STATUS = ("pending", "accepted", "dropped", "all")

# A plain YAML scalar we can emit unquoted: a simple token with no
# YAML-significant or line-breaking characters. Anything else (a colon,
# a hash, a quote, and crucially a newline or carriage return) is routed
# through json.dumps, which yields a valid double-quoted YAML flow
# scalar with those characters escaped — so player-controlled path/title
# can never inject a new frontmatter line.
_SAFE_PLAIN = re.compile(r"^[A-Za-z0-9_./\- ]+$")


def _yaml_scalar(v):
    s = str(v)
    if s and _SAFE_PLAIN.match(s) and not s.startswith(" ") \
            and not s.endswith(" "):
        return s
    return json.dumps(s, ensure_ascii=False)


def die(msg, code=1):
    print(f"suggestions: {msg}", file=sys.stderr)
    return code


def config():
    """Load the campaign config when run as a vendored verb."""
    cfg_env = os.environ.get("EDDIC_CONFIG")
    if not cfg_env:
        return {}, None
    cfg_path = Path(cfg_env)
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8")), cfg_path
    except (OSError, json.JSONDecodeError):
        return {}, cfg_path


def mcp_call(base, token, name, arguments):
    """One MCP tools/call over the DM-tier endpoint. Header auth keeps
    the token out of the URL. Returns the tool result dict."""
    url = base.rstrip("/") + "/mcp"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}}
                      ).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        # A normal User-Agent: a Cloudflare-fronted custom domain with
        # bot controls on will 403 the default `Python-urllib/*` UA,
        # while a plain client UA (like curl's) passes.
        headers={"content-type": "application/json",
                 "accept": "application/json",
                 "user-agent": "eddic-suggestions",
                 "authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"worker error: {payload['error']}")
    result = payload.get("result", {})
    if result.get("isError"):
        text = (result.get("content") or [{}])[0].get("text", "unknown error")
        raise RuntimeError(f"tool refused: {text}")
    return result


def fence_for(text):
    """A backtick fence longer than any run of backticks in the text, so
    arbitrary proposed content never breaks out of its code block."""
    longest = 0
    run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def render(sug):
    """Render one suggestion to a review markdown document. Frontmatter
    is machine-readable; the body is for the owner's eyes; the proposed
    content sits verbatim in a fence."""
    kind = sug.get("kind", "edit")
    sid = sug.get("id", "")
    fm = {
        "id": sid,
        "kind": kind,
        "status": sug.get("status", "pending"),
        "tier": sug.get("tier", ""),
        "created": sug.get("created", ""),
    }
    if sug.get("resolved"):
        fm["resolved"] = sug["resolved"]
    if kind == "page":
        fm["title"] = sug.get("title", "")
        if sug.get("path"):
            fm["path"] = sug["path"]
    else:
        fm["path"] = sug.get("path", "")
    if sug.get("note"):
        fm["note"] = sug["note"]

    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {_yaml_scalar(v)}")
    lines.append("---")
    lines.append("")

    heading = (sug.get("title") or sug.get("path") or "(untitled)")
    lines.append(f"# Suggestion {sid[:8]} — {kind}: {heading}")
    lines.append("")
    lines.append(f"- **Status:** {fm['status']}")
    lines.append(f"- **From tier:** {fm.get('tier') or 'unknown'}")
    lines.append(f"- **Created:** {fm.get('created') or 'unknown'}")
    if kind == "page":
        lines.append(f"- **Suggested title:** {sug.get('title', '')}")
        if sug.get("path"):
            lines.append(f"- **Suggested path:** `{sug['path']}`")
    else:
        lines.append(f"- **Target path:** `{sug.get('path', '')}`")
    if sug.get("rationale"):
        lines.append(f"- **Rationale:** {sug['rationale']}")
    if sug.get("resolved"):
        lines.append(f"- **Resolved:** {sug['resolved']}")
    if sug.get("note"):
        lines.append(f"- **Resolver note:** {sug['note']}")
    lines.append("")

    proposed = sug.get("content" if kind == "page" else "suggestion", "")
    lines.append("## Proposed " + ("page content" if kind == "page"
                                   else "edit"))
    lines.append("")
    fence = fence_for(proposed)
    lines.append(fence)
    lines.append(proposed.rstrip("\n"))
    lines.append(fence)
    lines.append("")
    lines.append("---")
    lines.append("_Staged for review only — nothing here is canon. To "
                 "apply, edit the target page yourself and commit, then "
                 "resolve this suggestion (accept/drop) from the DM tier._")
    lines.append("")
    return "\n".join(lines)


def main(argv):
    opts = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            opts[a] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        else:
            i += 1

    cfg, cfg_path = config()
    base = (opts.get("--url") or os.environ.get("EDDIC_WORKER_URL")
            or cfg.get("worker_url"))
    token = (opts.get("--token") or os.environ.get("EDDIC_DM_TOKEN")
             or os.environ.get("TOKEN_DM"))
    status = opts.get("--status", "all")
    if status not in VALID_STATUS:
        return die(f"--status must be one of {', '.join(VALID_STATUS)}", 2)

    if not base:
        return die("no worker base URL — set config.json 'worker_url', "
                   "$EDDIC_WORKER_URL, or pass --url", 2)
    if not token:
        return die("no DM token — set $EDDIC_DM_TOKEN or $TOKEN_DM, or "
                   "pass --token (this is the DM-tier token; it must "
                   "never land in the repo or a log)", 2)

    if opts.get("--out"):
        out = Path(opts["--out"])
    elif cfg_path is not None:
        out = cfg_path.parent.parent / "suggestions"
    else:
        out = Path("suggestions")

    try:
        result = mcp_call(base, token, "list_suggestions", {"status": "all"})
    except urllib.error.HTTPError as e:
        hint = " (is this the DM token?)" if e.code in (401, 403) else ""
        return die(f"worker returned HTTP {e.code}{hint}")
    except urllib.error.URLError as e:
        return die(f"cannot reach the worker at {base}: {e.reason}")
    except (RuntimeError, ValueError, json.JSONDecodeError) as e:
        return die(str(e))

    inbox = (result.get("structuredContent") or {}).get("suggestions", [])
    out.mkdir(parents=True, exist_ok=True)

    written = removed = 0
    for sug in inbox:
        sid = sug.get("id")
        if not sid:
            continue
        path = out / f"{sid}.md"
        st = sug.get("status", "pending")
        if st in ("pending", "accepted"):
            path.write_text(render(sug), encoding="utf-8")
            written += 1
        else:  # dropped (or anything else) — clear any stale review file
            if path.exists():
                path.unlink()
                removed += 1

    kept = "; ".join(f"{s.get('id', '')[:8]} [{s.get('status')}] "
                     f"{s.get('kind')}"
                     for s in inbox
                     if s.get("status") in ("pending", "accepted"))
    print(f"suggestions: {written} staged, {removed} stale removed, "
          f"in {out}")
    if kept:
        print(f"  {kept}")
    print("  review, apply by hand, and commit — nothing here is canon.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
