let totalFrames = 120;
const timeline = document.querySelector("#timeline");
const duck = document.querySelector("#duck");
const trail = document.querySelector("#trail");
const blueBlock = document.querySelector("#blue-block");
const redBall = document.querySelector("#red-ball");
const attentionCone = document.querySelector("#attention-cone");
const pauseButton = document.querySelector("#pause-button");
const playButton = document.querySelector("#play-button");
const playbackRate = document.querySelector("#playback-rate");
const eventList = document.querySelector("#event-list");
const inspector = document.querySelector("#json-inspector");

let frameIndex = totalFrames - 1;
let playing = true;
let selectedFilter = "all";
let selectedEvent = "action-7";
let timer;
let liveMode = false;
let runId = "SIM-0042";
let liveActionCount = 0;

let events = [
  { id:"boot", frame:2, kind:"body", icon:"↯", type:"RUN_STARTED", text:"MuJoCo adapter ready · seed 42", duration:"12ms", payload:{seed:42, model:"birdbrain_microduck_arena", mujoco:"3.17.0"} },
  { id:"observe-1", frame:14, kind:"body", icon:"◉", type:"OBSERVATION", text:"3 objects visible · pose confidence 0.96", duration:"3.7ms", payload:{visible:["blue_block","red_ball","charging_zone"], confidence:.96} },
  { id:"memory-2", frame:27, kind:"mind", icon:"◇", type:"MEMORY_RETRIEVED", text:"Blue block previously observed at (0.78, 0.51)", duration:"18ms", payload:{memory_id:"epi_0018", similarity:.91, age_seconds:84.2} },
  { id:"goal-3", frame:38, kind:"mind", icon:"◎", type:"GOAL_PROPOSED", text:"Inspect the unfamiliar blue block", duration:"26ms", payload:{goal:"inspect_blue_block", source:"novelty", utility:.86, constraints:["energy > .35","collision_risk < .2"]} },
  { id:"conflict-4", frame:51, kind:"mind", icon:"?", type:"BELIEF_CONFLICT", text:"Object moved 0.06 m from remembered pose", duration:"—", payload:{entity:"blue_block", observed:[.85,.55,.07], remembered:[.79,.52,.07], delta_m:.067} },
  { id:"plan-5", frame:61, kind:"mind", icon:"⌁", type:"PLAN_CREATED", text:"approach → inspect → push-test", duration:"41ms", payload:{steps:["approach_object","center_gaze","push_test"], predicted_success:.78} },
  { id:"slip-6", frame:73, kind:"body", icon:"!", type:"ANOMALY", text:"Unexpected foot slip · lateral drift 0.18 m/s", duration:"—", payload:{code:"foot_slip", severity:"warning", lateral_velocity:.18, contact:"left_foot_geom"} },
  { id:"action-7", frame:82, kind:"body", icon:"▶", type:"ACTION_SELECTED", text:"Set walking joint targets", duration:"0.4ms", payload:{action:"set_joint_targets", targets:{left_hip_motor:.10,right_hip_motor:-.08,left_ankle_motor:-.04,right_ankle_motor:.06,neck_motor:.25}, frame_skip:5} },
  { id:"reflect-8", frame:96, kind:"mind", icon:"✦", type:"REFLECTION", text:"Reduce stride amplitude after slip", duration:"52ms", payload:{lesson:"lower stride amplitude on low-confidence contact", confidence:.72, applies_to:"walk_forward"} },
  { id:"observe-9", frame:111, kind:"body", icon:"◉", type:"OBSERVATION", text:"Blue block now 0.42 m ahead", duration:"3.5ms", payload:{target:"blue_block", distance_m:.42, bearing_deg:7.4, visible:true} }
];

let frames = Array.from({length:totalFrames}, (_, i) => {
  const t = i / 10;
  const progress = i / (totalFrames - 1);
  const x = 270 + progress * 115 + Math.sin(i / 12) * 7;
  const y = 260 - progress * 100 + Math.cos(i / 17) * 5;
  const heading = -28 + progress * 14 + Math.sin(i / 15) * 5;
  return {
    t, x, y, heading,
    confidence: .69 + progress * .1 + Math.sin(i / 16) * .025,
    energy: .91 - progress * .07,
    speed: .12 + Math.abs(Math.sin(i / 10)) * .09,
    pitch: -1.7 - Math.sin(i / 9) * 1.1,
    joints:[.25 + Math.sin(i/18)*.05, .10 + Math.sin(i/9)*.1, -.04 + Math.sin(i/9+1)*.08, -.08 - Math.sin(i/9)*.1, .06 - Math.sin(i/9+1)*.08]
  };
});

