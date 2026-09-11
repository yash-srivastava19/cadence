"""The dashboard itself: one file, no build step, no dependencies.

A string rather than a template: nothing in it is filled in from Python.
Every number on the page comes from the same JSON `cadence runs list --json`
prints, fetched by the page after it loads, which is why there is exactly one
place where a shape is decided and it is `core/dto.py`.

Kept in one file because a dashboard that needs npm installed is a dashboard
that stops working the first week nobody runs it.
"""

__all__ = ["PAGE_HTML"]

PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>cadence</title>
<style>
  :root {
    --bg: #0f1115; --panel: #161920; --line: #262b36; --ink: #d7dae1;
    --dim: #7b8394; --accent: #7aa2f7; --good: #7fd88f; --bad: #f7768e;
    --warn: #e0af68; --add: #1d3226; --del: #34181d;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f7f8fa; --panel: #fff; --line: #e2e5ea; --ink: #1c2030;
      --dim: #6b7280; --accent: #2f5bd8; --good: #197a3d; --bad: #c0334a;
      --warn: #8a6100; --add: #e3f7e8; --del: #fdeaee;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 13px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif;
  }
  code, pre, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  #shell { display: grid; grid-template-columns: 210px 1fr; height: 100vh; }
  #rail {
    border-right: 1px solid var(--line); background: var(--panel);
    overflow-y: auto; padding: 12px 0;
  }
  #rail h1 {
    font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
    color: var(--dim); margin: 0 14px 10px; font-weight: 600;
  }
  .exp {
    padding: 7px 14px; cursor: pointer; border-left: 2px solid transparent;
    display: flex; justify-content: space-between; gap: 8px; align-items: baseline;
  }
  .exp:hover { background: rgba(122,162,247,.08); }
  .exp.on { border-left-color: var(--accent); background: rgba(122,162,247,.12); }
  .exp b { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .exp span { color: var(--dim); font-size: 11px; flex: none; }
  #main { overflow-y: auto; padding: 18px 22px 60px; }
  h2 { font-size: 15px; margin: 0 0 10px; font-weight: 600; }
  h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .1em;
       color: var(--dim); margin: 26px 0 8px; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; font-size: 11px; text-transform: uppercase;
    letter-spacing: .08em; color: var(--dim); font-weight: 600;
    padding: 6px 10px; border-bottom: 1px solid var(--line);
  }
  td { padding: 6px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tbody tr { cursor: pointer; }
  tbody tr:hover { background: rgba(122,162,247,.07); }
  tbody tr.on { background: rgba(122,162,247,.14); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .dim { color: var(--dim); }
  .pill {
    font-size: 11px; padding: 1px 7px; border-radius: 10px;
    border: 1px solid var(--line); white-space: nowrap;
  }
  .pill.running { color: var(--accent); border-color: var(--accent); }
  .pill.finished, .pill.scored { color: var(--good); border-color: var(--good); }
  .pill.failed, .pill.abandoned, .pill.crashed { color: var(--bad); border-color: var(--bad); }
  .pill.stalled, .pill.retried { color: var(--warn); border-color: var(--warn); }
  #cards { display: flex; flex-wrap: wrap; gap: 10px; margin: 4px 0 2px; }
  .card {
    background: var(--panel); border: 1px solid var(--line); border-radius: 7px;
    padding: 8px 13px; min-width: 96px;
  }
  .card .k { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--dim); }
  .card .v { font-size: 17px; font-variant-numeric: tabular-nums; margin-top: 2px; }
  pre.diff, pre.src {
    background: var(--panel); border: 1px solid var(--line); border-radius: 7px;
    padding: 0; overflow-x: auto; font-size: 12px; margin: 0;
  }
  pre.diff div { padding: 0 12px; white-space: pre; }
  pre.src { padding: 12px; white-space: pre; }
  .add { background: var(--add); }
  .del { background: var(--del); }
  .hunk { color: var(--accent); }
  .meta { color: var(--dim); }
  a { color: var(--accent); cursor: pointer; text-decoration: none; }
  #crumbs { margin-bottom: 14px; color: var(--dim); }
  .empty { color: var(--dim); padding: 14px 0; }
  details > summary { cursor: pointer; color: var(--dim); margin: 10px 0; }
</style>
</head>
<body>
<div id="shell">
  <nav id="rail"><h1>Experiments</h1><div id="exps"></div></nav>
  <main id="main"><div id="crumbs"></div><div id="body" class="empty">loading…</div></main>
</div>
<script>
const $ = (id) => document.getElementById(id);
// What the page is looking at. One object, so a refresh is just "draw this
// again" and there is no second copy of the answer to keep in step.
let at = { experiment: null, run: null, trial: null };
let timer = null;

const get = async (path) => {
  const r = await fetch(path);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
};

const esc = (s) => String(s ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
// Fingerprints only. A run id starts with its date, so the first eight
// characters of ten runs from the same day are the same eight characters --
// truncating one is how a listing becomes ten identical rows.
const short = (s, n = 12) => s ? esc(String(s).slice(0, n)) : '<span class="dim">–</span>';
const pill = (s) => `<span class="pill ${esc(s).toLowerCase()}">${esc(s)}</span>`;

const when = (iso) => {
  if (!iso) return "–";
  const d = new Date(iso), mins = (Date.now() - d) / 60000;
  if (mins < 1) return "just now";
  if (mins < 60) return Math.round(mins) + "m ago";
  if (mins < 1440) return Math.round(mins / 60) + "h ago";
  return d.toLocaleDateString();
};
const dur = (ms) => {
  if (ms == null) return "–";
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + "s";
  if (s < 3600) return Math.floor(s / 60) + "m " + Math.round(s % 60) + "s";
  return (s / 3600).toFixed(1) + "h";
};
const money = (u) => u == null ? "unpriced" : "$" + Number(u).toFixed(4);
const metrics = (m) => m && Object.keys(m).length
  ? Object.entries(m).map(([k, v]) =>
      `<span class="dim">${esc(k)}</span> ${typeof v === "number" ? v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "") : esc(v)}`
    ).join(" &nbsp; ")
  : '<span class="dim">–</span>';

const card = (k, v) => `<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`;

// --- drawing ------------------------------------------------------------

async function drawExperiments() {
  const rows = await get("/api/experiments");
  $("exps").innerHTML =
    `<div class="exp ${at.experiment === null ? "on" : ""}" data-x=""><b>All runs</b></div>` +
    rows.map(e => `
      <div class="exp ${at.experiment === e.name ? "on" : ""}" data-x="${esc(e.name)}">
        <b title="${esc(e.name)}">${esc(e.name)}</b>
        <span>${e.running ? "● " : ""}${e.runs}</span>
      </div>`).join("");
  $("exps").querySelectorAll(".exp").forEach(el =>
    el.onclick = () => { at = { experiment: el.dataset.x || null, run: null, trial: null }; draw(); });
}

async function drawRuns() {
  const q = at.experiment ? "?experiment=" + encodeURIComponent(at.experiment) : "";
  const rows = await get("/api/runs" + q);
  $("crumbs").innerHTML = at.experiment ? esc(at.experiment) : "All runs";
  if (!rows.length) { $("body").innerHTML = '<div class="empty">no runs recorded</div>'; return; }
  $("body").innerHTML = `<table><thead><tr>
      <th>run</th><th>status</th><th class="num">trials</th><th>best</th>
      <th>experiment</th><th>owner</th><th>started</th></tr></thead><tbody>${
    rows.map(r => `<tr data-id="${esc(r.id)}">
      <td class="mono">${esc(r.id)}</td>
      <td>${pill(r.stalled ? "stalled" : r.status)}</td>
      <td class="num">${r.trials}</td>
      <td class="mono">${short(r.best, 8)}</td>
      <td>${esc(r.experiment || "–")}</td>
      <td class="dim">${esc(r.owner || "–")}</td>
      <td class="dim">${when(r.started_at)}</td></tr>`).join("")}</tbody></table>`;
  $("body").querySelectorAll("tr[data-id]").forEach(tr =>
    tr.onclick = () => { at.run = tr.dataset.id; at.trial = null; draw(); });
}

async function drawRun() {
  const [run, trials] = await Promise.all([
    get("/api/runs/" + encodeURIComponent(at.run)),
    get("/api/runs/" + encodeURIComponent(at.run) + "/trials?limit=500"),
  ]);
  $("crumbs").innerHTML = `<a id="back">← ${esc(run.experiment || "all runs")}</a>`;
  $("body").innerHTML = `
    <h2 class="mono">${esc(run.id)} &nbsp; ${pill(run.stalled ? "stalled" : run.status)}</h2>
    <div id="cards">
      ${card("trials", run.trials)}
      ${card("scored", run.scored)}
      ${card("elapsed", dur(run.duration_ms))}
      ${card("calls", run.spend.calls + (run.spend.replayed ? ` <span class="dim" style="font-size:12px">${run.spend.replayed} replayed</span>` : ""))}
      ${card("tokens", (run.spend.tokens_in + run.spend.tokens_out).toLocaleString())}
      ${card("spent", money(run.spend.usd))}
    </div>
    ${run.reason ? `<p class="dim">${esc(run.reason)}</p>` : ""}
    <h3>Trials</h3>
    ${trials.length ? `<table><thead><tr>
      <th class="num">#</th><th>status</th><th>outcome</th><th>metrics</th>
      <th>candidate</th><th>why</th></tr></thead><tbody>${
      trials.map(t => `<tr data-id="${esc(t.id)}" class="${t.id === at.trial ? "on" : ""}">
        <td class="num">${t.seq}</td>
        <td>${pill(t.status)}</td>
        <td>${t.outcome ? pill(t.outcome) : '<span class="dim">–</span>'}</td>
        <td class="mono">${metrics(t.metrics)}</td>
        <td class="mono">${short(t.candidate, 8)}</td>
        <td class="dim">${esc(t.reason || "")}</td></tr>`).join("")}</tbody></table>`
      : '<div class="empty">no trials yet</div>'}
    <div id="trial"></div>
    ${run.manifest ? `<details><summary>manifest</summary><pre class="src">${esc(run.manifest)}</pre></details>` : ""}`;
  $("back").onclick = () => { at.run = null; at.trial = null; draw(); };
  $("body").querySelectorAll("tr[data-id]").forEach(tr =>
    tr.onclick = () => { at.trial = at.trial === tr.dataset.id ? null : tr.dataset.id; draw(); });
  if (at.trial) await drawTrial();
}

async function drawTrial() {
  const t = await get("/api/trials/" + encodeURIComponent(at.trial));
  $("trial").innerHTML = `
    <h3>Trial ${t.seq}</h3>
    <div id="cards">
      ${card("attempts", t.attempts)}
      ${card("measured", dur(t.wall_ms))}
      ${card("model latency", dur(t.latency_ms))}
      ${card("tokens", t.tokens_in == null ? "–" : (t.tokens_in + t.tokens_out).toLocaleString())}
      ${card("cost", t.model ? money(t.cost_usd) : "–")}
      ${card("model", `<span style="font-size:12px">${esc(t.model || "–")}</span>`)}
    </div>
    ${diffHtml(t)}
    ${t.response ? `<details><summary>what the model said</summary><pre class="src">${esc(t.response)}</pre></details>` : ""}
    ${t.code ? `<details><summary>the whole program</summary><pre class="src">${esc(t.code)}</pre></details>` : ""}`;
}

// Four different things, and the page must not render them the same way:
// nothing was ever asked, an answer came back that no patch could be made
// of, a candidate identical to its parent, and an actual change.
function diffHtml(t) {
  if (t.diff === null || t.diff === undefined) {
    // Which of the two "no candidate" cases this is, read off what is
    // there rather than guessed at. A trial that never got an answer and a
    // trial whose patch would not apply both have no candidate, and
    // telling somebody the patch was rejected when no call ever came back
    // sends them to read a diff that was never proposed.
    const why = t.response
      ? "The reply came back, but no patch could be made of it."
      : "No answer came back, so nothing was ever built.";
    return `<p class="empty">No candidate. ${esc(t.reason || why)}</p>`;
  }
  if (!t.diff.trim()) {
    return '<p class="empty">The candidate is identical to its parent.</p>';
  }
  const line = (l) => {
    const c = l.startsWith("+++") || l.startsWith("---") ? "meta"
      : l.startsWith("@@") ? "hunk"
      : l.startsWith("+") ? "add"
      : l.startsWith("-") ? "del" : "";
    return `<div class="${c}">${esc(l) || "&nbsp;"}</div>`;
  };
  return `<pre class="diff">${t.diff.split("\n").map(line).join("")}</pre>`;
}

// --- the loop -----------------------------------------------------------

async function draw() {
  try {
    await drawExperiments();
    if (at.run) await drawRun(); else await drawRuns();
  } catch (e) {
    $("body").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
  // Poll only while something is actually moving. A finished run does not
  // change, and a dashboard that refetches it every five seconds forever is
  // a dashboard nobody leaves open.
  clearTimeout(timer);
  if (document.querySelector(".pill.running")) timer = setTimeout(draw, 5000);
}

draw();
</script>
</body>
</html>
"""
