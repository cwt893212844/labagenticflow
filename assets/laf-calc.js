/** Shared cost math + formatting for calculator, model, and compare pages */
(function (global) {
  const PRESETS = {
    "tool-call": { requests: 1, input: 8000, output: 400, label: "Single tool call" },
    rag: { requests: 10000, input: 4000, output: 800, label: "RAG query" },
    agent: { requests: 100000, input: 2000, output: 500, label: "High-volume agent" },
  };

  const DEFAULT_WORKLOAD = { requests: 10000, inputPerReq: 2000, outputPerReq: 500, period: "monthly" };

  function fmtNum(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + "K";
    return String(n);
  }

  function fmtMoney(n) {
    if (n < 0.01) return "$" + n.toFixed(4);
    if (n < 1) return "$" + n.toFixed(3);
    if (n < 100) return "$" + n.toFixed(2);
    return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }

  function fmtCtx(n) {
    if (n >= 1e6) return (n / 1e6) + "M";
    return (n / 1e3) + "K";
  }

  function fmtDatasetDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
  }

  function getVolumes(workload) {
    const mult = workload.period === "daily" ? 1 / 30 : 1;
    return {
      totalInput: workload.requests * workload.inputPerReq * mult,
      totalOutput: workload.requests * workload.outputPerReq * mult,
      mult,
    };
  }

  function calcCost(model, workload) {
    const { totalInput, totalOutput } = getVolumes(workload);
    return (totalInput / 1e6) * model.input + (totalOutput / 1e6) * model.output;
  }

  function buildCapChips(model) {
    const chips = [];
    if (model.tags.includes("tools")) chips.push({ key: "tools", label: "Tools" });
    if (model.tags.includes("vision")) chips.push({ key: "vision", label: "Vision" });
    if (model.context >= 1_000_000) chips.push({ key: "ctx-1m", label: "1M ctx" });
    else if (model.context >= 500_000) chips.push({ key: "ctx-500k", label: "500K+" });
    return chips
      .map((c) => `<span class="cap-chip cap-chip--${c.key}">${c.label}</span>`)
      .join("");
  }

  function parseWorkloadFromUrl(search = location.search) {
    const params = new URLSearchParams(search);
    const workload = { ...DEFAULT_WORKLOAD };
    const r = params.get("r");
    const inp = params.get("in");
    const out = params.get("out");
    const period = params.get("period");
    if (r) workload.requests = clamp(+r, 1, 1000000);
    if (inp) workload.inputPerReq = clamp(+inp, 100, 128000);
    if (out) workload.outputPerReq = clamp(+out, 50, 32000);
    if (period === "daily" || period === "monthly") workload.period = period;
    return workload;
  }

  function buildWorkloadQuery(workload, extra = {}) {
    const params = new URLSearchParams();
    const set = (key, val, defaultVal) => {
      if (val !== defaultVal) params.set(key, val);
    };
    set("r", workload.requests, DEFAULT_WORKLOAD.requests);
    set("in", workload.inputPerReq, DEFAULT_WORKLOAD.inputPerReq);
    set("out", workload.outputPerReq, DEFAULT_WORKLOAD.outputPerReq);
    if (workload.period !== DEFAULT_WORKLOAD.period) params.set("period", workload.period);
    Object.entries(extra).forEach(([k, v]) => {
      if (v != null && v !== "") params.set(k, v);
    });
    return params.toString();
  }

  function detectPreset(workload) {
    for (const [id, p] of Object.entries(PRESETS)) {
      if (
        workload.requests === p.requests &&
        workload.inputPerReq === p.input &&
        workload.outputPerReq === p.output
      ) {
        return id;
      }
    }
    return null;
  }

  function getPriceSeries(modelId, history) {
    if (!history?.snapshots?.length) return [];
    return history.snapshots
      .map((s) => ({
        date: s.date,
        input: s.prices?.[modelId]?.input,
        output: s.prices?.[modelId]?.output,
      }))
      .filter((p) => p.input != null);
  }

  global.LAF = {
    PRESETS,
    DEFAULT_WORKLOAD,
    fmtNum,
    fmtMoney,
    fmtCtx,
    fmtDatasetDate,
    clamp,
    getVolumes,
    calcCost,
    buildCapChips,
    parseWorkloadFromUrl,
    buildWorkloadQuery,
    detectPreset,
    getPriceSeries,
  };
})(window);
