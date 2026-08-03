const recentGrid = document.querySelector("[data-recent]");
const recentHeading = document.querySelector("[data-recent-heading]");
const searchForm = document.querySelector("[data-search-form]");
const competitionFilters = document.querySelector("[data-competition-filters]");
const seasonFilters = document.querySelector("[data-season-filters]");
let competitionLabels = {};

init();

async function init() {
  const metadata = await loadMetadata();
  renderFilters(metadata);
  competitionLabels = labelsByCode(metadata.competitions);
  searchForm.addEventListener("submit", handleSearch);
  searchForm.querySelectorAll('input[name="competition"]').forEach((input) => {
    input.addEventListener("change", () => loadRecentMatches(input.value));
  });
  await loadRecentMatches();
}

async function loadRecentMatches(competition = selectedCompetition()) {
  updateRecentHeading(competition);
  setStatus(recentGrid, loadingRecentMessage(competition));
  try {
    const { matches } = await apiGet("/matches/recent", { limit: 12, competition });
    renderMatches(recentGrid, matches);
  } catch (error) {
    setStatus(recentGrid, error.message || "Could not load recent matches.");
  }
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

function renderFilters(metadata) {
  renderCompetitionFilters(metadata.competitions);
  renderSeasonFilters(metadata.seasons);
}

function renderCompetitionFilters(competitions) {
  competitionFilters.innerHTML = [
    filterRadio("competition", "", "All", null, true),
    ...competitions.map((competition) => filterRadio(
      "competition",
      competition.code,
      competition.short_name || competition.name,
      competition.logo_url,
      false,
    )),
  ].join("");
}

function renderSeasonFilters(seasons) {
  seasonFilters.innerHTML = [
    filterRadio("season", "", "All", null, true),
    ...seasons.map((season) => filterRadio("season", String(season.year), compactSeasonLabel(season.label), null, false)),
  ].join("");
}

function filterRadio(name, value, label, icon, checked) {
  const iconMarkup = icon ? `<img class="filter-emblem" src="${escapeAttr(icon)}" alt="" loading="lazy" onerror="this.remove()">` : "";
  return `
    <label class="filter-option">
      <input type="radio" name="${escapeAttr(name)}" value="${escapeAttr(value)}" ${checked ? "checked" : ""}>
      <span>${iconMarkup}${escapeHtml(label)}</span>
    </label>
  `;
}

function labelsByCode(competitions) {
  return competitions.reduce((labels, competition) => {
    labels[competition.code] = competition.name;
    return labels;
  }, {});
}

function fallbackMetadata() {
  return {
    competitions: [
      { code: "PL", name: "Premier League", short_name: "PL", logo_url: "https://media.api-sports.io/football/leagues/39.png" },
      { code: "PD", name: "La Liga", short_name: "La Liga", logo_url: "https://media.api-sports.io/football/leagues/140.png" },
      { code: "BL1", name: "Bundesliga", short_name: "Bundesliga", logo_url: "https://media.api-sports.io/football/leagues/78.png" },
      { code: "SA", name: "Serie A", short_name: "Serie A", logo_url: "https://media.api-sports.io/football/leagues/135.png" },
      { code: "FL1", name: "Ligue 1", short_name: "Ligue 1", logo_url: "https://media.api-sports.io/football/leagues/61.png" },
      { code: "CL", name: "UEFA Champions League", short_name: "UCL", logo_url: "https://media.api-sports.io/football/leagues/2.png" },
      { code: "EL", name: "UEFA Europa League", short_name: "UEL", logo_url: "https://media.api-sports.io/football/leagues/3.png" },
      { code: "UECL", name: "UEFA Conference League", short_name: "UECL", logo_url: "https://media.api-sports.io/football/leagues/848.png" },
    ],
    seasons: [
      { year: 2026, label: "2026/27", is_current: true },
      { year: 2025, label: "2025/26", is_current: false },
    ],
  };
}

function compactSeasonLabel(label) {
  const parts = String(label || "").split("/");
  if (parts.length !== 2) return label;
  return `${parts[0].slice(-2)}/${parts[1]}`;
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
        <span class="match-card__team">${teamCrest(match.home_crest, match.home)}${displayTeamName(match, "home")}</span>
        <strong>${displayScore(match)}</strong>
        <span class="match-card__team">${displayTeamName(match, "away")}${teamCrest(match.away_crest, match.away)}</span>
      </span>
      ${scoreContextMarkup(match)}
      <span class="match-card__round">${match.round || match.season || ""}</span>
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
  return detail ? `<span class="match-card__score-context">${detail}</span>` : "";
}

function displayTeamName(match, side) {
  const tla = match[`${side}_tla`];
  return tla || compactTeamName(match[`${side}_short_name`] || match[side]);
}

function compactTeamName(name) {
  const clean = String(name || "").trim();
  const replacements = {
    "AFC Bournemouth": "BOU",
    "ACF Fiorentina": "Fiorentina",
    "Arsenal": "ARS",
    "Aston Villa": "AVL",
    "Athletic Club": "Athletic Bilbao",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Brighton Hove": "BHA",
    "Brighton & Hove Albion": "BHA",
    "Borussia Mönchengladbach": "Gladbach",
    "Cagliari Calcio": "Cagliari",
    "Chelsea": "CHE",
    "Club Atlético de Madrid": "Atlético Madrid",
    "Club Atletico de Madrid": "Atlético Madrid",
    "Crystal Palace": "CRY",
    "Deportivo Alavés": "Alavés",
    "Everton": "EVE",
    "FC Bayern München": "Bayern Munich",
    "FC Internazionale Milano": "Inter Milan",
    "FC Nantes": "Nantes",
    "Fulham": "FUL",
    "Internazionale": "Inter Milan",
    "Feyenoord Rotterdam": "Feyenoord",
    "Genoa CFC": "Genoa",
    "Hellas Verona FC": "Hellas Verona",
    "Liverpool": "LIV",
    "Manchester City": "MCI",
    "Manchester United": "MUN",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "NFO",
    "Olympique Lyon": "Lyon",
    "Olympique Lyonnais": "Lyon",
    "Olympique de Marseille": "Marseille",
    "Paris Saint-Germain FC": "PSG",
    "RC Lens": "Lens",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "SSC Napoli": "Napoli",
    "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "WHU",
    "Wolverhampton": "WOL",
    "Wolverhampton Wanderers": "WOL",
    "Udinese Calcio": "Udinese",
    "US Cremonese": "Cremonese",
    "US Lecce": "Lecce",
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
  target.innerHTML = `<p class="status">${message}</p>`;
}

function selectedCompetition() {
  return searchForm.elements.competition?.value || "";
}

function updateRecentHeading(competition) {
  const label = competitionLabels[competition];
  recentHeading.textContent = label ? `Recent ${label} matches` : "Recent matches";
}

function loadingRecentMessage(competition) {
  const label = competitionLabels[competition];
  return label ? `Loading recent ${label} matches...` : "Loading recent matches...";
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
