"use strict";

const $ = (id) => document.getElementById(id);
const input = $("input"), dialog = $("menu-dialog");
const token = new URLSearchParams(location.hash.slice(1)).get("token") || sessionStorage.getItem("openvino-gui-token");
if (token) sessionStorage.setItem("openvino-gui-token", token);
if (location.hash) history.replaceState(null, "", location.pathname);
let state = null, commands = [], transcript = "", transcriptVersion = -1;
let draftVersion = 0, draftDirty = false, lastInputVersion = -1, draftTimer = null;
let actionQueue = Promise.resolve(), paletteIndex = 0, paletteQuery = "", menuCache = "";
let uploaded = [], uploading = false, draftStash = null, commandPending = false, selectionDragging = false;
let pollFailures = 0;
let localNoticeUntil = 0, minimumInputVersion = -1, inputMutation = 0;
let paragraphIndex = 0, followSpeech = true, speechUser = null;
let mobileSideOpen = false;
let motionPaused = localStorage.getItem("openvino-motion-paused") === "true";
document.body.classList.toggle("motion-paused", motionPaused);

async function request(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"X-OpenVINO-Token": token || "", ...(options.headers || {})}});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function notice(text, local = true) {
  if (local) localNoticeUntil = Date.now() + 5000;
  $("notice").textContent = text;
  $("notice").hidden = !text;
}

