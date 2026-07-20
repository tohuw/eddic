// Node harness for the retrieval worker: imports the staged worker
// and drives its fetch handler directly (no wrangler, no network).
// Usage: node harness.mjs <staged_worker_dir>
import { pathToFileURL } from "node:url";
import { join } from "node:path";

const dir = process.argv[2];
const worker = (await import(pathToFileURL(join(dir, "worker.js")))).default;

// The Workers ASSETS binding can't run in this pure-node harness — it
// needs the real Workers runtime to serve dist/site. Stub it with a
// sentinel so we can prove the unified-host routing decision (no valid
// token => serve the site) without faking the static serving itself.
const ASSETS_SENTINEL = "<static-site-served-by-ASSETS>";
const env = {
  TOKEN_DM: "dm-secret", TOKEN_PLAYER: "player-secret",
  ASSETS: { fetch: () => new Response(ASSETS_SENTINEL, { status: 200 }) },
};

let failures = 0;
function check(ok, msg) {
  console.log((ok ? "ok  " : "FAIL") + " " + msg);
  if (!ok) failures++;
}

async function rpc(token, body, viaPath = false, useEnv = env) {
  const url = viaPath
    ? `https://w.example/${token}/mcp`
    : "https://w.example/mcp";
  const headers = { "content-type": "application/json" };
  if (!viaPath && token) headers.Authorization = `Bearer ${token}`;
  const res = await worker.fetch(
    new Request(url, { method: "POST", headers,
                       body: JSON.stringify(body) }), useEnv);
  const isJson = (res.headers.get("content-type") || "").includes("json");
  return { status: res.status, body: isJson ? await res.json() : null };
}

const init = { jsonrpc: "2.0", id: 1, method: "initialize",
               params: { protocolVersion: "2025-06-18" } };

// auth: no/invalid token is not a 401 anymore — the unified host falls
// through to the static site (humans browsing the bare host get the
// wiki; agents authenticate to reach MCP/REST).
const noAuth = await worker.fetch(
  new Request("https://w.example/mcp", { method: "POST" }), env);
check(noAuth.status === 200 && (await noAuth.text()) === ASSETS_SENTINEL,
      "no token falls through to the static site (ASSETS binding)");
const badAuth = await rpc("wrong-token", init);
check(badAuth.status === 200,
      "wrong token also falls through to the static site");

// companion page: GET /<token>/companion is token-gated and fills the
// caller's own MCP URL per request; a bogus token does not serve it.
async function getPath(path) {
  const res = await worker.fetch(
    new Request(`https://w.example${path}`, { method: "GET" }), env);
  return { status: res.status,
           ctype: res.headers.get("content-type") || "",
           text: await res.text() };
}
const comp = await getPath("/player-secret/companion");
check(comp.status === 200 && comp.ctype.includes("text/html") &&
      comp.text.includes("https://w.example/player-secret/mcp"),
      "companion page served with the caller's own MCP URL filled");
check(!comp.text.includes("{{PLAYER_MCP_URL}}"),
      "companion page leaves no unfilled MCP-URL sentinel");
const compBad = await getPath("/wrong-token/companion");
check(compBad.text === ASSETS_SENTINEL,
      "bogus token does not serve the companion page (falls through)");
const compPost = await worker.fetch(
  new Request("https://w.example/player-secret/companion",
              { method: "POST" }), env);
check(compPost.status === 405, "companion page refuses non-GET");

// initialize, both auth styles
const viaHeader = await rpc("dm-secret", init);
check(viaHeader.body?.result?.serverInfo?.name?.endsWith("-dm"),
      "initialize via header, dm tier");
const viaPath = await rpc("player-secret", init, true);
check(viaPath.body?.result?.serverInfo?.name?.endsWith("-player"),
      "initialize via capability path, player tier");

// notifications get 202
const note = await rpc("dm-secret",
  { jsonrpc: "2.0", method: "notifications/initialized" });
check(note.status === 202, "notification accepted 202");

// tools/list
const tools = await rpc("dm-secret",
  { jsonrpc: "2.0", id: 2, method: "tools/list" });
check(tools.body?.result?.tools?.length === 4, "four tools listed");
check(tools.body?.result?.tools?.every(
        (t) => t.annotations?.readOnlyHint === true &&
               t.annotations?.openWorldHint === false),
      "every tool annotated read-only, closed-world");

