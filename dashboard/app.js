// BirdBrain mind observatory: a read-only view over one run's event log.
// Everything shown is derived from events; snapshots (STATE_SNAPSHOT, 2 Hz)
// drive the timeline, and other events are shown up to the snapshot's time.

const $ = (sel) => document.querySelector(sel);
const svg = $("#world-map");
const state = {
  runId: null, live: false, liveRunId: null, events: [], snapshots: [], truths: [], frames: [], generation: 0,
  index: 0, playing: false, follow: true, filter: "mind", selected: null,
  room: [3.0, 2.5], source: null, timer: null,
};

const FILTERS = {
  mind: new Set(["RUN_STARTED", "DECISION", "OUTCOME", "CHOICE_REJECTED", "FALL", "HEARD", "SKILL_WRITTEN",
                 "SKILL_REVIEWED", "RUN_STOPPED", "RUN_FAILED"]),
  skills: new Set(["SKILL_STEP_STARTED", "SKILL_STEP_ENDED", "SKILL_BIND", "EVENT_STARTED", "EVENT_ENDED", "GRASP_TRUTH"]),
  beliefs: new Set(["ENTITY_CREATED", "ASSERTION_OPENED", "ASSERTION_CLOSED"]),
};

const tc = (s) => {
  const tenths = Math.round(s * 10);
  return `${String(Math.floor(tenths / 600)).padStart(2, "0")}:${((tenths % 600) / 10).toFixed(1).padStart(4, "0")}`;
};
const text = (sel, value) => { $(sel).textContent = value; };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// Replace an element's contents only when they changed, keeping its scroll position.
function setHTML(el, html) {
  if (el._html === html) return;
  const top = el.scrollTop;
  el.innerHTML = html;
  el._html = html;
  el.scrollTop = top;
}
const fmtP = (p) => (p === null || p === undefined ? "—" : p.toFixed(2));

// ---- loading ---------------------------------------------------------------
async function loadRuns() {
  const wanted = new URLSearchParams(location.search).get("run");
  const response = await fetch(`/api/runs?limit=300${wanted ? `&include=${encodeURIComponent(wanted)}` : ""}`);
  const { live_run_id, runs } = await response.json();
  state.liveRunId = live_run_id;
  const select = $("#run-select");
  select.innerHTML = runs.map((r) => {
    const res = r.result ? ` · ${r.result.inBasket}/${r.result.toys} in basket` : r.status === "running" ? " · running" : "";
    return `<option value="${esc(r.run_id)}" title="${esc(r.run_id)}">${esc(r.title || r.run_id)}${res}</option>`;
  }).join("");
  const params = new URLSearchParams(location.search);
  const initial = params.get("run") || live_run_id || (runs[0] && runs[0].run_id);
  const at = Number(params.get("t") || NaN);
  if (params.get("truth")) $("#truth-toggle").checked = true;
  if (initial) {
    select.value = initial;
    await open(initial, initial === live_run_id && !params.get("run"));
    if (!Number.isNaN(at)) {
      const i = state.snapshots.findIndex((s) => s.sim_time >= at);
      render(i < 0 ? state.snapshots.length - 1 : i);
    }
  }
}

async function open(runId, live) {
  if (state.source) state.source.close();
  const generation = ++state.generation;      // a newer open() makes this one stop
  Object.assign(state, { runId, live, events: [], snapshots: [], truths: [], frames: [], index: 0, follow: true, selected: null, lastYaw: undefined });
  text("#run-id", runId);
  text("#connection-label", live ? "Live" : "Replay");
  let after = 0;
  for (;;) {
    const page = await (await fetch(`/api/runs/${encodeURIComponent(runId)}/events?after=${after}&limit=10000`)).json();
    if (generation !== state.generation) return;
    page.events.forEach(ingest);
    if (page.events.length < 10000) break;
    after = page.events.at(-1).sequence;
  }
  if (live) {
    state.source = new EventSource("/api/events");
    state.source.addEventListener("birdbrain", (msg) => {
      const e = JSON.parse(msg.data);
      if (e.run_id !== runId || (state.events.length && e.sequence <= state.events.at(-1).sequence)) return;
      ingest(e);
      if (state.follow) scheduleRender();
    });
  }
  render(live ? state.snapshots.length - 1 : 0);
}