function action(body) {
  const run = () => request("/action", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const result = actionQueue.then(run);
  actionQueue = result.catch((error) => {
    notice(error.message);
    if (dialog.open) { $("menu-error").textContent = error.message; $("menu-error").hidden = false; }
  });
  return result;
}

function key(name, extra = {}) {
  return action({action: "key", key: name, menu_id: state?.menu?.id || null, ...extra});
}

function cursorIndex() { return Array.from(input.value.slice(0, input.selectionStart)).length; }
function resizeInput() {
  const limit = Math.max(80, Math.min(400, innerHeight * .35));
  input.style.maxHeight = limit + "px";
  input.style.height = "auto";
  input.style.height = Math.min(limit, input.scrollHeight) + "px";
}

async function syncDraft() {
  clearTimeout(draftTimer);
  if (!state || state.menu || !draftDirty) return;
  const version = draftVersion, text = input.value, cursor = cursorIndex();
  inputMutation++;
  try {
    const result = await action({action: "draft", text, cursor});
    minimumInputVersion = Math.max(minimumInputVersion, result.input_version ?? -1);
  } finally { inputMutation--; }
  if (version === draftVersion) draftDirty = false;
}

async function send(text = input.value, preserveDraft = false) {
  if (!state || state.menu || uploading || !text.trim() || commandPending) return;
  clearTimeout(draftTimer);
  if (preserveDraft && input.value && input.value !== text) draftStash = input.value;
  commandPending = true;
  draftDirty = false;
  draftVersion++;
  try {
    const result = await action({action: "submit", text});
    minimumInputVersion = Math.max(minimumInputVersion, result.input_version ?? -1);
    if (!draftStash) { input.value = ""; uploaded = []; resizeInput(); }
    $("palette").hidden = true;
  } catch (error) {
    if (!input.value) input.value = text;
    notice(error.message);
  } finally {
    commandPending = false;
  }
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

const ansiColors = ["#161819", "#ef7c78", "#78cb91", "#e8c867", "#73b4ff", "#d6a4d9", "#63c9de", "#e8eaec",
                    "#939aa0", "#ff9793", "#9bdcae", "#ffe3a0", "#a1ccff", "#edc4ee", "#96e5ed", "#ffffff"];
function indexedColor(index) {
  if (index < 16) return ansiColors[index];
  if (index >= 232) { const c = 8 + (index - 232) * 10; return `rgb(${c},${c},${c})`; }
  const n = index - 16, levels = [0, 95, 135, 175, 215, 255];
  return `rgb(${levels[Math.floor(n / 36)]},${levels[Math.floor(n / 6) % 6]},${levels[n % 6]})`;
}

function ansiFragment(text) {
  const fragment = document.createDocumentFragment();
  const pattern = /\x1b\[([0-9;]*)m/g;
  let color = "", background = "", bold = false, italic = false, underline = false, dim = false, start = 0, match;
  function append(value) {
    value = value.replace(/\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|$))/g, "").replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
    if (!value) return;
    const span = element("span", "", value);
    if (color) span.style.color = color;
    if (background) span.style.backgroundColor = background;
    if (bold) span.style.fontWeight = "650";
    if (italic) span.style.fontStyle = "italic";
    if (underline) span.style.textDecoration = "underline";
    if (dim) span.style.opacity = ".7";
    fragment.append(span);
  }
  while ((match = pattern.exec(text))) {
    append(text.slice(start, match.index)); start = pattern.lastIndex;
    const codes = match[1] ? match[1].split(";").map(Number) : [0];
    for (let i = 0; i < codes.length; i++) {
      const c = codes[i];
      if (c === 0) { color = background = ""; bold = italic = underline = dim = false; }
      else if (c === 1) bold = true;
      else if (c === 2) dim = true;
      else if (c === 3) italic = true;
      else if (c === 4) underline = true;
      else if (c === 22) bold = dim = false;
      else if (c === 23) italic = false;
      else if (c === 24) underline = false;
      else if (c === 39) color = "";
      else if (c === 49) background = "";
      else if (c >= 30 && c <= 37) color = ansiColors[c - 30];
      else if (c >= 90 && c <= 97) color = ansiColors[c - 90 + 8];
      else if (c >= 40 && c <= 47) background = ansiColors[c - 40];
      else if ((c === 38 || c === 48) && codes[i + 1] === 2 && i + 4 < codes.length) {
        const rgb = codes.slice(i + 2, i + 5).map((v) => Math.max(0, Math.min(255, v)));
        const value = `rgb(${rgb.join(",")})`; if (c === 38) color = value; else background = value; i += 4;
      } else if ((c === 38 || c === 48) && codes[i + 1] === 5 && i + 2 < codes.length) {
        const value = indexedColor(Math.max(0, Math.min(255, codes[i + 2]))); if (c === 38) color = value; else background = value; i += 2;
      }
    }
  }
  append(text.slice(start));
  return fragment;
}

function selectedInside(node) {
  const selection = getSelection();
  return selectionDragging || (selection && !selection.isCollapsed && node.contains(selection.anchorNode));
}

function renderAnsi(node, text, {follow = false, scroller = node} = {}) {
  if (node._rendered === text || selectedInside(node)) return;
  const bottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 45;
  const position = scroller.scrollTop;
  node.replaceChildren(ansiFragment(text || "")); node._rendered = text;
  scroller.scrollTop = follow && bottom ? scroller.scrollHeight : position;
}

function paletteMatches() {
  const query = input.value.trimStart().toLowerCase();
  if (!query.startsWith("/") || /\s/.test(query) || state?.menu || !state?.ready) return [];
  return commands.filter((spec) => spec.command.startsWith(query));
}

function renderPalette() {
  const matches = paletteMatches(), query = input.value;
  if (query !== paletteQuery) { paletteIndex = 0; paletteQuery = query; }
  const node = $("palette"); node.hidden = !matches.length;
  if (!matches.length) return;
  paletteIndex = Math.max(0, Math.min(paletteIndex, matches.length - 1));
  const visible = Math.min(15, Math.max(3, Math.floor(innerHeight * .42 / 33)));
  const start = Math.max(0, Math.min(paletteIndex - visible + 1, matches.length - visible));
  node.replaceChildren();
  matches.slice(start, start + visible).forEach((spec, offset) => {
    const index = start + offset;
    const row = element("button", "command-row" + (index === paletteIndex ? " selected" : ""));
    row.setAttribute("role", "option"); row.setAttribute("aria-selected", String(index === paletteIndex));
    row.append(element("strong", "", spec.command), element("span", "", spec.description));
    row.addEventListener("mousedown", (event) => event.preventDefault());
    row.addEventListener("click", () => chooseCommand(spec)); node.append(row);
  });
  node.append(element("div", "palette-footer", `${paletteIndex + 1} / ${matches.length}   |   Up/Down select   Enter run   Tab complete`));
}

function chooseCommand(spec, completeOnly = false) {
  if (completeOnly || spec.usage.includes("<") || ["/chart"].includes(spec.command)) {
    input.value = spec.command + " "; draftDirty = true; draftVersion++; resizeInput(); renderPalette();
    notice("Usage: " + spec.usage); input.focus(); syncDraft().catch(() => {});
  } else send(spec.command).catch(() => {});
}

function renderMenu(menu) {
  if (!menu) {
    if (dialog.open) { dialog.close(); input.focus(); }
    menuCache = ""; return;
  }
  const signature = JSON.stringify(menu);
  if (signature === menuCache) return;
  const newDialog = dialog.dataset.id !== menu.id;
  if (newDialog) $("menu-error").hidden = true;
  if (!newDialog && menu.kind === "sampling" && dialog.contains(document.activeElement)) return;
  menuCache = signature; dialog.dataset.id = menu.id;
  $("menu-title").textContent = menu.title;
  $("menu-description").textContent = menu.text || "";
  $("menu-description").hidden = !menu.text;
  $("menu-warning").textContent = menu.warning || "";
  $("menu-warning").hidden = !menu.warning;
  const items = $("menu-items"), oldScroll = items.scrollTop;
  items.replaceChildren();
  menu.items.forEach((item, index) => {
    if (menu.kind === "sampling") {
      const row = element("label", "sampling-field"); row.append(element("span", "", item.name));
      const field = element("input"); field.type = "number"; field.name = item.name; field.value = item.value;
      field.step = Number.isInteger(item.step) ? "1" : "any";
      field.min = item.min; field.max = item.max; field.required = true;
      row.append(field); items.append(row); return;
    }
    const row = element("button", "menu-row" + (index === menu.selected ? " selected" : ""));
    row.setAttribute("aria-pressed", String(index === menu.selected));
    row.disabled = Boolean(item.disabled);
    row.append(element("strong", "", item.name + (item.active && menu.kind !== "timeline" ? "  / active" : "")));
    const summary = menu.kind === "timeline" ? `${item.active ? "Running" : item.ok ? "Completed" : "Failed"} | ${item.duration == null ? "" : item.duration.toFixed(1) + "s"} | attempt ${item.attempts}` :
      [item.state, item.size, item.repo, item.path, item.preview, item.thinking && "Thinking: " + item.thinking, item.effort && "Effort: " + item.effort].filter(Boolean).join("\n");
    if (summary) row.append(element("small", "", summary));
    if (menu.kind === "timeline" && item.expanded) row.append(element("pre", "", JSON.stringify(item.args, null, 2) + "\n\n" + item.result));
    if (menu.kind === "approval") {
      const hints = menu.confirmation ? ["Back to current request", "Warning: future computer actions will run without asking. Alt+Shift+S stops."] :
        ["Do not run this action", "Only this exact action", menu.computer ? "Computer actions until exit; warning follows" : "All file/shell tools until exit", menu.computer ? "Future computer actions until revoked; warning follows" : "All file/shell tools, including future sessions"];
      row.append(element("small", "", item.disabled ? "Alt+Shift+S unavailable; automatic access disabled" : hints[index]));
      row.title = hints[index] || "";
      row.addEventListener("click", () => {
        if (row.disabled) return;
        items.querySelectorAll("button").forEach(b => b.disabled = true);
        action({action: "approval", menu_id: menu.id, decision: ["deny", "once", "session", "always"][index]})
          .catch(() => { menuCache = ""; });
      });
    } else row.addEventListener("click", () => action({action: "select", menu_id: menu.id, index}).catch(() => {}));
    row.addEventListener("dblclick", () => key("enter", {index}).catch(() => {}));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); event.stopPropagation(); key("enter", {index}).catch(() => {}); }
    });
    items.append(row);
  });
  if (!menu.items.length) items.append(element("p", "empty", "Nothing here yet."));
  items.scrollTop = oldScroll;
  const actions = $("menu-actions"); actions.replaceChildren();
  for (const item of menu.actions) {
    if (menu.kind === "approval") continue;
    const button = element("button", "", item.label); button.dataset.key = item.key;
    button.disabled = Boolean(menu.retrying && ["r", "escape"].includes(item.key));
    button.addEventListener("click", () => applyMenu(item.key)); actions.append(button);
  }
  if (!dialog.open) dialog.showModal();
  if (newDialog) {
    items.querySelector(".selected")?.scrollIntoView({block: "nearest"});
    ($( "menu-close") || actions.firstElementChild).focus();
  }
}

