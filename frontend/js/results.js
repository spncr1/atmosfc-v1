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

// i'll need to add location to the match object here for this line: <small>${formatDate(match.date)}${match.round ? ` • ${match.round}` : ""}</small> - refactor to match with my sentiment analysis match mockup UI
function matchCard(match) {
  return `
    <button class="match-row" data-match="${encodeURIComponent(JSON.stringify(match))}">
      <span class="match-row-meta">
        <em>${match.competition}</em>
        <small>${formatDate(match.date)}${match.round ? ` • ${match.round}` : ""}</small>
      </span>
      <span class="match-row-main">
        <strong class="match-team match-team-home">${teamCrest(match.home_crest, match.home)}<span>${match.home}</span></strong>
        <b>${match.score}</b>
        <strong class="match-team match-team-away"><span>${match.away}</span>${teamCrest(match.away_crest, match.away)}</strong>
      </span>
      <span class="match-row-footer">
        <small>${match.season || "Selected season"}</small>
        <small>YouTube comments</small>
        <i>Analyse</i>
      </span>
    </button>
  `;
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
