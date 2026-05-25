const recentGrid = document.querySelector("[data-recent]");
const recentHeading = document.querySelector("[data-recent-heading]");
const searchForm = document.querySelector("[data-search-form]");
const competitionInputs = searchForm.querySelectorAll('input[name="competition"]');

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

const unavailableCompetitions = new Set(["EL", "UECL"]);

init();

async function init() {
  searchForm.addEventListener("submit", handleSearch);
  competitionInputs.forEach((input) => {
    input.addEventListener("change", () => loadRecentMatches(input.value));
  });
  await loadRecentMatches();
}

async function loadRecentMatches(competition = selectedCompetition()) {
  updateRecentHeading(competition);
  if (unavailableCompetitions.has(competition)) {
    setStatus(recentGrid, `${competitionLabels[competition]} is currently unavailable.`);
    return;
  }
  setStatus(recentGrid, loadingRecentMessage(competition));
  try {
    const { matches } = await apiGet("/matches/recent", { limit: 12, competition });
    renderMatches(recentGrid, matches);
  } catch (error) {
    setStatus(recentGrid, error.message || "Could not load recent matches.");
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
      <span class="match-card__teams">
        <span class="match-card__team">${teamCrest(match.home_crest, match.home)}${match.home}</span>
        <strong>${match.score}</strong>
        <span class="match-card__team">${match.away}${teamCrest(match.away_crest, match.away)}</span>
      </span>
      <span class="match-card__round">${match.round || match.season || ""}</span>
    </button>
  `;
}

function teamCrest(src, team) {
  if (!src) return "";
  return `<img class="team-crest" src="${src}" alt="" loading="lazy" onerror="this.remove()">`;
}

function setStatus(target, message) {
  target.innerHTML = `<p class="status">${message}</p>`;
}

function selectedCompetition() {
  return searchForm.elements.competition.value;
}

function updateRecentHeading(competition) {
  const label = competitionLabels[competition];
  recentHeading.textContent = label ? `Recent ${label} matches` : "Recent matches";
}

function loadingRecentMessage(competition) {
  const label = competitionLabels[competition];
  return label ? `Loading recent ${label} matches...` : "Loading recent matches...";
}