function applyMenu(name) {
  const extra = {};
  if (state?.menu?.kind === "sampling" && name === "enter") {
    extra.values = {};
    for (const field of $("menu-items").querySelectorAll("input")) {
      if (!field.reportValidity()) return;
      extra.values[field.name] = Number(field.value);
    }
  }
  key(name, extra).then(() => {
    if (state?.menu?.kind === "sampling" && name === "r") {
      document.activeElement?.blur(); menuCache = "";
    }
  }).catch(() => {});
}

function renderTimeline(entries) {
  const node = $("side-tools"), signature = JSON.stringify(entries);
  if (node._rendered === signature || selectedInside(node)) return;
  const open = new Set([...node.querySelectorAll("details[open]")].map((item) => item.dataset.id));
  const bottom = node.scrollHeight - node.scrollTop - node.clientHeight < 45, scroll = node.scrollTop;
  node.replaceChildren();
  for (const item of entries) {
    const details = element("details"); details.dataset.id = item.call_id; details.open = open.has(item.call_id);
    const summary = element("summary", item.active ? "running" : item.ok ? "ok" : "failed", item.name);
    summary.append(element("span", "", `${item.active ? "Running" : item.ok ? "Done" : "Failed"} ${item.duration == null ? "" : item.duration.toFixed(1) + "s"}`));
    details.append(summary, element("pre", "", JSON.stringify(item.args, null, 2) + "\n\n" + item.result + `\n\nAttempt ${item.attempts}`)); node.append(details);
  }
  if (!entries.length) node.append(element("p", "empty", "No tool calls yet."));
  node._rendered = signature; node.scrollTop = bottom ? node.scrollHeight : scroll;
}

