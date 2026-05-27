const API_BASE = resolveApiBase();

function resolveApiBase() {
  const configured =
    window.ATMOS_API_BASE ||
    window.ATMOS_CONFIG?.API_BASE ||
    localStorage.getItem("ATMOS_API_BASE") ||
    "";

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "http://localhost:8000";
  }

  return "";
}

async function apiGet(path, params = {}) {
  if (!API_BASE) {
    throw new Error("Frontend API URL is not configured. Set ATMOS_CONFIG.API_BASE in js/config.js to the deployed Railway backend URL.");
  }
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
  if (!API_BASE) {
    throw new Error("Frontend API URL is not configured. Set ATMOS_CONFIG.API_BASE in js/config.js to the deployed Railway backend URL.");
  }
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
  sessionStorage.setItem("resultsReturnUrl", window.location.href);
  window.location.href = `analysis.html?match_id=${encodeURIComponent(match.id)}`;
}
