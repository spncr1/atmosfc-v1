const title = document.querySelector("[data-match-title]");
const meta = document.querySelector("[data-match-meta]");
const summary = document.querySelector("[data-summary]");
const events = document.querySelector("[data-events]");
const comments = document.querySelector("[data-comments]");
const halves = document.querySelector("[data-halves]");
const statusEl = document.querySelector("[data-status]");
const params = new URLSearchParams(window.location.search);

init();

async function init() {
  const stored = JSON.parse(sessionStorage.getItem("selectedMatch") || "null");
  if (stored) renderMatchHeader(stored);

  const matchId = params.get("match_id") || stored?.id;
  if (!matchId) {
    statusEl.textContent = "Choose a match first.";
    return;
  }

  try {
    statusEl.textContent = "Analysing YouTube match comments...";
    const analysis = await apiPost("/analyse", { match_id: matchId });
    statusEl.textContent = "";
    renderAnalysis(analysis);
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

function renderAnalysis(data) {
  renderMatchHeader(data.match);
  renderSummary(data.meta);
  renderChart(data.sentiment_buckets);
  renderEvents(data.events);
  renderHalves(data.half_split);
  renderComments(data.top_comments, data.meta.youtube_video_url);
}

function renderMatchHeader(match) {
  title.textContent = `${match.home} ${match.score} ${match.away}`;
  meta.textContent = `${match.competition} - ${formatDate(match.date)} - ${match.round || match.season || ""}`;
}

function renderSummary(data) {
  summary.innerHTML = `
    <div><span>Total comments</span><strong>${data.total_comments}</strong></div>
    <div><span>Peak minute</span><strong>${data.peak_minute}'</strong></div>
    <div><span>Overall vibe</span><strong>${data.overall_vibe}</strong></div>
    <div><span>Crowd energy</span><strong>${data.crowd_energy}</strong></div>
  `;
}

function renderChart(buckets) {
  const ctx = document.querySelector("#pulseChart");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: buckets.map((bucket) => `${bucket.minute}'`),
      datasets: [
        {
          label: "Sentiment",
          data: buckets.map((bucket) => bucket.score),
          borderColor: "#13a77a",
          backgroundColor: "rgba(19, 167, 122, 0.14)",
          borderWidth: 3,
          pointRadius: 3,
          tension: 0.35,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { min: -1, max: 1, grid: { color: "#e6ebe7" } },
        x: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel(context) {
              const bucket = buckets[context.dataIndex];
              return `${bucket.comment_count} comments`;
            },
          },
        },
      },
    },
  });
}

function renderEvents(items) {
  events.innerHTML = items.length
    ? items.map((event) => `<li><strong>${event.minute}'</strong><span>${event.description}</span></li>`).join("")
    : `<li><span>Event detail unavailable from the match feed.</span></li>`;
}

function renderHalves(split) {
  halves.innerHTML = Object.entries(split)
    .map(([half, values]) => `
      <div>
        <span>${half === "first" ? "First half" : "Second half"}</span>
        <strong>${values.pos}</strong><small>positive</small>
        <strong>${values.neg}</strong><small>negative</small>
        <strong>${values.neu}</strong><small>neutral</small>
      </div>
    `)
    .join("");
}

function renderComments(items, videoUrl) {
  comments.innerHTML = items.length
    ? items.map((item) => `
        <article class="comment-card">
          <p>${item.text}</p>
          <span>${item.minute}' - ${item.score} likes - ${item.sentiment}</span>
        </article>
      `).join("")
    : `<p class="status">No peak comments found.</p>`;
  if (videoUrl) {
    comments.insertAdjacentHTML("beforeend", `<a class="video-link" href="${videoUrl}" target="_blank" rel="noreferrer">Open YouTube video</a>`);
  }
}