function renderMetrics(text) {
  const node = $("metrics"); if (node._text === text) return;
  node._text = text; node.replaceChildren();
  const plain = text.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "");
  const model = /(?:^|[|\n])\s*model:\s*([^|\n]+)/i.exec(plain)?.[1]?.trim() || "";
  const device = /(?:^|[|\n])\s*device:\s*([^|\n]+)/i.exec(plain)?.[1]?.trim() || "";
  $("active-model").textContent = [model, device].filter(Boolean).join(" / ");
  $("active-model").title = $("active-model").textContent;
  for (const part of plain.split(/[|\n]/).map((s) => s.trim()).filter(Boolean)) {
    if (/^(state|openvino|quack)(:|$)/i.test(part)) continue;
    const index = part.indexOf(":"), item = element("span");
    if (index > 0) item.append(element("b", "", part.slice(0, index) + ":"), document.createTextNode(part.slice(index + 1).trim()));
    else item.textContent = part;
    node.append(item);
  }
}

function renderQueue(items, paused) {
  const panel = $("queue-panel"), signature = JSON.stringify([items, paused]);
  panel.hidden = !items.length && !paused;
  if (panel._signature === signature) return;
  panel._signature = signature;
  $("queue-title").textContent = `Queue ${items.length}${paused ? " / paused" : ""}`;
  $("queue-pause").textContent = paused ? "Resume" : "Pause";
  const list = $("queue-items"); list.replaceChildren();
  for (const item of items) {
    const row = element("div", "queued-message");
    row.append(element("span", "", `#${item.id} ${item.text}`));
    for (const operation of ["edit", "remove"]) {
      const button = element("button", "", operation === "edit" ? "Edit" : "Remove");
      button.title = `${operation} queued message ${item.id}`;
      button.addEventListener("click", async () => {
        try {
          if (operation === "edit") {
            if (input.value.trim()) { notice("Clear current draft before editing queued message"); return; }
            await syncDraft();
          }
          await action({action:"queue",operation,id:item.id});
        } catch (_) {}
      });
      row.append(button);
    }
    list.append(row);
  }
}

