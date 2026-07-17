// Node harness for the retrieval worker: imports the staged worker
// and drives its fetch handler directly (no wrangler, no network).
// Usage: node harness.mjs <staged_worker_dir>
import { pathToFileURL } from "node:url";
import { join } from "node:path";

const dir = process.argv[2];
const worker = (await import(pathToFileURL(join(dir, "worker.js")))).default;
const env = { TOKEN_DM: "dm-secret", TOKEN_PLAYER: "player-secret" };

let failures = 0;
function check(ok, msg) {
  console.log((ok ? "ok  " : "FAIL") + " " + msg);
  if (!ok) failures++;
}

async function rpc(token, body, viaPath = false) {
  const url = viaPath
    ? `https://w.example/${token}/mcp`
    : "https://w.example/mcp";
  const headers = { "content-type": "application/json" };
  if (!viaPath && token) headers.Authorization = `Bearer ${token}`;
  const res = await worker.fetch(
    new Request(url, { method: "POST", headers,
                       body: JSON.stringify(body) }), env);
  const isJson = (res.headers.get("content-type") || "").includes("json");
  return { status: res.status, body: isJson ? await res.json() : null };
}

const init = { jsonrpc: "2.0", id: 1, method: "initialize",
               params: { protocolVersion: "2025-06-18" } };

// auth
const noAuth = await worker.fetch(
  new Request("https://w.example/mcp", { method: "POST" }), env);
check(noAuth.status === 401, "no token rejected 401");
const badAuth = await rpc("wrong-token", init);
check(badAuth.status === 401, "wrong token rejected 401");

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
check(restNoAuth.status === 401, "REST without token rejected 401");
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

process.exit(failures ? 1 : 0);
