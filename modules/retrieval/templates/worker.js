/**
 * eddic retrieval worker — a minimal MCP server over the campaign
 * corpus, two tiers behind two bearer tokens.
 *
 * The corpora are bundled at deploy time (corpus_dm.mjs /
 * corpus_player.mjs, written by `eddic stage`) so DM content never
 * sits at a public URL. Auth: `Authorization: Bearer <token>` or a
 * capability-URL path segment (https://.../<token>/mcp) for
 * connector UIs that only accept a URL. TOKEN_DM sees the master,
 * TOKEN_PLAYER sees the projection. Rotation = `wrangler secret put`.
 *
 * MCP: streamable HTTP, JSON-RPC 2.0, tools only
 * (list_pages / read_page / search).
 */

import CORPUS_DM from "./corpus_dm.mjs";
import CORPUS_PLAYER from "./corpus_player.mjs";

const PROTOCOL = "2025-06-18";
const SNIPPET = 120;
const MAX_HITS = 8;

function tier(request, env) {
  const auth = request.headers.get("Authorization") || "";
  const bearer = auth.startsWith("Bearer ") ? auth.slice(7).trim() : null;
  const seg = new URL(request.url).pathname.split("/").filter(Boolean)[0];
  for (const [token, name] of [[env.TOKEN_DM, "dm"],
                               [env.TOKEN_PLAYER, "player"]]) {
    if (token && (bearer === token || seg === token)) return name;
  }
  return null;
}

const TOOLS = [
  { name: "list_pages",
    description: "List every page in the campaign wiki: path and title.",
    inputSchema: { type: "object", properties: {} } },
  { name: "read_page",
    description: "Read one wiki page in full, by path (as returned by " +
                 "list_pages or search).",
    inputSchema: { type: "object", required: ["path"],
                   properties: { path: { type: "string" } } } },
  { name: "search",
    description: "Search the wiki. Returns the best-matching pages " +
                 "with snippets; follow up with read_page.",
    inputSchema: { type: "object", required: ["query"],
                   properties: { query: { type: "string" } } } },
];

function text(s) { return { content: [{ type: "text", text: s }] }; }

function callTool(corpus, name, args) {
  const pages = corpus.pages;
  if (name === "list_pages") {
    const lines = Object.entries(pages)
      .map(([p, e]) => `${p} — ${e.title}`);
    return text(lines.join("\n") || "no pages");
  }
  if (name === "read_page") {
    const entry = pages[(args && args.path) || ""];
    if (!entry) return text(`no such page: ${args && args.path}`);
    return text(`# ${entry.title}\n(${args.path})\n\n${entry.text}`);
  }
  if (name === "search") {
    const q = ((args && args.query) || "").toLowerCase().trim();
    if (!q) return text("empty query");
    const terms = q.split(/\s+/);
    const scored = [];
    for (const [path, entry] of Object.entries(pages)) {
      const hay = (entry.title + "\n" + entry.text).toLowerCase();
      let score = 0;
      for (const t of terms) {
        let i = hay.indexOf(t);
        while (i !== -1) { score++; i = hay.indexOf(t, i + t.length); }
        if (entry.title.toLowerCase().includes(t)) score += 3;
      }
      if (score > 0) scored.push({ path, entry, score });
    }
    scored.sort((a, b) => b.score - a.score);
    if (!scored.length) return text(`nothing found for: ${q}`);
    const out = scored.slice(0, MAX_HITS).map(({ path, entry }) => {
      const hay = entry.text.toLowerCase();
      let i = -1;
      for (const t of terms) { i = hay.indexOf(t); if (i !== -1) break; }
      const start = Math.max(0, i - SNIPPET / 2);
      const snip = entry.text.slice(start, start + SNIPPET)
        .replace(/\s+/g, " ").trim();
      return `${path} — ${entry.title}\n  …${snip}…`;
    });
    return text(out.join("\n\n"));
  }
  return { isError: true,
           content: [{ type: "text", text: `unknown tool: ${name}` }] };
}

function rpcResponse(id, result) {
  return Response.json({ jsonrpc: "2.0", id, result });
}

function rpcError(id, code, message, status = 200) {
  return Response.json(
    { jsonrpc: "2.0", id, error: { code, message } }, { status });
}

export default {
  async fetch(request, env) {
    const t = tier(request, env);
    if (!t) return new Response("unauthorized", { status: 401 });
    if (request.method !== "POST") {
      return new Response("MCP endpoint: POST JSON-RPC here",
                          { status: 405, headers: { Allow: "POST" } });
    }
    let msg;
    try { msg = await request.json(); }
    catch { return rpcError(null, -32700, "parse error", 400); }
    const corpus = t === "dm" ? CORPUS_DM : CORPUS_PLAYER;

    if (msg.method === "initialize") {
      return rpcResponse(msg.id, {
        protocolVersion: msg.params?.protocolVersion || PROTOCOL,
        capabilities: { tools: {} },
        serverInfo: { name: `eddic-${corpus.site || "campaign"}-${t}`,
                      version: "0.1.0" },
      });
    }
    if (typeof msg.method === "string" &&
        msg.method.startsWith("notifications/")) {
      return new Response(null, { status: 202 });
    }
    if (msg.method === "tools/list") {
      return rpcResponse(msg.id, { tools: TOOLS });
    }
    if (msg.method === "tools/call") {
      const { name, arguments: args } = msg.params || {};
      return rpcResponse(msg.id, callTool(corpus, name, args || {}));
    }
    if (msg.method === "ping") return rpcResponse(msg.id, {});
    return rpcError(msg.id ?? null, -32601,
                    `method not found: ${msg.method}`);
  },
};
