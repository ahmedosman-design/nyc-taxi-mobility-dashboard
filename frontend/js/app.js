const API = "/api";

async function getJSON(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
  return res.json();
}

async function loadKPIs() {
  const s = await getJSON("/stats/summary");
  document.getElementById("kpi-trips").textContent = s.trips.toLocaleString();
  document.getElementById("kpi-fare").textContent = `$${s.avg_fare}`;
  document.getElementById("kpi-dist").textContent = `${s.avg_distance} mi`;
  document.getElementById("kpi-tip").textContent = `${s.avg_tip_pct}%`;
}

async function loadHourChart() {
  const data = await getJSON("/stats/by-hour");
  new Chart(document.getElementById("hourChart"), {
    data: {
      labels: data.map(d => `${d.hour}:00`),
      datasets: [
        { type: "bar", label: "Trips", data: data.map(d => d.trips),
          backgroundColor: "#fcd34d", yAxisID: "yTrips" },
        { type: "line", label: "Avg speed (mph)", data: data.map(d => d.avg_speed),
          borderColor: "#dc2626", yAxisID: "ySpeed", tension: 0.3 }
      ]
    },
    options: {
      scales: {
        yTrips: { position: "left", title: { display: true, text: "Trips" } },
        ySpeed: { position: "right", title: { display: true, text: "mph" },
                  grid: { drawOnChartArea: false } }
      }
    }
  });
}

async function loadZoneChart() {
  const data = await getJSON("/top-zones?k=10");
  new Chart(document.getElementById("zoneChart"), {
    type: "bar",
    data: {
      labels: data.map(d => d.zone_name),
      datasets: [{ label: "Pickups", data: data.map(d => d.trips),
                   backgroundColor: "#fcd34d" }]
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } } }
  });
}

async function loadWeekdayChart() {
  const data = await getJSON("/stats/by-weekday");
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  new Chart(document.getElementById("weekdayChart"), {
    type: "bar",
    data: {
      labels: data.map(d => names[d.day]),
      datasets: [{ label: "Trips", data: data.map(d => d.trips),
                   backgroundColor: "#111827" }]
    },
    options: { plugins: { legend: { display: false } } }
  });
}

loadKPIs().catch(console.error);
loadHourChart().catch(console.error);
loadZoneChart().catch(console.error);
loadWeekdayChart().catch(console.error);