/* taglog-web front end. Plain JavaScript, no external libraries. */
"use strict";

// ---------------------------------------------------------------- helpers
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else if (v === true) e.setAttribute(k, "");
    else e.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return e;
}

async function api(method, path, body) {
  const opts = { method, headers: { "X-Taglog": "1" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    toast("Cannot reach the taglog server. Is it still running?", true);
    throw e;
  }
  let data = {};
  try { data = await res.json(); } catch (e) { /* ignore */ }
  if (!res.ok) {
    const msg = data.error || `${res.status} ${res.statusText}`;
    toast(msg, true);
    throw new Error(msg);
  }
  return data;
}

let toastTimer = null;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "show" + (isError ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, isError ? 5000 : 2200);
}

function pad(n) { return String(n).padStart(2, "0"); }
function isoDate(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function parseIso(s) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
function addDays(s, n) { const d = parseIso(s); d.setDate(d.getDate() + n); return isoDate(d); }
function mondayOf(s) { const d = parseIso(s); const wd = (d.getDay() + 6) % 7; d.setDate(d.getDate() - wd); return isoDate(d); }
const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function fmtClock(secs) {
  secs = Math.max(0, Math.floor(secs));
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
  return `${h}:${pad(m)}:${pad(s)}`;
}
function fmtDur(secs, mode) {
  mode = mode || (state.prefs && state.prefs.duration_format) || "hhmm";
  secs = Math.round(secs || 0);
  if (mode === "hours") return (secs / 3600).toFixed(2);
  if (mode === "days") {
    const hpd = parseFloat((state.prefs && state.prefs.showtime_hours_per_day) || "7.58") || 7.58;
    return (secs / 3600 / hpd).toFixed(2);
  }
  const mins = Math.round(secs / 60);
  return `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`;
}
/** Elapsed time in the same style as start/end times: H:MM:SS, or H:MM when
 *  the "Time format" setting is H:MM (seconds are then dropped, as taglog does). */
/** Money with 2 decimals and the currency from Settings, e.g. "€ 1,234.50". */
function fmtMoney(v, cur) {
  if (v === null || v === undefined) return "";
  const n = Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return cur ? `${cur} ${n}` : n;
}
function fmtHM(secs) {
  secs = Math.max(0, Math.round(secs || 0));
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
  if (state.prefs && state.prefs.currentTimeFormat === "%d:%02d") return `${h}:${pad(m)}`;
  return `${h}:${pad(m)}:${pad(s)}`;
}
function fmtDate(iso) {
  if (!iso) return "";
  const f = (state.prefs && state.prefs.dateformat_view) || "YYYY-MM-DD";
  const m = /^(\d{4})-(\d{2})-(\d{2})(.*)$/.exec(iso);
  if (!m) return iso;
  if (f === "DD/MM/YYYY") return `${m[3]}/${m[2]}/${m[1]}${m[4]}`;
  if (f === "MM/DD/YYYY") return `${m[2]}/${m[3]}/${m[1]}${m[4]}`;
  return iso;
}
function longDate(iso) {
  const d = parseIso(iso);
  return d.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}
function fillDatalist(id, items) {
  const dl = document.getElementById(id);
  dl.replaceChildren(...(items || []).map(v => el("option", { value: v })));
}
function debounce(fn, ms) {
  let t = null;
  const f = (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  f.flush = (...a) => { clearTimeout(t); return fn(...a); };
  f.cancel = () => clearTimeout(t);
  return f;
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied to clipboard"); }
  catch (e) {
    openDialog({ title: "Copy text", body: el("textarea", { rows: 18, class: "mono", value: text }),
      buttons: [{ label: "Close" }] });
  }
}

// ---------------------------------------------------------------- dialog
function openDialog({ title, body, buttons = [], wide = false, onClose, help: helpId }) {
  const dlg = $("#dlg");
  $("#dlg-title").textContent = title;
  $("#dlg-help").replaceChildren(helpId ? (helpQ(helpId) || "") : "");
  dlg.dataset.help = helpId || "";
  const b = $("#dlg-body");
  b.replaceChildren(typeof body === "string" ? el("div", { text: body }) : body);
  const foot = $("#dlg-foot");
  foot.replaceChildren();
  for (const bt of buttons) {
    if (bt.spacer) { foot.append(el("span", { class: "spacer" })); continue; }
    const btn = el("button", {
      type: "button",
      class: "b" + (bt.primary ? " primary" : "") + (bt.danger ? " danger" : ""),
      text: bt.label,
    });
    btn.addEventListener("click", async () => {
      if (!bt.onClick) { dlg.close(); return; }
      btn.disabled = true;
      try {
        const keepOpen = await bt.onClick();
        if (keepOpen !== true) dlg.close();
      } catch (e) { /* error already shown */ }
      finally { btn.disabled = false; }
    });
    foot.append(btn);
  }
  dlg.style.width = wide ? "min(980px, calc(100vw - 32px))" : "";
  dlg.onclose = () => { if (onClose) onClose(); };
  dlg.showModal();
  const first = b.querySelector("input, textarea, select");
  if (first) first.focus();
}
function field(label, input, cls) {
  return el("label", { class: "f" + (cls ? " " + cls : "") }, el("span", { text: label }), input);
}
function confirmDialog(title, text, okLabel = "OK", danger = false) {
  return new Promise(resolve => {
    let answered = false;
    openDialog({
      title, body: el("p", { text }),
      buttons: [
        { label: "Cancel", onClick: () => { answered = true; resolve(false); } },
        { label: okLabel, primary: !danger, danger, onClick: () => { answered = true; resolve(true); } },
      ],
      onClose: () => { if (!answered) resolve(false); },
    });
  });
}

// ---------------------------------------------------------------- state
const state = {
  today: null, prefs: null, fetchedAt: 0, dirty: false,
  logDate: isoDate(new Date()), projects: [],
};

// ---------------------------------------------------------------- navigation
function showView(name) {
  $$("nav.side button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  if (name === "today") loadToday();
  if (name === "log") loadLogDay();
  if (name === "actions") loadActions();
  if (name === "projects") loadProjects();
  if (name === "settings") loadSettings();
  if (name === "help") loadHelpView();
  if (name === "reports") initReports();
  try { localStorage.setItem("taglog.view", name); } catch (e) { /* ignore */ }
}
function setupSubtabs(containerId) {
  const tabs = $("#" + containerId);
  const view = tabs.parentElement;
  tabs.addEventListener("click", e => {
    const b = e.target.closest("button[data-sub]");
    if (!b) return;
    $$("button", tabs).forEach(x => x.classList.toggle("active", x === b));
    $$(".sub", view).forEach(s => s.classList.toggle("hidden", s.dataset.sub !== b.dataset.sub));
  });
}

// ================================================================ TODAY
const curFields = {
  start: "#cur-start", project: "#cur-project", activity: "#cur-activity",
  contact: "#cur-contact", rate: "#cur-rate", description: "#cur-desc",
};
function readCurFields() {
  const out = {};
  for (const [k, sel] of Object.entries(curFields)) out[k] = $(sel).value;
  return out;
}
const saveSession = debounce(async () => {
  $("#cur-saved").textContent = "Saving…";
  try {
    await api("POST", "/api/session", readCurFields());
    state.dirty = false;
    $("#cur-saved").textContent = "Saved";
  } catch (e) { $("#cur-saved").textContent = "Not saved"; }
}, 700);

async function loadToday() {
  const data = await api("GET", "/api/today");
  renderToday(data);
}

function renderToday(data) {
  state.today = data;
  state.prefs = data.prefs;
  state.fetchedAt = Date.now();
  const s = data.session;
  fillDatalist("dl-projects", data.projects);
  fillDatalist("dl-activities", data.activities);
  fillDatalist("dl-contacts", data.contacts);
  $("#side-ver").textContent = "v" + data.version;

  if (!state.dirty) {
    for (const [k, sel] of Object.entries(curFields)) {
      const input = $(sel);
      if (document.activeElement !== input) input.value = s[k] || "";
    }
  }
  // action select
  const sel = $("#cur-action");
  const opts = [el("option", { value: "", text: "—" })];
  const known = new Set();
  for (const a of data.active_actions) {
    known.add(a.id);
    opts.push(el("option", { value: a.id, text: (a.subtask_of ? "  ↳ " : "") + a.title + (a.project ? `  [${a.project}]` : "") }));
  }
  if (s.action && !known.has(s.action)) opts.push(el("option", { value: s.action, text: s.action_title || s.action }));
  sel.replaceChildren(...opts);
  sel.value = s.action || "";
  $("#btn-complete").disabled = !s.action;
  $("#btn-abort").disabled = !s.action;

  $("#btn-pause").textContent = s.running ? "Pause" : "Resume";
  $("#btn-adjust").disabled = !s.running;
  $("#btn-next").disabled = !s.running;
  $("#btn-next-menu").disabled = !s.running;
  $("#btn-pop").disabled = !s.stack_depth;
  const stackPill = $("#cur-stack");
  stackPill.classList.toggle("hidden", !s.stack_depth && !s.stack_info);
  stackPill.textContent = s.stack_depth ? `Stack depth ${s.stack_depth}` : (s.stack_info || "");
  stackPill.title = s.stack_info ? `Stack-info: ${s.stack_info}` : "";

  renderTimer();
  renderBanners(data);
  renderTodayEntries(data);
  renderProjectTimes(data);
  renderTodayActions(data);
  $("#side-date").textContent = longDate(data.date);
}

function renderTimer() {
  const d = state.today;
  if (!d) return;
  const s = d.session;
  const t = $("#cur-timer");
  if (!s.running) {
    t.textContent = "Paused";
    t.classList.add("paused");
    $("#cur-since").textContent = "Not timing — press Resume to start a new entry";
    return;
  }
  t.classList.remove("paused");
  const secs = (s.elapsed || 0) + (Date.now() - state.fetchedAt) / 1000;
  t.textContent = fmtClock(secs);
  $("#cur-since").textContent = `Started at ${s.start}`;
}

function renderBanners(data) {
  const box = $("#banners");
  box.replaceChildren();
  for (const a of data.due_blocked || []) {
    box.append(el("div", { class: "banner row" },
      el("span", {}, el("b", { text: "Time-blocked action due: " }), `${a.title} (${a.id}), active after ${a.active_after}`),
      el("span", { class: "spacer" }),
      el("button", { class: "b", type: "button", text: "Activate", onclick: async () => {
        await api("POST", `/api/actions/${encodeURIComponent(a.id)}/state`, { state: "Active" });
        toast("Action activated"); loadToday();
      } })));
  }
  for (const w of (data.prefs.warnings || [])) {
    box.append(el("div", { class: "banner small" }, el("b", { text: "Preferences: " }), w));
  }
}

function entryCard(e, date, onChanged) {
  const meta = [e.Activity, e.ActionTitle && `Action: ${e.ActionTitle}`, e.Contact && `Contact: ${e.Contact}`, e.Rate, e["Stack-info"] && `Stack: ${e["Stack-info"]}`].filter(Boolean);
  const card = el("div", { class: "entry", tabindex: "0", title: "Click to edit" },
    el("div", { class: "h" },
      el("span", { class: "time", text: `${e.StartTime || "?"} – ${e.EndTime || "?"}` }),
      el("span", { class: "proj", text: e.Project || "(no project)" }),
      meta.length ? el("span", { class: "muted small", text: meta.join(" · ") }) : null,
      el("span", { class: "dur", text: fmtHM(e._duration) })),
    e.Description ? el("div", { class: "desc", text: e.Description }) : null);
  const open = () => editEntryDialog(date, e, onChanged);
  card.addEventListener("click", open);
  card.addEventListener("keydown", ev => { if (ev.key === "Enter") open(); });
  return card;
}

function renderTodayEntries(data) {
  const box = $("#today-entries");
  const sum = $("#today-summary");
  sum.replaceChildren(data.summary ? el("div", { class: "summary-text", text: data.summary }) : "");
  if (!data.entries.length) {
    box.replaceChildren(el("div", { class: "empty", text: "No entries yet today. Press Next when you finish something." }));
    return;
  }
  box.replaceChildren(...data.entries.slice().reverse().map(e => entryCard(e, data.date, loadToday)));
}

function renderProjectTimes(data) {
  const t = $("#proj-times");
  const pt = data.project_times;
  const cur = data.session.project || "unknown";
  const rows = pt.rows.map(r => {
    const over = !!r.over_budget;
    const hasExp = r.expected_seconds !== null && r.expected_seconds !== undefined;
    const tr = el("tr", { class: "click" + (r.project === cur && data.session.running ? " current-row" : ""),
      title: `Start a new entry on ${r.project}` },
      el("td", {}, r.project === "unknown" ? el("i", { class: "muted", text: "unknown" }) : r.project,
        r.breaks ? el("span", { class: "pill grey", style: "margin-left:6px", text: "break" }) : null,
        over ? el("span", { class: "pill danger", style: "margin-left:6px", text: "over budget" }) : null),
      el("td", { class: "num" + (over ? " over" : ""), text: r.total_booked === null ? "" : fmtHM(r.total_booked) }),
      el("td", { class: "num", text: fmtHM(r.seconds) }),
      el("td", { class: "num muted", text: hasExp ? fmtHM(r.expected_seconds) : "—",
        title: r.expected_unreadable ? "The expected time on this project cannot be read" : "" }),
      el("td", { class: "num" + (over ? " over" : ""), text: !hasExp ? "—" : (over ? "−" + fmtHM(-r.remaining) : fmtHM(r.remaining)) }));
    tr.addEventListener("click", () => doNext("", r.project === "unknown" ? "" : r.project));
    return tr;
  });
  const blank = () => el("td", {});
  rows.push(el("tr", { class: "total" }, el("td", { text: "Booked today" }), blank(),
    el("td", { class: "num", text: fmtHM(pt.total) }), blank(), blank()));
  rows.push(el("tr", {}, el("td", { class: "muted", text: "Booked today (non breaks)" }), blank(),
    el("td", { class: "num", text: fmtHM(pt.total_nonbreaks) }), blank(), blank()));
  t.replaceChildren(
    el("thead", {}, el("tr", {}, el("th", { text: "Project" }),
      el("th", { class: "num", text: "Total booked", title: "All time logged on the project since its start date" }),
      el("th", { class: "num", text: "Today" }),
      el("th", { class: "num", text: "Expected" }),
      el("th", { class: "num", text: "Remaining", title: "Expected minus total booked" }))),
    el("tbody", {}, ...rows));
}

function renderTodayActions(data) {
  const card = $("#today-actions-card");
  const n = data.today_actions.length;
  card.classList.toggle("hidden", n === 0);
  const box = $("#today-actions");
  if (box.contains(document.activeElement)) return;
  const save = debounce(async () => {
    await api("POST", "/api/today-actions", { titles: $$("input", box).map(i => i.value) });
  }, 800);
  box.replaceChildren(...data.today_actions.map((t, i) =>
    el("input", { value: t, placeholder: `Action ${i + 1}`, list: "dl-today-acts", oninput: save })));
  let dl = document.getElementById("dl-today-acts");
  if (!dl) { dl = el("datalist", { id: "dl-today-acts" }); document.body.append(dl); }
  dl.replaceChildren(...data.active_actions.map(a => el("option", { value: a.title })));
}

async function doNext(activity = "", project = null) {
  saveSession.cancel();
  const data = await api("POST", "/api/next", { activity, project, fields: readCurFields() });
  state.dirty = false;
  $("#cur-desc").value = "";
  renderToday(data);
  $("#cur-saved").textContent = "Entry logged";
}

function nextMenu() {
  const acts = state.today ? state.today.activities : [];
  const wrap = el("div", { class: "row" });
  const close = () => $("#dlg").close();
  wrap.append(el("button", { type: "button", class: "b", text: "— (no activity)", onclick: () => { close(); doNext(""); } }));
  for (const a of acts) {
    wrap.append(el("button", { type: "button", class: "b", text: a, onclick: () => { close(); doNext(a); } }));
  }
  openDialog({ title: "Next, with activity…", help: "introduction", body: el("div", {},
    el("p", { class: "muted", style: "margin-top:0", text: "Logs the current entry and starts a new one with the chosen activity." }), wrap),
  buttons: [{ label: "Cancel" }] });
}

function adjustDialog() {
  const d = state.today;
  const s = d.session;
  if (!s.running) { toast("Taglog is paused; press Resume first", true); return; }
  const last = d.entries[d.entries.length - 1];
  const prevStart = last ? last.StartTime : "0:00:00";
  const toSecs = t => { const p = (t || "0").split(":").map(Number); return (p[0] || 0) * 3600 + (p[1] || 0) * 60 + (p[2] || 0); };
  const curSecs = toSecs(s.start);
  const room = Math.max(0, curSecs - toSecs(prevStart));          // seconds the start can move back
  const maxMin = Math.floor(room / 60);
  const input = el("input", { class: "mono", value: s.start });
  const slider = el("input", { type: "range", min: 0, max: maxMin, value: 0, step: 1, style: "width:100%" });
  const fmtStart = secs => {
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), ss = secs % 60;
    return (state.prefs.currentTimeFormat === "%d:%02d") ? `${h}:${pad(m)}` : `${h}:${pad(m)}:${pad(ss)}`;
  };
  const lbl = el("span", { class: "muted small", text: "0 minutes earlier" });
  slider.addEventListener("input", () => {
    input.value = fmtStart(Math.max(0, curSecs - slider.value * 60));
    lbl.textContent = `${slider.value} minute${slider.value == 1 ? "" : "s"} earlier`;
  });
  const hasPrev = !!(last && last.EndTime);
  const adjPrev = el("input", { type: "checkbox", checked: hasPrev });
  const intro = last
    ? `The previous entry is ${last.StartTime}–${last.EndTime || "?"}` + (last.Project ? ` (${last.Project})` : "") +
      `. The start can move back as far as ${prevStart}, so the two entries don't overlap.`
    : "No earlier entry today: the start can move back as far as the start of the day.";
  const tooShort = last && maxMin < 1;
  const body = el("div", {},
    el("p", { class: "muted", style: "margin-top:0", text: intro }),
    tooShort ? el("div", { class: "banner small" },
      el("b", { text: "The slider can't move: " }),
      `the previous entry started only ${room} second${room === 1 ? "" : "s"} before this one. ` +
      "To go further back, edit or delete that entry first. ",
      el("button", { type: "button", class: "b", text: "Edit previous entry", onclick: () => {
        $("#dlg").close(); setTimeout(() => editEntryDialog(d.date, last, loadToday), 0);
      } })) : null,
    field("New start time", input),
    tooShort ? null : el("div", { style: "margin:12px 0" }, slider, lbl),
    hasPrev ? el("label", { class: "check" }, adjPrev, "Also set the previous entry's end time to this") : null);
  openDialog({ title: "Adjust start time", help: "adjstart", body, buttons: [
    { label: "Cancel" },
    { label: "Set", primary: true, onClick: async () => {
      const v = input.value.trim();
      if (!/^\d{1,2}:\d{2}(:\d{2})?$/.test(v)) { toast("Enter the time as H:MM or H:MM:SS", true); return true; }
      if (hasPrev && adjPrev.checked && toSecs(v) < toSecs(prevStart)) {
        toast(`${v} is before the previous entry started (${prevStart}). Edit that entry first, or untick the box.`, true);
        return true;
      }
      if (v === s.start) return;
      const data = await api("POST", "/api/adjust-start", { start: v, adjust_prev: hasPrev && adjPrev.checked });
      state.dirty = false;
      renderToday(data);
      toast(`Start time set to ${v}`);
    } }] });
}

function editEntryDialog(date, e, onChanged) {
  const mk = (name, attrs = {}) => el("input", Object.assign({ value: e[name] || "" }, attrs));
  const inputs = {
    StartTime: mk("StartTime", { class: "mono" }), EndTime: mk("EndTime", { class: "mono" }),
    Project: mk("Project", { list: "dl-allprojects" }), Activity: mk("Activity", { list: "dl-activities" }),
    Action: mk("Action"), ActionTitle: mk("ActionTitle"), Contact: mk("Contact", { list: "dl-contacts" }),
    Rate: mk("Rate"), "Stack-info": mk("Stack-info", { class: "mono" }),
    Description: el("textarea", { rows: 7, value: e.Description || "" }),
  };
  const body = el("div", { class: "fields" },
    field("Start", inputs.StartTime), field("End", inputs.EndTime),
    field("Project", inputs.Project), field("Activity", inputs.Activity),
    field("Action Id", inputs.Action), field("Action title", inputs.ActionTitle),
    field("Contact", inputs.Contact), field("Rate", inputs.Rate), field("Stack-info", inputs["Stack-info"]),
    field("Description", inputs.Description, "wide"));
  addFieldHelp(inputs, n => "logedit_" + n.toLowerCase().replace(/-/g, "_"));
  openDialog({ title: `Edit entry — ${fmtDate(date)}`, help: "logedit", body, buttons: [
    { label: "Delete", danger: true, onClick: async () => {
      if (!(await confirmDialog("Delete entry", "Delete this log entry? This cannot be undone.", "Delete", true))) return;
      await api("DELETE", `/api/log/${date}/${e._index}`);
      toast("Entry deleted"); onChanged && onChanged();
    } },
    { spacer: true },
    { label: "Cancel" },
    { label: "Save", primary: true, onClick: async () => {
      const b = {};
      for (const [k, i] of Object.entries(inputs)) b[k] = i.value;
      await api("PUT", `/api/log/${date}/${e._index}`, b);
      toast("Entry saved"); onChanged && onChanged();
    } }] });
}

async function daySummaryDialog(date, current, onDone) {
  const ta = el("textarea", { rows: 12, value: current || "" });
  openDialog({ title: `Summary of ${fmtDate(date)}`, help: "summarybox", body: el("div", {},
    el("p", { class: "muted", style: "margin-top:0", text: "Enter the summary of what you did on this day." }), ta),
  buttons: [{ label: "Cancel" }, { label: "Save", primary: true, onClick: async () => {
    await api("POST", `/api/log/${date}/summary`, { text: ta.value });
    toast("Summary saved"); onDone && onDone();
  } }] });
}

function setupToday() {
  for (const sel of Object.values(curFields)) {
    $(sel).addEventListener("input", () => { state.dirty = true; $("#cur-saved").textContent = "…"; saveSession(); });
  }
  $("#cur-action").addEventListener("change", async ev => {
    await saveSession.flush();
    const data = await api("POST", "/api/current-action", { id: ev.target.value });
    state.dirty = false;
    renderToday(data);
  });
  $("#btn-next").addEventListener("click", () => doNext(""));
  $("#btn-next-menu").addEventListener("click", nextMenu);
  $("#btn-pause").addEventListener("click", async () => {
    saveSession.cancel();
    const running = state.today && state.today.session.running;
    const data = await api("POST", running ? "/api/pause" : "/api/resume", { fields: readCurFields() });
    state.dirty = false;
    renderToday(data);
  });
  const stackOp = (path, body) => async () => {
    saveSession.cancel();
    const data = await api("POST", path, Object.assign({ fields: readCurFields() }, body || {}));
    state.dirty = false;
    renderToday(data);
  };
  $("#btn-interrupt").addEventListener("click", stackOp("/api/stack/push", { kind: "!" }));
  $("#btn-push").addEventListener("click", stackOp("/api/stack/push", { kind: "+" }));
  $("#btn-pop").addEventListener("click", stackOp("/api/stack/pop"));
  $("#btn-complete").addEventListener("click", stackOp("/api/current-action/complete"));
  $("#btn-abort").addEventListener("click", async () => {
    if (await confirmDialog("Abort action", "Log this entry and mark the current action as Aborted?", "Abort action", true))
      await stackOp("/api/current-action/abort")();
  });
  $("#btn-adjust").addEventListener("click", adjustDialog);
  $("#btn-day-summary").addEventListener("click", () => daySummaryDialog(state.today.date, state.today.summary, loadToday));
  document.addEventListener("keydown", ev => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter" && $("#view-today").classList.contains("active") && !$("#dlg").open) {
      ev.preventDefault();
      if (state.today && state.today.session.running) doNext("");
    }
  });
  setInterval(renderTimer, 1000);
  setInterval(() => {
    if ($("#view-today").classList.contains("active") && !document.hidden && !$("#dlg").open) loadToday().catch(() => {});
  }, 60000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && $("#view-today").classList.contains("active")) loadToday().catch(() => {});
  });
}

