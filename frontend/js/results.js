const resultsGrid = document.querySelector("[data-results]");
const resultsSummary = document.querySelector("[data-results-summary]") || createResultsSummary();
const paginationEl = document.querySelector("[data-pagination]");
const filterForm = document.querySelector("[data-filter-form]");
const params = new URLSearchParams(window.location.search);
const PAGE_SIZE = 15;
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
  if (!resultsGrid || !filterForm) return;
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
  const page = currentPage();
  if (unavailableCompetitions.has(competition)) {
    resultsGrid.innerHTML = "";
    clearPagination();
    setStatus(resultsSummary, `${competitionLabels[competition]} is currently unavailable.`);
    return;
  }
  resultsGrid.innerHTML = "";
  clearPagination();
  setStatus(resultsSummary, `Searching ${searchContext(q, competition, season)}...`);
  try {
    const { matches, pagination } = await apiGet("/matches/search", {
      q,
      competition,
      season,
      page,
      page_size: PAGE_SIZE,
    });
    renderMatches(matches, pagination, q, competition, season);
  } catch (error) {
    resultsGrid.innerHTML = "";
    clearPagination();
    setStatus(resultsSummary, error.message);
  }
}

function handleFilter(event) {
  event.preventDefault();
  const nextParams = new URLSearchParams(new FormData(filterForm));
  nextParams.set("page", "1");
  window.location.href = `results.html?${nextParams.toString()}`;
}

function renderMatches(matches, pagination, q, competition, season) {
  if (!matches.length) {
    resultsGrid.innerHTML = "";
    clearPagination();
    setStatus(resultsSummary, `No matches found ${searchContext(q, competition, season)}.`);
    return;
  }
  setSummary(`${pagination.total} ${pagination.total === 1 ? "result" : "results"} ${searchContext(q, competition, season)}`);
  resultsGrid.innerHTML = matches.map(matchCard).join("");
  resultsSummary.removeAttribute("aria-busy");
  resultsGrid.querySelectorAll("[data-match]").forEach((button) => {
    button.addEventListener("click", () => storeMatch(JSON.parse(decodeURIComponent(button.dataset.match))));
  });
  renderPagination(pagination);
}

function matchCard(match) {
  return `
    <button class="match-row" data-match="${encodeURIComponent(JSON.stringify(match))}">
      <span class="match-row-meta">
        <em>${match.competition}</em>
        <small class="match-row-stage">${stageWithSeason(match)}</small>
        <small>${formatDate(match.date)}</small>
      </span>
      <span class="match-row-main">
        <strong class="match-team match-team-home">${teamCrest(match.home_crest, match.home)}<span>${displayTeamName(match, "home")}</span></strong>
        <b>${displayScore(match)}</b>
        <strong class="match-team match-team-away"><span>${displayTeamName(match, "away")}</span>${teamCrest(match.away_crest, match.away)}</strong>
      </span>
      ${scoreContextMarkup(match)}
      <span class="match-row-footer">
        <small>YouTube comments</small>
        <i>Analyse</i>
      </span>
    </button>
  `;
}

function displayScore(match) {
  return [match.score, match.score_note].filter(Boolean).join(" ");
}

function scoreDetail(match) {
  return [match.penalty_score, match.aggregate_score].filter(Boolean).join(" · ");
}

function scoreContextMarkup(match) {
  const detail = scoreDetail(match);
  return detail ? `<span class="match-row-score-context">${detail}</span>` : "";
}

function stageWithSeason(match) {
  return [match.round || "Stage unavailable", match.season].filter(Boolean).join(" · ");
}

function displayTeamName(match, side) {
  const shortName = match[`${side}_short_name`];
  return shortName || shortTeamName(match[side]);
}

