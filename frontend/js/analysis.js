const statusEl = document.querySelector("[data-status]");
const badgesEl = document.querySelector("[data-match-badges]");
const matchDetailEl = document.querySelector("[data-match-detail]");
const homeCrestEl = document.querySelector("[data-home-crest]");
const awayCrestEl = document.querySelector("[data-away-crest]");
const homeShortEl = document.querySelector("[data-home-short]");
const awayShortEl = document.querySelector("[data-away-short]");
const homeFullEl = document.querySelector("[data-home-full]");
const awayFullEl = document.querySelector("[data-away-full]");
const scoreEl = document.querySelector("[data-match-score]");
const halfTimeEl = document.querySelector("[data-half-time]");
const summaryEl = document.querySelector("[data-summary]");
const eventsEl = document.querySelector("[data-events]");
const commentsEl = document.querySelector("[data-comments]");
const legendEl = document.querySelector("[data-chart-legend]");
const backLinkEl = document.querySelector("[data-back-link]");
const params = new URLSearchParams(window.location.search);
let pulseChart;

init();

async function init() {
  setupBackLink();
  const stored = JSON.parse(sessionStorage.getItem("selectedMatch") || "null");
  if (stored) renderMatchHeader(stored);

  const matchId = params.get("match_id") || stored?.id;
  if (!matchId) {
    setStatus("Choose a match first.");
    return;
  }

  try {
    setStatus("Analysing YouTube match comments...");
    const analysis = await apiPost("/analyse", { match_id: matchId });
    setStatus("");
    renderAnalysis(analysis);
  } catch (error) {
    setStatus(error.message);
  }
}

function renderAnalysis(data) {
  renderMatchHeader(data.match);
  renderSummary(data.meta);
  renderChart(data.reaction_intensity || []);
  renderEvents(data.events || []);
  renderComments(data.top_comments || [], data.meta.youtube_video_url);
}

function renderMatchHeader(match) {
  badgesEl.innerHTML = `
    <span class="analysis-pill">${escapeHtml(match.competition || "Competition")}</span>
    <span class="analysis-pill analysis-pill-muted">${escapeHtml(match.round || match.season || "Stage unavailable")}</span>
  `;
  matchDetailEl.textContent = [formatDate(match.date), match.venue || "Venue unavailable"].filter(Boolean).join(" · ");
  setCrest(homeCrestEl, match.home_crest);
  setCrest(awayCrestEl, match.away_crest);
  homeShortEl.textContent = match.home;
  awayShortEl.textContent = match.away;
  homeFullEl.textContent = `${match.home_short_name || shortTeamName(match.home)} (H)`;
  awayFullEl.textContent = `${match.away_short_name || shortTeamName(match.away)} (A)`;
  scoreEl.textContent = (match.score || "0 - 0").replace(" - ", " - ");
  if (match.half_time_score) {
    halfTimeEl.textContent = `HT ${match.half_time_score.replace(" - ", " - ")}`;
    halfTimeEl.hidden = false;
  } else {
    halfTimeEl.textContent = "";
    halfTimeEl.hidden = true;
  }
}

function renderSummary(meta) {
  const peak = meta.peak_window || { hour_start: 0, hour_end: 1 };
  summaryEl.innerHTML = `
    ${metricCard("Overall vibe", meta.overall_vibe?.label || "Forgettable", meta.overall_vibe?.subtext || "", true)}
    ${metricCard("Crowd energy", meta.crowd_energy?.label || "Quiet", meta.crowd_energy?.subtext || "", true)}
    ${metricCard("Peak reaction window", `Hours ${peak.hour_start} – ${peak.hour_end}`, "Highest volume post match", false)}
    ${metricCard("Comments analysed", formatNumber(meta.total_comments), "First 24 hours after full time", false)}
  `;
}

function metricCard(label, value, subtext, accent) {
  return `
    <article class="analysis-metric">
      <span>${label}</span>
      <strong class="${accent ? "is-accent" : ""}">${escapeHtml(value)}</strong>
      <small>${escapeHtml(subtext || "")}</small>
    </article>
  `;
}

