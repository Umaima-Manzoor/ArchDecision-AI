const form = document.getElementById("search-form");
const questionInput = document.getElementById("question");
const submitBtn = document.getElementById("submit-btn");
const loadingEl = document.getElementById("loading");
const loadingStatus = document.getElementById("loading-status");
const errorEl = document.getElementById("error");
const errorMessage = document.getElementById("error-message");
const resultsEl = document.getElementById("results");
const summaryBar = document.getElementById("summary-bar");
const matrixContainer = document.getElementById("matrix-container");
const conflictsContainer = document.getElementById("conflicts-container");
const insufficientContainer = document.getElementById("insufficient-container");
const traceList = document.getElementById("trace-list");
const clearBtn = document.getElementById("clear-btn");

function showState(state) {
  loadingEl.classList.toggle("hidden", state !== "loading");
  errorEl.classList.toggle("hidden", state !== "error");
  resultsEl.classList.toggle("hidden", state !== "results");
}

function resetForm() {
  showState("none");
  questionInput.value = "";
  clearBtn.classList.add("hidden");
  questionInput.focus();
}

clearBtn.addEventListener("click", resetForm);

function formatTime(isoString) {
  const d = new Date(isoString);
  return d.toLocaleTimeString("en-GB", { hour12: false });      // 24-hour format: HH:MM:SS
}

function confidenceBar(level) {       // small colored bar that visually encodes confidence level
  const cls = level === "H" ? "confidence-bar-h" : level === "M" ? "confidence-bar-m" : "confidence-bar-l";
  return `<span class="confidence-bar ${cls}"></span>`;
}

function confidenceBadge(level) {
  const cls = level === "H" ? "badge-h" : level === "M" ? "badge-m" : "badge-l";
  const label = level === "H" ? "High" : level === "M" ? "Medium" : "Low";
  return `<span class="badge ${cls}" title="Confidence: ${label}">${confidenceBar(level)}${level}</span>`;
}

function tagBadge(tag) {
  const cls =
    tag === "FACT" ? "badge-fact" :
    tag === "INFERENCE" ? "badge-inference" : "badge-unverified";
  return `<span class="badge ${cls}">${tag}</span>`;
}

function esc(str) {         // prevents execution of script from the results
  const div = document.createElement("div");
  div.textContent = str;        // plain text not HTML
  return div.innerHTML;
}

function handleStreamEvent(data) {
  if (data.step === "error") {
    errorMessage.textContent = data.detail;
    showState("error");
    return;
  }

  if (data.step === "complete" && data.data) {
    renderResults(data.data);
    return;
  }

  // Update the loading text for intermediate steps
  const labels = {
    planning: "Planning research axes",
    planned: data.detail,
    searching: "Searching for evidence",
    searched: data.detail,
    cleaning: "Cleaning and deduplicating sources",
    cleaned: data.detail,
    synthesizing: "Synthesizing trade-off matrix",
  };

  const text = labels[data.step] || data.detail;
  loadingStatus.textContent = text;
}

