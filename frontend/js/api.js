const API_BASE = window.ATMOS_API_BASE || localStorage.getItem("ATMOS_API_BASE") || "http://localhost:8000";

async function apiGet(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  const response = await fetch(url);
  return readResponse(response);
}

async function apiPost(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readResponse(response);
}

async function readResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Atmos FC API request failed");
  }
  return payload;
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function storeMatch(match) {
  sessionStorage.setItem("selectedMatch", JSON.stringify(match));
  window.location.href = `analysis.html?match_id=${encodeURIComponent(match.id)}`;
}