function callBody(id, name, args) {
  return { jsonrpc: "2.0", id, method: "tools/call",
           params: { name, arguments: args } };
}
const textOf = (r) => r.body?.result?.content?.[0]?.text || "";

// tier isolation: the DM page exists for dm, not for player
const dmRead = await rpc("dm-secret",
  callBody(3, "read_page", { path: "keep.dm.md" }));
check(textOf(dmRead).includes("midpoint twist"),
      "dm token reads DM page");
const plRead = await rpc("player-secret",
  callBody(4, "read_page", { path: "keep.dm.md" }));
check(textOf(plRead).startsWith("no such page"),
      "player token cannot read DM page");

// search: dm-only term invisible to player tier
const dmSearch = await rpc("dm-secret",
  callBody(5, "search", { query: "midpoint twist" }));
check(textOf(dmSearch).includes("keep.dm.md"),
      "dm search finds DM-only term");
const plSearch = await rpc("player-secret",
  callBody(6, "search", { query: "midpoint twist" }));
check(textOf(plSearch).startsWith("nothing found"),
      "player search blind to DM-only term");
const plSearch2 = await rpc("player-secret",
  callBody(7, "search", { query: "garrison" }));
check(textOf(plSearch2).includes("keep.md"),
      "player search finds player content");

// list_pages tier counts differ
const dmList = textOf(await rpc("dm-secret", callBody(8, "list_pages", {})));
const plList = textOf(await rpc("player-secret",
                                callBody(9, "list_pages", {})));
check(dmList.split("\n").length > plList.split("\n").length,
      "dm lists more pages than player");

// fetch: canonical search+fetch counterpart, same tier walls
const dmFetch = await rpc("dm-secret",
  callBody(10, "fetch", { id: "keep.dm.md" }));
check(textOf(dmFetch).includes("midpoint twist"),
      "dm fetch reads DM page");
check(dmFetch.body?.result?.structuredContent?.id === "keep.dm.md" &&
      typeof dmFetch.body?.result?.structuredContent?.text === "string",
      "fetch returns structured document");
const plFetch = await rpc("player-secret",
  callBody(11, "fetch", { id: "keep.dm.md" }));
check(textOf(plFetch).startsWith("no such page"),
      "player fetch blind to DM page, indistinguishable from absent");
check(plFetch.body?.result?.structuredContent === undefined,
      "blind fetch leaks no structured document");

// search carries structured results beside the portable text
const dmSearchS = await rpc("dm-secret",
  callBody(12, "search", { query: "midpoint twist" }));
check(dmSearchS.body?.result?.structuredContent?.results?.[0]?.id
        === "keep.dm.md",
      "search structured results carry ids");
const plSearchS = await rpc("player-secret",
  callBody(13, "search", { query: "midpoint twist" }));
check(plSearchS.body?.result?.structuredContent?.results?.length === 0,
      "player structured results empty for DM-only term");

// argument validation is isError, not a silent guess
for (const [name, args] of
     [["read_page", {}], ["fetch", {}], ["search", { query: "  " }]]) {
  const r = await rpc("dm-secret", callBody(14, name, args));
  check(r.body?.result?.isError === true,
        `${name} with bad arguments returns isError`);
}
const unknown = await rpc("dm-secret", callBody(15, "write_page", {}));
check(unknown.body?.result?.isError === true,
      "unknown tool returns isError");

// cross-client request forms
const getRes = await worker.fetch(
  new Request("https://w.example/mcp", {
    method: "GET",
    headers: { Authorization: "Bearer dm-secret" } }), env);
check(getRes.status === 405, "GET answers 405 (no SSE stream offered)");
const sseAccept = await worker.fetch(
  new Request("https://w.example/mcp", {
    method: "POST",
    headers: { "content-type": "application/json",
               Accept: "application/json, text/event-stream",
               Authorization: "Bearer dm-secret" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 16,
                           method: "tools/list" }) }), env);
check(sseAccept.status === 200 &&
      (sseAccept.headers.get("content-type") || "").includes("json"),
      "event-stream-accepting client still gets JSON");

// REST facade (Custom GPT Actions): same tiers, same walls
async function restGet(token, path, viaPath = false) {
  const url = viaPath
    ? `https://w.example/${token}${path}`
    : `https://w.example${path}`;
  const headers = {};
  if (!viaPath && token) headers.Authorization = `Bearer ${token}`;
  const res = await worker.fetch(
    new Request(url, { method: "GET", headers }), env);
  const isJson = (res.headers.get("content-type") || "").includes("json");
  return { status: res.status, body: isJson ? await res.json() : null };
}