// ================================================================ LOG
async function loadLogDay() {
  $("#log-date").value = state.logDate;
  const data = await api("GET", `/api/log/${state.logDate}`);
  const box = $("#log-day");
  const total = data.entries.reduce((a, e) => a + (e._duration || 0), 0);
  $("#log-total").textContent = data.exists ? `${data.entries.length} entries · ${fmtHM(total)}` : "";
  state.logSummary = data.summary;
  const card = el("div", { class: "card" }, el("h2", { text: longDate(state.logDate) }));
  if (!data.exists) card.append(el("div", { class: "empty", text: "No log file for this day." }));
  if (data.summary) card.append(el("div", { class: "summary-text", text: data.summary }));
  const list = el("div", { class: "entries" }, ...data.entries.map(e => entryCard(e, state.logDate, loadLogDay)));
  card.append(list);
  box.replaceChildren(card);
  // refresh projects datalist for editing
  if (!state.projects.length) {
    const p = await api("GET", "/api/projects");
    state.projects = p.projects;
    fillDatalist("dl-allprojects", p.projects.map(x => x.name));
  }
}

function searchQuery() {
  const q = new URLSearchParams();
  for (const [k, id] of [["from", "s-from"], ["to", "s-to"], ["project", "s-project"],
    ["activity", "s-activity"], ["contact", "s-contact"], ["text", "s-text"]]) {
    const v = $("#" + id).value.trim();
    if (v) q.set(k, v);
  }
  return q;
}
async function doSearch() {
  const data = await api("GET", "/api/search?" + searchQuery().toString());
  state.searchResult = data.days;
  const summOnly = $("#s-summ").checked;
  const box = $("#s-results");
  if (!data.days.length) { box.replaceChildren(el("div", { class: "card empty", text: "Nothing found." })); return; }
  let n = 0, total = 0;
  const parts = [];
  for (const day of data.days) {
    if (summOnly && !day.summary) continue;
    const card = el("div", { class: "card" }, el("h2", {}, el("button", { class: "link", type: "button", text: longDate(day.date),
      onclick: () => { state.logDate = day.date; showView("log"); $("#log-tabs button[data-sub=day]").click(); } })));
    if (day.summary) card.append(el("div", { class: "summary-text", text: day.summary }));
    if (!summOnly) {
      for (const e of day.entries) { n++; total += e._duration; }
      card.append(el("div", { class: "entries" }, ...day.entries.map(e => entryCard(e, day.date, doSearch))));
    }
    parts.push(card);
  }
  box.replaceChildren(summOnly ? "" : el("p", { class: "muted", text: `${n} entries, ${fmtHM(total)} in total.` }), ...parts);
}
function searchAsText() {
  const days = state.searchResult || [];
  const summOnly = $("#s-summ").checked;
  const lines = [];
  for (const d of days) {
    if (summOnly && !d.summary) continue;
    lines.push("", "   " + fmtDate(d.date), "");
    if (d.summary) lines.push("Summary: " + d.summary);
    if (summOnly) continue;
    for (const e of d.entries) {
      for (const [k, v] of Object.entries(e)) if (!k.startsWith("_") && k !== "Id") lines.push(`${k}: ${v}`);
      lines.push("_______________________________");
    }
  }
  return lines.join("\n");
}

