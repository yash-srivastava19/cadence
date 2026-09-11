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
  /* Five colors and two type sizes. Everything else is spacing.
     A status that is coloured does not also need a border, and a number
     that is on its own line does not also need a box around it. */
  :root {
    --bg: #0f1115; --panel: #161920; --line: #262b36; --ink: #d7dae1;
    --dim: #7b8394; --accent: #7aa2f7; --good: #7fd88f; --bad: #f7768e;
    --add: #1d3226; --del: #34181d;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f7f8fa; --panel: #f0f2f5; --line: #e2e5ea; --ink: #1c2030;
      --dim: #6b7280; --accent: #2f5bd8; --good: #197a3d; --bad: #c0334a;
      --add: #e3f7e8; --del: #fdeaee;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 13px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif;
  }
  code, pre, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  #shell { display: grid; grid-template-columns: 200px 1fr; height: 100vh; }
  #rail { border-right: 1px solid var(--line); overflow-y: auto; padding: 18px 0; }
  #rail h1 {
    font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
    color: var(--dim); margin: 0 18px 8px; font-weight: 600;
  }
  .exp {
    padding: 6px 18px; cursor: pointer; color: var(--dim);
    display: flex; justify-content: space-between; gap: 8px; align-items: baseline;
  }
  .exp:hover { color: var(--ink); }
  .exp.on { color: var(--ink); box-shadow: inset 2px 0 var(--accent); }
  .exp b { font-weight: 400; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .exp i { font-style: normal; font-size: 11px; flex: none; }
  #main { overflow-y: auto; padding: 18px 24px 60px; }
  h2 { font-size: 15px; margin: 0 0 6px; font-weight: 600; }
  h3 {
    font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
    color: var(--dim); margin: 30px 0 6px; font-weight: 600;
  }
  /* The six boxes this replaces said the same six numbers. */
  .facts { color: var(--dim); margin: 0 0 18px; }
  .facts b { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }
  .facts span + span::before { content: " · "; color: var(--line); }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; font-size: 11px; text-transform: uppercase;
    letter-spacing: .08em; color: var(--dim); font-weight: 600;
    padding: 5px 10px; border-bottom: 1px solid var(--line);
  }
  td { padding: 5px 10px; border-bottom: 1px solid var(--line); }
  tbody tr { cursor: pointer; }
  tbody tr:hover td { background: rgba(122,162,247,.07); }
  tbody tr.on td { background: rgba(122,162,247,.13); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .dim { color: var(--dim); }
  .bad { color: var(--bad); }
  .live { color: var(--accent); }
  /* The winner, marked where the loop's own choice lands rather than
     inferred from the numbers: the page does not know which way is better. */
  .won { color: var(--good); font-size: 11px; }
  pre.diff, pre.src {
    background: var(--panel); border-radius: 6px; padding: 0;
    overflow-x: auto; font-size: 12px; margin: 0;
  }
  pre.diff div { padding: 0 12px; white-space: pre; }
  pre.src { padding: 12px; white-space: pre; }
  .add { background: var(--add); }
  .del { background: var(--del); }
  .hunk { color: var(--accent); }
  .meta { color: var(--dim); }
  a { color: var(--accent); cursor: pointer; text-decoration: none; }
  #crumbs { margin-bottom: 16px; color: var(--dim); }
  .empty { color: var(--dim); padding: 14px 0; }
  details > summary { cursor: pointer; color: var(--dim); margin: 14px 0 8px; }
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
// Whether what is on screen can still change. Read off the rows rather than
// off the rendered page, so restyling cannot quietly stop the polling.
let moving = false;

const get = async (path) => {
  const r = await fetch(path);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
};

const esc = (s) => String(s ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
// Colour marks the exception, never the norm. Ten trials that all scored
// are ten rows of the same word, and painting them green spends the eye's
// attention on the thing it already expected -- so success is plain, and
// the only green on the page is the one candidate that won.
const BAD = ["failed", "stalled", "crashed", "abandoned", "rejected"];
const state = (s) => {
  const c = s === "running" ? "live" : BAD.includes(s) ? "bad" : "dim";
  return `<span class="${c}">${esc(s)}</span>`;
};

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

// Value first, then what it is: "10 trials" reads; "TRIALS / 10" in a box
// is the same two words with a border drawn round them.
// A fact nobody recorded is left out rather than printed as a dash: six
// dashes in a row is not a summary. Callers pass null for those, so the
// nulls have to go before anything unpacks a pair.
const facts = (pairs) => `<p class="facts">${
  pairs.filter(p => p && p[0] !== null && p[0] !== undefined)
       .map(([v, k]) => `<span><b>${v}</b> ${k}</span>`).join("")}</p>`;

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
  moving = rows.some(r => r.status === "running" && !r.stalled);
  if (!rows.length) { $("body").innerHTML = '<div class="empty">no runs recorded</div>'; return; }
  $("body").innerHTML = `<table><thead><tr>
      <th>run</th><th>status</th><th class="num">trials</th>
      <th>experiment</th><th>owner</th><th>started</th></tr></thead><tbody>${
    rows.map(r => `<tr data-id="${esc(r.id)}">
      <td class="mono">${esc(r.id)}</td>
      <td>${state(r.stalled ? "stalled" : r.status)}</td>
      <td class="num">${r.trials}</td>
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
  moving = run.status === "running" && !run.stalled;
  $("body").innerHTML = `
    <h2 class="mono">${esc(run.id)} &nbsp; ${state(run.stalled ? "stalled" : run.status)}</h2>
    ${facts([
      [run.trials, "trials"],
      [run.scored, "scored"],
      [dur(run.duration_ms), "elapsed"],
      [run.spend.calls, "model calls" + (run.spend.replayed ? ` (${run.spend.replayed} replayed)` : "")],
      [(run.spend.tokens_in + run.spend.tokens_out).toLocaleString(), "tokens"],
      run.spend.usd == null ? null : [money(run.spend.usd), "spent"],
    ])}
    ${run.reason ? `<p class="dim">${esc(run.reason)}</p>` : ""}
    <h3>Trials</h3>
    ${trials.length ? `<table><thead><tr>
      <th class="num">#</th><th>result</th><th>metrics</th><th>why</th>
      </tr></thead><tbody>${
      trials.map(t => `<tr data-id="${esc(t.id)}" class="${t.id === at.trial ? "on" : ""}">
        <td class="num">${t.seq}</td>
        <td>${state(t.outcome || t.status)}${
          t.candidate && t.candidate === run.best ? ' <span class="won">best</span>' : ""}</td>
        <td class="mono">${metrics(t.metrics)}</td>
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
    ${facts([
      t.model ? [esc(t.model), "answered"] : null,
      t.latency_ms == null ? null : [dur(t.latency_ms), "waiting on it"],
      t.tokens_in == null ? null : [(t.tokens_in + t.tokens_out).toLocaleString(), "tokens"],
      t.cost_usd == null ? null : [money(t.cost_usd), "spent"],
      t.wall_ms == null ? null : [dur(t.wall_ms), "measuring"],
      t.attempts > 1 ? [t.attempts, "attempts"] : null,
    ])}
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
  if (moving) timer = setTimeout(draw, 5000);
}

draw();
</script>
</body>
</html>
"""