function render(next) {
  const previous = state;
  state = next;
  if (next.transcript) transcript = next.transcript.replace ? next.transcript.text : transcript + next.transcript.text;
  transcriptVersion = next.transcript_version;
  document.body.classList.toggle("quack", next.duck);
  const page = next.duck ? "/duck.html" : "/openvino.html";
  if (location.pathname !== page) history.replaceState(null, "", page);
  document.body.classList.toggle("speaking", next.duck && next.operation === "generating" && Boolean(next.speech));
  document.body.classList.toggle("working", next.operation !== "ready");
  $("brand").textContent = next.duck ? "Quack" : "OpenVINO"; document.title = next.duck ? "Quack | OpenVINO" : "OpenVINO Chat";
  $("quack-toggle").setAttribute("aria-pressed", String(next.duck));
  $("disconnected").hidden = next.mode === "gui";
  $("disconnect-title").textContent = "Terminal active";
  $("disconnect-message").textContent = "Session continues in terminal. Keep terminal open to reconnect.";
  $("reconnect").hidden = false;
  const reading = Boolean(next.help || next.reader);
  $("reader-view").hidden = !reading; $("quack-view").hidden = !next.duck || reading; $("chat-view").hidden = next.duck || reading;
  if (reading) {
    $("reader-title").textContent = next.help ? "Help" : "Quack / Full reply";
    renderAnsi($("reader-content"), next.help || next.speech_formatted || next.speech);
  } else if (next.duck) {
    const parts = next.speech_parts.length ? next.speech_parts : [next.operation !== "ready" ? "On it. QUACK." : "QUACK. Your move."];
    if (speechUser !== next.user || (previous?.speech && !next.speech)) { followSpeech = true; speechUser = next.user; }
    paragraphIndex = followSpeech ? parts.length - 1 : Math.min(paragraphIndex, parts.length - 1);
    const speech = parts[paragraphIndex];
    const node = $("speech-bubbles");
    if (node._text !== speech && !selectedInside(node)) {
      const bottom = node.scrollHeight - node.scrollTop - node.clientHeight < 45, scroll = node.scrollTop;
      const bubble = element("div", "bubble"); bubble.append(ansiFragment(speech));
      node.replaceChildren(bubble);
      node._text = speech; node.scrollTop = bottom ? node.scrollHeight : scroll;
    }
    $("paragraph-count").textContent = `${paragraphIndex + 1} / ${parts.length}`;
    $("speech-prev").disabled = paragraphIndex === 0;
    $("speech-next").disabled = paragraphIndex >= parts.length - 1;
    $("speech-latest").hidden = followSpeech || parts.length < 2;
    $("speech-controls").hidden = parts.length < 2;
    const size = innerHeight >= 900 && innerWidth >= 1100 ? "large" : "small";
    renderAnsi($("character"), next.character[size] || "");
    const stage = $("character-stage"), zone = stage.parentElement;
    const scale = Math.min(.8, Math.max(.15, (zone.clientHeight - 12) / Math.max(1, stage.offsetHeight))).toFixed(3);
    if (stage.dataset.scale !== scale) { stage.dataset.scale = scale; stage.style.setProperty("--character-scale", scale); }
    const face = next.faces[size];
    for (const [id, x] of [["eye-left", face.left], ["eye-right", face.right]]) {
      $(id).style.left = x + "%"; $(id).style.top = face.eyes_y + "%";
    }
    $("beak").style.left = face.beak_x + "%"; $("beak").style.top = face.beak_y + "%";
    $("user-caption").textContent = next.user;
    $("tool-badge").textContent = /tool|command|search/.test(next.operation) ? `${next.detail || next.operation} / ${next.elapsed}s` : "";
    $("read-button").disabled = !next.speech;
    $("copy-reply").disabled = !next.speech;
    $("motion-toggle").setAttribute("aria-pressed", String(motionPaused));
  } else renderAnsi($("chat-log"), transcript, {follow: true, scroller: $("chat-view")});
  const showTasks = !next.duck && Boolean(next.tasks.trim());
  const mobile = innerWidth <= 640;
  $("sidebar").hidden = !next.sidepanel || reading || (mobile && !mobileSideOpen);
  $("side-toggle").setAttribute("aria-pressed", String(!$("sidebar").hidden));
  $("tasks-title").hidden = !showTasks;
  document.querySelectorAll("[data-tab]").forEach((button) => { button.hidden = false; button.setAttribute("aria-selected", String(button.dataset.tab === next.tab)); });
  for (const tab of ["chat", "tools", "charts"]) $("side-" + tab).hidden = next.tab !== tab;
  $("side-tasks").hidden = !showTasks || next.tab !== "chat";
  if (next.tab === "chat" && next.sidepanel && !reading) renderAnsi($("side-log"), transcript, {follow: true, scroller: $("side-chat")});
  if (next.tab === "tools") renderTimeline(next.timeline);
  if (next.tab === "charts") { $("visual-title").textContent = next.visual.kind || "Visual"; renderAnsi($("visual-content"), next.visual.text || "No visual yet."); }
  if (showTasks) renderAnsi($("tasks-content"), next.tasks);
  if (draftStash && next.ready && !commandPending) {
    input.value = draftStash; draftStash = null; draftDirty = true; draftVersion++; syncDraft().catch(() => {});
  } else if (!draftDirty && !draftStash && !commandPending && !inputMutation && next.input_version >= minimumInputVersion && next.input_version !== lastInputVersion) {
    if (input.value !== next.input) { input.value = next.input; const cursor = Array.from(next.input).slice(0, next.cursor).join("").length; input.setSelectionRange(cursor, cursor); }
    lastInputVersion = next.input_version;
  }
  input.disabled = Boolean(next.menu) || next.mode !== "gui";
  input.placeholder = next.ready ? "Message or /command" : "Queue next message";
  $("send-button").hidden = Boolean(next.menu); $("stop-button").hidden = next.ready || Boolean(next.menu);
  $("send-button").title = next.ready ? "Send (Enter)" : "Queue message (Enter)";
  $("send-button").disabled = uploading; $("attach-button").disabled = !next.ready || uploading;
  $("activity").hidden = next.ready || next.operation === "ready";
  $("activity").textContent = [next.detail || next.operation, `${next.elapsed}s`, next.stop_hotkey ? "Alt+Shift+S to stop" : "Esc to stop"].join(" / ");
  document.querySelectorAll("[data-command]").forEach((button) => button.disabled = !next.ready);
  $("connection").textContent = "Local"; $("state-label").textContent = next.operation;
  $("state-label").className = next.operation === "thinking" ? "thinking" : next.operation === "generating" ? "generating" : "";
  renderMetrics(next.status);
  if (!uploading && Date.now() >= localNoticeUntil) notice(next.notice, false);
  const tray = $("attachment-tray"); tray.hidden = !next.attachments.length && !uploading;
  tray.replaceChildren(...next.attachments.map(([kind, name]) => { const item = element("span", "attachment"); item.append(element("span", "", kind + ": " + name)); return item; }));
  if (uploading) tray.append(element("span", "", "Uploading attachment"));
  renderMenu(next.mode === "gui" ? next.menu : null); resizeInput(); renderPalette(); updateLatest();
  renderQueue(next.queue, next.queue_paused);
}