function setupLog() {
  setupSubtabs("log-tabs");
  $("#log-date").addEventListener("change", e => { if (e.target.value) { state.logDate = e.target.value; loadLogDay(); } });
  $("#log-prev").addEventListener("click", () => { state.logDate = addDays(state.logDate, -1); loadLogDay(); });
  $("#log-next").addEventListener("click", () => { state.logDate = addDays(state.logDate, 1); loadLogDay(); });
  $("#log-today").addEventListener("click", () => { state.logDate = isoDate(new Date()); loadLogDay(); });
  $("#log-summary-btn").addEventListener("click", () => daySummaryDialog(state.logDate, state.logSummary, loadLogDay));
  const today = isoDate(new Date());
  $("#s-from").value = addDays(today, -30);
  $("#s-to").value = today;
  $("#s-go").addEventListener("click", doSearch);
  $("#s-copy").addEventListener("click", () => copyText(searchAsText()));
  $$("#view-log [data-sub=search] input").forEach(i => i.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); }));
  // month / year summaries
  const ms = $("#ms-month");
  for (let m = 1; m <= 12; m++) ms.append(el("option", { value: pad(m), text: new Date(2000, m - 1, 1).toLocaleDateString(undefined, { month: "long" }) }));
  $("#ms-year").value = new Date().getFullYear();
  ms.value = pad(new Date().getMonth() + 1);
  const msPath = () => `/api/summary/${$("#ms-year").value}${ms.value ? "-" + ms.value : ""}`;
  const msLoad = async () => { const d = await api("GET", msPath()); $("#ms-text").value = d.text; };
  $("#ms-load").addEventListener("click", msLoad);
  ms.addEventListener("change", msLoad);
  $("#ms-year").addEventListener("change", msLoad);
  $("#ms-save").addEventListener("click", async () => { await api("POST", msPath(), { text: $("#ms-text").value }); toast("Summary saved"); });
  $("#log-tabs button[data-sub=summaries]").addEventListener("click", msLoad);
}

// ================================================================ ACTIONS
const STATES = ["Unclaimed", "Pending", "Active", "Blocked", "Delegated", "Completed", "Aborted", "Periodic"];
const DEFAULT_STATES = ["Unclaimed", "Pending", "Active", "Blocked", "Delegated"];
const EXPECTED_TIMES = ["0:05", "0:10", "0:20", "0:30", "1:00", "2:00", "3:00", "4:00", "6:00", "8:00", "12:00", "16:00", "24:00", "40:00"];

function setupActions() {
  const box = $("#a-states");
  let saved = DEFAULT_STATES;
  try { const s = JSON.parse(localStorage.getItem("taglog.states") || "null"); if (Array.isArray(s)) saved = s; } catch (e) { /* ignore */ }
  for (const s of STATES) {
    box.append(el("label", { class: "check" }, el("input", { type: "checkbox", value: s, checked: saved.includes(s), onchange: () => {
      try { localStorage.setItem("taglog.states", JSON.stringify(checkedStates())); } catch (e) { /* ignore */ }
      loadActions();
    } }), s));
  }
  const reload = debounce(loadActions, 300);
  ["#a-project", "#a-maxpri", "#a-text"].forEach(s => $(s).addEventListener("input", reload));
  $("#a-sort").addEventListener("change", loadActions);
  $("#a-new").addEventListener("click", () => actionDialog(null));
}
function checkedStates() { return $$("#a-states input:checked").map(i => i.value); }

