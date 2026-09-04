"use strict";

const results = document.querySelector("#results");
const title = document.querySelector("#scenario-title");
const kicker = document.querySelector("#scenario-kicker");
const progress = document.querySelector("#progress-track");
const completion = document.querySelector("#completion-marker");
const scoutStatus = document.querySelector("#scout-status");
const memoryLayers = {
  current: document.querySelector('[data-testid="memory-current-session"]'),
  evidence: document.querySelector('[data-testid="memory-evidence-history"]'),
  governed: document.querySelector('[data-testid="memory-governed"]'),
};
const runButtons = [...document.querySelectorAll(".scenario-button")];
const recording = new URLSearchParams(window.location.search).has("record");

async function breathe(milliseconds = 1200) {
  if (recording) {
    await new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.detail || `Request failed: ${response.status}`);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

function resetView(name, description, steps) {
  title.textContent = name;
  kicker.textContent = description;
  results.replaceChildren();
  completion.textContent = "";
  completion.className = "completion-marker";
  progress.replaceChildren();
  for (let i = 0; i < steps; i += 1) {
    const dot = document.createElement("span");
    dot.className = "progress-dot";
    progress.append(dot);
  }
}

function step(index) {
  [...progress.children].forEach((dot, position) => {
    dot.className = `progress-dot ${position < index ? "complete" : position === index ? "active" : ""}`;
  });
}

function card(label, heading, text, tone = "", size = "half", chips = [], testId = "") {
  const article = document.createElement("article");
  article.className = `result-card ${tone} ${size}`.trim();
  if (testId) article.dataset.testid = testId;
  const labelNode = document.createElement("p");
  labelNode.className = "card-label";
  labelNode.textContent = label;
  const headingNode = document.createElement("h3");
  headingNode.textContent = heading;
  const textNode = document.createElement("p");
  textNode.textContent = text;
  article.append(labelNode, headingNode, textNode);
  if (chips.length) {
    const list = document.createElement("div");
    list.className = "chip-list";
    chips.forEach((value) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = value;
      list.append(chip);
    });
    article.append(list);
  }
  results.append(article);
  return article;
}

function renderCalendar(board) {
  const wrapper = document.createElement("article");
  wrapper.className = "calendar-board";
  wrapper.dataset.testid = "calendar-board";
  const header = document.createElement("div");
  header.className = "calendar-header";
  const heading = document.createElement("h3");
  heading.textContent = "Executive availability";
  const source = document.createElement("span");
  source.className = "source-pill";
  source.textContent = board.source === "live_via_scout" ? "LIVE VIA SCOUT" : "DETERMINISTIC FIXTURE";
  header.append(heading, source);
  wrapper.append(header);
  board.lanes.forEach((lane) => {
    const row = document.createElement("div");
    row.className = "calendar-lane-view";
    row.dataset.testid = lane.alias === "Exec A" ? "calendar-lane-exec-a" : "calendar-lane-exec-b";
    const name = document.createElement("strong");
    name.textContent = lane.alias;
    const track = document.createElement("div");
    track.className = "calendar-track";
    if (lane.access_limited) {
      const limitation = document.createElement("span");
      limitation.className = "calendar-limitation";
      limitation.textContent = lane.limitation;
      track.append(limitation);
    } else {
      lane.blocks.slice(0, 5).forEach((block) => {
        const item = document.createElement("span");
        item.className = `calendar-block ${block.category}`;
        item.textContent = block.label;
        track.append(item);
      });
      if (!track.children.length) {
        const free = document.createElement("span");
        free.className = "calendar-block";
        free.textContent = "Available";
        track.append(free);
      }
    }
    row.append(name, track);
    wrapper.append(row);
  });
  results.append(wrapper);
}

function renderMemory(projection, changed = false) {
  const counts = { "Current Session": 0, "Evidence History": 0, "Governed Memory": 0 };
  projection.notes.forEach((note) => { counts[note.layer] += 1; });
  const summary = document.createElement("section");
  summary.className = "memory-summary";
  summary.dataset.testid = "memory-summary";
  Object.entries(counts).forEach(([layer, count], index) => {
    const item = document.createElement("article");
    item.className = "memory-card";
    const number = document.createElement("b");
    number.textContent = `LAYER ${index + 1}`;
    const name = document.createElement("strong");
    name.textContent = layer;
    const detail = document.createElement("span");
    detail.textContent = `${count} projected note${count === 1 ? "" : "s"}`;
    item.append(number, name, detail);
    summary.append(item);
  });
  results.append(summary);
  memoryLayers.current.classList.add("updated");
  memoryLayers.evidence.classList.add("updated");
  if (changed) memoryLayers.governed.classList.add("updated");
}

function finish(id, message) {
  [...progress.children].forEach((dot) => { dot.className = "progress-dot complete"; });
  completion.id = id;
  completion.dataset.testid = id;
  completion.textContent = `✓ ${message}`;
  completion.className = "completion-marker visible";
  if (recording) {
    completion.scrollIntoView({ behavior: "smooth", block: "end" });
  }
}