function shortTeamName(name) {
  const clean = String(name || "").trim();
  const replacements = {
    "ACF Fiorentina": "Fiorentina",
    "Athletic Club": "Athletic Bilbao",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Brighton & Hove Albion": "Brighton",
    "Borussia Mönchengladbach": "Gladbach",
    "Cagliari Calcio": "Cagliari",
    "Club Atlético de Madrid": "Atlético Madrid",
    "Club Atletico de Madrid": "Atlético Madrid",
    "Deportivo Alavés": "Alavés",
    "FC Bayern München": "Bayern Munich",
    "FC Internazionale Milano": "Inter Milan",
    "FC Nantes": "Nantes",
    "Feyenoord Rotterdam": "Feyenoord",
    "Genoa CFC": "Genoa",
    "Hellas Verona FC": "Hellas Verona",
    "Internazionale": "Inter Milan",
    "Leeds United": "Leeds",
    "Newcastle United": "Newcastle",
    "Olympique Lyon": "Lyon",
    "Olympique Lyonnais": "Lyon",
    "Olympique de Marseille": "Marseille",
    "Paris Saint-Germain FC": "PSG",
    "RC Lens": "Lens",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "SSC Napoli": "Napoli",
    "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur": "Tottenham",
    "Udinese Calcio": "Udinese",
    "US Cremonese": "Cremonese",
    "US Lecce": "Lecce",
    "Wolverhampton Wanderers": "Wolves"
  };
  if (replacements[clean]) return replacements[clean];
  return clean
    .replace(/^FC\s+/i, "")
    .replace(/\s+FC$/i, "")
    .replace(/\s+CF$/i, "")
    .replace(/\s+AFC$/i, "")
    .replace("Paris Saint-Germain", "PSG");
}

function teamCrest(src, team) {
  if (!src) return "";
  return `<img class="team-crest" src="${src}" alt="" loading="lazy" onerror="this.remove()">`;
}

function setStatus(target, message) {
  target.setAttribute("aria-busy", "true");
  target.innerHTML = `<p class="status">${message}</p>`;
}

function setSummary(message) {
  resultsSummary.innerHTML = `<p class="results-summary__text">${message}</p>`;
}

function renderPagination(pagination) {
  if (!paginationEl || pagination.total_pages <= 1) {
    clearPagination();
    return;
  }

  const pages = visiblePages(pagination.page, pagination.total_pages);
  paginationEl.innerHTML = `
    <button class="pagination__step" type="button" data-page="${pagination.page - 1}" ${pagination.has_previous ? "" : "disabled"}>Prev</button>
    ${pages.map((page) => `
      <button class="pagination__page" type="button" data-page="${page}" ${page === pagination.page ? 'aria-current="page"' : ""}>${page}</button>
    `).join("")}
    <button class="pagination__step" type="button" data-page="${pagination.page + 1}" ${pagination.has_next ? "" : "disabled"}>Next</button>
  `;

  paginationEl.querySelectorAll("[data-page]:not([disabled])").forEach((button) => {
    button.addEventListener("click", () => navigateToPage(button.dataset.page));
  });
}

function visiblePages(page, totalPages) {
  if (totalPages <= 3) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const start = Math.max(1, Math.min(page - 1, totalPages - 2));
  return [start, start + 1, start + 2];
}

function navigateToPage(page) {
  const nextParams = new URLSearchParams(window.location.search);
  nextParams.set("page", page);
  window.location.href = `results.html?${nextParams.toString()}`;
}

function clearPagination() {
  if (paginationEl) {
    paginationEl.innerHTML = "";
  }
}

function currentPage() {
  const page = Number.parseInt(params.get("page") || "1", 10);
  return Number.isNaN(page) || page < 1 ? 1 : page;
}

function createResultsSummary() {
  const summary = document.createElement("section");
  summary.className = "results-summary";
  summary.dataset.resultsSummary = "";
  const grid = document.querySelector("[data-results]");
  if (grid) {
    grid.before(summary);
  }
  return summary;
}

function searchContext(q, competition, season) {
  const parts = [];
  if (q) parts.push(`for "${q}"`);
  if (competitionLabels[competition]) parts.push(`in ${competitionLabels[competition]}`);
  if (seasonLabels[season]) parts.push(`during ${seasonLabels[season]}`);
  return parts.length ? parts.join(" ") : "across all supported matches";
}