function updateLatest() {
  for (const [scroller, button] of [["chat-view", "main-latest"], ["side-chat", "side-latest"]]) {
    const node = $(scroller); $(button).hidden = node.hidden || node.scrollHeight - node.scrollTop - node.clientHeight < 50 || Boolean(state?.help || state?.reader);
  }
}

async function poll() {
  try {
    const next = await request("/state?since=" + transcriptVersion); pollFailures = 0; render(next);
  } catch (error) {
    pollFailures++; $("connection").textContent = "Disconnected";
    if (pollFailures >= 3) {
      $("disconnected").hidden = false; $("disconnect-title").textContent = "Connection lost";
      $("disconnect-message").textContent = error.message + ". Keep terminal running; reconnecting automatically.";
      $("reconnect").hidden = true;
    }
  } finally { setTimeout(poll, document.hidden || pollFailures ? 1000 : 250); }
}

async function uploadFiles(files) {
  if (!state?.ready || uploading) return;
  uploading = true;
  try {
    for (const file of files) {
      if (file.size > 256 * 1024 * 1024) throw new Error("Attachment exceeds 256 MiB");
      notice("Uploading " + file.name);
      const result = await request("/upload?name=" + encodeURIComponent(file.name), {method: "POST", body: file});
      uploaded.push(result);
      input.value += (input.value ? "\n" : "") + '"' + result.path + '"';
      draftDirty = true; draftVersion++; resizeInput();
    }
    await syncDraft(); notice("Attachment ready"); input.focus();
  } catch (error) { notice(error.message); }
  finally { uploading = false; $("file-input").value = ""; }
}