const restNoAuth = await restGet(null, "/api/pages");
check(restNoAuth.status === 200,
      "REST without token falls through to the static site (no 401 leak)");
const dmPages = await restGet("dm-secret", "/api/pages");
const plPages = await restGet("player-secret", "/api/pages", true);
check(dmPages.body?.pages?.length > plPages.body?.pages?.length,
      "REST: dm lists more pages than player (capability path works)");
const dmPage = await restGet("dm-secret", "/api/page?id=keep.dm.md");
check(dmPage.status === 200 && dmPage.body?.text?.includes("midpoint"),
      "REST: dm reads DM page");
const plPage = await restGet("player-secret", "/api/page?id=keep.dm.md");
check(plPage.status === 404, "REST: DM page is 404 for player tier");
const dmRest = await restGet("dm-secret", "/api/search?q=midpoint%20twist");
check(dmRest.body?.results?.[0]?.id === "keep.dm.md",
      "REST: dm search finds DM-only term");
const plRest = await restGet("player-secret",
                             "/api/search?q=midpoint%20twist");
check(plRest.body?.results?.length === 0,
      "REST: player search blind to DM-only term");
const restPost = await worker.fetch(
  new Request("https://w.example/api/pages", {
    method: "POST",
    headers: { Authorization: "Bearer dm-secret" } }), env);
check(restPost.status === 405, "REST refuses non-GET (read-only)");

// ---- the witness write path: KV-backed suggestion inbox ----
// A mock in-memory KV (get/put/list) stands in for the Workers KV
// binding; no live Cloudflare is touched. Bound as INBOX in a separate
// env so the read-only-env tests above stay exactly as they were.
function mockKV() {
  const store = new Map();
  return {
    _store: store,
    async get(k) { return store.has(k) ? store.get(k) : null; },
    async put(k, v) { store.set(k, v); },
    async list({ prefix = "", cursor } = {}) {   // eslint-disable-line
      const keys = [...store.keys()].filter((k) => k.startsWith(prefix))
        .map((name) => ({ name }));
      return { keys, list_complete: true, cursor: undefined };
    },
  };
}
const envKV = { ...env, INBOX: mockKV() };

// tools/list is tier- and INBOX-aware
const plTools = await rpc("player-secret",
  { jsonrpc: "2.0", id: 20, method: "tools/list" }, false, envKV);
const plNames = plTools.body?.result?.tools?.map((x) => x.name) || [];
check(plNames.includes("suggest_edit") && plNames.includes("suggest_page") &&
      !plNames.includes("list_suggestions") &&
      !plNames.includes("resolve_suggestion"),
      "player tools/list: read tools + suggest_*, no DM review tools");
const dmTools = await rpc("dm-secret",
  { jsonrpc: "2.0", id: 21, method: "tools/list" }, false, envKV);
const dmNames = dmTools.body?.result?.tools?.map((x) => x.name) || [];
check(dmNames.includes("list_suggestions") &&
      dmNames.includes("resolve_suggestion"),
      "dm tools/list: additionally list_suggestions + resolve_suggestion");
check(plTools.body?.result?.tools?.find((x) => x.name === "suggest_edit")
        ?.annotations?.readOnlyHint === false,
      "suggest_edit is annotated as a write (not read-only)");

// player files an edit against a DM-only path: accepted with NO corpus
// check (no existence oracle), stored pending
const sug = await rpc("player-secret",
  callBody(22, "suggest_edit",
    { path: "keep.dm.md", suggestion: "note the cellars", rationale: "lore" }),
  false, envKV);
check(textOf(sug).includes("review") &&
      !!sug.body?.result?.structuredContent?.id,
      "suggest_edit files a suggestion and confirms warmly with an id");
const sugId = sug.body?.result?.structuredContent?.id;
check(sug.body?.result?.structuredContent?.status === "pending",
      "suggest_edit reports status pending");
const sugP = await rpc("player-secret",
  callBody(23, "suggest_page",
    { title: "A New Rumor", content: "A traveler speaks of the keep." }),
  false, envKV);
check(!!sugP.body?.result?.structuredContent?.id,
      "suggest_page files a pending suggestion");

// tier gating is enforced in the HANDLER, not only by tools/list
const wPlList = await rpc("player-secret",
  callBody(24, "list_suggestions", {}), false, envKV);
