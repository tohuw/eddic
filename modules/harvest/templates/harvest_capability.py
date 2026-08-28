"""harvest capability — the nightly runner, in the lore bot's process.

Vendored beside bot.py and named in CAPABILITIES. It rides there rather
than living in its own service for four reasons, all of them things the
bot already has: the Discord token with the Message Content intent, the
wiki corpus in memory, the question log on the same disk, and a model
provider with the corpus already prompt-cached. A separate service would
need its own copy of all four, and on a host with per-service disks it
could not read the question log at all.

Once a night it pulls the allow-listed channels since the last
watermark, asks the model what the wiki should gain, and files the
findings as suggestions. It never edits the wiki, it never posts to the
table, and it holds no message store: harvest.py keeps watermarks.

Config (environment):
    HARVEST_HOUR=4              host clock, 0-23; nightly run time
    HARVEST_MAX_PAGES=20        pages of 100 per channel per run; the
                                first run reads history, so raise it for
                                a deeper backlog
    HARVEST_CONFIG=harvest.json the allow-list, dm_ids, announced flag
    HARVEST_STATE=harvest-state.json   watermarks; put it on a volume
    WITNESS_URL / WITNESS_TOKEN  where findings are filed
    HARVEST_REPORT_TO=<user id>  who gets the run report (default OWNER_ID)
"""

import asyncio
import importlib.util
import json
import os
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_FILED = 12          # per night, so a noisy day cannot flood the inbox


def _load_harvest():
    """The module's own script, imported by path so the capability and
    the CLI verb can never drift apart — one implementation of the
    watermark, the consent gate, and the intent check, not two.

    Looked up in the order a deployment actually varies: an explicit
    path, then beside this file (the vendored bot directory), then the
    module's own scripts/ (a checkout, which is how verify runs)."""
    candidates = [
        Path(os.environ["HARVEST_SCRIPT"]) if os.environ.get(
            "HARVEST_SCRIPT") else None,
        HERE / "harvest.py",
        HERE.parent / "scripts" / "harvest.py",
    ]
    src = next((c for c in candidates if c and c.exists()), None)
    if src is None:
        raise FileNotFoundError(
            "harvest.py not found beside the capability or in the "
            "module's scripts/; set HARVEST_SCRIPT to its path")
    spec = importlib.util.spec_from_file_location("harvest_core", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def file_suggestion(base_url, token, tool, arguments, timeout=30):
    """One witness write. Header auth keeps the token out of the URL."""
    url = base_url.rstrip("/") + "/mcp"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}
                      ).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"content-type": "application/json",
                 "accept": "application/json",
                 "user-agent": "eddic-harvest",
                 "authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"worker error: {payload['error']}")
    result = payload.get("result", {})
    if result.get("isError"):
        raise RuntimeError((result.get("content") or [{}])[0].get(
            "text", "unknown error"))
    return result


PROMPT = """You are mining one night of a D&D table's Discord for work \
the campaign wiki needs. The packet below is the whole input; you have \
no other source and you must invent nothing.

Work the packet's `checklist`, honor its `not_in_scope`, and return \
JSON matching its `findings_schema` — an object with a `findings` list \
and nothing else. No prose around it.

The rules that decide correctness here:
* Only a message in `dm_statements` can become a `canon-candidate`. \
Those are the DM's words. A player stating lore confidently is still a \
player, and belongs in `gap` at most.
* Report contradictions; never adjudicate them. Say what both sides \
said and stop.
* Rank `gap` findings by how often the same thing was asked. A question \
asked three times is the page to write next.
* `naming` findings are about spelling, not lore: chat spells names \
correctly and transcripts mangle them.
* An empty `findings` list is a correct answer for a quiet night. Do not \
manufacture work.

Each finding needs: category, severity, summary (one sentence, what the \
wiki should gain or fix), evidence (quote plus channel and timestamp), \
and suggestion (the concrete edit, naming the page).

PACKET:
"""