function renderChart(buckets) {
  const ctx = document.querySelector("#pulseChart");
  if (!ctx) return;
  if (pulseChart) pulseChart.destroy();
  if (!window.Chart) {
    showChartFallback("Reaction chart could not load.");
    return;
  }
  if (!buckets.length) {
    showChartFallback("Reaction chart unavailable for this match.");
    return;
  }

  const labels = buckets.map((bucket, index) => index === 0 ? "FT" : `${bucket.hour_offset}h`);
  const peakIndex = buckets.reduce((best, bucket, index) => {
    if (best === -1) return index;
    const current = buckets[best];
    return bucket.intensity > current.intensity ? index : best;
  }, -1);

  pulseChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Reaction intensity",
          data: buckets.map((bucket) => bucket.intensity),
          borderColor: "#C8FF47",
          borderWidth: 2.5,
          pointBackgroundColor: "#C8FF47",
          pointBorderColor: "#C8FF47",
          pointRadius: buckets.map((_, index) => index === peakIndex ? 6 : 3),
          pointHoverRadius: buckets.map((_, index) => index === peakIndex ? 7 : 4),
          tension: 0.35,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          max: 100,
          title: { display: true, text: "Reaction intensity", color: "#505058" },
          ticks: { color: "#505058", font: { size: 11 } },
          grid: { color: "#242428" },
        },
        x: {
          title: { display: true, text: "Hours after full time", color: "#505058" },
          ticks: { color: "#505058", font: { size: 11 } },
          grid: { color: "#242428" },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(context) {
              const bucket = buckets[context.dataIndex];
              return `Intensity ${Math.round(bucket.intensity)}`;
            },
            afterLabel(context) {
              const bucket = buckets[context.dataIndex];
              return [
                `VADER sentiment score: ${bucket.sentiment.toFixed(2)} (${sentimentLabel(bucket.sentiment).toLowerCase()})`,
                `${formatNumber(bucket.comment_count)} comments in this window`,
              ];
            },
          },
        },
      },
    },
    plugins: [reactionZonePlugin],
  });

  legendEl.innerHTML = `
    <span><i class="legend-line"></i>Reaction intensity</span>
    <span><i class="legend-fill-positive"></i>High reaction zone</span>
    <span><i class="legend-fill-negative"></i>Low reaction zone</span>
    <span><i class="legend-dot"></i>Peak window</span>
  `;
}

function showChartFallback(message) {
  const wrap = document.querySelector(".analysis-chart-wrap");
  if (wrap) {
    wrap.innerHTML = `<p class="analysis-empty">${escapeHtml(message)}</p>`;
  }
  if (legendEl) {
    legendEl.innerHTML = "";
  }
}

const reactionZonePlugin = {
  id: "reactionZone",
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea) return;
    const midY = scales.y.getPixelForValue(50);
    ctx.save();
    ctx.fillStyle = "rgba(200,255,71,0.08)";
    ctx.fillRect(chartArea.left, chartArea.top, chartArea.right - chartArea.left, midY - chartArea.top);
    ctx.fillStyle = "rgba(80,80,88,0.15)";
    ctx.fillRect(chartArea.left, midY, chartArea.right - chartArea.left, chartArea.bottom - midY);
    ctx.restore();
  },
};

function renderEvents(items) {
  eventsEl.innerHTML = items.length
    ? items.map((event) => `
      <li>
        <strong>${event.minute}'</strong>
        <span>${escapeHtml(event.description)}</span>
        <em class="event-pill event-pill-${event.type}">${escapeHtml(eventLabel(event.type))}</em>
      </li>
    `).join("")
    : `<li class="analysis-empty">Event detail unavailable from the match feed.</li>`;
}

function renderComments(items, videoUrl) {
  commentsEl.innerHTML = items.length
    ? items.slice(0, 3).map((item) => {
      const sourceUrl = item.source_url || videoUrl;
      return `
      <article class="analysis-comment">
        <span>↑ ${formatNumber(item.score)} likes</span>
        <p>"${escapeHtml(item.text)}"</p>
        ${item.source_label ? `<small>From ${escapeHtml(item.source_label)}</small>` : ""}
        ${sourceUrl ? `<a href="${sourceUrl}" target="_blank" rel="noreferrer">View source video ↗</a>` : ""}
      </article>
    `;
    }).join("")
    : `<p class="analysis-empty">No usable YouTube comments found for this match.</p>`;
}

function setCrest(target, src) {
  if (!src) {
    target.removeAttribute("src");
    target.hidden = true;
    return;
  }
  target.hidden = false;
  target.src = src;
  target.onerror = () => { target.hidden = true; };
}

function shortTeamName(name) {
  return (name || "")
    .replace(/^FC\s+/i, "")
    .replace(/\s+FC$/i, "")
    .replace(/\s+CF$/i, "")
    .replace(/\s+AFC$/i, "")
    .replace("Paris Saint-Germain", "PSG")
    .replace("FC Bayern München", "Bayern Munich");
}

function sentimentLabel(score) {
  if (score >= 0.05) return "Positive";
  if (score <= -0.05) return "Negative";
  return "Mixed";
}

function eventLabel(type) {
  if (type === "yellow-card") return "Yellow card";
  if (type === "red-card") return "Red card";
  return "Goal";
}

function formatNumber(value) {
  return new Intl.NumberFormat("en").format(value || 0);
}

function setStatus(message) {
  statusEl.textContent = message;
  statusEl.hidden = !message;
}

function setupBackLink() {
  if (!backLinkEl) return;
  backLinkEl.href = sessionStorage.getItem("resultsReturnUrl") || "results.html";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
