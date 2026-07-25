/* LabAgenticFlow model hub + /model/{slug} pages */
(function () {
  const BASE = document.body.dataset.base || "";
  const MODELS_URL = `${BASE}data/models.json`;
  const HISTORY_URL = `${BASE}data/price_history.json`;
  const HOME = `${BASE}index.html`;
  const COMPARE = `${BASE}compare.html`;
  const MODEL_HUB = `${BASE}model.html`;

  let MODELS = [];
  let history = null;
  let workload = LAF.parseWorkloadFromUrl();

  const $ = (sel, root = document) => root.querySelector(sel);

  function modelHref(id) {
    return `/model/${encodeURIComponent(id)}`;
  }

  function getModelId() {
    const pinned = document.body.dataset.modelId;
    if (pinned) return pinned;
    const path = location.pathname.replace(/\/+$/, "");
    const match = path.match(/\/model\/([^/]+?)(?:\.html)?$/);
    if (match && match[1] !== "index") return decodeURIComponent(match[1]);
    return new URLSearchParams(location.search).get("m");
  }

  function fmtPriceTick(v) {
    if (v >= 10) return "$" + v.toFixed(1);
    if (v >= 1) return "$" + v.toFixed(2);
    return "$" + v.toFixed(3);
  }

  function fmtDateTick(iso) {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function pickTickIndices(count, maxTicks) {
    if (count <= 1) return [0];
    const n = Math.min(maxTicks, count);
    const out = [];
    for (let i = 0; i < n; i++) {
      out.push(Math.round((i / (n - 1)) * (count - 1)));
    }
    return [...new Set(out)];
  }

  function renderSparkline(series) {
    if (series.length < 2) {
      return `<div class="sparkline-wrap"><p class="load-state">Price history needs more daily snapshots (building…).</p></div>`;
    }

    const values = series.map((p) => p.input);
    const dates = series.map((p) => p.date);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);

    let min = rawMin;
    let max = rawMax;
    if (rawMin === rawMax) {
      const pad = Math.max(rawMin * 0.12, 0.05);
      min = rawMin - pad;
      max = rawMax + pad;
    } else {
      const pad = (rawMax - rawMin) * 0.1;
      min = rawMin - pad;
      max = rawMax + pad;
    }
    const range = max - min || 1;

    const W = 520;
    const H = 168;
    const margin = { top: 22, right: 16, bottom: 30, left: 52 };
    const plotW = W - margin.left - margin.right;
    const plotH = H - margin.top - margin.bottom;

    const xAt = (i) => margin.left + (i / (values.length - 1)) * plotW;
    const yAt = (v) => margin.top + plotH - ((v - min) / range) * plotH;

    const yTickCount = 4;
    const yTicks = Array.from({ length: yTickCount + 1 }, (_, i) => {
      const v = min + (range * i) / yTickCount;
      return { v, y: yAt(v) };
    });

    const xIndices = pickTickIndices(dates.length, 5);

    const gridLines = yTicks
      .map((t) => `<line class="sparkline-grid" x1="${margin.left}" y1="${t.y}" x2="${margin.left + plotW}" y2="${t.y}" />`)
      .join("");

    const yLabels = yTicks
      .map(
        (t) =>
          `<text class="sparkline-tick" x="${margin.left - 10}" y="${t.y + 3}" text-anchor="end">${fmtPriceTick(t.v)}</text>`
      )
      .join("");

    const xLabels = xIndices
      .map((i) => {
        const x = xAt(i);
        return `
            <line class="sparkline-grid" x1="${x}" y1="${margin.top}" x2="${x}" y2="${margin.top + plotH}" />
            <text class="sparkline-tick" x="${x}" y="${H - 8}" text-anchor="middle">${fmtDateTick(dates[i])}</text>`;
      })
      .join("");

    const pts = values.map((v, i) => `${xAt(i)},${yAt(v)}`);
    const baseline = margin.top + plotH;
    const area = `${xAt(0)},${baseline} ${pts.join(" ")} ${xAt(values.length - 1)},${baseline}`;

    const hoverDots = values
      .map(
        (v, i) =>
          `<circle class="sparkline-hover-dot" cx="${xAt(i)}" cy="${yAt(v)}" r="4" fill="var(--phosphor)" data-date="${dates[i]}" data-value="${v}" data-output="${series[i].output}" />`
      )
      .join("");

    const hitRects = values
      .map(
        (v, i) =>
          `<rect class="sparkline-hit-area" x="${xAt(i) - plotW / values.length / 2}" y="${margin.top}" width="${plotW / values.length}" height="${plotH}" data-date="${dates[i]}" data-value="${v}" data-output="${series[i].output}" />`
      )
      .join("");

    const first = series[0].date;
    const last = series[series.length - 1].date;
    const delta = values[values.length - 1] - values[0];
    const deltaLabel =
      delta === 0 ? "flat" : delta > 0 ? `+${delta.toFixed(3)} $/M in` : `${delta.toFixed(3)} $/M in`;

    const ariaLabel = `Input price from ${first} to ${last}, ${deltaLabel}`;

    return `
        <div class="sparkline-wrap" style="position:relative">
          <div class="sparkline-meta">
            <span>Input price · ${series.length} days</span>
            <span>${first} → ${last} · ${deltaLabel}</span>
          </div>
          <svg class="sparkline-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${ariaLabel}">
            ${gridLines}
            ${xLabels}
            <line class="sparkline-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${baseline}" />
            <line class="sparkline-axis" x1="${margin.left}" y1="${baseline}" x2="${margin.left + plotW}" y2="${baseline}" />
            <text class="sparkline-y-label" x="${margin.left}" y="${margin.top - 6}" text-anchor="start">$/M in</text>
            ${yLabels}
            <polygon class="sparkline-fill" points="${area}" />
            <polyline class="sparkline-line" points="${pts.join(" ")}" />
            ${values.map((v, i) => `<circle cx="${xAt(i)}" cy="${yAt(v)}" r="2.5" fill="var(--phosphor)" />`).join("")}
            ${hoverDots}
            ${hitRects}
          </svg>
          <div class="sparkline-tooltip" id="sparkline-tooltip"></div>
        </div>`;
  }

  function renderWorkloadPanel(model) {
    const preset = LAF.detectPreset(workload);
    const cost = LAF.calcCost(model, workload);
    const periodLabel = workload.period === "daily" ? "/day" : "/mo";

    const presetBtns = Object.entries(LAF.PRESETS)
      .map(([id, p]) => `<button type="button" class="preset-btn${preset === id ? " active" : ""}" data-preset="${id}">${p.label}</button>`)
      .join("");

    return `
        <h2 class="section-label">Workload estimate</h2>
        <div class="workload-panel" id="workload-panel">
          <div class="preset-row" role="group" aria-label="Scenario presets">${presetBtns}</div>
          <div class="slider-field">
            <div class="slider-head"><span>Monthly requests</span><span id="val-r">${workload.requests.toLocaleString()}</span></div>
            <input type="range" id="sl-r" min="1" max="1000000" step="1" value="${workload.requests}" />
          </div>
          <div class="slider-field">
            <div class="slider-head"><span>Input tokens / request</span><span id="val-in">${workload.inputPerReq.toLocaleString()}</span></div>
            <input type="range" id="sl-in" min="100" max="128000" step="100" value="${workload.inputPerReq}" />
          </div>
          <div class="slider-field">
            <div class="slider-head"><span>Output tokens / request</span><span id="val-out">${workload.outputPerReq.toLocaleString()}</span></div>
            <input type="range" id="sl-out" min="50" max="32000" step="50" value="${workload.outputPerReq}" />
          </div>
          <div class="action-row">
            <a class="action-link" href="${HOME}?${LAF.buildWorkloadQuery(workload, { model: model.id })}">Open in full calculator</a>
            <a class="action-link" href="${COMPARE}?${LAF.buildWorkloadQuery(workload, { models: model.id })}">Add to compare</a>
          </div>
        </div>
        <p class="hero-cost-sub" style="margin-top:12px" id="live-cost-hint">Estimated <strong style="color:var(--phosphor)">${LAF.fmtMoney(cost)}</strong>${periodLabel} at current workload</p>`;
  }

  function bindWorkload(model) {
    const update = () => {
      const qs = LAF.buildWorkloadQuery(workload);
      const path = modelHref(model.id);
      history.replaceState(null, "", qs ? `${path}?${qs}` : path);
      const cost = LAF.calcCost(model, workload);
      const periodLabel = workload.period === "daily" ? "/day" : "/mo";
      $("#hero-cost-value").textContent = LAF.fmtMoney(cost);
      $("#hero-cost-sub").textContent = periodLabel + " est.";
      $("#live-cost-hint").innerHTML = `Estimated <strong style="color:var(--phosphor)">${LAF.fmtMoney(cost)}</strong>${periodLabel} at current workload`;
      $("#val-r").textContent = workload.requests.toLocaleString();
      $("#val-in").textContent = workload.inputPerReq.toLocaleString();
      $("#val-out").textContent = workload.outputPerReq.toLocaleString();
      document.querySelectorAll(".preset-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.preset === LAF.detectPreset(workload));
      });
    };

    $("#sl-r")?.addEventListener("input", (e) => { workload.requests = +e.target.value; update(); });
    $("#sl-in")?.addEventListener("input", (e) => { workload.inputPerReq = +e.target.value; update(); });
    $("#sl-out")?.addEventListener("input", (e) => { workload.outputPerReq = +e.target.value; update(); });

    document.querySelectorAll(".preset-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const p = LAF.PRESETS[btn.dataset.preset];
        if (!p) return;
        workload.requests = p.requests;
        workload.inputPerReq = p.input;
        workload.outputPerReq = p.output;
        $("#sl-r").value = workload.requests;
        $("#sl-in").value = workload.inputPerReq;
        $("#sl-out").value = workload.outputPerReq;
        update();
      });
    });
  }

  function getDisclaimer(model) {
    const p = (model.provider || "").toLowerCase();
    const oid = (model.openrouter_id || "").toLowerCase();
    if (p === "deepseek") {
      return "DeepSeek Direct API has peak/off-peak pricing — roughly 20–30% higher during peak hours (10:30–18:30 & 21:00–23:00 Beijing time). This estimate uses the OpenRouter single rate and may underestimate actual peak-hour spend.";
    }
    if (p === "anthropic") {
      return "Anthropic charges separately for input cache reads (<code>input_cache_read</code>), which is not reflected in this estimate.";
    }
    if (p === "google" && model.name && model.name.toLowerCase().includes("gemini")) {
      return "Gemini multimodal inference (image, audio, web search) is billed separately and not included in this estimate.";
    }
    if (/o[134]/.test(oid) && oid.includes("thinking")) {
      return "Input $/M includes reasoning tokens — a complex problem may consume far more tokens than the output.";
    }
    return "";
  }

  function renderModel(model) {
    const cost = LAF.calcCost(model, workload);
    const periodLabel = workload.period === "daily" ? "/day" : "/mo";
    const series = LAF.getPriceSeries(model.id, history);
    const bench = model.benchmark_url
      ? `<a class="bench-link" href="${model.benchmark_url}" target="_blank" rel="noopener noreferrer">See ${model.benchmark_source || "provider"} benchmarks →</a>`
      : "";

    document.title = `${model.name} API pricing — LabAgenticFlow`;

    $("#page-root").innerHTML = `
        <section class="model-hero">
          <div>
            <p class="doc-eyebrow">Model pricing</p>
            <h1>${model.name}</h1>
            <p class="model-provider">${model.provider}</p>
            <p class="model-id">${model.openrouter_id}</p>
            <div class="model-tags">${LAF.buildCapChips(model)}</div>
            ${bench}
            ${getDisclaimer(model) ? `<p class="model-disclaimer">${getDisclaimer(model)}</p>` : ""}
          </div>
          <div class="hero-cost">
            <p class="hero-cost-label">Estimated cost</p>
            <p class="hero-cost-value" id="hero-cost-value">${LAF.fmtMoney(cost)}</p>
            <p class="hero-cost-sub" id="hero-cost-sub">${periodLabel} est.</p>
          </div>
        </section>

        <div class="stat-grid">
          <div class="stat-cell"><p class="stat-label">Input</p><p class="stat-value">$${model.input}/M</p></div>
          <div class="stat-cell"><p class="stat-label">Output</p><p class="stat-value">$${model.output}/M</p></div>
          <div class="stat-cell"><p class="stat-label">Context</p><p class="stat-value">${LAF.fmtCtx(model.context)}</p></div>
          <div class="stat-cell"><p class="stat-label">Source</p><p class="stat-value">OpenRouter</p></div>
        </div>

        ${renderWorkloadPanel(model)}

        <h2 class="section-label">Price trend</h2>
        ${renderSparkline(series)}
      `;

    bindWorkload(model);
    bindSparklineHover();
  }

  function bindSparklineHover() {
    const tooltip = document.getElementById("sparkline-tooltip");
    const svg = document.querySelector(".sparkline-chart");
    if (!tooltip || !svg) return;

    const getPos = (e) => ({ screenX: e.clientX, screenY: e.clientY });

    const hitRects = svg.querySelectorAll(".sparkline-hit-area");
    hitRects.forEach((rect) => {
      rect.addEventListener("mouseenter", (e) => {
        const date = e.target.dataset.date;
        const value = e.target.dataset.value;
        const output = e.target.dataset.output;
        if (!date || value === undefined) return;
        const { screenX, screenY } = getPos(e);
        const wrapRect = tooltip.parentElement.getBoundingClientRect();
        tooltip.innerHTML = `${date}<br>$${value}/M in  ·  $${output}/M out`;
        tooltip.style.whiteSpace = "nowrap";
        tooltip.style.left = `${screenX - wrapRect.left + 12}px`;
        tooltip.style.top = `${screenY - wrapRect.top - 36}px`;
        tooltip.classList.add("visible");
        svg.querySelectorAll(".sparkline-hover-dot").forEach((dot) => {
          dot.style.opacity = dot.dataset.date === date ? "1" : "0";
        });
      });
      rect.addEventListener("mouseleave", () => {
        tooltip.classList.remove("visible");
        svg.querySelectorAll(".sparkline-hover-dot").forEach((dot) => {
          dot.style.opacity = "0";
        });
      });
    });
  }

  function renderIndex() {
    document.title = "All models — LabAgenticFlow";
    const cards = MODELS.map((m) => `
        <a class="model-index-card" href="${modelHref(m.id)}">
          <h2>${m.name}</h2>
          <p>${m.provider} · $${m.input}/M in · ${LAF.fmtCtx(m.context)} ctx</p>
        </a>`).join("");

    $("#page-root").innerHTML = `
        <section class="doc-hero">
          <p class="doc-eyebrow">Model index</p>
          <h1>LLM pricing pages</h1>
          <p class="doc-lead">Per-model API rates, context limits, and workload estimates. Each model has a stable URL under <code>/model/{id}</code>.</p>
        </section>
        <div class="model-index">${cards}</div>
      `;
  }

  function renderNotFound(id) {
    document.title = "Unknown model — LabAgenticFlow";
    $("#page-root").innerHTML = `
        <div class="not-found">
          <p class="doc-eyebrow">Not found</p>
          <h1>Unknown model</h1>
          <p>No model with id <code>${id}</code>. <a href="${MODEL_HUB}">Browse all models</a>.</p>
        </div>`;
  }

  async function init() {
    const root = $("#page-root");
    if (!root) return;

    if (document.body.dataset.archived === "true") {
      return;
    }

    try {
      const [modelsRes, histRes] = await Promise.all([
        fetch(MODELS_URL),
        fetch(HISTORY_URL).catch(() => null),
      ]);
      if (!modelsRes.ok) throw new Error("models");
      const data = await modelsRes.json();
      MODELS = data.models || [];
      if (histRes?.ok) history = await histRes.json();

      const footer = $("#footer-note");
      if (footer) {
        footer.textContent =
          `Rates from OpenRouter (updated ${LAF.fmtDatasetDate(data.last_updated)}). Estimates only.`;
      }

      const id = getModelId();
      if (!id) {
        renderIndex();
        return;
      }
      const model = MODELS.find((m) => m.id === id);
      if (!model) {
        renderNotFound(id);
        return;
      }
      renderModel(model);
    } catch {
      root.innerHTML = `<p class="load-state">Failed to load data/models.json</p>`;
    }
  }

  init();
})();
