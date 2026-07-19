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
 * (list_pages / read_page / search / fetch). All tools are
 * read-only and closed-world, and say so via annotations; results
 * carry portable text plus structuredContent for clients that
 * prefer it. `fetch` is the cross-client canonical reader (some
 * clients expect a search+fetch pair); `read_page` remains.
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

const READ_ONLY = { readOnlyHint: true, destructiveHint: false,
                    idempotentHint: true, openWorldHint: false };

const TOOLS = [
  { name: "list_pages", title: "List wiki pages",
    description: "List every page in the campaign wiki: path and title.",
    inputSchema: { type: "object", properties: {} },
    annotations: READ_ONLY },
  { name: "read_page", title: "Read a wiki page",
    description: "Read one wiki page in full, by path (as returned by " +
                 "list_pages or search).",
    inputSchema: { type: "object", required: ["path"],
                   properties: { path: { type: "string" } } },
    annotations: READ_ONLY },
  { name: "search", title: "Search the wiki",
    description: "Search the wiki. Returns the best-matching pages " +
                 "with snippets; follow up with read_page or fetch.",
    inputSchema: { type: "object", required: ["query"],
                   properties: { query: { type: "string" } } },
    annotations: READ_ONLY },
  { name: "fetch", title: "Fetch a document",
    description: "Fetch one wiki document by id (a path from search " +
                 "or list_pages). Canonical search+fetch counterpart.",
    inputSchema: { type: "object", required: ["id"],
                   properties: { id: { type: "string" } } },
    annotations: READ_ONLY },
];

function searchHits(pages, q) {
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
  return scored.slice(0, MAX_HITS).map(({ path, entry }) => {
    const hay = entry.text.toLowerCase();
    let i = -1;
    for (const t of terms) { i = hay.indexOf(t); if (i !== -1) break; }
    const start = Math.max(0, i - SNIPPET / 2);
    const snip = entry.text.slice(start, start + SNIPPET)
      .replace(/\s+/g, " ").trim();
    return { path, title: entry.title, snippet: snip };
  });
}

function text(s) { return { content: [{ type: "text", text: s }] }; }

function structured(s, obj) {
  return { content: [{ type: "text", text: s }], structuredContent: obj };
}

function argError(msg) {
  return { isError: true, content: [{ type: "text", text: msg }] };
}

function callTool(corpus, name, args) {
  const pages = corpus.pages;
  if (name === "list_pages") {
    const lines = Object.entries(pages)
      .map(([p, e]) => `${p} — ${e.title}`);
    return text(lines.join("\n") || "no pages");
  }
  if (name === "read_page") {
    if (typeof (args && args.path) !== "string" || !args.path) {
      return argError("read_page requires 'path' (string)");
    }
    const entry = pages[args.path];
    if (!entry) return text(`no such page: ${args.path}`);
    return text(`# ${entry.title}\n(${args.path})\n\n${entry.text}`);
  }
  if (name === "fetch") {
    if (typeof (args && args.id) !== "string" || !args.id) {
      return argError("fetch requires 'id' (string)");
    }
    const entry = pages[args.id];
    if (!entry) return text(`no such page: ${args.id}`);
    return structured(
      `# ${entry.title}\n(${args.id})\n\n${entry.text}`,
      { id: args.id, title: entry.title, text: entry.text,
        url: `eddic:${args.id}`, metadata: {} });
  }
  if (name === "search") {
    if (typeof (args && args.query) !== "string" || !args.query.trim()) {
      return argError("search requires 'query' (non-empty string)");
    }
    const q = args.query.toLowerCase().trim();
    const hits = searchHits(pages, q);
    if (!hits.length) {
      return structured(`nothing found for: ${q}`, { results: [] });
    }
    const out = hits.map((h) => `${h.path} — ${h.title}\n  …${h.snippet}…`);
    return structured(out.join("\n\n"), {
      results: hits.map((h) => ({ id: h.path, title: h.title,
                                  url: `eddic:${h.path}`,
                                  snippet: h.snippet })),
    });
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

// REST facade for clients that speak OpenAPI, not MCP (Custom GPT
// Actions). Read-only GETs, same tiers, same walls, same corpus.
function rest(corpus, url) {
  const p = url.pathname;
  const route = p.slice(p.indexOf("/api/") + 4);
  if (route === "/pages") {
    return Response.json({ pages: Object.entries(corpus.pages)
      .map(([id, e]) => ({ id, title: e.title })) });
  }
  if (route === "/page") {
    const id = url.searchParams.get("id") || "";
    const entry = corpus.pages[id];
    if (!entry) {
      return Response.json({ error: `no such page: ${id}` },
                           { status: 404 });
    }
    return Response.json({ id, title: entry.title, text: entry.text });
  }
  if (route === "/search") {
    const q = (url.searchParams.get("q") || "").toLowerCase().trim();
    if (!q) {
      return Response.json({ error: "q required" }, { status: 400 });
    }
    return Response.json({ results: searchHits(corpus.pages, q)
      .map((h) => ({ id: h.path, title: h.title, snippet: h.snippet })) });
  }
  return Response.json({ error: "no such endpoint" }, { status: 404 });
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Authorization, Content-Type, Accept, Mcp-Session-Id, " +
    "Mcp-Protocol-Version",
  "Access-Control-Expose-Headers": "Mcp-Session-Id",
  "Access-Control-Max-Age": "86400",
};

// Every response carries CORS, and the preflight is answered without
// auth: browser-based MCP connectors (e.g. claude.ai) send an OPTIONS
// preflight and abort if it lacks Access-Control-* headers. curl skips
// the preflight — which is why the endpoint can pass a curl check yet
// refuse to attach as a connector.
function withCors(resp) {
  const r = new Response(resp.body, resp);
  for (const k in CORS) r.headers.set(k, CORS[k]);
  return r;
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    return withCors(await this._handle(request, env));
  },
  async _handle(request, env) {
    // Do not advertise OAuth. Auth-discovery probes (/.well-known/...)
    // return 404, not 401 — a 401 makes a connector (e.g. claude.ai)
    // believe there is a sign-in service and attempt OAuth client
    // registration, which then fails. 404 says "no OAuth here", so the
    // connector uses the bearer token carried in the URL directly.
    if (new URL(request.url).pathname.includes("/.well-known/")) {
      return new Response("not found", { status: 404 });
    }
    const t = tier(request, env);
    if (!t) return new Response("unauthorized", { status: 401 });
    const url = new URL(request.url);
    if (url.pathname.includes("/api/")) {
      if (request.method !== "GET") {
        return new Response("read-only API: GET only",
                            { status: 405, headers: { Allow: "GET" } });
      }
      return rest(t === "dm" ? CORPUS_DM : CORPUS_PLAYER, url);
    }
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