async function loadActions() {
  const q = new URLSearchParams();
  const st = checkedStates();
  q.set("status", st.length ? st.join(",") : "none");
  if ($("#a-project").value) q.set("project", $("#a-project").value);
  if ($("#a-maxpri").value) q.set("maxpriority", $("#a-maxpri").value);
  if ($("#a-text").value) q.set("text", $("#a-text").value);
  if ($("#a-sort").value) q.set("sort", $("#a-sort").value);
  const [data, pj] = await Promise.all([api("GET", "/api/actions?" + q), api("GET", "/api/projects")]);
  state.projects = pj.projects;
  fillDatalist("dl-allprojects", pj.projects.map(x => x.name));
  const list = $("#a-list");
  let totalExpected = 0;
  for (const a of data.actions) {
    const m = /^(\d+):(\d+)/.exec(a["Expected-time"] || "");
    if (m) totalExpected += (+m[1]) * 3600 + (+m[2]) * 60;
  }
  $("#a-stats").textContent = `Displayed ${data.actions.length} actions · total expected time ${fmtHM(totalExpected)}`;
  if (!data.actions.length) { list.replaceChildren(el("div", { class: "empty", text: "No actions match." })); return; }
  const today = isoDate(new Date());
  list.replaceChildren(...data.actions.map(a => {
    const due = a["Expected-completed-date"];
    const overdue = due && due.slice(0, 10) < today && !["Completed", "Aborted"].includes(a.Status);
    const statusCls = { Active: "ok", Completed: "grey", Aborted: "grey", Blocked: "warn", Delegated: "warn" }[a.Status] || "";
    const card = el("div", { class: "action", tabindex: "0" },
      el("div", { class: "title", text: a.Title || "(untitled)" }),
      el("div", {}, el("span", { class: "pill " + statusCls, text: a.Status || "?" })),
      el("div", { class: "meta" }, [a.Id, a.Project, a.Priority && `priority ${a.Priority}`, a["Expected-time"] && `expected ${a["Expected-time"]}`,
        a["Subtask-of"] && `subtask of ${a["Subtask-of"]}`].filter(Boolean).join(" · ")),
      el("div", { class: "meta" }, due ? el("span", { class: overdue ? "pill danger" : "", text: `due ${fmtDate(due)}` }) : ""));
    card.addEventListener("click", () => actionDialog(a.Id));
    card.addEventListener("keydown", e => { if (e.key === "Enter") actionDialog(a.Id); });
    return card;
  }));
}

async function actionDialog(id, preset) {
  let a = {};
  let items = [];
  if (id) {
    const d = await api("GET", `/api/actions/${encodeURIComponent(id)}`);
    a = d.action; items = a._items || [];
  } else {
    a = Object.assign({ Id: "", Priority: "50", Status: "Pending", Project: (state.today && state.today.session.project) || "" }, preset || {});
  }
  if (!state.projects.length) {
    const pj = await api("GET", "/api/projects");
    state.projects = pj.projects;
    fillDatalist("dl-allprojects", pj.projects.map(x => x.name));
  }
  const allActs = (await api("GET", "/api/actions?status=" + STATES.join(","))).actions;
  let dl = document.getElementById("dl-action-ids");
  if (!dl) { dl = el("datalist", { id: "dl-action-ids" }); document.body.append(dl); }
  dl.replaceChildren(...allActs.map(x => el("option", { value: x.Id, label: x.Title })));
  let dlt = document.getElementById("dl-exptimes");
  if (!dlt) { dlt = el("datalist", { id: "dl-exptimes" }); document.body.append(dlt); dlt.append(...EXPECTED_TIMES.map(v => el("option", { value: v }))); }

  const inp = {};
  const text = (name, attrs = {}) => (inp[name] = el("input", Object.assign({ value: a[name] || "" }, attrs)));
  const select = (name, values) => {
    const s = el("select", {}, el("option", { value: "", text: "—" }), ...values.map(v => el("option", { value: v, text: v })));
    if (a[name] && !values.includes(a[name])) s.append(el("option", { value: a[name], text: a[name] }));
    s.value = a[name] || "";
    return (inp[name] = s);
  };
  const area = name => (inp[name] = el("textarea", { rows: 4, value: a[name] || "" }));
  const dateHint = { placeholder: "YYYY-MM-DD", class: "mono" };
  const body = el("div", {},
    el("div", { class: "fields" },
      field("Title", text("Title"), "wide"),
      field("Id", text("Id", id ? { readonly: true, class: "mono" } : { placeholder: "automatic", class: "mono" })),
      field("Project", text("Project", { list: "dl-allprojects" })),
      field("Status", select("Status", STATES)),
      field("Priority", select("Priority", ["10", "20", "30", "40", "50", "60", "70", "80", "90"])),
      field("Date", text("Date", { placeholder: "YYYY-MM-DD HH:MM (automatic)", class: "mono" })),
      field("Expected time (h:mm)", text("Expected-time", { list: "dl-exptimes", class: "mono" })),
      field("Expected start date", text("Expected-start-date", dateHint)),
      field("Expected completed date", text("Expected-completed-date", dateHint)),
      field("Active after", text("Active-after", { placeholder: "YYYY-MM-DD [HH:MM]", class: "mono", title: "If set, the action is Blocked until this time" })),
      field("Expected cost", text("Expected-cost")),
      field("Difficulty", select("Difficulty", ["0", "1", "2", "3", "4", "5"])),
      field("Period", text("Period", { placeholder: "e.g. Daily, Weekly 1" })),
      field("Subtask of", text("Subtask-of", { list: "dl-action-ids", class: "mono" })),
      field("Next action (activated on completion)", text("Next-action", { list: "dl-action-ids", class: "mono" })),
      field("Abort action", text("Abort-action", { list: "dl-action-ids", class: "mono" })),
      field("Precursor", text("Precursor", { list: "dl-action-ids", class: "mono" })),
      field("Delegated to", text("Delegated-to", { list: "dl-contacts" })),
      field("Email status to (stored only; mail is not sent)", text("Email-status-to")),
      field("Description", area("Description"), "wide"),
      field("Deliverable", area("Deliverable"), "wide"),
      field("Reason", area("Reason"), "wide"),
      field("Summary", area("Summary"), "wide")));

  if (id) {
    const known = new Set(Object.keys(inp).concat(["End"]));
    const extra = items.filter(([k]) => !known.has(k));
    if (extra.length) {
      body.append(el("h3", { style: "margin-top:16px", text: "History fields" }),
        el("table", { class: "t" }, el("tbody", {}, ...extra.map(([k, v]) =>
          el("tr", {}, el("td", { class: "muted", text: k }), el("td", { style: "white-space:pre-wrap", text: v }))))));
    }
    const note = el("textarea", { rows: 2, placeholder: "Optional note recorded with the state change" });
    const stateBtns = el("div", { class: "row" });
    const transitions = [["Active", "Activate"], ["Completed", "Complete"], ["Aborted", "Abort"], ["Pending", "Make pending"], ["Blocked", "Block"], ["Delegated", "Delegate"]];
    for (const [s, label] of transitions) {
      if (s === a.Status) continue;
      stateBtns.append(el("button", { type: "button", class: "b" + (s === "Aborted" ? " danger" : ""), text: label, onclick: async () => {
        const r = await api("POST", `/api/actions/${encodeURIComponent(id)}/state`, { state: s, note: note.value });
        toast(`Action ${s.toLowerCase()}` + (r.next_action ? ` — next action ${r.next_action} activated` : ""));
        $("#dlg").close(); refreshAfterActionChange();
      } }));
    }
    body.append(el("h3", { style: "margin-top:16px", text: "Change state" }), note, el("div", { style: "margin-top:8px" }, stateBtns));
    const hist = el("div", { class: "muted small", text: "Loading time logged…" });
    body.append(el("h3", { style: "margin-top:16px", text: "Time logged" }), hist);
    api("GET", `/api/actions/${encodeURIComponent(id)}/history`).then(h => {
      if (!h.entries.length) { hist.textContent = "No log entries refer to this action."; return; }
      hist.replaceChildren(el("p", { text: `Total ${fmtHM(h.total)} in ${h.entries.length} entries` + (a["Expected-time"] ? ` (expected ${a["Expected-time"]})` : "") }),
        el("table", { class: "t" }, el("tbody", {}, ...h.entries.map(e => el("tr", {},
          el("td", { class: "mono", text: fmtDate(e.date) }), el("td", { class: "mono", text: `${e.start}–${e.end}` }),
          el("td", { class: "num", text: fmtHM(e.duration) }), el("td", { style: "white-space:pre-wrap", text: e.description || e.activity || "" }))))));
    }).catch(() => { hist.textContent = "Could not load."; });
  }

  const collect = () => { const b = {}; for (const [k, i] of Object.entries(inp)) b[k] = i.value; return b; };
  const buttons = [];
  if (id) {
    buttons.push({ label: "Work on this now", onClick: async () => {
      await api("POST", "/api/current-action", { id }); toast("Current action set"); showView("today");
    } });
    buttons.push({ label: "Add subtask…", onClick: async () => {
      setTimeout(() => actionDialog(null, { Project: a.Project || "", "Subtask-of": id }), 50);
    } });
  }
  buttons.push({ spacer: true }, { label: "Cancel" });
  buttons.push({ label: id ? "Save" : "Add action", primary: true, onClick: async () => {
    const b = collect();
    if (!b.Title.trim()) { toast("Please enter a title", true); return true; }
    if (id) { await api("PUT", `/api/actions/${encodeURIComponent(id)}`, b); toast("Action saved"); }
    else { const r = await api("POST", "/api/actions", b); toast(`Action ${r.action.Id} added`); }
    refreshAfterActionChange();
  } });
  addFieldHelp(inp, n => "actinput_" + n.toLowerCase().replace(/-/g, "_"));
  openDialog({ title: id ? `Action ${id}` : "New action", help: "actinput", body, buttons, wide: true });
}
function refreshAfterActionChange() {
  if ($("#view-actions").classList.contains("active")) loadActions();
  if ($("#view-today").classList.contains("active")) loadToday();
  if ($("#view-reports").classList.contains("active") && !$("[data-sub=review]", $("#view-reports")).classList.contains("hidden")) loadReview();
  if ($("#view-reports").classList.contains("active") && !$("[data-sub=gantt]", $("#view-reports")).classList.contains("hidden") && state.gantt) loadGantt();
}

// ================================================================ PROJECTS
async function loadProjects() {
  const data = await api("GET", "/api/projects");
  state.projects = data.projects;
  fillDatalist("dl-allprojects", data.projects.map(x => x.name));
  const showClosed = $("#p-showclosed").checked;
  const flag = b => b ? "✓" : "";
  const rows = data.projects.filter(p => showClosed || !p.closed).map(p => {
    const tr = el("tr", { class: "click", tabindex: "0" },
      el("td", {}, p.name, p.closed ? el("span", { class: "pill grey", style: "margin-left:6px", text: "closed" }) : null),
      el("td", { class: "mono", text: p.code }),
      el("td", { text: flag(p.active) }), el("td", { text: flag(p.breaks) }), el("td", { text: flag(p.overheads) }), el("td", { text: flag(p.immutable) }),
      el("td", { class: "mono", text: fmtDate(p.start) }), el("td", { class: "mono", text: fmtDate(p.end) }),
      el("td", { class: "mono", text: p.expected_time }),
      el("td", {}, el("button", { type: "button", class: "b", text: "Gantt", title: `Gantt chart for ${p.name}`,
        onclick: ev => { ev.stopPropagation(); openGantt(p.name); } })));
    tr.addEventListener("click", () => projectDialog(p));
    tr.addEventListener("keydown", e => { if (e.key === "Enter") projectDialog(p); });
    return tr;
  });
  $("#p-table").replaceChildren(
    el("thead", {}, el("tr", {}, ...["Name", "Code", "Active", "Breaks", "Overheads", "Immutable", "Start", "End", "Expected time", ""].map(h => el("th", { text: h })))),
    el("tbody", {}, ...(rows.length ? rows : [el("tr", {}, el("td", { colspan: 10, class: "empty", text: "No projects yet. Add one to start booking time to it." }))])));
}