function timecode(seconds) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2,"0");
  return `${minutes}:${(seconds % 60).toFixed(2).padStart(5,"0")}`;
}

function setText(selector, text) { document.querySelector(selector).textContent = text; }

function jointBar(id, value) {
  const bar = document.querySelector(`#${id}`);
  const width = Math.min(49, Math.abs(value) / .7 * 50);
  bar.style.width = `${width}%`;
  bar.style.left = value < 0 ? `${50 - width}%` : "50%";
  bar.style.background = value < 0 ? "#65a8ff" : "#f5c84c";
}

function renderFrame(index, fromUser = false) {
  if (!frames.length) return;
  frameIndex = Math.max(0, Math.min(frames.length - 1, index));
  const f = frames[frameIndex];
  timeline.max = frames.length - 1;
  timeline.value = frameIndex;
  duck.setAttribute("transform", `translate(${f.x} ${f.y}) rotate(${f.heading})`);
  const points = frames.slice(0, frameIndex + 1).filter((_, i) => i % 4 === 0).map(p => `${p.x},${p.y}`).join(" ");
  trail.setAttribute("d", points ? `M ${points.replaceAll(" ", " L ")}` : "");
  const blockPosition = f.blueBlock || [430 + Math.sin(frameIndex/22)*3, 115 + Math.cos(frameIndex/22)*2];
  const ballPosition = f.redBall || [455, 306];
  blueBlock.setAttribute("transform", `translate(${blockPosition[0]} ${blockPosition[1]})`);
  redBall.setAttribute("transform", `translate(${ballPosition[0]} ${ballPosition[1]})`);
  attentionCone.setAttribute("cx", `${blockPosition[0]}`);
  attentionCone.setAttribute("cy", `${blockPosition[1]}`);

  setText("#sim-time", timecode(f.t));
  setText("#timeline-time", `${timecode(f.t)} / ${timecode(frames.at(-1).t)}`);
  setText("#pos-x", `${((f.x-310)/146).toFixed(2)}`);
  setText("#pos-y", `${((215-f.y)/98).toFixed(2)}`);
  setText("#heading", `${Math.round((f.heading+360)%360)}°`);
  setText("#confidence", `${Math.round(f.confidence*100)}%`);
  setText("#energy", `${Math.round(f.energy*100)}%`);
  document.querySelector("#confidence-meter").style.width = `${f.confidence*100}%`;
  document.querySelector("#energy-meter").style.width = `${f.energy*100}%`;
  setText("#pitch", `${f.pitch.toFixed(1)}°`);
  setText("#speed", f.speed.toFixed(2));
  setText("#step-time", (f.stepMs ?? 3.4 + Math.abs(Math.sin(frameIndex/7))*.7).toFixed(1));
  const jointIds = ["neck","lhip","lankle","rhip","rankle"];
  f.joints.forEach((value, i) => { jointBar(`joint-${jointIds[i]}`, value); setText(`#joint-${jointIds[i]}-value`, `${value >= 0 ? "+" : ""}${value.toFixed(2)}`); });
  renderEvents();
  if (fromUser && frameIndex < totalFrames - 1) setPlaying(false);
  setText("#replay-state", frameIndex === frames.length-1 && playing ? "Live tail" : `Reviewing frame ${frameIndex}`);
}

function renderEvents() {
  const visible = events.filter(event => event.frame <= frameIndex && (selectedFilter === "all" || event.kind === selectedFilter));
  eventList.innerHTML = visible.map(event => `
    <button class="event ${event.id === selectedEvent ? "selected" : ""}" data-id="${event.id}">
      <time>${timecode(frames[event.frame]?.t ?? event.envelope?.sim_time ?? 0)}</time><span class="event-icon">${event.icon}</span>
      <strong>${event.type}</strong><span>${event.text}</span><em>${event.duration}</em>
    </button>`).join("");
  eventList.querySelectorAll(".event").forEach(button => button.addEventListener("click", () => selectEvent(button.dataset.id)));
}

