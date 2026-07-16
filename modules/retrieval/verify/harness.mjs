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
check(tools.body?.result?.tools?.length === 3, "three tools listed");

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

process.exit(failures ? 1 : 0);