function projectDialog(p) {
  const isNew = !p;
  p = p || { name: "", code: "", start: isoDate(new Date()), end: "", expected_time: "", active: true, breaks: false, overheads: false, immutable: false };
  const inp = {
    name: el("input", { value: p.name }), code: el("input", { value: p.code, class: "mono" }),
    start: el("input", { type: "date", value: p.start }), end: el("input", { type: "date", value: p.end }),
    expected_time: el("input", { value: p.expected_time, placeholder: "hours, e.g. 40 or 40:30", class: "mono" }),
  };
  const chk = {};
  for (const f of ["active", "breaks", "overheads", "immutable"]) chk[f] = el("input", { type: "checkbox", checked: !!p[f] });
  const body = el("div", {},
    el("div", { class: "fields" },
      field("Project name", inp.name), field("Booking code", inp.code),
      field("Start date", inp.start), field("End date", inp.end), field("Expected time", inp.expected_time)),
    el("div", { class: "row", style: "margin-top:14px" },
      el("label", { class: "check" }, chk.active, "Project is active"),
      el("label", { class: "check" }, chk.breaks, "Book as breaks"),
      el("label", { class: "check" }, chk.overheads, "Book as overheads"),
      el("label", { class: "check" }, chk.immutable, "Project is immutable")));
  const buttons = [];
  if (!isNew) buttons.push({ label: "Delete", danger: true, onClick: async () => {
    if (!(await confirmDialog("Delete project", `Delete project “${p.name}”? Log entries that use it are not changed.`, "Delete", true))) return;
    await api("DELETE", `/api/projects/${encodeURIComponent(p.name)}`); toast("Project deleted"); loadProjects();
  } }, { label: "Close today", onClick: async () => { inp.end.value = isoDate(new Date()); return true; } });
  buttons.push({ spacer: true }, { label: "Cancel" }, { label: isNew ? "Add project" : "Save", primary: true, onClick: async () => {
    const b = { name: inp.name.value.trim(), code: inp.code.value.trim(), start: inp.start.value, end: inp.end.value,
      expected_time: inp.expected_time.value.trim() };
    for (const [k, c] of Object.entries(chk)) b[k] = c.checked;
    if (!b.name) { toast("Please enter a project name", true); return true; }
    if (isNew) await api("POST", "/api/projects", b); else await api("PUT", `/api/projects/${encodeURIComponent(p.name)}`, b);
    toast("Project saved"); loadProjects();
  } });
  addFieldHelp(inp, n => ({ expected_time: "project_expectedtime", end: "ep_enddate" })[n]);
  openDialog({ title: isNew ? "Add project" : `Project ${p.name}`, help: isNew ? "addproject" : "editproject", body, buttons });
}

function setupProjects() {
  $("#p-new").addEventListener("click", () => projectDialog(null));
  $("#p-showclosed").addEventListener("change", loadProjects);
}

// ================================================================ REPORTS
let reportsInit = false;
function initReports() {
  if (reportsInit) return;
  reportsInit = true;
  const prefs = state.prefs || {};
  let start = mondayOf(isoDate(new Date()));
  if (prefs.timebook_startlastweek !== "0") start = addDays(start, -7);
  $("#tb-start").value = start;
  $("#tb-spread").value = prefs.showtime_spreadoverheads || "byweek";
  $("#tb-bookby").value = prefs.book_by || "code";
  $("#tb-format").value = prefs.duration_format || "hours";
  const today = isoDate(new Date());
  const monthStart = today.slice(0, 8) + "01";
  for (const id of ["ta-from", "ir-from"]) $("#" + id).value = monthStart;
  for (const id of ["ta-to", "ir-to", "pp-to"]) $("#" + id).value = today;
  const lm = parseIso(monthStart); lm.setMonth(lm.getMonth() - 1);
  $("#pp-from").value = isoDate(lm);
}
function tbQuery() {
  return new URLSearchParams({ start: mondayOf($("#tb-start").value || isoDate(new Date())), weeks: $("#tb-weeks").value || "1",
    spread: $("#tb-spread").value, book_by: $("#tb-bookby").value, format: $("#tb-format").value });
}
async function loadTimebook() {
  const q = tbQuery();
  $("#tb-start").value = q.get("start");
  const data = await api("GET", "/api/reports/timebook?" + q);
  const fmt = q.get("format");
  const out = [];
  for (const w of data.weeks) {
    const days = w.days.map(d => { const x = parseIso(d); return `${WD[x.getDay()]} ${pad(x.getDate())}/${pad(x.getMonth() + 1)}`; });
    const priced = !!data.rates;
    const cur = data.currency || "";
    const moneyCells = (otSecs, amount, bold) => priced ? [
      el("td", { class: "num", text: otSecs ? fmtDur(otSecs, fmt) : "" }),
      el("td", { class: "num", text: fmtMoney(amount, cur), style: bold ? "font-weight:700" : null })] : [];
    const tbl = el("table", { class: "t" },
      el("thead", {}, el("tr", {}, el("th", { text: "Project" }), el("th", { class: "num", text: "Total" }), ...days.map(d => el("th", { class: "num", text: d })),
        ...(priced ? [el("th", { class: "num", text: "Overtime" }), el("th", { class: "num", text: cur ? `Amount (${cur})` : "Amount" })] : []))),
      el("tbody", {},
        ...w.rows.map(r => el("tr", {}, el("td", { text: r.project }), el("td", { class: "num", text: fmtDur(r.total, fmt), style: "font-weight:700" }),
          ...r.days.map(v => el("td", { class: "num", text: v ? fmtDur(v, fmt) : "" })), ...moneyCells(r.overtime, r.amount, true))),
        el("tr", { class: "total" }, el("td", { text: "Total (non breaks)" }), el("td", { class: "num", text: fmtDur(w.nonbreaks_total, fmt) }),
          ...w.day_totals.map(v => el("td", { class: "num", text: v ? fmtDur(v, fmt) : "" })), ...moneyCells(w.overtime_total, w.amount_total, true)),
        el("tr", {}, el("td", { class: "muted", text: "Breaks total" }), el("td", { class: "num", text: fmtDur(w.breaks_total, fmt) }))));
    const card = el("div", { class: "card" },
      el("h2", { text: `Week ${w.iso_week} — ${fmtDate(w.days[0])} to ${fmtDate(w.days[6])}` }),
      priced ? el("p", { class: "muted small", text: `Amounts at ${fmtMoney(data.rates.hourly, cur)} per hour; overtime × ${data.rates.overtime_multiplier}. Breaks are not charged.` })
        : el("p", { class: "muted small", text: "Set an hourly rate in Settings to see amounts." }),
      w.overheads_total ? el("p", { class: "muted small", text: `Overheads of ${fmtHM(w.overheads_total)} spread ${data.spread === "byday" ? "per day" : "over the week"} in proportion to project time.` }) : null,
      el("div", { class: "scroll-x" }, tbl),
      w.warnings.length ? el("p", { class: "muted small", text: w.warnings.join(" · ") }) : null);
    out.push(card);
  }
  $("#tb-out").replaceChildren(...out);
}
async function loadActivityReport() {
  const q = new URLSearchParams({ from: $("#ta-from").value, to: $("#ta-to").value, project: $("#ta-project").value });
  const d = await api("GET", "/api/reports/activity?" + q);
  $("#ta-out").replaceChildren(el("div", { class: "card" }, el("table", { class: "t" },
    el("thead", {}, el("tr", {}, el("th", { text: "Activity" }), el("th", { class: "num", text: "Total time" }), el("th", { class: "num", text: "%" }))),
    el("tbody", {}, ...d.rows.map(r => el("tr", {}, el("td", { text: r.activity }), el("td", { class: "num", text: fmtHM(r.seconds) }),
      el("td", { class: "num", text: d.total ? (100 * r.seconds / d.total).toFixed(1) : "" }))),
    el("tr", { class: "total" }, el("td", { text: "Total" }), el("td", { class: "num", text: fmtHM(d.total) }), el("td", {}))))));
}
async function loadProjectTotal() {
  const q = new URLSearchParams({ project: $("#pt-project").value, from: $("#pt-from").value, to: $("#pt-to").value });
  const d = await api("GET", "/api/reports/project-total?" + q);
  const over = !!d.over_budget;
  const proj = state.projects.find(x => x.name === d.project);
  const partial = proj && ((q.get("from") && q.get("from") !== (proj.start || "")) || (q.get("to") && q.get("to") !== (proj.end || "")));
  const stat = (label, value, cls, extra) => el("div", { class: "stat" },
    el("div", { class: "stat-label", text: label }), el("div", { class: "stat-value" + (cls ? " " + cls : ""), text: value }), extra || null);
  let expectedTile, remainingTile;
  if (d.expected_seconds === null || d.expected_seconds === undefined) {
    const hint = d.expected_unreadable ? `“${d.expected_time}” is not a time taglog can read (use hours, e.g. 40 or 40.5, or h:mm, e.g. 40:30)`
      : "No expected time set for this project";
    expectedTile = stat("Expected", "—", "", el("div", { class: "muted small" }, hint, " — ",
      el("button", { class: "link", type: "button", text: "set it in Projects", onclick: () => showView("projects") })));
    remainingTile = stat("Remaining", "—");
  } else {
    expectedTile = stat("Expected", fmtHM(d.expected_seconds), "", el("div", { class: "muted small", text: `${fmtDur(d.expected_seconds, "hours")} hours` }));
    remainingTile = over
      ? stat("Over by", fmtHM(-d.remaining), "over", el("div", { class: "muted small", text: `${(100 * d.total / d.expected_seconds).toFixed(0)}% of expected time used` }))
      : stat("Remaining", fmtHM(d.remaining), "", el("div", { class: "muted small", text: d.expected_seconds ? `${(100 * d.total / d.expected_seconds).toFixed(0)}% of expected time used` : "" }));
  }
  const actualTile = stat("Actual", fmtHM(d.total), over ? "over" : "",
    el("div", { class: "muted small", text: `${fmtDur(d.total, "hours")} hours · ${fmtDur(d.total, "days")} days` }));
  $("#pt-out").replaceChildren(el("div", { class: "card" },
    el("div", { class: "row" }, el("h2", { style: "margin:0", text: `Total time for ${d.project}` }),
      over ? el("span", { class: "pill danger", text: "over budget" }) : null),
    el("div", { class: "stats" }, actualTile, expectedTile, remainingTile),
    partial ? el("p", { class: "muted small", text: "Actual time is for the selected dates only, not the whole project." }) : null,
    d.amount !== null && d.amount !== undefined ? el("p", {}, el("b", { text: `Amount: ${fmtMoney(d.amount, d.currency)}` }),
      d.breaks ? " (Breaks project: not charged)" : (d.overtime ? ` — includes ${fmtHM(d.overtime)} of overtime` : "")) : null,
    el("p", { class: "muted", text: `Examined ${d.files_examined} day files and found entries in ${d.days_with_entries} of them.` +
      (d.first_date ? ` First date ${fmtDate(d.first_date)}, last date ${fmtDate(d.last_date)}.` : "") }),
    el("table", { class: "t" }, el("thead", {}, el("tr", {}, el("th", { text: "Activity" }), el("th", { class: "num", text: "Total time" }))),
      el("tbody", {}, ...d.activities.map(r => el("tr", {}, el("td", { text: r.activity }), el("td", { class: "num", text: fmtHM(r.seconds) }))),
        el("tr", { class: "total" }, el("td", { text: "Total" }), el("td", { class: "num" + (over ? " over" : ""), text: fmtHM(d.total) }))))));
}
async function loadProgress() {
  const q = new URLSearchParams({ project: $("#pp-project").value, from: $("#pp-from").value, to: $("#pp-to").value });
  const d = await api("GET", "/api/reports/progress?" + q);
  state.progress = d;
  const section = (title, rows, h1, h2) => el("div", { class: "card" }, el("h2", { text: title }),
    rows.length ? el("table", { class: "t" }, el("thead", {}, el("tr", {}, el("th", { text: "Title" }), el("th", { text: h1 }), el("th", { text: h2 }))),
      el("tbody", {}, ...rows.map(r => el("tr", { class: "click", onclick: () => actionDialog(r.id) }, el("td", { text: r.title }),
        el("td", { class: "mono", text: fmtDate(r.expected) }), el("td", { class: "mono", text: fmtDate(r.actual) })))))
      : el("div", { class: "empty", text: "None." }));
  $("#pp-out").replaceChildren(
    el("p", { class: "muted", text: `Project progress report for ${d.project || "all projects"}, from ${fmtDate(d.start) || "the beginning"} to ${fmtDate(d.end) || "today"}.` }),
    section("Tasks completed", d.completed, "Expected date", "Completed date"),
    section("Tasks started", d.started, "Expected start", "Actual start"),
    section("Tasks slipped (past their expected completion date)", d.slipped, "Expected date", "Original expected date"),
    section("Active tasks", d.active, "Scheduled completion", "Started"));
}
function progressAsText() {
  const d = state.progress;
  if (!d) return "";
  const out = [`Project Progress Report`, `Project: ${d.project || "(all)"}`, `Progress from ${d.start} to ${d.end}`, ""];
  for (const [t, rows] of [["Tasks completed", d.completed], ["Tasks started", d.started], ["Tasks slipped", d.slipped], ["Active tasks", d.active]]) {
    out.push(t);
    for (const r of rows) out.push(`  ${r.title}\t${r.expected}\t${r.actual}`);
    if (!rows.length) out.push("  (none)");
    out.push("");
  }
  return out.join("\n");
}
async function loadReview() {
  const d = await api("GET", "/api/reports/review");
  const rows = d.rows.map(r => {
    const et = el("input", { value: r.expected_time, class: "mono", style: "width:80px", list: "dl-exptimes" });
    const ed = el("input", { value: r.expected_completed, class: "mono", style: "width:150px", placeholder: "YYYY-MM-DD" });
    const save = el("button", { class: "b", type: "button", text: "Revise", onclick: async () => {
      const res = await api("POST", `/api/actions/${encodeURIComponent(r.id)}/revise`, { expected_time: et.value, expected_date: ed.value });
      toast(res.revised ? "Revised" : "Nothing changed"); loadReview();
    } });
    return el("tr", {},
      el("td", {}, el("button", { class: "link", type: "button", text: r.title, onclick: () => actionDialog(r.id) }), el("div", { class: "muted small", text: r.project })),
      el("td", { class: "num" }, el("span", { class: r.over_time ? "pill danger" : "", text: fmtHM(r.spent) })),
      el("td", {}, et), el("td", {}, ed, r.overdue ? el("span", { class: "pill danger", style: "margin-left:6px", text: "overdue" }) : null),
      el("td", {}, save));
  });
  $("#rv-out").replaceChildren(el("div", { class: "card scroll-x" }, rows.length ? el("table", { class: "t" },
    el("thead", {}, el("tr", {}, ...["Action", "Time logged", "Expected time", "Expected completion", ""].map(h => el("th", { text: h })))),
    el("tbody", {}, ...rows)) : el("div", { class: "empty", text: "No active actions." })));
  let dlt = document.getElementById("dl-exptimes");
  if (!dlt) { dlt = el("datalist", { id: "dl-exptimes" }); document.body.append(dlt); dlt.append(...EXPECTED_TIMES.map(v => el("option", { value: v }))); }
}
async function loadInterruptions() {
  const q = new URLSearchParams({ from: $("#ir-from").value, to: $("#ir-to").value });
  const d = await api("GET", "/api/reports/interruptions?" + q);
  $("#ir-out").replaceChildren(el("div", { class: "card" },
    el("p", { text: `There were a total of ${d.total} interruptions in ${d.days} days.` }),
    el("p", { text: `The average number of interruptions in a day was ${d.average}.` }),
    el("p", { text: `The peak number of interruptions per day was ${d.peak}` + (d.peak_day ? ` (${fmtDate(d.peak_day)}).` : ".") }),
    el("p", { class: "muted small", text: "Interruptions are entries started with the Interrupt (!) button." })));
}
function setupReports() {
  setupSubtabs("rep-tabs");
  $("#tb-go").addEventListener("click", loadTimebook);
  $("#tb-prev").addEventListener("click", () => { $("#tb-start").value = addDays(mondayOf($("#tb-start").value), -7); loadTimebook(); });
  $("#tb-nextw").addEventListener("click", () => { $("#tb-start").value = addDays(mondayOf($("#tb-start").value), 7); loadTimebook(); });
  $("#tb-csv").addEventListener("click", () => { window.location.href = "/export/timebook.csv?" + tbQuery(); });
  $("#ta-go").addEventListener("click", loadActivityReport);
  $("#pt-go").addEventListener("click", loadProjectTotal);
  $("#pt-project").addEventListener("change", () => {
    const p = state.projects.find(x => x.name === $("#pt-project").value);
    if (p) { $("#pt-from").value = p.start || ""; $("#pt-to").value = p.end || ""; }
  });
  $("#pp-go").addEventListener("click", loadProgress);
  $("#pp-copy").addEventListener("click", () => copyText(progressAsText()));
  $("#rv-go").addEventListener("click", loadReview);
  $("#rep-tabs button[data-sub=review]").addEventListener("click", loadReview);
  $("#ir-go").addEventListener("click", loadInterruptions);
  api("GET", "/api/projects").then(p => { state.projects = p.projects; fillDatalist("dl-allprojects", p.projects.map(x => x.name)); }).catch(() => {});
}