function ingest(e) {
  state.events.push(e);
  if (e.type === "STATE_SNAPSHOT") state.snapshots.push(e);
  else if (e.type === "CAMERA_FRAME") state.frames.push(e);
  else if (e.type === "TRUTH" || (e.type === "RUN_STOPPED" && e.payload.truth)) state.truths.push({ t: e.sim_time, ...(e.payload.truth || e.payload) });
  else if (e.type === "RUN_STARTED") {
    if (e.payload.room) state.room = e.payload.room;
    text("#brain-name", e.payload.model || e.payload.provider || "—");
  }
}

// ---- rendering -------------------------------------------------------------
function render(i) {
  if (!state.snapshots.length) return;
  state.index = Math.max(0, Math.min(state.snapshots.length - 1, i));
  state.follow = state.index === state.snapshots.length - 1;
  const snap = state.snapshots[state.index];
  const t = snap.sim_time;
  const tl = $("#timeline");
  tl.max = state.snapshots.length - 1;
  tl.value = state.index;
  text("#sim-time", tc(t));
  text("#timeline-time", `${tc(t)} / ${tc(state.snapshots.at(-1).sim_time)}`);
  text("#replay-state", state.live && state.follow ? "Live tail" : "Rewind the Quack");
  const upTo = state.events.filter((e) => e.sim_time <= t + 1e-9);
  renderWorld(snap, upTo);
  renderCamera(snap);
  renderMind(snap.payload, upTo);
  renderDecisions(upTo);
  renderTables(snap.payload);
  renderNeeds(snap.payload, upTo);
  renderTrace(upTo);
}

function toSvg([x, y]) {
  const [w, h] = state.room;
  const scale = Math.min(560 / w, 460 / h);
  return [300 + x * scale, 250 - y * scale, scale];
}