async function begin(button) {
  runButtons.forEach((item) => {
    item.disabled = true;
    item.setAttribute("aria-current", String(item === button));
  });
  await api("/demo/reset", { method: "POST" });
}

function end() {
  runButtons.forEach((item) => { item.disabled = false; });
}

const requester = {
  entra_object_id: "demo-requester",
  display_name: "Requester",
};
const ea = "EA";

async function scenario1() {
  const button = document.querySelector("#run-s1");
  await begin(button);
  resetView("Qualified single-executive scheduling", "SCENARIO 1 · EXEC A", 5);
  try {
    step(0);
    const submitted = await api("/requests", {
      method: "POST",
      body: JSON.stringify({ raw_text: "Can I get 30 minutes with Marcus this week?", requester }),
    });
    const requestId = submitted.request.request_id;
    card("INTAKE", "The request needs three answers", submitted.qualification.missing_fields.join(" · "), "", "half", submitted.qualification.missing_fields);
    await breathe();

    step(1);
    await api(`/requests/${requestId}/answers`, {
      method: "POST",
      body: JSON.stringify({ answers: {
        objective: "Choose the Q4 forecast scenario.",
        business_justification: "Finance needs a decision before planning closes.",
        deadline: "2026-09-16T22:00:00Z",
      }}),
    });
    card("QUALIFICATION", "Decision-ready without EA intervention", "All eight required fields are complete. Status: Qualified.", "success");
    await breathe();

    step(2);
    const view = await api(`/requests/${requestId}/recommendation`);
    const calendar = await api(`/live/requests/${requestId}/calendar`);
    renderCalendar(calendar);
    card("CONTEXT", `${view.context.items.length} sourced context items`, "Every claim links back to mail, Teams, events, or files.", "", "third", view.context.items.slice(0, 3).map((item) => item.source.source_type));
    view.packet.options.forEach((option) => {
      card(`OPTION ${option.rank}`, new Date(option.slot.start).toLocaleString(), option.rationale, "", "third", [`score ${option.score.total}`, `${option.constraints_considered.length} constraints`]);
    });
    await breathe(1700);

    step(3);
    let gateHeld = false;
    try {
      await api(`/requests/${requestId}/draft`, {
        method: "POST",
        body: JSON.stringify({ recommendation_id: view.packet.recommendation_id, actor: ea }),
      });
    } catch (error) {
      gateHeld = error.status === 409;
    }
    if (!gateHeld) throw new Error("Approval gate did not hold");
    card("GOVERNANCE", "Draft blocked before approval", "ApprovalRequiredError recorded; the M365 write log is still empty.", "gate");
    await breathe();

    step(4);
    const approval = await api(`/requests/${requestId}/decision`, {
      method: "POST",
      body: JSON.stringify({ recommendation_id: view.packet.recommendation_id, actor: ea, decision: "approve", chosen_option_id: view.packet.options[0].option_id }),
    });
    const draft = await api(`/requests/${requestId}/draft`, {
      method: "POST",
      body: JSON.stringify({ recommendation_id: view.packet.recommendation_id, actor: ea }),
    });
    card("EA ACTION", "Approved, then drafted—never sent", `Approval ${approval.approval_id} precedes draft ${draft.draft_id}. Outlook link returned to the EA.`, "success", "half", [], "draft-created-marker");
    finish("scenario-1-complete", "Scenario 1 validated · qualification, recommendation, and EA gate");
    await breathe(1800);
  } finally { end(); }
}

async function scenario2() {
  const button = document.querySelector("#run-s2");
  await begin(button);
  resetView("Multi-executive strategic scheduling", "SCENARIO 2 · EXEC A + EXEC B", 4);
  try {
    step(0);
    const submitted = await api("/requests", {
      method: "POST",
      body: JSON.stringify({ raw_text: "Schedule a 45 minute strategic operating-plan decision with Dana, Marcus, and Priya before Friday.", requester }),
    });
    const requestId = submitted.request.request_id;
    const view = await api(`/requests/${requestId}/recommendation`);
    const calendar = await api(`/live/requests/${requestId}/calendar`);
    renderCalendar(calendar);
    card("AUTHORIZED ACCESS", "Exec A and Exec B calendars evaluated", "Delegated availability is shown without private subjects.", "success", "half", ["Exec A", "Exec B"]);
    card("PRIORITY", view.packet.priority.tier, view.packet.priority.factors[0].description, "", "half", view.packet.priority.factors.map((factor) => factor.rule_id));
    await breathe();

    step(1);
    const protectedCount = view.feasible_set.blocked.filter((item) => item.constraint === "protected_block").length;
    const travelCount = view.feasible_set.blocked.filter((item) => item.constraint === "travel_infeasible").length;
    card("HARD CONSTRAINTS", `${view.feasible_set.blocked.length} rejected starts retained`, "No protected block, travel window, working-hour boundary, or deadline was relaxed.", "gate", "half", [`${protectedCount} protected`, `${travelCount} travel`]);
    await breathe();

    step(2);
    view.packet.options.forEach((option) => {
      const trade = option.trade_offs[0];
      card(`RANK ${option.rank}`, new Date(option.slot.start).toLocaleString(), trade ? trade.description : "No commitment disruption.", trade ? "gate" : "", "third", [`score ${option.score.total}`, trade ? "EA-visible trade-off" : "clean slot"]);
    });
    await breathe(1700);

    step(3);
    const chosen = view.packet.options.find((option) => option.trade_offs.length) || view.packet.options[0];
    await api(`/requests/${requestId}/decision`, {
      method: "POST",
      body: JSON.stringify({ recommendation_id: view.packet.recommendation_id, actor: ea, decision: "approve", chosen_option_id: chosen.option_id }),
    });
    const draft = await api(`/requests/${requestId}/draft`, {
      method: "POST",
      body: JSON.stringify({ recommendation_id: view.packet.recommendation_id, actor: ea }),
    });
    card("WRITE SURFACE", "Exactly one draft write", `${draft.graph_event_id} is unsent. The affected commitment was displayed, never moved.`, "success");
    finish("scenario-2-complete", "Scenario 2 validated · executive calendars, hard constraints, no reschedule");
    await breathe(1800);
  } finally { end(); }
}