// ================================================================ SETTINGS
async function loadSettings() {
  const p = await api("GET", "/api/prefs");
  state.prefs = p;
  $("#set-file").textContent = p.prefs_exists ? `Preferences file: ${p.prefs_path} (shared with the original taglog)` :
    `No preferences file yet; saving will create ${p.prefs_path}.`;
  $("#set-warnings").replaceChildren(...(p.warnings || []).map(w => el("div", { class: "banner small", text: w })));
  $("#set-rootdir").value = p.rootdir;
  $("#set-actfile").value = p.activitiesfilename;
  $("#set-datefmt").value = p.dateformat_view;
  $("#set-timefmt").value = p.currentTimeFormat;
  $("#set-hpd").value = p.showtime_hours_per_day;
  $("#set-spread").value = p.showtime_spreadoverheads;
  $("#set-lastweek").value = p.timebook_startlastweek;
  $("#set-nta").value = p.num_today_actions;
  if (!help.index) await loadHelpIndex();
  const langs = help.index.languages.slice();
  if (!langs.find(l => l.code === p.language)) langs.push({ code: p.language, name: p.language, topics: 0 });
  $("#set-language").replaceChildren(...langs.map(l => el("option", { value: l.code,
    text: l.code === "en" ? l.name : `${l.name} (${l.topics} help topics)` })));
  $("#set-language").value = p.language;
  $("#set-activities").value = (p.activities || []).join("\n");
  $("#set-rate").value = p.hourly_rate;
  $("#set-otmult").value = p.overtime_multiplier;
  $("#set-currency").value = p.rate_currency;
  const files = [["Data directory", p.rootdir_expanded], ["Projects", p.files.projects], ["Actions", p.files.actions],
    ["Contacts", p.files.contacts], ["Activities", p.activities_file]];
  $("#set-files").replaceChildren(el("tbody", {}, ...files.map(([k, v]) => el("tr", {}, el("td", { class: "muted", text: k }), el("td", { class: "mono", text: v })))));
}
function setupSettings() {
  $("#set-save").addEventListener("click", async () => {
    const values = {
      rootdir: $("#set-rootdir").value.trim() || "~/diary",
      activitiesfilename: $("#set-actfile").value.trim(),
      dateformat_view: $("#set-datefmt").value, currentTimeFormat: $("#set-timefmt").value,
      showtime_hours_per_day: $("#set-hpd").value, language: $("#set-language").value,
      hourly_rate: $("#set-rate").value, overtime_multiplier: $("#set-otmult").value, rate_currency: $("#set-currency").value, showtime_spreadoverheads: $("#set-spread").value,
      timebook_startlastweek: $("#set-lastweek").value, num_today_actions: $("#set-nta").value,
    };
    const activities = $("#set-activities").value.split("\n").map(s => s.trim()).filter(Boolean);
    await api("POST", "/api/prefs", { values, activities });
    toast("Settings saved");
    help.lang = null;
    reportsInit = false;
    loadSettings();
  });
}

// ================================================================ GANTT
const SVGNS = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, ...children) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v);
  for (const c of children.flat()) if (c !== null && c !== undefined) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return e;
}
function dayDiff(a, b) { return Math.round((parseIso(b) - parseIso(a)) / 864e5); }