function renderWorld(snap, upTo) {
  const p = snap.payload;
  const [w, h] = state.room;
  const [x0, y0, s] = toSvg([-w / 2, h / 2]);
  const parts = [`<clipPath id="room-clip"><rect x="${x0}" y="${y0}" width="${w * s}" height="${h * s}" rx="6" /></clipPath>`,
    `<rect class="room" x="${x0}" y="${y0}" width="${w * s}" height="${h * s}" rx="6" />`];
  const trail = state.snapshots.slice(0, state.index + 1).filter((_, k) => k % 2 === 0).map((sn) => toSvg(sn.payload.pose).slice(0, 2).join(","));
  if (trail.length > 1) parts.push(`<polyline class="trail" points="${trail.join(" ")}" />`);
  const target = p.action && Object.values(p.action.args || {})[0];
  for (const e of p.entities) {
    if (e.cls === "place") continue;
    const [ex, ey] = toSvg([e.x, e.y]);
    const r = Math.max(3, e.sigma * s);
    const confident = e.conf >= 0.5;
    if (e.cls === "basket") {
      const half = 0.15 * s;
      parts.push(`<rect class="basket ${confident ? "" : "doubt"}" x="${ex - half}" y="${ey - half}" width="${2 * half}" height="${2 * half}" rx="3"><title>${esc(e.id)}</title></rect>`);
    } else {
      parts.push(`<circle class="sigma" cx="${ex}" cy="${ey}" r="${r}" />`);
      parts.push(`<circle class="entity ${esc(e.cls)} ${confident ? "" : "doubt"} ${e.id === target ? "target" : ""}" cx="${ex}" cy="${ey}" r="5"><title>${esc(e.id)} ±${e.sigma.toFixed(2)} m conf ${e.conf}</title></circle>`);
    }
  }
  if ($("#truth-toggle").checked) {
    const truth = [...state.truths].reverse().find((tr) => tr.t <= snap.sim_time + 1e-9);
    if (truth) {
      if (truth.basket) {
        const [bx, by] = toSvg(truth.basket);
        const half = 0.15 * s;
        parts.push(`<rect class="truth" x="${bx - half}" y="${by - half}" width="${2 * half}" height="${2 * half}" rx="3"><title>basket (truth)</title></rect>`);
      }
      if (truth.duck) {
        const [tx, ty] = toSvg(truth.duck);
        parts.push(`<circle class="truth" cx="${tx}" cy="${ty}" r="10"><title>duck (truth)</title></circle>`);
      }
      for (const toy of truth.toys) {
        const [tx, ty] = toSvg([toy.x, toy.y]);
        parts.push(`<circle class="truth" cx="${tx}" cy="${ty}" r="7"><title>${esc(toy.id)} (truth)</title></circle>`);
      }
    }
  }
  const [dx, dy] = toSvg(p.pose);
  if (p.view) {   // the camera's horizontal field of view, out to 1.5 m
    const a = p.pose[2] + (p.view.cam_yaw || 0), half = (58 * Math.PI) / 180, reach = 1.5;
    const corner = (b) => toSvg([p.pose[0] + reach * Math.cos(a + b), p.pose[1] + reach * Math.sin(a + b)]);
    const [lx, ly] = corner(half), [rx, ry] = corner(-half), rr = reach * s;
    parts.push(`<path class="fov" clip-path="url(#room-clip)" d="M${dx} ${dy} L${lx} ${ly} A${rr} ${rr} 0 0 1 ${rx} ${ry} Z" />`);
  }
  // Unwrap the heading so a turn through ±180° glides the short way round.
  let yaw = (-p.pose[2] * 180) / Math.PI;
  if (state.lastYaw !== undefined) yaw = state.lastYaw + ((((yaw - state.lastYaw) % 360) + 540) % 360) - 180;
  state.lastYaw = yaw;
  if (target) {
    const t = p.entities.find((e) => e.id === target);
    if (t) { const [tx, ty] = toSvg([t.x, t.y]); parts.push(`<line class="aim" x1="${dx}" y1="${dy}" x2="${tx}" y2="${ty}" />`); }
  }
  setHTML(svg.querySelector("#layer") || initMap(), parts.join(""));
  const duck = svg.querySelector("#duck");
  duck.style.setProperty("--step", `${state.playing ? 500 / Number($("#rate").value) : 0}ms`);
  duck.setAttribute("transform", "");
  duck.style.transform = `translate(${dx}px, ${dy}px) rotate(${yaw}deg)`;
}

let pending = false;
function scheduleRender() {          // at most one render per animation frame while live
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => { pending = false; if (state.follow) render(state.snapshots.length - 1); });
}

function renderCamera(snap) {
  const t = snap.sim_time;
  let shot = null;
  for (let k = state.frames.length - 1; k >= 0; k--) { if (state.frames[k].sim_time <= t + 1e-9) { shot = state.frames[k]; break; } }
  const img = $("#camera-image");
  $("#camera-empty").hidden = Boolean(shot);
  img.hidden = !shot;
  if (!shot) { setHTML($("#camera-boxes"), ""); text("#camera-time", "—"); return; }
  const f = shot.payload;
  const src = `/api/runs/${encodeURIComponent(state.runId)}/camera/${f.file}`;
  if (img.getAttribute("src") !== src) img.setAttribute("src", src);
  text("#camera-time", `frame ${tc(f.t)}`);
  // Detections the mind received with the same frame, projected with a pinhole model.
  const view = f.view;               // what the mind made of this very frame
  const boxes = $("#camera-boxes");
  boxes.setAttribute("viewBox", `0 0 ${f.width} ${f.height}`);
  if (!view) { setHTML(boxes, ""); return; }
  const th = Math.tan(f.hfov / 2), tv = Math.tan(f.vfov / 2);
  setHTML(boxes, view.sightings.map((d) => {
    const u = f.width / 2 - (f.width / 2) * Math.tan(d.bearing) / th;
    const v = f.height / 2 - (f.height / 2) * (Math.tan(d.elevation) / Math.cos(d.bearing)) / tv;
    const half = Math.max(5, (f.width / 2) * Math.tan(d.width / 2) / th);
    const label = d.as && d.as !== "not placed" ? d.as : `${d.cls}?`;
    return `<rect class="${d.as === "not placed" ? "unplaced" : ""}" x="${u - half}" y="${v - half}" width="${2 * half}" height="${2 * half}" />`
      + `<text x="${u - half}" y="${Math.max(12, v - half - 4)}">${esc(label)}</text>`;
  }).join(""));
}

