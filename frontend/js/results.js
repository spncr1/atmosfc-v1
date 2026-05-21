const resultsGrid = document.querySelector("[data-results]");
const resultsTitle = document.querySelector("[data-results-title]");
const filterForm = document.querySelector("[data-filter-form]");
const params = new URLSearchParams(window.location.search);
const unavailableCompetitions = new Set(["EL", "UECL"]);
const competitionLabels = {
  PL: "Premier League",
  PD: "La Liga",
  BL1: "Bundesliga",
  SA: "Serie A",
  FL1: "Ligue 1",
  CL: "UCL",
  EL: "UEL",
  UECL: "UECL",
};

const seasonLabels = {
  2025: "2025/26",
  2024: "2024/25",
  2023: "2023/24",
  2022: "2022/23",
  2021: "2021/22",
  2020: "2020/21",
  2019: "2019/20",
  2018: "2018/19",
  2017: "2017/18",
  2016: "2016/17",
  2015: "2015/16",
};

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
  const competition = params.get("competition");
  const season = params.get("season");
  resultsTitle.textContent = q ? `Matches for ${q}` : "Match Results";
  if (unavailableCompetitions.has(competition)) {
    setStatus(resultsGrid, `${competitionLabels[competition]} is currently unavailable.`);
    return;
  }
  setStatus(resultsGrid, `Searching ${searchContext(q, competition, season)}...`);
  try {
    const { matches } = await apiGet("/matches/search", {
      q,
      competition,
      season,
      limit: 50,
    });
    renderMatches(matches, q, competition, season);
  } catch (error) {
    setStatus(resultsGrid, error.message);
  }
}

function handleFilter(event) {
  event.preventDefault();
  window.location.href = `results.html?${new URLSearchParams(new FormData(filterForm)).toString()}`;
}

function renderMatches(matches, q, competition, season) {
  if (!matches.length) {
    setStatus(resultsGrid, `No matches found ${searchContext(q, competition, season)}.`);
    return;
  }
  resultsTitle.textContent = `${matches.length} ${matches.length === 1 ? "result" : "results"} ${searchContext(q, competition, season)}`;
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

function searchContext(q, competition, season) {
  const parts = [];
  if (q) parts.push(`for "${q}"`);
  if (competitionLabels[competition]) parts.push(`in ${competitionLabels[competition]}`);
  if (seasonLabels[season]) parts.push(`during ${seasonLabels[season]}`);
  return parts.length ? parts.join(" ") : "across all supported matches";
}