/** Visual state of a row's actual bar; always shown with a text label too. */
function ganttState(r) {
  if (r.status === "Aborted") return { cls: "gt-aborted", label: "aborted" };
  if (r.late) return { cls: "gt-late", label: r.status === "Completed" ? "finished late" : (r.actual_start ? "late" : "late, not started") };
  if (r.status === "Completed") return { cls: "gt-done", label: "done on time" };
  if (!r.actual_start) return { cls: "", label: "not started" };
  return { cls: "gt-open", label: "in progress" };
}
function ganttRowText(r) {
  const st = ganttState(r);
  const plan = r.planned_start ? `planned ${fmtDate(r.planned_start)} – ${fmtDate(r.planned_end)}` +
    (r.planned_start_from_created ? " (start = creation date)" : "") : "no planned dates";
  const act = r.actual_start ? `actual ${fmtDate(r.actual_start)} – ${r.actual_open ? "today (open)" : fmtDate(r.actual_end)}` : "not started";
  return { st, plan, act };
}

async function loadGantt() {
  const project = $("#gt-project").value.trim();
  if (!project) { toast("Choose a project", true); return; }
  const q = new URLSearchParams({ project, aborted: $("#gt-aborted").checked ? "1" : "0" });
  const d = await api("GET", "/api/reports/gantt?" + q);
  state.gantt = d;
  renderGantt();
}

function renderGantt() {
  const d = state.gantt;
  const out = $("#gt-out");
  if (!d) return;
  const card = el("div", { class: "card" }, el("h2", { text: `Gantt — ${d.project}` }));
  if (!d.rows.length) {
    card.append(el("div", { class: "empty", text: d.unscheduled.length
      ? "None of this project's actions has dates yet. Give actions an Expected start / completed date to place them on the chart."
      : "This project has no actions yet." }));
  } else if ($("#gt-table").checked) {
    card.append(el("div", { class: "scroll-x" }, el("table", { class: "t" },
      el("thead", {}, el("tr", {}, ...["Action", "Status", "Planned", "Actual", ""].map(h => el("th", { text: h })))),
      el("tbody", {}, ...d.rows.map(r => {
        const t = ganttRowText(r);
        return el("tr", { class: "click", onclick: () => actionDialog(r.id) },
          el("td", { style: `padding-left:${8 + r.depth * 16}px`, text: r.title || r.id }),
          el("td", { text: r.status }), el("td", { class: "mono", text: t.plan.replace(/^planned /, "") }),
          el("td", { class: "mono", text: t.act.replace(/^actual /, "") }),
          el("td", {}, r.late ? el("span", { class: "pill danger", text: t.st.label }) : t.st.label));
      })))));
  } else {
    card.append(ganttLegend(d), ganttChart(d));
  }
  if (d.unscheduled.length) {
    card.append(el("h3", { style: "margin-top:16px", text: "Not scheduled" }),
      el("p", { class: "muted small", style: "margin-top:0", text: "These actions have no planned or actual dates." }),
      el("div", { class: "row" }, ...d.unscheduled.map(r =>
        el("button", { type: "button", class: "b", text: `${r.title || r.id} (${r.status})`, onclick: () => actionDialog(r.id) }))));
  }
  out.replaceChildren(card);
}

function ganttLegend(d) {
  const sw = (cls, label, shape) => el("span", { class: "gt-leg" },
    shape || el("span", { class: "gt-sw " + cls }), label);
  const items = [
    sw("gt-plan-sw", "Planned"),
    sw("gt-open", "Actual: in progress"),
    sw("gt-done", "Actual: done on time"),
    sw("gt-late", "Actual: late"),
  ];
  if (d.rows.some(r => r.status === "Aborted")) items.push(sw("gt-aborted", "Actual: aborted"));
  items.push(sw("", "Today", el("span", { class: "gt-sw-line" })));
  if (d.project_start || d.project_end) items.push(sw("", "Project start / end", el("span", { class: "gt-sw-diamond" })));
  if (d.links.length) items.push(sw("", "Next action / precursor", el("span", { class: "gt-sw-arrow", text: "→" })));
  return el("div", { class: "gt-legend" }, ...items);
}

function ganttChart(d) {
  const wrap = el("div", { class: "gt-wrap" });
  const tip = el("div", { class: "gt-tip hidden", role: "tooltip" });
  const narrow = window.innerWidth < 720;
  const labelW = narrow ? 150 : 250, rowH = 36, headH = 46, padR = 16;
  const days = dayDiff(d.range_start, d.range_end) + 1;
  const avail = Math.max(320, ($("#gt-out").clientWidth || 900) - 40 - labelW - padR);
  const dayW = Math.max(6, Math.min(36, avail / days));
  const W = labelW + days * dayW + padR, H = headH + d.rows.length * rowH + 8;
  const x = iso => labelW + dayDiff(d.range_start, iso) * dayW;     // start of that day
  const xEnd = iso => x(iso) + dayW;                                 // end of that day (inclusive)
  const root = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "gt-svg", role: "img",
    "aria-label": `Gantt chart for ${d.project}: ${d.rows.length} actions` });
  root.append(svg("defs", {}, svg("marker", { id: "gt-arrow", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
    svg("path", { d: "M0,0 L8,4 L0,8 z", class: "gt-arrowhead" }))));

  // grid: Mondays (hairlines) and month labels
  const grid = svg("g", {});
  const months = svg("g", {});
  for (let i = 0; i < days; i++) {
    const date = new Date(parseIso(d.range_start)); date.setDate(date.getDate() + i);
    const iso = isoDate(date), gx = x(iso);
    if (date.getDay() === 1) {
      grid.append(svg("line", { x1: gx, x2: gx, y1: headH - 14, y2: H, class: "gt-grid" }));
      if (dayW * 7 >= 30) grid.append(svg("text", { x: gx + 3, y: headH - 4, class: "gt-axis" }, String(date.getDate())));
    }
    if (date.getDate() === 1 || i === 0) {
      months.append(svg("text", { x: gx + 3, y: 14, class: "gt-axis gt-month" },
        date.toLocaleDateString(undefined, { month: "short", year: date.getMonth() === 0 || i === 0 ? "numeric" : undefined })));
      if (i > 0) grid.append(svg("line", { x1: gx, x2: gx, y1: 0, y2: H, class: "gt-grid gt-grid-month" }));
    }
  }
  root.append(grid, months, svg("line", { x1: labelW, x2: W - padR, y1: headH, y2: headH, class: "gt-grid" }));

  // rows
  const rowY = {};
  const rowsG = svg("g", {});
  d.rows.forEach((r, i) => {
    const y = headH + i * rowH;
    rowY[r.id] = y;
    const st = ganttState(r);
    const g = svg("g", { class: "gt-row", tabindex: "0", role: "button", "aria-label": `${r.title}: ${r.status}, ${st.label}` });
    if (i % 2) g.append(svg("rect", { x: 0, y, width: W, height: rowH, class: "gt-band" }));
    const indent = 8 + r.depth * 14;
    const maxChars = Math.floor((labelW - indent - 8) / 6.6);
    const title = (r.depth ? "↳ " : "") + (r.title || r.id);
    g.append(svg("text", { x: indent, y: y + 15, class: "gt-label" }, title.length > maxChars ? title.slice(0, maxChars - 1) + "…" : title));
    const sub = `${r.status} · ${st.label}`, subMax = Math.floor((labelW - indent - (r.depth ? 12 : 0) - 8) / 5.6);
    g.append(svg("text", { x: indent + (r.depth ? 12 : 0), y: y + 29, class: "gt-sub" + (r.late ? " gt-sub-late" : "") },
      sub.length > subMax ? sub.slice(0, subMax - 1) + "…" : sub));
    if (r.planned_start) {
      g.append(svg("rect", { x: x(r.planned_start) + 1, y: y + 8, width: Math.max(4, xEnd(r.planned_end) - x(r.planned_start) - 2), height: 18, rx: 4, class: "gt-plan" }));
    }
    if (r.actual_start) {
      const ax = x(r.actual_start) + 1, aw = Math.max(4, xEnd(r.actual_end) - x(r.actual_start) - 2);
      g.append(svg("rect", { x: ax, y: y + 20, width: aw, height: 6, rx: 3, class: st.cls }));
      if (r.actual_open) g.append(svg("circle", { cx: ax + aw, cy: y + 23, r: 4, class: st.cls + " gt-ring" }));
    }
    // generous hit target: the whole row
    g.append(svg("rect", { x: 0, y, width: W, height: rowH, class: "gt-hit" }));
    const show = ev => {
      const t = ganttRowText(r);
      tip.replaceChildren(...[el("b", { text: r.title || r.id }), el("div", { text: `${r.id} · ${r.status}` }),
        el("div", { text: t.plan }), el("div", { text: t.act }),
        r.late ? el("div", {}, el("span", { class: "pill danger", text: t.st.label })) : el("div", { class: "muted", text: t.st.label }),
        r.expected_time ? el("div", { class: "muted", text: `expected time ${r.expected_time}` }) : null,
        el("div", { class: "muted small", text: "Click to open" })].filter(Boolean));
      tip.classList.remove("hidden");
      const box = wrap.getBoundingClientRect();
      const px = (ev.clientX !== undefined && ev.clientX) ? ev.clientX - box.left + wrap.scrollLeft : labelW;
      const py = y + rowH + 4;
      tip.style.left = Math.min(px + 12, wrap.scrollLeft + wrap.clientWidth - 280) + "px";
      tip.style.top = py + "px";
    };
    g.addEventListener("mousemove", show);
    g.addEventListener("focus", show);
    g.addEventListener("mouseleave", () => tip.classList.add("hidden"));
    g.addEventListener("blur", () => tip.classList.add("hidden"));
    g.addEventListener("click", () => actionDialog(r.id));
    g.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); actionDialog(r.id); } });
    rowsG.append(g);
  });
  root.append(rowsG);

  // dependency arrows: from the end of one bar to the start of the next
  const barEnd = r => xEnd(r.actual_end && (!r.planned_end || r.actual_end > r.planned_end) ? r.actual_end : (r.planned_end || r.actual_end));
  const barStart = r => x(r.planned_start && (!r.actual_start || r.planned_start < r.actual_start) ? r.planned_start : (r.actual_start || r.planned_start));
  const byId = Object.fromEntries(d.rows.map(r => [r.id, r]));
  const linksG = svg("g", { class: "gt-links" });
  for (const l of d.links) {
    const a = byId[l.from], b = byId[l.to];
    const x1 = barEnd(a), y1 = rowY[a.id] + 17, x2 = barStart(b), y2 = rowY[b.id] + 17;
    const midY = y2 > y1 ? rowY[b.id] - 2 : rowY[b.id] + rowH + 2;
    const path = x2 - x1 >= 14
      ? `M${x1},${y1} H${x1 + 7} V${y2} H${x2 - 1}`
      : `M${x1},${y1} H${x1 + 7} V${midY} H${x2 - 8} V${y2} H${x2 - 1}`;
    linksG.append(svg("path", { d: path, class: "gt-link", "marker-end": "url(#gt-arrow)" },
      svg("title", {}, `${a.title} → ${b.title} (${l.kind === "next" ? "next action" : "precursor"})`)));
  }
  root.append(linksG);

  // today line and project start / end markers (drawn on top)
  if (d.today >= d.range_start && d.today <= d.range_end) {
    const tx = x(d.today) + dayW / 2;
    root.append(svg("line", { x1: tx, x2: tx, y1: headH - 16, y2: H, class: "gt-today" }),
      svg("text", { x: tx + 4, y: headH - 18, class: "gt-axis gt-today-label" }, "Today"));
  }
  for (const [iso, label] of [[d.project_start, "Project start"], [d.project_end, "Project end"]]) {
    if (!iso || iso < d.range_start || iso > d.range_end) continue;
    const mx = label === "Project start" ? x(iso) : xEnd(iso);
    root.append(svg("line", { x1: mx, x2: mx, y1: headH, y2: H, class: "gt-milestone-line" }),
      svg("path", { d: `M${mx},${headH - 13} l5,5 l-5,5 l-5,-5 z`, class: "gt-milestone" },
        svg("title", {}, `${label}: ${fmtDate(iso)}`)));
  }
  wrap.append(root, tip);
  // start scrolled so that today is visible
  requestAnimationFrame(() => {
    const tx = x(d.today);
    if (tx > wrap.clientWidth) wrap.scrollLeft = tx - wrap.clientWidth / 2;
  });
  return wrap;
}