function selectEvent(id) {
  const event = events.find(item => item.id === id);
  if (!event) return;
  selectedEvent = id;
  const eventTime = frames[event.frame]?.t ?? event.envelope?.sim_time ?? 0;
  setText("#inspector-type", event.type);
  setText("#inspector-time", timecode(eventTime));
  inspector.textContent = JSON.stringify(event.envelope || {run_id:runId, sequence:event.frame, sim_time:eventTime, type:event.type, ...event.payload}, null, 2);
  renderEvents();
}

function setPlaying(next) {
  playing = next;
  pauseButton.setAttribute("aria-pressed", String(!playing));
  setText("#pause-label", playing ? "Pause" : "Resume");
  pauseButton.querySelector(".pause-icon").textContent = playing ? "Ⅱ" : "▶";
  playButton.textContent = playing ? "Ⅱ" : "▶";
  playButton.setAttribute("aria-label", playing ? "Pause replay" : "Play replay");
  clearInterval(timer);
  if (liveMode) {
    if (playing && frames.length) renderFrame(frames.length - 1);
    return;
  }
  if (playing) timer = setInterval(() => {
    const next = frameIndex >= frames.length - 1 ? 0 : frameIndex + 1;
    renderFrame(next);
  }, 100 / Number(playbackRate.value));
}

pauseButton.addEventListener("click", () => setPlaying(!playing));
playButton.addEventListener("click", () => setPlaying(!playing));
timeline.addEventListener("input", event => renderFrame(Number(event.target.value), true));
document.querySelector("#step-back").addEventListener("click", () => { setPlaying(false); renderFrame(frameIndex - 1); });
document.querySelector("#step-forward").addEventListener("click", () => { setPlaying(false); renderFrame(frameIndex + 1); });
playbackRate.addEventListener("change", () => { setText("#rate", `${Number(playbackRate.value).toFixed(1)}×`); if (playing) setPlaying(true); });

document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-filter]").forEach(item => item.classList.remove("active"));
  button.classList.add("active"); selectedFilter = button.dataset.filter; renderEvents();
}));
document.querySelectorAll("[data-overlay]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-overlay]").forEach(item => item.classList.remove("active")); button.classList.add("active");
  document.querySelectorAll(".remembered, #attention-cone").forEach(item => item.style.display = button.dataset.overlay === "belief" ? "" : "none");
}));
document.querySelector("#focus-alerts").addEventListener("click", () => document.querySelector("#anomalies").scrollIntoView({behavior:"smooth", block:"center"}));
document.querySelector("#copy-json").addEventListener("click", async event => { await navigator.clipboard.writeText(inspector.textContent); event.currentTarget.textContent = "Copied"; setTimeout(() => event.currentTarget.textContent = "Copy JSON", 1000); });
document.querySelectorAll(".anomaly").forEach(button => button.addEventListener("click", () => { document.querySelectorAll(".anomaly").forEach(item => item.classList.remove("active")); button.classList.add("active"); selectEvent(button.dataset.event); }));
document.addEventListener("keydown", event => { if (event.target.matches("input,select,button")) return; if (event.code === "Space") { event.preventDefault(); setPlaying(!playing); } if (event.code === "ArrowLeft") { setPlaying(false); renderFrame(frameIndex-1); } if (event.code === "ArrowRight") { setPlaying(false); renderFrame(frameIndex+1); } });

function worldPoint(position) {
  return [310 + position[0] * 146, 215 - position[1] * 98];
}

function liveFrame(snapshot, simTime) {
  const targets = snapshot.actuator_targets;
  const duckPosition = worldPoint(snapshot.duck.position);
  return {
    t: simTime,
    x: duckPosition[0],
    y: duckPosition[1],
    heading: snapshot.heading_deg,
    confidence: snapshot.confidence,
    energy: snapshot.energy,
    speed: snapshot.speed_mps,
    pitch: snapshot.pitch_deg,
    stepMs: snapshot.step_ms,
    blueBlock: worldPoint(snapshot.blue_block.position),
    redBall: worldPoint(snapshot.red_ball.position),
    joints: [targets.neck_motor, targets.left_hip_motor, targets.left_ankle_motor, targets.right_hip_motor, targets.right_ankle_motor]
  };
}