function initMap() {
  // The duck is a persistent element above a layer rebuilt each frame, so it can glide.
  svg.innerHTML = `<g id="layer"></g><g class="duck" id="duck"><path d="M14 0 L-9 -8 L-5 0 L-9 8 Z" /></g>`;
  return svg.querySelector("#layer");
}

function renderMind(p, upTo) {
  const a = p.action;
  text("#action", a ? `${a.skill}(${Object.values(a.args || {}).join(", ")})` : "Idle");
  text("#reason", a ? a.reason : "No decision yet.");
  text("#expect", a ? a.expect : "—");
  text("#p-rule", fmtP(a && a.p_rule));
  text("#p-model", fmtP(a && a.p_model));
  $("#p-rule-meter").style.width = `${a && a.p_rule != null ? a.p_rule * 100 : 0}%`;
  $("#p-model-meter").style.width = `${a && a.p_model != null ? a.p_model * 100 : 0}%`;
  text("#note", p.note || "—");
  text("#holding", p.holding || "nothing");
  text("#provider-badge", a ? (a.provider === "local" ? "local policy" : a.provider) : "—");
  const lat = upTo.filter((e) => e.type === "DECISION" && e.payload.provider !== "local").map((e) => e.payload.latency_s).sort((x, y) => x - y);
  const median = lat.length ? lat[Math.floor(lat.length / 2)] : null;
  const s = p.stats || {};
  const chips = [
    ["decisions", s.decisions], ["fallbacks", s.fallbacks], ["rejected", s.invalid], ["errors", s.provider_errors],
    ["tokens", p.tokens], ["latency", median == null ? "—" : `${median.toFixed(2)} s`],
  ];
  setHTML($("#stats"), chips.map(([k, v]) => `<span><b>${esc(k)}</b>${esc(v ?? 0)}</span>`).join(""));
}

function renderDecisions(upTo) {
  const rows = [];
  let open = null;
  for (const e of upTo) {
    if (e.type === "DECISION") { open = { d: e, o: null }; rows.push(open); }
    else if (e.type === "OUTCOME" && open) { open.o = e; open = null; }
  }
  setHTML($("#decision-list"), rows.slice(-14).reverse().map(({ d, o }) => {
    const dp = d.payload;
    const status = o ? o.payload.status : "running";
    const held = o ? (o.payload.effect_held ? "held" : "did not hold") : "";
    const surprise = o && o.payload.surprise_rule != null ? `surprise ${o.payload.surprise_rule.toFixed(2)}` : "";
    return `<li class="${esc(status)} ${dp.fallback ? "fallback" : ""}">
      <time>${tc(d.sim_time)}</time>
      <strong>${esc(dp.skill)}(${esc(Object.values(dp.args || {}).join(", "))})${dp.variant_of ? ` <em>in place of ${esc(dp.variant_of)}</em>` : ""}</strong>
      <span>${esc(dp.reason)}</span>
      <em>${esc(dp.provider)}${dp.fallback ? ` · fallback: ${esc(dp.fallback)}` : ""} · p ${fmtP(dp.p_model ?? dp.p_rule)}</em>
      <em class="outcome">${esc(status)}${o && o.payload.reason ? ` (${esc(o.payload.reason)})` : ""}${held ? ` · effect ${held}` : ""} ${surprise}</em>
    </li>`;
  }).join(""));
}