function setupGantt() {
  $("#gt-go").addEventListener("click", loadGantt);
  $("#gt-project").addEventListener("keydown", e => { if (e.key === "Enter") loadGantt(); });
  $("#gt-aborted").addEventListener("change", () => { if (state.gantt) loadGantt(); });
  $("#gt-table").addEventListener("change", renderGantt);
  let t = null;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => {
    if (state.gantt && !$("[data-sub=gantt]", $("#view-reports")).classList.contains("hidden")) renderGantt();
  }, 200); });
}
function openGantt(project) {
  showView("reports");
  $("#rep-tabs button[data-sub=gantt]").click();
  $("#gt-project").value = project;
  loadGantt();
}

// ================================================================ HELP
const help = { ids: new Set(), index: null, lang: null, current: null, matches: null };

function helpLang() {
  return help.lang || (state.prefs && state.prefs.language) || "en";
}
async function loadHelpIndex(lang) {
  const q = new URLSearchParams({ lang: lang || helpLang() });
  const data = await api("GET", "/api/help?" + q);
  help.index = data;
  help.ids = new Set(data.topics.map(t => t.id));
  return data;
}
/** A small "?" button for a help topic, or null if there is no such topic. */
function helpQ(id) {
  if (help.index && !help.ids.has(id)) return null;
  return el("span", { class: "help-q", role: "button", tabindex: "0", "data-help": id, "aria-label": "Help", text: "?" });
}
/** Turn plain help text into nodes, making http(s) URLs clickable. */
function helpTextNodes(text) {
  const out = [];
  const re = /https?:\/\/[^\s<>()]+[^\s<>().,;:'"]/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    out.push(text.slice(last, m.index));
    out.push(el("a", { href: m[0], target: "_blank", rel: "noopener noreferrer", text: m[0] }));
    last = m.index + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}
function helpNotes(t) {
  const langName = code => {
    const l = help.index && help.index.languages.find(x => x.code === code);
    return l ? l.name : code;
  };
  const notes = [];
  if (!t.found) return notes;
  if (!t.translated) notes.push(`Not translated into ${langName(t.requested_lang)} yet — showing ${langName(t.lang)}.`);
  if (t.describes_original_ui) notes.push("This text comes from the original taglog and may describe its old windows and menus. The English version has been updated for this program.");
  if (t.group === "missing") notes.push("This topic is about a feature of the original taglog that this version does not have yet.");
  return notes.map(n => el("p", { class: "help-note banner", text: n }));
}
async function fetchTopic(id, lang) {
  return api("GET", `/api/help/${encodeURIComponent(id)}?` + new URLSearchParams({ lang: lang || helpLang() }));
}
async function showHelp(id) {
  const t = await fetchTopic(id);
  $("#hd-title").textContent = t.title;
  $("#hd-body").replaceChildren(...helpNotes(t), el("div", { class: "help-text" }, ...helpTextNodes(t.text)));
  $("#hd-open").onclick = () => { $("#help-dlg").close(); if ($("#dlg").open) $("#dlg").close(); showView("help"); selectTopic(id); };
  const d = $("#help-dlg");
  if (!d.open) d.showModal();
  $("#hd-ok").focus();
}

function renderHelpTopics() {
  const box = $("#h-topics");
  if (!help.index) return;
  const showMissing = $("#h-missing").checked;
  const matches = help.matches ? new Set(help.matches) : null;
  const groups = [];
  let n = 0;
  for (const g of help.index.groups) {
    if (g.id === "missing" && !showMissing && !matches) continue;
    const topics = help.index.topics.filter(t => t.group === g.id && (!matches || matches.has(t.id)));
    if (!topics.length) continue;
    n += topics.length;
    topics.sort((a, b) => {
      const pa = a.title.includes(":") ? 1 : 0, pb = b.title.includes(":") ? 1 : 0;
      return pa - pb || a.title.localeCompare(b.title);
    });
    groups.push(el("div", { class: "help-group" }, el("h3", { text: g.name }),
      ...topics.map(t => el("button", { type: "button", class: t.id === help.current ? "active" : "", "data-topic": t.id,
        onclick: () => selectTopic(t.id) }, t.title, !t.translated && helpLang() !== "en" ? el("span", { class: "untr", text: "(en)" }) : null))));
  }
  $("#h-count").textContent = matches ? `${n} matching topic${n === 1 ? "" : "s"}` : "";
  box.replaceChildren(...(groups.length ? groups : [el("div", { class: "empty", text: "No topics match." })]));
}
async function selectTopic(id) {
  help.current = id;
  try { localStorage.setItem("taglog.helpTopic", id); } catch (e) { /* ignore */ }
  $$("#h-topics button[data-topic]").forEach(b => b.classList.toggle("active", b.dataset.topic === id));
  const t = await fetchTopic(id);
  const related = [];
  if (t.describes_original_ui || !t.translated) {
    related.push(el("button", { type: "button", class: "b", text: t.describes_original_ui ? "Show the updated English text" : "Show in English",
      onclick: async () => { const en = await fetchTopic(id, "en"); renderHelpTopic(en, []); } }));
  }
  renderHelpTopic(t, related);
}
function renderHelpTopic(t, extra) {
  $("#h-view").replaceChildren(el("h2", { text: t.title }), ...helpNotes(t),
    el("div", { class: "help-text" }, ...helpTextNodes(t.text)),
    extra && extra.length ? el("div", { class: "row", style: "margin-top:16px" }, ...extra) : "",
    el("p", { class: "muted small", style: "margin-top:20px" }, `Topic id: ${t.id}`));
}
async function loadHelpView() {
  const sel = $("#h-lang");
  if (!sel.options.length || (help.index && help.index.lang !== helpLang())) await loadHelpIndex();
  sel.replaceChildren(...help.index.languages.map(l => el("option", { value: l.code,
    text: `${l.name}${l.code === "en" ? "" : ` (${l.topics} topics)`}` })));
  sel.value = helpLang();
  renderHelpTopics();
  let id = help.current;
  if (!id) { try { id = localStorage.getItem("taglog.helpTopic"); } catch (e) { /* ignore */ } }
  selectTopic(id && help.ids.has(id) ? id : "introduction");
}
function setupHelp() {
  document.addEventListener("click", ev => {
    const b = ev.target.closest(".help-q[data-help]");
    if (!b) return;
    ev.preventDefault();
    ev.stopPropagation();
    showHelp(b.dataset.help);
  });
  document.addEventListener("keydown", ev => {
    const b = ev.target.closest && ev.target.closest(".help-q[data-help]");
    if (b && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); ev.stopPropagation(); showHelp(b.dataset.help); }
  });
  $("#hd-close").addEventListener("click", () => $("#help-dlg").close());
  $("#hd-ok").addEventListener("click", () => $("#help-dlg").close());
  $("#h-missing").addEventListener("change", renderHelpTopics);
  $("#h-lang").addEventListener("change", async e => {
    help.lang = e.target.value;
    await loadHelpIndex();
    if ($("#h-search").value.trim()) await runHelpSearch(); else renderHelpTopics();
    if (help.current) selectTopic(help.current);
  });
  const runHelpSearch = async () => {
    const q = $("#h-search").value.trim();
    if (!q) { help.matches = null; renderHelpTopics(); return; }
    const d = await api("GET", "/api/help?" + new URLSearchParams({ lang: helpLang(), q }));
    help.matches = d.matches || [];
    renderHelpTopics();
  };
  $("#h-search").addEventListener("input", debounce(runHelpSearch, 250));
  // "?" key: help for the page you are on (when not typing)
  const viewTopic = { today: "introduction", log: "logsel", actions: "actions", projects: "editproject", reports: "reports", settings: "editprefs" };
  document.addEventListener("keydown", ev => {
    if (ev.key !== "?" || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const t = ev.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if ($("#help-dlg").open) return;
    ev.preventDefault();
    const view = ($(".view.active") || {}).id || "";
    const name = view.replace("view-", "");
    if (name === "help") { $("#h-search").focus(); return; }
    showHelp($("#dlg").open && $("#dlg").dataset.help ? $("#dlg").dataset.help : (viewTopic[name] || "introduction"));
  });
}
/** Add "?" buttons to the labels of a dialog's fields. */
function addFieldHelp(inputs, topicFor) {
  for (const [name, input] of Object.entries(inputs)) {
    const id = topicFor(name);
    const q = id && helpQ(id);
    const span = input.closest("label.f") && input.closest("label.f").querySelector(":scope > span");
    if (q && span) span.append(" ", q);
  }
}

// ================================================================ boot
function boot() {
  // Pressing Enter in a dialog field must not close the dialog unsaved.
  $("#dlg-form").addEventListener("submit", e => e.preventDefault());
  $("#dlg-close").addEventListener("click", () => $("#dlg").close());
  $$("nav.side button").forEach(b => b.addEventListener("click", () => showView(b.dataset.view)));
  setupToday();
  setupLog();
  setupActions();
  setupProjects();
  setupReports();
  setupSettings();
  setupHelp();
  setupGantt();
  let v = "today";
  try { v = localStorage.getItem("taglog.view") || "today"; } catch (e) { /* ignore */ }
  // Always load today's data first (prefs, lists), then switch view.
  loadToday()
    .then(() => loadHelpIndex())
    .then(() => { if (v !== "today") showView(v); }).catch(() => {});
}
document.addEventListener("DOMContentLoaded", boot);
