// NYC Taxi Mobility Dashboard: talks to the Flask API and draws charts with Chart.js.
const API = "http://127.0.0.1:5000";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PAGE_SIZE = 50; // must match the LIMIT in /api/trips

const state = {
  page: 1,
  sort: "pickup_dt",
  order: "desc",
  zoneNames: {},       // location_id -> "Zone name (Borough)"
  charts: {},
  requestId: 0,        // used to ignore out-of-date responses
};

const $ = (id) => document.getElementById(id);

// ---------- helpers ----------
async function api(path, params) {
  const url = new URL(API + path);
  if (params) {
    for (const [k, v] of params) url.searchParams.set(k, v);
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

function showError(msg) {
  const box = $("error");
  box.textContent = msg;
  box.hidden = false;
  $("status").textContent = "API offline";
  $("status").className = "status bad";
}

function clearError() {
  $("error").hidden = true;
  $("status").textContent = "Connected";
  $("status").className = "status ok";
}

const fmtInt = (n) => (n == null ? "–" : Number(n).toLocaleString("en-US"));
const fmtMoney = (n) => (n == null ? "–" : "$" + Number(n).toFixed(2));
const fmtNum = (n, d = 1) => (n == null ? "–" : Number(n).toFixed(d));

function hourLabel(h) {
  const suffix = h < 12 ? "am" : "pm";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}${suffix}`;
}

// Build the filter query string shared by every endpoint.
function filterParams() {
  const p = new URLSearchParams();
  const add = (key, id) => {
    const v = $(id).value;
    if (v !== "") p.set(key, v);
  };
  add("start", "f-start");
  add("hour", "f-hour");
  add("zone", "f-zone");
  add("payment", "f-payment");
  add("min_distance", "f-min-distance");
  add("max_distance", "f-max-distance");
  add("max_fare", "f-max-fare");

  // The API treats "end" as exclusive, so move the picked date forward one day
  // to make the chosen end date inclusive.
  const end = $("f-end").value;
  if (end) {
    const d = new Date(end + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + 1);
    p.set("end", d.toISOString().slice(0, 10));
  }
  return p;
}

function withExtra(base, extra) {
  const p = new URLSearchParams(base);
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p;
}

// ---------- charts ----------
function initCharts() {
  Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  Chart.defaults.color = "#667085";

  state.charts.hour = new Chart($("chart-hour"), {
    data: {
      labels: Array.from({ length: 24 }, (_, h) => hourLabel(h)),
      datasets: [
        {
          type: "bar",
          label: "Trips",
          data: [],
          backgroundColor: "#f5b301",
          yAxisID: "y",
          order: 2,
        },
        {
          type: "line",
          label: "Avg speed (mph)",
          data: [],
          borderColor: "#2b6cb0",
          backgroundColor: "#2b6cb0",
          tension: 0.3,
          pointRadius: 3,
          yAxisID: "y1",
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: "Trips" } },
        y1: {
          beginAtZero: true,
          position: "right",
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Speed (mph)" },
        },
      },
    },
  });

  state.charts.weekday = new Chart($("chart-weekday"), {
    type: "bar",
    data: {
      labels: WEEKDAYS,
      datasets: [{ label: "Trips", data: [], backgroundColor: "#2b6cb0" }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });

  state.charts.zones = new Chart($("chart-zones"), {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ label: "Trips", data: [], backgroundColor: "#f5b301" }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true } },
    },
  });
}

function updateHourChart(rows) {
  // Fill all 24 hours so empty hours show as zero instead of disappearing.
  const trips = new Array(24).fill(0);
  const speed = new Array(24).fill(null);
  for (const r of rows) {
    trips[r.hour] = r.trips;
    speed[r.hour] = r.avg_speed;
  }
  const c = state.charts.hour;
  c.data.datasets[0].data = trips;
  c.data.datasets[1].data = speed;
  c.update();
}

function updateWeekdayChart(rows) {
  const trips = new Array(7).fill(0);
  for (const r of rows) trips[r.day] = r.trips;
  const c = state.charts.weekday;
  c.data.datasets[0].data = trips;
  c.update();
}

function updateZonesChart(rows) {
  const c = state.charts.zones;
  c.data.labels = rows.map((r) => r.zone_name);
  c.data.datasets[0].data = rows.map((r) => r.trips);
  c.update();
}

// ---------- data loading ----------
async function loadDashboard() {
  const id = ++state.requestId;
  const base = filterParams();
  const k = $("top-k").value;

  try {
    const [summary, byHour, byDay, top] = await Promise.all([
      api("/api/stats/summary", base),
      api("/api/stats/by-hour", base),
      api("/api/stats/by-weekday", base),
      api("/api/top-zones", withExtra(base, { k })),
    ]);
    if (id !== state.requestId) return; // a newer request replaced this one

    $("k-trips").textContent = fmtInt(summary.trips);
    $("k-fare").textContent = fmtMoney(summary.avg_fare);
    $("k-distance").textContent = summary.avg_distance == null ? "–" : fmtNum(summary.avg_distance, 2) + " mi";
    $("k-tip").textContent = summary.avg_tip_pct == null ? "–" : fmtNum(summary.avg_tip_pct, 1) + "%";

    updateHourChart(byHour);
    updateWeekdayChart(byDay);
    updateZonesChart(top);
    clearError();
  } catch (err) {
    showError(
      "Could not load data from the API at " + API +
      ". Make sure the backend is running (python backend/app.py). Details: " + err.message
    );
    return;
  }

  state.page = 1;
  await loadTrips();
}

async function loadTrips() {
  const base = withExtra(filterParams(), {
    sort: state.sort,
    order: state.order,
    page: state.page,
  });
  try {
    const rows = await api("/api/trips", base);
    renderTrips(rows);
  } catch (err) {
    showError("Could not load trips: " + err.message);
  }
}

function renderTrips(rows) {
  const body = document.querySelector("#trips tbody");
  body.replaceChildren();

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 7;
    td.className = "empty";
    td.textContent = "No trips match these filters.";
    tr.appendChild(td);
    body.appendChild(tr);
  }

  for (const r of rows) {
    const tr = document.createElement("tr");
    const cells = [
      [r.pickup_dt, ""],
      [state.zoneNames[r.pu_zone_id] || "Zone " + r.pu_zone_id, ""],
      [fmtNum(r.distance, 2), "num"],
      [fmtMoney(r.fare), "num"],
      [fmtMoney(r.tip), "num"],
      [fmtNum(r.duration_min, 1), "num"],
      [fmtNum(r.avg_speed_mph, 1), "num"],
    ];
    for (const [text, cls] of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      if (cls) td.className = cls;
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }

  const first = rows.length ? (state.page - 1) * PAGE_SIZE + 1 : 0;
  const last = (state.page - 1) * PAGE_SIZE + rows.length;
  $("table-info").textContent = rows.length ? `Showing rows ${fmtInt(first)}–${fmtInt(last)}` : "";
  $("page-label").textContent = "Page " + state.page;
  $("prev").disabled = state.page <= 1;
  $("next").disabled = rows.length < PAGE_SIZE;
  updateSortHeaders();
}

function updateSortHeaders() {
  document.querySelectorAll("#trips th[data-sort]").forEach((th) => {
    const active = th.dataset.sort === state.sort;
    th.classList.toggle("sorted", active);
    th.querySelector(".arrow")?.remove();
    if (active) {
      const span = document.createElement("span");
      span.className = "arrow";
      span.textContent = state.order === "asc" ? "▲" : "▼";
      th.appendChild(span);
    }
  });
}

// ---------- setup ----------
async function loadZones() {
  const zones = await api("/api/zones");
  const select = $("f-zone");

  // Group the dropdown by borough.
  const byBorough = {};
  for (const z of zones) {
    state.zoneNames[z.location_id] = `${z.zone_name || "Unknown"} (${z.borough})`;
    (byBorough[z.borough] = byBorough[z.borough] || []).push(z);
  }
  for (const borough of Object.keys(byBorough).sort()) {
    const group = document.createElement("optgroup");
    group.label = borough;
    for (const z of byBorough[borough]) {
      const opt = document.createElement("option");
      opt.value = z.location_id;
      opt.textContent = z.zone_name || "Zone " + z.location_id;
      group.appendChild(opt);
    }
    select.appendChild(group);
  }
}

function fillHours() {
  const select = $("f-hour");
  for (let h = 0; h < 24; h++) {
    const opt = document.createElement("option");
    opt.value = h;
    opt.textContent = hourLabel(h);
    select.appendChild(opt);
  }
}

function resetFilters() {
  document.querySelectorAll(".filters input").forEach((i) => (i.value = ""));
  document.querySelectorAll(".filters select").forEach((s) => (s.value = ""));
  loadDashboard();
}

function bindEvents() {
  $("apply").addEventListener("click", loadDashboard);
  $("reset").addEventListener("click", resetFilters);
  $("top-k").addEventListener("change", loadDashboard);

  // Pressing Enter in a filter box applies the filters.
  document.querySelectorAll(".filters input").forEach((i) =>
    i.addEventListener("keydown", (e) => { if (e.key === "Enter") loadDashboard(); })
  );

  document.querySelectorAll("#trips th[data-sort]").forEach((th) =>
    th.addEventListener("click", () => {
      const col = th.dataset.sort;
      if (state.sort === col) {
        state.order = state.order === "asc" ? "desc" : "asc";
      } else {
        state.sort = col;
        state.order = "desc";
      }
      state.page = 1;
      loadTrips();
    })
  );

  $("prev").addEventListener("click", () => {
    if (state.page > 1) { state.page--; loadTrips(); }
  });
  $("next").addEventListener("click", () => {
    state.page++; loadTrips();
  });
}

async function init() {
  if (typeof Chart === "undefined") {
    showError("Chart.js failed to load. Check your internet connection and reload.");
    return;
  }
  fillHours();
  initCharts();
  bindEvents();
  try {
    await loadZones();
  } catch (err) {
    showError(
      "Could not reach the API at " + API +
      ". Start the backend first (python backend/app.py), then reload. Details: " + err.message
    );
    return;
  }
  await loadDashboard();
}

init();