function liveEventView(envelope) {
  const icons = {RUN_STARTED:"↯", ACTION_SELECTED:"▶", ANOMALY:"!", RUN_FAILED:"×"};
  const kind = ["ACTION_SELECTED", "ANOMALY", "RUN_FAILED"].includes(envelope.type) ? "body" : "mind";
  return {
    id: `live-${envelope.sequence}`,
    frame: Math.max(0, frames.length - 1),
    kind,
    icon: icons[envelope.type] || "◉",
    type: envelope.type,
    text: envelope.payload.summary || envelope.payload.message || envelope.type.replaceAll("_", " ").toLowerCase(),
    duration: "live",
    payload: envelope.payload,
    envelope
  };
}

function renderLiveMind(snapshot) {
  setText("#mode-badge", snapshot.mode);
  setText("#intention", snapshot.intention);
  setText("#rationale", snapshot.rationale);
  setText("#skill", snapshot.skill);
  setText("#attention-label", snapshot.attention);
  const list = document.querySelector("#goal-list");
  list.innerHTML = snapshot.goals.map((goal, index) => `<li class="${index === 0 ? "active" : ""}"><b>${index + 1}</b><div><strong>${goal.name}</strong><span>${index === 0 ? "active objective" : "queued"}</span></div><code>${goal.utility.toFixed(2)}</code></li>`).join("");
}

function ingestLiveEvent(envelope) {
  if (envelope.type === "STATE_SNAPSHOT") {
    frames.push(liveFrame(envelope.payload, envelope.sim_time));
    totalFrames = frames.length;
    timeline.max = Math.max(0, frames.length - 1);
    renderLiveMind(envelope.payload);
    if (playing) renderFrame(frames.length - 1);
    return;
  }
  if (envelope.type === "ACTION_SELECTED") {
    liveActionCount += 1;
    if (liveActionCount % 10 !== 0) return;
  }
  events.push(liveEventView(envelope));
  if (events.length > 120) events = events.slice(-120);
  if (!selectedEvent) {
    selectedEvent = events.at(-1)?.id;
    selectEvent(selectedEvent);
  }
  if (envelope.type === "ANOMALY") renderLiveAnomaly(envelope);
  renderEvents();
}

function renderLiveAnomaly(envelope) {
  const button = document.querySelector(".anomaly");
  button.style.display = "grid";
  button.dataset.event = `live-${envelope.sequence}`;
  button.querySelector("strong").textContent = envelope.payload.summary || envelope.payload.code;
  button.querySelector("small").textContent = `${envelope.payload.severity || "warning"} · ${timecode(envelope.sim_time)}`;
  button.dataset.live = "true";
  const count = document.querySelectorAll(".anomaly[data-live='true']").length;
  setText(".count-badge", `${count} open`);
  setText("#alert-count", String(count));
}

async function connectLiveBridge() {
  try {
    const response = await fetch("/api/status", {cache:"no-store"});
    if (!response.ok) return;
    const status = await response.json();
    if (status.schema_version !== "birdbrain.event.v1") return;
    liveMode = true;
    runId = status.run_id;
    frames = [];
    events = [];
    totalFrames = 0;
    frameIndex = 0;
    selectedEvent = "";
    liveActionCount = 0;
    clearInterval(timer);
    playing = true;
    document.querySelectorAll(".anomaly").forEach(item => item.style.display = "none");
    setText(".count-badge", "0 open");
    setText("#alert-count", "0");
    setText("#connection-label", "Live simulator");
    setText("#run-id", runId.toUpperCase());
    setText("#inspector-type", "AWAITING_EVENT");
    setText("#inspector-time", "00:00.00");
    inspector.textContent = JSON.stringify({run_id:runId, status:"connected", schema_version:status.schema_version}, null, 2);
    document.querySelector(".status-pill").title = `Connected to ${runId}`;
    const source = new EventSource(status.stream);
    source.addEventListener("birdbrain", event => ingestLiveEvent(JSON.parse(event.data)));
    source.onopen = () => setText("#connection-label", "Live simulator");
    source.onerror = () => setText("#connection-label", "Reconnecting");
  } catch (_error) {
    // The private hosted dashboard intentionally remains in demo mode when
    // there is no same-origin local simulator bridge.
  }
}

selectEvent(selectedEvent);
renderFrame(frameIndex);
setPlaying(true);
connectLiveBridge();