check(wPlList.body?.result?.isError === true,
      "player list_suggestions is rejected by the handler (DM-tier only)");
const plResolve = await rpc("player-secret",
  callBody(25, "resolve_suggestion", { id: sugId, action: "accept" }),
  false, envKV);
check(plResolve.body?.result?.isError === true,
      "player resolve_suggestion is rejected by the handler (DM-tier only)");

// dm lists the pending inbox: sees both player submissions
const wDmList = await rpc("dm-secret",
  callBody(26, "list_suggestions", { status: "pending" }), false, envKV);
const pend = wDmList.body?.result?.structuredContent?.suggestions || [];
check(pend.length === 2 && pend.every((s) => s.status === "pending"),
      "dm list_suggestions returns the pending inbox");
check(pend.some((s) => s.path === "keep.dm.md" && s.tier === "player" &&
                       s.kind === "edit"),
      "a stored edit carries the submitter tier and the raw path verbatim");

// dm accepts: status transitions, resolved timestamp + note recorded
const res = await rpc("dm-secret",
  callBody(27, "resolve_suggestion",
    { id: sugId, action: "accept", note: "good catch" }), false, envKV);
const resolved = res.body?.result?.structuredContent?.suggestion;
check(resolved?.status === "accepted" && !!resolved?.resolved,
      "resolve accept transitions status to accepted and stamps resolved");
const dmAcc = await rpc("dm-secret",
  callBody(28, "list_suggestions", { status: "accepted" }), false, envKV);
check((dmAcc.body?.result?.structuredContent?.suggestions || [])
        .some((s) => s.id === sugId && s.note === "good catch"),
      "accepted suggestion carries the resolver note");
const dmPendAfter = await rpc("dm-secret",
  callBody(29, "list_suggestions", { status: "pending" }), false, envKV);
check((dmPendAfter.body?.result?.structuredContent?.suggestions || [])
        .every((s) => s.id !== sugId),
      "an accepted suggestion leaves the pending queue");

// dropping works, and resolving an unknown id is a clean isError
const drop = await rpc("dm-secret",
  callBody(30, "resolve_suggestion",
    { id: sugP.body.result.structuredContent.id, action: "drop" }),
  false, envKV);
check(drop.body?.result?.structuredContent?.suggestion?.status === "dropped",
      "resolve drop transitions status to dropped");
const resBad = await rpc("dm-secret",
  callBody(31, "resolve_suggestion", { id: "nope", action: "drop" }),
  false, envKV);
check(resBad.body?.result?.isError === true,
      "resolve on an unknown id returns isError (no crash)");

// argument validation on the write tools
const sugBad = await rpc("player-secret",
  callBody(32, "suggest_edit", { path: "keep.dm.md" }), false, envKV);
check(sugBad.body?.result?.isError === true,
      "suggest_edit without a suggestion returns isError");
const listBad = await rpc("dm-secret",
  callBody(33, "list_suggestions", { status: "bogus" }), false, envKV);
check(listBad.body?.result?.isError === true,
      "list_suggestions with a bad status returns isError");

// the firewall still holds under the write env: a player still cannot
// read the DM page, and nothing the write path did reached canon
const plReadAfter = await rpc("player-secret",
  callBody(34, "read_page", { path: "keep.dm.md" }), false, envKV);
check(textOf(plReadAfter).startsWith("no such page"),
      "read firewall intact after writes: player cannot read the DM page");

// ---- graceful degradation: INBOX unbound (default env) ----
const dmToolsNoKV = await rpc("dm-secret",
  { jsonrpc: "2.0", id: 35, method: "tools/list" });
const noKV = dmToolsNoKV.body?.result?.tools?.map((x) => x.name) || [];
check(!noKV.includes("suggest_edit") && !noKV.includes("suggest_page") &&
      !noKV.includes("list_suggestions"),
      "INBOX unbound: no write tool is advertised (read-only campaign)");
const sugNoKV = await rpc("player-secret",
  callBody(36, "suggest_edit", { path: "a", suggestion: "b" }));
check(sugNoKV.body?.result?.isError === true &&
      textOf(sugNoKV).includes("not enabled"),
      "INBOX unbound: suggest_edit returns a clean not-enabled error");