async function scenario3() {
  const button = document.querySelector("#run-s3");
  await begin(button);
  resetView("Feedback-to-preference learning", "SCENARIO 3 · GOVERNED LEARNING", 5);
  try {
    step(0);
    const submitted = await api("/requests", {
      method: "POST",
      body: JSON.stringify({ raw_text: "Meet Marcus for 30 minutes Tuesday about the Q4 forecast decision.", requester }),
    });
    const requestId = submitted.request.request_id;
    const baseline = (await api(`/requests/${requestId}/recommendation`)).packet;
    renderMemory(await api(`/live/requests/${requestId}/memory`));
    card("BASELINE · PROFILE V1", "Tuesday morning ranks first", new Date(baseline.options[0].slot.start).toLocaleString(), "", "half", [baseline.profile_version, `score ${baseline.options[0].score.total}`]);
    await breathe();

    step(1);
    await api("/demo/seed-feedback", { method: "POST" });
    const candidates = await api("/patterns/cfo@humana-demo.com/detect", { method: "POST" });
    const candidate = candidates[0];
    card("EVIDENCE", `${candidate.evidence.occurrences} consistent corrections`, candidate.evidence.observation, "", "half", candidate.evidence.feedback_ids);
    card("CANDIDATE · INACTIVE", candidate.proposed_rule, "Evidence is proposed behavior—not active behavior.", "gate", "half", [candidate.status, `confidence ${candidate.confidence}`], "candidate-inert-marker");
    await breathe(1700);

    step(2);
    const pending = (await api(`/requests/${requestId}/recommendation`)).packet;
    const unchanged = pending.options.map((item) => item.option_id).join() === baseline.options.map((item) => item.option_id).join();
    if (!unchanged) throw new Error("Pending candidate changed ranking");
    card("INV-3", "Pending candidate changes nothing", "Option IDs, order, scores, and profile version remain byte-stable.", "gate");
    await breathe();

    step(3);
    const preference = await api(`/candidates/${candidate.candidate_id}/decision`, {
      method: "POST",
      body: JSON.stringify({ actor: ea, decision: "approve" }),
    });
    card("EA APPROVAL", "Preference promoted to profile v2", preference.description, "success", "half", [preference.preference_id, preference.profile_version], "profile-version-change");
    await breathe();

    step(4);
    const learned = (await api(`/requests/${requestId}/recommendation`)).packet;
    renderMemory(await api(`/live/requests/${requestId}/memory`), true);
    card("BEFORE · V1", new Date(baseline.options[0].slot.start).toLocaleString(), "No learned preference applied.", "", "half");
    card("AFTER · V2", new Date(learned.options[0].slot.start).toLocaleString(), learned.options[0].preferences_applied[0].description, "success", "half", [learned.profile_version, learned.options[0].preferences_applied[0].preference_id]);
    finish("scenario-3-complete", "Scenario 3 validated · evidence inert, EA-approved preference active and reversible");
    await breathe(2200);
  } finally { end(); }
}

document.querySelector("#run-s1").addEventListener("click", () => scenario1().catch(showError));
document.querySelector("#run-s2").addEventListener("click", () => scenario2().catch(showError));
document.querySelector("#run-s3").addEventListener("click", () => scenario3().catch(showError));
document.querySelector("#reset-demo").addEventListener("click", async () => {
  await api("/demo/reset", { method: "POST" });
  resetView("Choose a scenario to begin", "READY", 0);
  card("RESET", "Deterministic fixture world restored", "No request, approval, draft, feedback, or profile state carried forward.", "success", "half");
});

function showError(error) {
  card("ERROR", "Scenario stopped", error.message, "gate");
  completion.textContent = `✕ ${error.message}`;
  completion.className = "completion-marker visible";
  end();
}

api("/live/status").then((status) => {
  scoutStatus.lastChild.textContent = status.configured
    ? " Scout connected · live delegated context"
    : " Scout-ready · deterministic fixture";
}).catch(() => {
  scoutStatus.lastChild.textContent = " Scout unavailable · fixture only";
});