function renderTables(p) {
  // Milestone 4: credible rules, as the cloud brain reads them.
  setHTML($("#rule-list"), (p.rules || []).map((r) => `<li>${esc(r)}</li>`).join(""));
  // Milestone 5: skills the cloud brain wrote, the situation each is for, and how they are doing.
  setHTML($("#written-list"), (p.written_skills || []).map((w) =>
    `<li><b>${esc(w.skill)}</b> <span class="status-${esc(w.status)}">${esc(w.status)}</span> · for ${esc(w.for)}<br>`
    + `written: ${esc(w.written)} · original: ${esc(w.parent)}<br><i>${esc(w.doc)}</i></li>`).join(""));
  // Skills named w_… were written by the cloud brain (Milestone 5); their description is on hover.
  const written = Object.fromEntries((p.written_skills || []).map((w) => [w.skill, w]));
  setHTML($("#skill-rows"), Object.entries(p.records || {}).map(([name, r]) =>
    `<tr><td class="skill-name" title="${esc(written[name] ? `${written[name].doc} (for ${written[name].for}; ${written[name].status})` : name)}">${esc(name)}${written[name] ? '<span class="written-tag">WRITTEN</span>' : ""}</td><td>${r.trials}</td><td>${r.effect_held}</td><td>${r.p.toFixed(2)}</td><td>${r.mean_s ?? "—"}</td></tr>`).join(""));
  setHTML($("#belief-rows"), (p.entities || []).filter((e) => e.cls !== "place").map((e) =>
    `<tr class="${e.conf >= 0.5 ? "" : "doubt"}"><td>${esc(e.id)}</td><td>${e.x.toFixed(2)}, ${e.y.toFixed(2)}</td><td>${e.sigma.toFixed(2)}</td><td>${e.conf.toFixed(2)}</td><td>${e.seen_ago.toFixed(0)} s</td></tr>`).join(""));
}

// Needs are pressures (0 satisfied, 1 urgent; tidiness is weighted and can reach 2).
// The scorecard is the one the latest decision saw; the chosen goal is marked.
function renderNeeds(p, upTo) {
  const needs = p.needs;
  if (!needs) {
    setHTML($("#need-bars"), "");
    setHTML($("#score-rows"), "");
    setHTML($("#owner-rows"), "");
    $("#owner-table").hidden = true;
    text("#battery", "—");
    text("#goal-now", "No needs in this run (it was given a task).");
    return;
  }
  const bar = (name, value, max, cls = "") =>
    `<span>${esc(name)}</span><span class="bar ${cls}"><i style="width:${Math.min(100, (100 * value) / max)}%"></i></span><code>${value.toFixed(2)}</code>`;
  setHTML($("#need-bars"), Object.entries(needs.pressure).map(([k, v]) => bar(k, v, k === "tidiness" ? 2 : 1)).join("")
    + bar("battery", needs.battery, 1, "battery"));
  text("#battery", `battery ${Math.round(needs.battery * 100)}%`);
  let decision = null;
  for (let k = upTo.length - 1; k >= 0; k--) { if (upTo[k].type === "DECISION") { decision = upTo[k]; break; } }
  const d = decision && decision.payload;
  const goal = p.goal;
  setHTML($("#goal-now"), goal
    ? `Pursuing <b>${esc(goal.id)}</b> for ${esc(goal.source)}${d ? `, chosen by ${esc(d.provider)}${d.agrees_with_scorecard ? " (the scorecard's top goal)" : " (not the scorecard's top goal)"}` : ""}.`
    : "No goal yet.");
  setHTML($("#score-rows"), ((d && d.scorecard) || []).map((g) =>
    `<tr class="${goal && g.id === goal.id ? "chosen" : ""}"><td>${esc(g.id)}</td><td>${g.U.toFixed(2)}</td><td>${g.dV.toFixed(2)}</td><td>${g.C.toFixed(2)}</td><td>${g.R.toFixed(2)}</td></tr>`).join(""));
  // Milestone 3b: what the duck believes each kind of action earns from its owner.
  const model = Object.entries(p.owner_model || {}).sort((a, b) => b[1].expected - a[1].expected);
  setHTML($("#owner-rows"), model.map(([k, v]) =>
    `<tr><td>${esc(k)}</td><td>${v.p_approve.toFixed(2)}</td><td>${v.p_disapprove.toFixed(2)}</td><td>${v.expected >= 0 ? "+" : ""}${v.expected.toFixed(2)}</td><td>${v.trials.toFixed(0)}</td></tr>`).join(""));
  $("#owner-table").hidden = !model.length;
}

