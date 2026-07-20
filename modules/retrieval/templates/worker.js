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
 * The same token path also serves the player companion page at
 * GET /<token>/companion — the self-documenting handoff (persona,
 * setup, and the caller's own MCP URL, filled per request from the
 * authenticated token). Bundled from companion.mjs by `eddic stage`.
 *
 * MCP: streamable HTTP, JSON-RPC 2.0, tools only
 * (list_pages / read_page / search / fetch). All tools are
 * read-only and closed-world, and say so via annotations; results
 * carry portable text plus structuredContent for clients that
 * prefer it. `fetch` is the cross-client canonical reader (some
 * clients expect a search+fetch pair); `read_page` remains.
 *
 * Optional witness write path (when the INBOX KV namespace is bound):
 * suggest_edit / suggest_page let any tier file a *pending suggestion*
 * into a review inbox — never canon, never a player-visible surface —
 * and list_suggestions / resolve_suggestion (DM tier only) let the DM
 * triage it. The worker cannot write the repo; it only writes KV, and
 * an accepted suggestion is still promoted out of band by the owner
 * (`eddic suggestions`). No INBOX binding => the campaign stays
 * read-only and no write tool is advertised or callable.
 */

import CORPUS_DM from "./corpus_dm.mjs";
import CORPUS_PLAYER from "./corpus_player.mjs";
import COMPANION from "./companion.mjs";

const PROTOCOL = "2025-06-18";
const SNIPPET = 120;
const MAX_HITS = 8;

