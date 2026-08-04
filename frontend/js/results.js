const resultsGrid = document.querySelector("[data-results]");
const resultsSummary = document.querySelector("[data-results-summary]") || createResultsSummary();
const paginationEl = document.querySelector("[data-pagination]");
const filterForm = document.querySelector("[data-filter-form]");
const params = new URLSearchParams(window.location.search);
const PAGE_SIZE = 15;
let competitionLabels = {};
let seasonLabels = {};

init();

async function init() {
  if (!resultsGrid || !filterForm) return;
  const metadata = await loadMetadata();
  competitionLabels = labelsByCode(metadata.competitions);
  seasonLabels = labelsByYear(metadata.seasons);
  hydrateForm();
  filterForm.addEventListener("submit", handleFilter);
  await loadResults();
}

async function loadMetadata() {
  try {
    const metadata = await apiGet("/metadata");
    if (Array.isArray(metadata.competitions) && Array.isArray(metadata.seasons)) {
      return metadata;
    }
  } catch (error) {
    console.warn("Falling back to bundled filter metadata.", error);
  }
  return fallbackMetadata();
}

function labelsByCode(competitions) {
  return competitions.reduce((labels, competition) => {
    labels[competition.code] = competition.name;
    return labels;
  }, {});
}

function labelsByYear(seasons) {
  return seasons.reduce((labels, season) => {
    labels[String(season.year)] = season.label;
    return labels;
  }, {});
}

function fallbackMetadata() {
  return {
    competitions: [
      { code: "PL", name: "Premier League" },
      { code: "PD", name: "La Liga" },
      { code: "BL1", name: "Bundesliga" },
      { code: "SA", name: "Serie A" },
      { code: "FL1", name: "Ligue 1" },
      { code: "NED1", name: "Eredivisie" },
      { code: "POR1", name: "Liga Portugal" },
      { code: "BEL1", name: "Belgian Pro League" },
      { code: "TUR1", name: "Turkish Super Lig" },
      { code: "CL", name: "UEFA Champions League" },
      { code: "EL", name: "UEFA Europa League" },
      { code: "UECL", name: "UEFA Conference League" },
    ],
    seasons: [
      { year: 2026, label: "2026/27", is_current: true },
      { year: 2025, label: "2025/26", is_current: false },
      { year: 2024, label: "2024/25", is_current: false },
      { year: 2023, label: "2023/24", is_current: false },
      { year: 2022, label: "2022/23", is_current: false },
      { year: 2021, label: "2021/22", is_current: false },
      { year: 2020, label: "2020/21", is_current: false },
      { year: 2019, label: "2019/20", is_current: false },
      { year: 2018, label: "2018/19", is_current: false },
      { year: 2017, label: "2017/18", is_current: false },
      { year: 2016, label: "2016/17", is_current: false },
      { year: 2015, label: "2015/16", is_current: false },
      { year: 2014, label: "2014/15", is_current: false },
      { year: 2013, label: "2013/14", is_current: false },
      { year: 2012, label: "2012/13", is_current: false },
      { year: 2011, label: "2011/12", is_current: false },
      { year: 2010, label: "2010/11", is_current: false },
    ],
  };
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
  resultsGrid.innerHTML = "";
  clearPagination();
  setStatus(resultsSummary, `Searching ${searchContext(q, competition, season)}...`);
  try {
    const { matches, pagination, notices = [] } = await apiGet("/matches/search", {
      q,
      competition,
      season,
      page,
      page_size: PAGE_SIZE,
    });
    renderMatches(matches, pagination, q, competition, season, notices);
  } catch (error) {
    resultsGrid.innerHTML = "";
    clearPagination();
    setStatus(resultsSummary, error.message);
  }
}

function handleFilter(event) {
  event.preventDefault();
  applyFilters();
}

function applyFilters() {
  const nextParams = new URLSearchParams(new FormData(filterForm));
  nextParams.set("page", "1");
  window.location.href = `results.html?${nextParams.toString()}`;
}

function renderMatches(matches, pagination, q, competition, season, notices = []) {
  if (!matches.length) {
    resultsGrid.innerHTML = "";
    clearPagination();
    setSearchStatus(
      resultsSummary,
      notices,
      `No matches found ${searchContext(q, competition, season)}.`,
    );
    return;
  }
  setSummary(
    `${pagination.total} ${pagination.total === 1 ? "result" : "results"} ${searchContext(q, competition, season)}`,
    notices,
  );
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
        <small>${youtubeCommentLabel(match)}</small>
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

function youtubeCommentLabel(match) {
  const status = match.youtube_comment_status || "unchecked";
  const count = Number.isInteger(match.youtube_comment_count) ? match.youtube_comment_count : null;
  if (status === "complete" && count !== null) {
    return `${formatNumber(count)} YouTube ${count === 1 ? "comment" : "comments"}`;
  }
  if (status === "pending") return "Comments pending";
  if (status === "no_comments") return "No public comments found";
  if (status === "unavailable") return "Comments unavailable";
  if (status === "failed") return "Comment check failed";
  return "Comments not checked";
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

function formatNumber(value) {
  return new Intl.NumberFormat("en").format(value || 0);
}

function setStatus(target, message) {
  target.setAttribute("aria-busy", "true");
  target.innerHTML = `<p class="status">${message}</p>`;
}

function setSummary(message, notices = []) {
  resultsSummary.innerHTML = `
    <p class="results-summary__text">${escapeHtml(message)}</p>
    ${noticeMarkup(notices)}
  `;
  resultsSummary.removeAttribute("aria-busy");
}

function setSearchStatus(target, notices, fallbackMessage) {
  target.setAttribute("aria-busy", "true");
  target.innerHTML = notices.length
    ? noticeMarkup(notices)
    : `<p class="status">${escapeHtml(fallbackMessage)}</p>`;
}

function noticeMarkup(notices) {
  if (!Array.isArray(notices) || !notices.length) return "";
  return notices.map((notice) => `
    <article class="search-notice search-notice--${escapeAttr(notice.type || "info")}">
      <strong>${escapeHtml(notice.title || "Search notice")}</strong>
      <p>${escapeHtml(notice.message || "")}</p>
    </article>
  `).join("");
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
