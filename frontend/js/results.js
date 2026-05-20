const resultsGrid = document.querySelector("[data-results]");
const resultsTitle = document.querySelector("[data-results-title]");
const filterForm = document.querySelector("[data-filter-form]");
const params = new URLSearchParams(window.location.search);

init();

async function init() {
  hydrateForm();
  filterForm.addEventListener("submit", handleFilter);
  await loadResults();
}

function hydrateForm() {
  ["q", "competition", "season"].forEach((name) => {
    const input = filterForm.elements[name];
    if (input) input.value = params.get(name) || "";
  });
}

async function loadResults() {
  const q = params.get("q") || "";
  resultsTitle.textContent = q ? `Matches for ${q}` : "Match Results";
  setStatus(resultsGrid, "Searching matches...");
  try {
    const { matches } = await apiGet("/matches/search", {
      q,
      competition: params.get("competition"),
      season: params.get("season"),
      limit: 30,
    });
    renderMatches(matches);
  } catch (error) {
    setStatus(resultsGrid, error.message);
  }
}

function handleFilter(event) {
  event.preventDefault();
  window.location.href = `results.html?${new URLSearchParams(new FormData(filterForm)).toString()}`;
}

function renderMatches(matches) {
  if (!matches.length) {
    setStatus(resultsGrid, "No matches found.");
    return;
  }
  resultsGrid.innerHTML = matches.map(matchCard).join("");
  resultsGrid.querySelectorAll("[data-match]").forEach((button) => {
    button.addEventListener("click", () => storeMatch(JSON.parse(decodeURIComponent(button.dataset.match))));
  });
}

function matchCard(match) {
  return `
    <button class="match-row" data-match="${encodeURIComponent(JSON.stringify(match))}">
      <span class="match-row__meta">
        <em>${match.competition}</em>
        <small>${formatDate(match.date)}${match.round ? ` - ${match.round}` : ""}</small>
      </span>
      <span class="match-row__main">
        <strong>${match.home}</strong>
        <b>${match.score}</b>
        <strong>${match.away}</strong>
      </span>
      <span class="match-row__footer">
        <small>${match.season || "Selected season"}</small>
        <small>Reddit comments</small>
        <i>Analyse</i>
      </span>
    </button>
  `;
}

function setStatus(target, message) {
  target.innerHTML = `<p class="status">${message}</p>`;
}
