const recentGrid = document.querySelector("[data-recent]");
const searchForm = document.querySelector("[data-search-form]");

init();

async function init() {
  searchForm.addEventListener("submit", handleSearch);
  await loadRecentMatches();
}

async function loadRecentMatches() {
  setStatus(recentGrid, "Loading recent matches...");
  try {
    const { matches } = await apiGet("/matches/recent", { limit: 12 });
    renderMatches(recentGrid, matches);
  } catch (error) {
    setStatus(recentGrid, error.message);
  }
}

function handleSearch(event) {
  event.preventDefault();
  const data = new FormData(searchForm);
  const params = new URLSearchParams(data);
  window.location.href = `results.html?${params.toString()}`;
}

function renderMatches(target, matches) {
  if (!matches.length) {
    setStatus(target, "No matches found.");
    return;
  }
  target.innerHTML = matches.map(matchCard).join("");
  target.querySelectorAll("[data-match]").forEach((button) => {
    button.addEventListener("click", () => storeMatch(JSON.parse(decodeURIComponent(button.dataset.match))));
  });
}

function matchCard(match) {
  return `
    <button class="match-card" data-match="${encodeURIComponent(JSON.stringify(match))}">
      <span class="match-card__meta">${match.competition} - ${formatDate(match.date)}</span>
      <span class="match-card__teams">${match.home} <strong>${match.score}</strong> ${match.away}</span>
      <span class="match-card__round">${match.round || match.season || ""}</span>
    </button>
  `;
}

function setStatus(target, message) {
  target.innerHTML = `<p class="status">${message}</p>`;
}