// Resolve the request's tier and the concrete token it authenticated
// with — the token is what the companion page needs to build a caller's
// own capability URL, so we return it rather than discarding it.
function auth(request, env) {
  const a = request.headers.get("Authorization") || "";
  const bearer = a.startsWith("Bearer ") ? a.slice(7).trim() : null;
  const seg = new URL(request.url).pathname.split("/").filter(Boolean)[0];
  for (const [token, name] of [[env.TOKEN_DM, "dm"],
                               [env.TOKEN_PLAYER, "player"]]) {
    if (token && bearer === token) return { tier: name, token };
    if (token && seg === token) return { tier: name, token };
  }
  return { tier: null, token: null };
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

// The witness write path. Every write is a *pending suggestion* in a
// KV-backed review inbox (env.INBOX) — never canon, never a player-
// visible surface. Only the owner promotes a suggestion, out of band
// (see `eddic suggestions`). suggest_* are open to any valid tier;
// list_suggestions / resolve_suggestion are DM-tier only, enforced in
// the handler as well as omitted from a non-DM tools/list. A write
// tool is not "read-only" but is closed-world (it never reaches beyond
// the campaign's own inbox).
const WRITE = { readOnlyHint: false, destructiveHint: false,
                idempotentHint: false, openWorldHint: false };
const READ_INBOX = { readOnlyHint: true, destructiveHint: false,
                     idempotentHint: true, openWorldHint: false };

// Any valid tier may file a suggestion.
const WRITE_TOOLS = [
  { name: "suggest_edit", title: "Suggest an edit",
    description: "Propose a change to a wiki page. This files a pending " +
      "suggestion for the DM to review — nothing is published and no " +
      "page changes until the DM accepts it out of band. Any page path " +
      "is accepted, whether or not it already exists.",
    inputSchema: { type: "object", required: ["path", "suggestion"],
      properties: { path: { type: "string" },
                    suggestion: { type: "string" },
                    rationale: { type: "string" } } },
    annotations: WRITE },
  { name: "suggest_page", title: "Suggest a new page",
    description: "Propose a brand-new wiki page. This files a pending " +
      "suggestion for the DM to review — nothing is published until the " +
      "DM accepts it out of band.",
    inputSchema: { type: "object", required: ["title", "content"],
      properties: { title: { type: "string" }, content: { type: "string" },
                    path: { type: "string" }, rationale: { type: "string" } } },
    annotations: WRITE },
];

// DM tier only: the review inbox itself.
const DM_TOOLS = [
  { name: "list_suggestions", title: "List review suggestions",
    description: "DM only. List submissions in the review inbox, " +
      "optionally filtered by status (pending, accepted, dropped, all; " +
      "default pending).",
    inputSchema: { type: "object",
      properties: { status: { type: "string",
        enum: ["pending", "accepted", "dropped", "all"] } } },
    annotations: READ_INBOX },
  { name: "resolve_suggestion", title: "Resolve a suggestion",
    description: "DM only. Accept or drop a suggestion by id, with an " +
      "optional note. Accepting only marks it for the DM to apply out of " +
      "band; it never writes canon on its own.",
    inputSchema: { type: "object", required: ["id", "action"],
      properties: { id: { type: "string" },
        action: { type: "string", enum: ["accept", "drop"] },
        note: { type: "string" } } },
    annotations: WRITE },
];

const WRITE_NAMES = new Set(WRITE_TOOLS.concat(DM_TOOLS).map((t) => t.name));
const DM_ONLY = new Set(DM_TOOLS.map((t) => t.name));

// tools/list is tier- and INBOX-aware: the four read tools always; the
// two suggest_* for any tier when INBOX is bound; the two review tools
// only for the DM tier. With no INBOX binding the campaign is read-only
// and no write tool is advertised (graceful degradation).
function toolsFor(env, tier) {
  const tools = TOOLS.slice();
  if (env.INBOX) {
    tools.push(...WRITE_TOOLS);
    if (tier === "dm") tools.push(...DM_TOOLS);
  }
  return tools;
}

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

async function callTool(env, tier, corpus, name, args) {
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
  // The witness write path. Gated on the INBOX binding, and — for the
  // review tools — on the DM tier, enforced HERE in the handler, not
  // only by omission from a non-DM tools/list. A player token that
  // calls list_suggestions / resolve_suggestion is refused outright.
  if (WRITE_NAMES.has(name)) {
    if (!env.INBOX) return inboxError();
    if (DM_ONLY.has(name) && tier !== "dm") {
      return argError(`${name} is available to the DM tier only`);
    }
    return writeTool(env, tier, name, args || {});
  }
  return { isError: true,
           content: [{ type: "text", text: `unknown tool: ${name}` }] };
}

function inboxError() {
  return { isError: true, content: [{ type: "text",
    text: "writeable retrieval is not enabled for this campaign" }] };
}

// Warm, id-bearing confirmation for a filed suggestion. The message
// carries a short id (first 8 chars); structuredContent carries the
// full id a client can quote back.
function confirm(id) {
  return structured(
    `Filed for the DM's review — suggestion ${id.slice(0, 8)}.`,
    { id, status: "pending" });
}

// Append a pending submission to the KV inbox. crypto.randomUUID and
// Date are both available in the Workers runtime. Key: sug:<id>.
async function appendSuggestion(env, rec) {
  const id = crypto.randomUUID();
  const value = { id, ...rec, status: "pending",
                  created: new Date().toISOString() };
  await env.INBOX.put(`sug:${id}`, JSON.stringify(value));
  return id;
}

// Read the whole inbox (paginated list + per-key get). Small by nature
// — a review queue, not a corpus.
async function readInbox(env) {
  const out = [];
  let cursor;
  do {
    const page = await env.INBOX.list({ prefix: "sug:", cursor });
    for (const k of page.keys) {
      const raw = await env.INBOX.get(k.name);
      if (raw) { try { out.push(JSON.parse(raw)); } catch { /* skip */ } }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return out;
}

async function writeTool(env, tier, name, args) {
  if (name === "suggest_edit") {
    if (typeof args.path !== "string" || !args.path.trim()) {
      return argError("suggest_edit requires 'path' (non-empty string)");
    }
    if (typeof args.suggestion !== "string" || !args.suggestion.trim()) {
      return argError(
        "suggest_edit requires 'suggestion' (non-empty string)");
    }
    // NO existence oracle: the path is stored verbatim and never checked
    // against the corpus. A player must not be able to probe which
    // DM-only pages exist by watching suggest_edit succeed or fail.
    const id = await appendSuggestion(env, {
      kind: "edit", tier, path: args.path, suggestion: args.suggestion,
      rationale: typeof args.rationale === "string" ? args.rationale : "" });
    return confirm(id);
  }
  if (name === "suggest_page") {
    if (typeof args.title !== "string" || !args.title.trim()) {
      return argError("suggest_page requires 'title' (non-empty string)");
    }
    if (typeof args.content !== "string" || !args.content.trim()) {
      return argError("suggest_page requires 'content' (non-empty string)");
    }
    const id = await appendSuggestion(env, {
      kind: "page", tier, title: args.title, content: args.content,
      path: typeof args.path === "string" ? args.path : "",
      rationale: typeof args.rationale === "string" ? args.rationale : "" });
    return confirm(id);
  }
  if (name === "list_suggestions") {
    const want = typeof args.status === "string" ? args.status : "pending";
    if (!["pending", "accepted", "dropped", "all"].includes(want)) {
      return argError("list_suggestions 'status' must be one of: " +
                      "pending, accepted, dropped, all");
    }
    const all = await readInbox(env);
    const rows = want === "all" ? all : all.filter((s) => s.status === want);
    rows.sort((a, b) => (a.created || "").localeCompare(b.created || ""));
    const lines = rows.map((s) =>
      `${s.id}  [${s.status}] ${s.kind} — ` +
      (s.kind === "page" ? (s.title || "(untitled)") : s.path));
    return structured(
      lines.join("\n") ||
        `no ${want === "all" ? "" : want + " "}suggestions`,
      { suggestions: rows });
  }
  if (name === "resolve_suggestion") {
    if (typeof args.id !== "string" || !args.id.trim()) {
      return argError("resolve_suggestion requires 'id' (string)");
    }
    if (args.action !== "accept" && args.action !== "drop") {
      return argError(
        "resolve_suggestion 'action' must be 'accept' or 'drop'");
    }
    const raw = await env.INBOX.get(`sug:${args.id}`);
    if (!raw) return argError(`no such suggestion: ${args.id}`);
    const rec = JSON.parse(raw);
    rec.status = args.action === "accept" ? "accepted" : "dropped";
    rec.resolved = new Date().toISOString();
    if (typeof args.note === "string" && args.note) rec.note = args.note;
    await env.INBOX.put(`sug:${args.id}`, JSON.stringify(rec));
    return structured(`Suggestion ${args.id.slice(0, 8)} ${rec.status}.`,
                      { suggestion: rec });
  }
  return argError(`unknown tool: ${name}`);
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
    const { tier: t, token } = auth(request, env);
    // No valid token -> not an MCP/REST request. Serve the static site
    // (the player projection rendered to HTML) from the ASSETS binding.
    // One host: humans get the site at /, agents get MCP at /<token>/mcp.
    if (!t) return env.ASSETS.fetch(request);
    const url = new URL(request.url);
    // Companion page: GET /<token>/companion serves the self-documenting
    // player kit — persona, setup, and this caller's own MCP URL. Token-
    // gated exactly like MCP (we only reach here with a valid tier). The
    // MCP URL is filled per request from the authenticated token, so no
    // token is ever baked into the bundled page.
    const seg = url.pathname.split("/").filter(Boolean);
    if (seg[seg.length - 1] === "companion" && seg.length <= 2) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return new Response("companion page: GET only",
                            { status: 405, headers: { Allow: "GET, HEAD" } });
      }
      const mcpUrl = `${url.origin}/${token}/mcp`;
      const page = COMPANION.html.split("{{PLAYER_MCP_URL}}").join(mcpUrl);
      // no-store: the page is token-bearing and filled per request, so
      // it must never be edge-cached (and a cached probe must never be
      // replayed for it).
      return new Response(request.method === "HEAD" ? null : page,
        { status: 200, headers: { "content-type": "text/html; charset=utf-8",
          "Cache-Control": "no-store" } });
    }
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
      return rpcResponse(msg.id, { tools: toolsFor(env, t) });
    }
    if (msg.method === "tools/call") {
      const { name, arguments: args } = msg.params || {};
      return rpcResponse(msg.id,
        await callTool(env, t, corpus, name, args || {}));
    }
    if (msg.method === "ping") return rpcResponse(msg.id, {});
    return rpcError(msg.id ?? null, -32601,
                    `method not found: ${msg.method}`);
  },
};