// ---- bug 2: prototype-key pages are a clean miss, not garbage ----
// pages[key] would resolve __proto__/constructor/hasOwnProperty to
// Object.prototype and return "# undefined"; hasOwn must reject them.
for (const key of ["__proto__", "constructor", "hasOwnProperty",
                   "toString"]) {
  const r = await rpc("dm-secret", callBody(40, "read_page", { path: key }));
  check(textOf(r).startsWith("no such page"),
        `read_page("${key}") is a clean miss, not prototype garbage`);
  const f = await rpc("dm-secret", callBody(41, "fetch", { id: key }));
  check(textOf(f).startsWith("no such page") &&
        f.body?.result?.structuredContent === undefined,
        `fetch("${key}") is a clean miss with no structured leak`);
  const rp = await restGet("dm-secret", `/api/page?id=${key}`);
  check(rp.status === 404, `REST /page?id=${key} is 404, not prototype garbage`);
}

// ---- bug 1: witness writes are length- and count-bounded ----
const bigSug = await rpc("player-secret",
  callBody(42, "suggest_edit",
    { path: "keep.md", suggestion: "x".repeat(20000) }), false, envKV);
check(bigSug.body?.result?.isError === true &&
      textOf(bigSug).includes("limit"),
      "suggest_edit rejects an oversize suggestion (per-field length cap)");
const bigPath = await rpc("player-secret",
  callBody(43, "suggest_edit",
    { path: "k".repeat(600), suggestion: "ok" }), false, envKV);
check(bigPath.body?.result?.isError === true &&
      textOf(bigPath).includes("limit"),
      "suggest_edit rejects an oversize path");
const bigContent = await rpc("player-secret",
  callBody(44, "suggest_page",
    { title: "t", content: "y".repeat(20000) }), false, envKV);
check(bigContent.body?.result?.isError === true &&
      textOf(bigContent).includes("limit"),
      "suggest_page rejects oversize content (per-field length cap)");
const bigRat = await rpc("player-secret",
  callBody(45, "suggest_edit",
    { path: "keep.md", suggestion: "ok", rationale: "z".repeat(5000) }),
  false, envKV);
check(bigRat.body?.result?.isError === true,
      "suggest_edit rejects an oversize rationale");

// ---- bug 3: a corrupt KV value degrades gracefully, never crashes ----
envKV.INBOX._store.set("sug:corrupt", "{ this is not valid json");
const resCorrupt = await rpc("dm-secret",
  callBody(46, "resolve_suggestion", { id: "corrupt", action: "drop" }),
  false, envKV);
check(resCorrupt.body?.result?.isError === true,
      "resolve_suggestion on a corrupt entry is a clean isError (guarded parse)");
const listCorrupt = await rpc("dm-secret",
  callBody(47, "list_suggestions", { status: "all" }), false, envKV);
check(Array.isArray(listCorrupt.body?.result?.structuredContent?.suggestions),
      "list_suggestions skips a corrupt entry without throwing");

// a handler throw returns a JSON-RPC error envelope THROUGH withCors —
// not a bare 500 with no CORS headers. A binding that throws forces it.
const envThrow = { ...env, INBOX: {
  get() { throw new Error("boom"); },
  put() { throw new Error("boom"); },
  list() { throw new Error("boom"); },
} };
const throwRes = await worker.fetch(
  new Request("https://w.example/mcp", {
    method: "POST",
    headers: { "content-type": "application/json",
               Authorization: "Bearer dm-secret" },
    body: JSON.stringify(callBody(48, "list_suggestions", {})) }), envThrow);
check(throwRes.headers.get("Access-Control-Allow-Origin") === "*",
      "a thrown handler error still carries CORS headers");
const throwBody = await throwRes.json();
check(throwBody?.error?.code === -32603 && throwBody?.jsonrpc === "2.0",
      "a thrown handler error returns a JSON-RPC error envelope, not bare 500");

// ---- bug 5: tiered MCP + REST responses set Cache-Control: no-store ----
const ccMcp = await worker.fetch(
  new Request("https://w.example/mcp", {
    method: "POST",
    headers: { "content-type": "application/json",
               Authorization: "Bearer dm-secret" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 49, method: "tools/list" }) }),
  env);
check(ccMcp.headers.get("Cache-Control") === "no-store",
      "MCP responses set Cache-Control: no-store");
const ccRest = await worker.fetch(
  new Request("https://w.example/api/pages", {
    method: "GET", headers: { Authorization: "Bearer dm-secret" } }), env);
check(ccRest.headers.get("Cache-Control") === "no-store",
      "REST responses set Cache-Control: no-store");

process.exit(failures ? 1 : 0);