input.addEventListener("input", () => { draftDirty = true; draftVersion++; resizeInput(); renderPalette(); clearTimeout(draftTimer); draftTimer = setTimeout(() => syncDraft().catch(() => {}), 150); });
input.addEventListener("keydown", (event) => {
  if (event.isComposing) return;
  const matches = paletteMatches();
  if (matches.length && ["ArrowUp", "ArrowDown", "Tab"].includes(event.key)) {
    event.preventDefault();
    if (event.key === "Tab") chooseCommand(matches[paletteIndex], true);
    else { paletteIndex = Math.max(0, Math.min(matches.length - 1, paletteIndex + (event.key === "ArrowDown" ? 1 : -1))); renderPalette(); }
  } else if (event.key === "Enter" && !event.shiftKey && !event.ctrlKey) {
    event.preventDefault(); if (matches.length) chooseCommand(matches[paletteIndex]); else send().catch(() => {});
  } else if (event.ctrlKey && event.key.toLowerCase() === "j") {
    event.preventDefault(); input.setRangeText("\n", input.selectionStart, input.selectionEnd, "end"); input.dispatchEvent(new Event("input"));
  }
});
document.addEventListener("keydown", (event) => {
  if (event.isComposing) return;
  if (event.key === "Escape" && state?.ready && $("runtime-details").open) {
    event.preventDefault(); $("runtime-details").open = false; return;
  }
  if (state?.menu) {
    const editing = event.target instanceof HTMLInputElement;
    if (editing && event.key === "Enter") { event.preventDefault(); applyMenu("enter"); return; }
    if (!editing && ["ArrowUp", "ArrowDown", "Enter"].includes(event.key)) {
      if (event.key === "Enter" && event.target instanceof HTMLButtonElement) return;
      event.preventDefault(); key({ArrowUp: "up", ArrowDown: "down", Enter: "enter"}[event.key]).catch(() => {});
    }
    return;
  }
  const mapping = {F1: "f1", F2: "f2", F3: "f3", F4: "f4", F6: "f6", Escape: "escape"};
  if (mapping[event.key]) {
    event.preventDefault();
    if (event.key === "Escape" && !$("palette").hidden) { input.value = ""; input.dispatchEvent(new Event("input")); return; }
    key(mapping[event.key]).catch(() => {});
  } else if (event.target !== input && ["PageUp", "PageDown", "Home", "End"].includes(event.key)) {
    const node = !$("reader-view").hidden ? $("reader-content") : state?.duck && state.sidepanel ? $("side-" + state.tab) : $("chat-view");
    if (event.key.startsWith("Page")) { event.preventDefault(); node.scrollBy(0, node.clientHeight * (event.key === "PageDown" ? .9 : -.9)); }
    else if (event.ctrlKey) { event.preventDefault(); node.scrollTop = event.key === "Home" ? 0 : node.scrollHeight; }
  }
});
dialog.addEventListener("cancel", (event) => { event.preventDefault(); key("escape").catch(() => {}); });
$("menu-close").addEventListener("click", () => key("escape").catch(() => {}));
document.querySelectorAll("[data-command]").forEach((button) => button.addEventListener("click", () => send(button.dataset.command, true).catch(() => {})));
document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => action({action: "tab", tab: button.dataset.tab}).catch(() => {})));
$("send-button").addEventListener("click", () => send().catch(() => {}));
$("stop-button").addEventListener("click", () => key("escape").catch(() => {}));
$("help-button").addEventListener("click", () => key("f1").catch(() => {}));
$("read-button").addEventListener("click", () => key("f2").catch(() => {}));
$("reader-close").addEventListener("click", () => key(state?.help ? "f1" : "f2").catch(() => {}));
$("side-toggle").addEventListener("click", () => {
  if (innerWidth <= 640 && state?.sidepanel) { mobileSideOpen = !mobileSideOpen; render({...state, transcript: null}); }
  else { mobileSideOpen = true; send("/sidepanel " + (state?.sidepanel ? "off" : "on"), true).catch(() => {}); }
});
$("side-close").addEventListener("click", () => { mobileSideOpen = false; render({...state, transcript: null}); });
function moveParagraph(amount) {
  const count = state?.speech_parts.length || 1;
  paragraphIndex = Math.max(0, Math.min(count - 1, paragraphIndex + amount));
  followSpeech = paragraphIndex === count - 1;
  $("speech-bubbles").scrollTop = 0;
  render({...state, transcript: null});
}
$("speech-prev").addEventListener("click", () => moveParagraph(-1));
$("speech-next").addEventListener("click", () => moveParagraph(1));
$("speech-latest").addEventListener("click", () => { followSpeech = true; render({...state, transcript: null}); });
$("copy-reply").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(state?.speech || ""); notice("Reply copied"); }
  catch (_) { notice("Clipboard unavailable. Select reply text to copy."); }
});
$("motion-toggle").addEventListener("click", () => {
  motionPaused = !motionPaused; localStorage.setItem("openvino-motion-paused", String(motionPaused));
  document.body.classList.toggle("motion-paused", motionPaused);
  $("motion-toggle").setAttribute("aria-pressed", String(motionPaused));
});
$("queue-pause").addEventListener("click", () => action({action:"queue",operation:state?.queue_paused ? "resume" : "pause"}).catch(() => {}));
$("queue-clear").addEventListener("click", () => action({action:"queue",operation:"clear"}).catch(() => {}));
$("visual-close").addEventListener("click", () => action({action: "dismiss_visual"}).catch(() => {}));
$("tui-button").addEventListener("click", async () => { try { await syncDraft(); await action({action: "frontend", mode: "tui"}); } catch (_) {} });
$("reconnect").addEventListener("click", () => action({action: "frontend", mode: "gui"}).catch(() => {}));
$("attach-button").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (event) => uploadFiles(event.target.files));
for (const [scroller, button] of [["chat-view", "main-latest"], ["side-chat", "side-latest"]]) {
  $(scroller).addEventListener("scroll", updateLatest);
  $(button).addEventListener("click", () => { $(scroller).scrollTop = $(scroller).scrollHeight; });
}
document.addEventListener("pointerdown", (event) => { if (event.target.closest("pre,.bubble")) selectionDragging = true; });
document.addEventListener("pointerup", () => { selectionDragging = false; });
document.addEventListener("dragover", (event) => { event.preventDefault(); document.body.classList.add("dragging"); });
document.addEventListener("dragleave", (event) => { if (!event.relatedTarget) document.body.classList.remove("dragging"); });
document.addEventListener("drop", (event) => { event.preventDefault(); document.body.classList.remove("dragging"); uploadFiles(event.dataTransfer.files); });
input.addEventListener("paste", (event) => { const files = [...event.clipboardData.items].filter((item) => item.kind === "file").map((item) => item.getAsFile()).filter(Boolean); if (files.length) { event.preventDefault(); uploadFiles(files); } });
window.addEventListener("resize", () => { resizeInput(); renderPalette(); if (state) render({...state, transcript: null}); });

if (location.protocol === "file:" || !token) {
  $("disconnected").hidden = false; $("disconnect-title").textContent = "Open through terminal";
  $("disconnect-message").textContent = "Run openvino, then enter /gui. duck.html connects to that running session."; $("reconnect").hidden = true;
} else {
  request("/commands").then((items) => { commands = items; renderPalette(); }).catch((error) => notice(error.message));
  poll();
}