def setup(client):
    harvest = _load_harvest()
    hour = int(os.environ.get("HARVEST_HOUR", "4"))
    cfg_path = HERE / os.environ.get("HARVEST_CONFIG", "harvest.json")
    state_path = os.environ.get("HARVEST_STATE", str(HERE / "harvest-state.json"))
    witness_url = os.environ.get("WITNESS_URL", "")
    witness_token = os.environ.get("WITNESS_TOKEN", "")
    report_to = int(os.environ.get("HARVEST_REPORT_TO",
                                   os.environ.get("OWNER_ID", "0")) or 0)
    token = os.environ.get("DISCORD_TOKEN", "")
    # Pages of 100 messages per channel per run. The default is plenty
    # for a night; the first run reads history, so raise it when the
    # backlog is deeper than 2,000 messages in a channel.
    max_pages = int(os.environ.get("HARVEST_MAX_PAGES",
                                   harvest.DEFAULT_MAX_PAGES))

    class Harvest:
        def __init__(self):
            self.corpus = ""
            self.last_run = ""

        async def ready(self, corpus=""):
            self.corpus = corpus
            client.loop.create_task(self.loop())

        async def on_corpus_refresh(self, corpus):
            self.corpus = corpus

        # ---- the run ------------------------------------------------
        def pull(self):
            """Deterministic half. Runs in a thread: it is blocking HTTP
            and must not stall the bot's event loop."""
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
            config.setdefault("state_file", state_path)
            config["corpus_dir"] = ""       # the live corpus is better
            packet, code = harvest.do_pull(
                config, state_path, token, harvest.http_get, max_pages)
            if packet is None:
                return None, code
            known = set(harvest.PROPER.findall(self.corpus))
            packet["novel_proper_nouns"] = {
                n: c for n, c in packet["novel_proper_nouns"].items()
                if n not in known}
            packet["counts"]["novel_proper_nouns"] = len(
                packet["novel_proper_nouns"])
            return packet, 0

        def mine(self, packet, llm, model, max_tokens):
            # The provider's own shape: the packet rides in the cached
            # corpus slot, the instructions in the persona slot. No
            # roster — this pass has no business with real names.
            raw = llm.complete(
                model=model, max_tokens=max_tokens,
                corpus_text="HARVEST PACKET:\n"
                            + json.dumps(packet, ensure_ascii=False),
                persona=PROMPT, roster="",
                prompt="Return the findings JSON now.")
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end < 0:
                raise RuntimeError("model returned no JSON object")
            doc = json.loads(raw[start:end + 1])
            errs = harvest.validate_findings(doc)
            if errs:
                raise RuntimeError("; ".join(errs[:3]))
            return doc["findings"]

        def file_all(self, findings):
            filed, refused = 0, []
            for f in findings[:MAX_FILED]:
                try:
                    file_suggestion(witness_url, witness_token,
                                    "suggest_edit", {
                                        "path": f.get("page", "index.md"),
                                        "suggestion": f["suggestion"],
                                        "rationale": (
                                            f"[harvest/{f['category']}] "
                                            f"{f['summary']}\n\n"
                                            f"{f['evidence']}"),
                                    })
                    filed += 1
                except Exception as e:
                    refused.append(f"{f['category']}: {e}")
            return filed, refused

        async def run_once(self, llm=None, model=None, max_tokens=1200):
            packet, code = await asyncio.to_thread(self.pull)
            if packet is None:
                return ("harvest did not run: not armed, or no channels "
                        "configured (exit %d)" % code)
            counts = packet["counts"]
            if not counts["messages"]:
                return "harvest: nothing said since the last run."
            if llm is None:
                return (f"harvest: {counts['messages']} message(s) read, "
                        "no model configured to mine them")
            findings = await asyncio.to_thread(
                self.mine, packet, llm, model, max_tokens)
            if not findings:
                return (f"harvest: {counts['messages']} message(s), "
                        "nothing worth filing.")
            if not (witness_url and witness_token):
                return (f"harvest: {len(findings)} finding(s), no witness "
                        "configured — nothing filed.")
            filed, refused = await asyncio.to_thread(self.file_all, findings)
            note = (f"harvest: {counts['messages']} message(s) -> "
                    f"{len(findings)} finding(s), {filed} filed")
            if len(findings) > MAX_FILED:
                note += f" ({len(findings) - MAX_FILED} held back for tomorrow)"
            if refused:
                note += "\nrefused: " + "; ".join(refused[:3])
            for name in packet["window"].get("failed_channels", []):
                note += f"\nchannel skipped: {name}"
            return note

        async def loop(self):
            """Wake hourly and run once a day at HARVEST_HOUR. Missing a
            night costs nothing: the watermark simply widens the next
            window."""
            while True:
                await asyncio.sleep(3600)
                try:
                    today = time.strftime("%Y-%m-%d")
                    if (int(time.strftime("%H")) != hour
                            or self.last_run == today):
                        continue
                    self.last_run = today
                    report = await self.run_once(
                        getattr(client, "eddic_llm", None),
                        getattr(client, "eddic_model", None),
                        getattr(client, "eddic_max_tokens", 1200))
                    print(report)
                    if report_to:
                        user = client.get_user(report_to) or \
                            await client.fetch_user(report_to)
                        await user.send(report[:1900])
                except Exception as e:
                    print(f"harvest run failed: {e}")

    return Harvest()