function summary(e) {
  const p = e.payload;
  if (p.summary) return p.summary;
  switch (e.type) {
    case "SKILL_STEP_STARTED": return `${p.path} → ${p.skill} ${JSON.stringify(p.args)}`;
    case "SKILL_STEP_ENDED": return `${p.path} ${p.status}${p.reason ? ` (${p.reason})` : ""} after ${p.seconds} s`;
    case "SKILL_BIND": return `${p.path}: ${p.name} := ${p.value}`;
    case "ENTITY_CREATED": return `new ${p.cls} ${p.entity}`;
    case "ASSERTION_OPENED": return `${p.rel}(${p.args.join(", ")}) = ${JSON.stringify(p.value).slice(0, 60)}`;
    case "ASSERTION_CLOSED": return `${p.rel}(${p.args.join(", ")}) ended${p.reason ? `: ${p.reason}` : ""}`;
    case "EVENT_STARTED": case "EVENT_ENDED": return `${p.kind} ${p.data.skill || ""} ${p.data.outcome || ""}`;
    case "GRASP_TRUTH": return `grasp ${p.held ? "held" : "missed"} (true error ${p.error_m ?? "—"} m)`;
    case "FALL": return `fell during ${p.skill}: ${p.note}`;
    case "CHOICE_REJECTED": return `rejected ${p.skill}: ${p.problem}`;
    case "SKILL_REVIEWED": return `${p.child}: ${p.status} (p better ${p.p_better})`;
    case "RUN_STARTED": return `seed ${p.seed} · ${p.provider}${p.model ? ` (${p.model})` : ""}`;
    default: return "";
  }
}

function renderTrace(upTo) {
  const allowed = FILTERS[state.filter];
  const shown = upTo.filter((e) => e.type !== "STATE_SNAPSHOT" && e.type !== "TRUTH" && (!allowed || allowed.has(e.type))).slice(-120).reverse();
  setHTML($("#event-list"), shown.map((e) =>
    `<button class="event ${e.sequence === state.selected ? "selected" : ""} t-${esc(e.type)}" data-seq="${e.sequence}">
      <time>${tc(e.sim_time)}</time><strong>${esc(e.type)}</strong><span>${esc(summary(e))}</span></button>`).join(""));
}

// ---- controls --------------------------------------------------------------
$("#event-list").addEventListener("click", (ev) => {
  const button = ev.target.closest(".event");
  if (!button) return;
  state.selected = Number(button.dataset.seq);
  const e = state.events.find((x) => x.sequence === state.selected);
  $("#json-inspector").textContent = JSON.stringify(e, null, 2);
  render(state.index);
});
$("#filters").addEventListener("click", (ev) => {
  const b = ev.target.closest("button");
  if (!b) return;
  document.querySelectorAll("#filters button").forEach((x) => x.classList.toggle("active", x === b));
  state.filter = b.dataset.filter;
  render(state.index);
});
$("#timeline").addEventListener("input", (ev) => { setPlaying(false); render(Number(ev.target.value)); });
$("#truth-toggle").addEventListener("change", () => render(state.index));
$("#run-select").addEventListener("change", (ev) => open(ev.target.value, ev.target.value === state.liveRunId));
$("#play-button").addEventListener("click", () => setPlaying(!state.playing));

function setPlaying(on) {
  state.playing = on;
  $("#play-button").textContent = on ? "Ⅱ" : "▶";
  clearInterval(state.timer);
  if (!on) return;
  state.timer = setInterval(() => {
    if (state.index >= state.snapshots.length - 1) { if (!state.live) setPlaying(false); return; }
    render(state.index + 1);
  }, 500 / Number($("#rate").value));
}
$("#rate").addEventListener("change", () => { if (state.playing) setPlaying(true); });

loadRuns().catch((err) => { text("#connection-label", "Offline"); console.error(err); });