function renderResults(data) {
  const m = data.matrix;

  // Build token usage HTML if available
  let tokenHTML = "";
  if (data.token_usage && data.token_usage.total_tokens > 0) {
    const tokens = data.token_usage.total_tokens.toLocaleString();      // adds commas: 2450 -> "2,450"
    const cost = data.token_usage.estimated_cost_usd.toFixed(4);        // 4 decimal places: 0.0012
    tokenHTML = `<span class="summary-stat">~${tokens} tokens</span><span class="summary-stat cost-stat">~$${cost}</span>`;
  }

  summaryBar.innerHTML = `
    <h2>${esc(m.technology_a)} vs ${esc(m.technology_b)}</h2>
    <span class="summary-stat">${data.total_sources} sources</span>
    <span class="summary-stat">${m.cells.length} cells</span>
    <span class="summary-stat">${data.latency_seconds}s</span>
    ${tokenHTML}
  `;

  const axes = [...new Set(m.cells.map((c) => c.axis))];        // creates array of axis - Set: no duplicates - ... takes them out of set and put them in array (since func like .map() and .filter() can't be used for Set)
  let tableHTML = `
    <table class="matrix-table">
      <thead>
        <tr>
          <th>Axis</th>
          <th>${esc(m.technology_a)}</th>
          <th>${esc(m.technology_b)}</th>
        </tr>
      </thead>
      <tbody>
  `;

  for (const axis of axes) {
    const cells = m.cells.filter((c) => c.axis === axis);
    const cellA = cells.find((c) => c.technology === m.technology_a);
    const cellB = cells.find((c) => c.technology === m.technology_b);

    tableHTML += `<tr>`;
    tableHTML += `<td class="axis-name" data-label="Axis">${esc(axis)}</td>`;
    tableHTML += `<td data-label="${esc(m.technology_a)}">${renderCell(cellA)}</td>`;
    tableHTML += `<td data-label="${esc(m.technology_b)}">${renderCell(cellB)}</td>`;
    tableHTML += `</tr>`;
  }

  tableHTML += `</tbody></table>`;
  matrixContainer.innerHTML = tableHTML;

  if (m.conflicts.length > 0) {
    let html = `<p class="section-label">Conflicts detected</p>`;
    for (const c of m.conflicts) {
      html += `
        <div class="conflict-box">
          <strong>${esc(c.axis)}</strong>
          <p>${esc(c.description)}</p>
          <div class="conflict-sources">
            <a class="source-link" href="${esc(c.source_a_url)}" target="_blank" rel="noopener">Source A</a>
            &middot;
            <a class="source-link" href="${esc(c.source_b_url)}" target="_blank" rel="noopener">Source B</a>
          </div>
        </div>
      `;        // _blank opens link in new page - noopener prevents the new tab from accessing the original page
    }
    conflictsContainer.innerHTML = html;
  } else {
    conflictsContainer.innerHTML = "";
  }

  if (m.insufficient_data.length > 0) {
    let html = `<p class="section-label">Insufficient data</p><ul class="insufficient-list">`;
    for (const axis of m.insufficient_data) {
      html += `<li>${esc(axis)}</li>`;
    }
    html += `</ul>`;
    insufficientContainer.innerHTML = html;
  } else {
    insufficientContainer.innerHTML = "";
  }

  let traceHTML = "";
  for (const step of data.trace) {
    traceHTML += `
      <div class="trace-step">
        <span class="trace-time">${formatTime(step.timestamp)}</span>
        <span class="trace-label">${esc(step.step)}</span>
        <span>${esc(step.detail)}</span>
      </div>
    `;
  }
  traceList.innerHTML = traceHTML;

  showState("results");
  clearBtn.classList.remove("hidden");
  resultsEl.classList.add("fade-in");       // trigger the CSS fade-in animation
}

function renderCell(cell) {
  if (!cell) return `<span style="color:var(--text-muted)">No data</span>`;

  const sourceTitle = cell.source_title || cell.source_url;
  return `
    <p class="claim-text">${esc(cell.claim)}</p>
    <div class="claim-meta">
      ${confidenceBadge(cell.confidence)}
      ${tagBadge(cell.tag)}
      <a class="source-link" href="${esc(cell.source_url)}" target="_blank" rel="noopener">${esc(sourceTitle)}</a>
    </div>
  `;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();       // prevents full page reload

  const question = questionInput.value.trim();
  if (question.length < 10) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Working...";
  loadingStatus.textContent = "Connecting";
  resultsEl.classList.remove("fade-in");       // reset animation so it replays on next query
  showState("loading");
  clearBtn.classList.remove("hidden");

  try {
    const url = `/api/research/stream?question=${encodeURIComponent(question)}`;       // encodeURIComponent converts spaces to %20 etc.
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const reader = response.body.getReader();       // reads the response body chunk by chunk
    const decoder = new TextDecoder();              // converts raw bytes to JavaScript strings
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });    // indicates more data is coming so hold off onto any incomplete multi-byte chars before decoding
      const events = buffer.split("\n\n");          // SSE events are separated by double newlines
      buffer = events.pop();                        // keep any incomplete event in the buffer

      for (const event of events) {
        if (event.startsWith("data: ")) {
          const jsonStr = event.slice(6);            // strip the "data: " prefix
          const data = JSON.parse(jsonStr);
          handleStreamEvent(data);
        }
      }
    }
  } catch (err) {
    if (!errorEl.classList.contains("hidden")) return;      // error already shown by handleStreamEvent
    errorMessage.textContent = err.message;     // use textContent instead of innerHTML for safety
    showState("error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Analyze";
  }
});