const totalFrames = 120;
const timeline = document.querySelector("#timeline");
const duck = document.querySelector("#duck");
const trail = document.querySelector("#trail");
const blueBlock = document.querySelector("#blue-block");
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

const events = [
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

const frames = Array.from({length:totalFrames}, (_, i) => {
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
  frameIndex = Math.max(0, Math.min(totalFrames - 1, index));
  const f = frames[frameIndex];
  timeline.value = frameIndex;
  duck.setAttribute("transform", `translate(${f.x} ${f.y}) rotate(${f.heading})`);
  const points = frames.slice(0, frameIndex + 1).filter((_, i) => i % 4 === 0).map(p => `${p.x},${p.y}`).join(" ");
  trail.setAttribute("d", points ? `M ${points.replaceAll(" ", " L ")}` : "");
  blueBlock.setAttribute("transform", `translate(${430 + Math.sin(frameIndex/22)*3} ${115 + Math.cos(frameIndex/22)*2})`);
  attentionCone.setAttribute("cx", `${430 + Math.sin(frameIndex/22)*3}`);
  attentionCone.setAttribute("cy", `${115 + Math.cos(frameIndex/22)*2}`);

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
  setText("#step-time", (3.4 + Math.abs(Math.sin(frameIndex/7))*.7).toFixed(1));
  const jointIds = ["neck","lhip","lankle","rhip","rankle"];
  f.joints.forEach((value, i) => { jointBar(`joint-${jointIds[i]}`, value); setText(`#joint-${jointIds[i]}-value`, `${value >= 0 ? "+" : ""}${value.toFixed(2)}`); });
  renderEvents();
  if (fromUser && frameIndex < totalFrames - 1) setPlaying(false);
  setText("#replay-state", frameIndex === totalFrames-1 && playing ? "Live tail" : `Reviewing frame ${frameIndex}`);
}

function renderEvents() {
  const visible = events.filter(event => event.frame <= frameIndex && (selectedFilter === "all" || event.kind === selectedFilter));
  eventList.innerHTML = visible.map(event => `
    <button class="event ${event.id === selectedEvent ? "selected" : ""}" data-id="${event.id}">
      <time>${timecode(frames[event.frame].t)}</time><span class="event-icon">${event.icon}</span>
      <strong>${event.type}</strong><span>${event.text}</span><em>${event.duration}</em>
    </button>`).join("");
  eventList.querySelectorAll(".event").forEach(button => button.addEventListener("click", () => selectEvent(button.dataset.id)));
}

function selectEvent(id) {
  const event = events.find(item => item.id === id);
  if (!event) return;
  selectedEvent = id;
  setText("#inspector-type", event.type);
  setText("#inspector-time", timecode(frames[event.frame].t));
  inspector.textContent = JSON.stringify({run_id:"SIM-0042", sequence:event.frame, sim_time:frames[event.frame].t, type:event.type, ...event.payload}, null, 2);
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
  if (playing) timer = setInterval(() => {
    const next = frameIndex >= totalFrames - 1 ? 0 : frameIndex + 1;
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
document.querySelectorAll(".anomaly").forEach(button => button.addEventListener("click", () => { document.querySelectorAll(".anomaly").forEach(item => item.classList.remove("active")); button.classList.add("active"); selectEvent(button.dataset.event === "grip-slip" ? "slip-6" : "conflict-4"); }));
document.addEventListener("keydown", event => { if (event.target.matches("input,select,button")) return; if (event.code === "Space") { event.preventDefault(); setPlaying(!playing); } if (event.code === "ArrowLeft") { setPlaying(false); renderFrame(frameIndex-1); } if (event.code === "ArrowRight") { setPlaying(false); renderFrame(frameIndex+1); } });

selectEvent(selectedEvent);
renderFrame(frameIndex);
setPlaying(true);
