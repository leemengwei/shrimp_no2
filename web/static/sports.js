const state = {
  markets: [],
  market: null,
  tokens: [],
  token: null,
  rows: [],
  total: 0,
  offset: 0,
  limit: 500,
  sort: "asc",
  fromTs: "",
  toTs: "",
  includeRaw: false,
  summary: {},
};

const marketQuery = document.getElementById("marketQuery");
const marketSelect = document.getElementById("marketSelect");
const tokenSelect = document.getElementById("tokenSelect");
const fromTsInput = document.getElementById("fromTsInput");
const toTsInput = document.getElementById("toTsInput");
const sortSelect = document.getElementById("sortSelect");
const limitSelect = document.getElementById("limitSelect");
const rawToggle = document.getElementById("rawToggle");
const loadBtn = document.getElementById("loadBtn");
const resetBtn = document.getElementById("resetBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const pageInfo = document.getElementById("pageInfo");
const tableBody = document.getElementById("tableBody");
const marketCount = document.getElementById("marketCount");
const pointsCount = document.getElementById("pointsCount");
const rangeInfo = document.getElementById("rangeInfo");
const marketInfo = document.getElementById("marketInfo");
const tokenInfo = document.getElementById("tokenInfo");
const fidelityInfo = document.getElementById("fidelityInfo");
const priceChart = document.getElementById("priceChart");

function formatTs(ts) {
  if (ts === null || ts === undefined) return "-";
  const dt = new Date(ts * 1000);
  return dt.toISOString().replace("T", " ").slice(0, 19);
}

function formatNumber(val, digits = 6) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  return Number(val).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function parseInputTs(value) {
  if (!value) return null;
  const text = value.trim();
  if (!text) return null;
  if (/^\d+$/.test(text)) return parseInt(text, 10);
  let candidate = text;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    candidate = `${text}T00:00:00Z`;
  }
  const parsed = Date.parse(candidate);
  if (!Number.isNaN(parsed)) {
    return Math.floor(parsed / 1000);
  }
  return null;
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return await res.json();
}

function updateSummary() {
  marketCount.textContent = state.summary.available_markets ?? "-";
  fidelityInfo.textContent = state.summary.fidelity ?? "-";
  if (state.rows.length > 0) {
    pointsCount.textContent = `${state.total}`;
    rangeInfo.textContent = `${formatTs(state.summaryMinTs)} ~ ${formatTs(state.summaryMaxTs)}`;
  } else {
    pointsCount.textContent = "-";
    rangeInfo.textContent = "-";
  }
  if (state.market) {
    marketInfo.textContent = `${state.market.index} / ${state.market.question || "-"}`;
  } else {
    marketInfo.textContent = "-";
  }
  tokenInfo.textContent = state.token || "-";
}

function updatePageInfo() {
  if (state.total === 0) {
    pageInfo.textContent = "-";
    return;
  }
  const start = state.offset + 1;
  const end = Math.min(state.offset + state.limit, state.total);
  pageInfo.textContent = `${start}-${end} / ${state.total}`;
}

function buildTable() {
  tableBody.innerHTML = "";
  if (!state.rows.length) {
    tableBody.innerHTML = `<tr><td colspan="4">无数据</td></tr>`;
    return;
  }
  state.rows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    const rawCell = state.includeRaw && row.raw ? JSON.stringify(row.raw) : "";
    tr.innerHTML = `
      <td>${state.offset + idx + 1}</td>
      <td>${formatTs(row.ts)}</td>
      <td>${formatNumber(row.price)}</td>
      <td class="raw-cell">${rawCell}</td>
    `;
    tableBody.appendChild(tr);
  });
}

function drawChart() {
  const ctx = priceChart.getContext("2d");
  const w = priceChart.width;
  const h = priceChart.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0f1520";
  ctx.fillRect(0, 0, w, h);

  if (!state.rows.length) {
    ctx.fillStyle = "#8aa0b6";
    ctx.font = "12px sans-serif";
    ctx.fillText("无数据", 12, 24);
    return;
  }

  const rows = state.rows.filter((r) => typeof r.ts === "number" && typeof r.price === "number");
  if (!rows.length) return;
  const minTs = Math.min(...rows.map((r) => r.ts));
  const maxTs = Math.max(...rows.map((r) => r.ts));
  const minPrice = Math.min(...rows.map((r) => r.price));
  const maxPrice = Math.max(...rows.map((r) => r.price));

  const xScale = maxTs === minTs ? 1 : w / (maxTs - minTs);
  const yScale = maxPrice === minPrice ? 1 : (h - 20) / (maxPrice - minPrice);

  ctx.strokeStyle = "#47c0ff";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  rows.forEach((row, idx) => {
    const x = (row.ts - minTs) * xScale;
    const y = h - 10 - (row.price - minPrice) * yScale;
    if (idx === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
}

function populateMarketSelect(list) {
  marketSelect.innerHTML = "";
  list.forEach((market) => {
    const option = document.createElement("option");
    option.value = market.index;
    option.textContent = `${market.index} | ${market.question || market.slug || market.market_id}`;
    marketSelect.appendChild(option);
  });
  if (list.length > 0) {
    marketSelect.value = list[0].index;
  }
}

function populateTokenSelect(tokens) {
  tokenSelect.innerHTML = "";
  tokens.forEach((token) => {
    const option = document.createElement("option");
    option.value = token.token_id;
    option.textContent = token.token_id;
    tokenSelect.appendChild(option);
  });
  if (tokens.length > 0) {
    tokenSelect.value = tokens[0].token_id;
  }
}

async function loadSummary() {
  state.summary = await fetchJson("/api/sports/summary");
  updateSummary();
}

async function loadMarkets() {
  const data = await fetchJson("/api/sports/markets");
  state.markets = data.markets || [];
  applyMarketFilter();
}

function applyMarketFilter() {
  const query = (marketQuery.value || "").trim().toLowerCase();
  const filtered = query
    ? state.markets.filter((m) => `${m.question || ""} ${m.slug || ""}`.toLowerCase().includes(query))
    : state.markets;
  populateMarketSelect(filtered);
  if (filtered.length > 0) {
    selectMarket(filtered[0].index);
  }
}

async function selectMarket(index) {
  if (!index) return;
  const market = await fetchJson(`/api/sports/market/${index}`);
  state.market = market;
  state.tokens = market.tokens || [];
  populateTokenSelect(state.tokens);
  state.token = tokenSelect.value || null;
  updateSummary();
}

async function loadPoints() {
  if (!state.market || !state.token) return;
  state.limit = parseInt(limitSelect.value, 10);
  state.sort = sortSelect.value;
  state.fromTs = parseInputTs(fromTsInput.value);
  state.toTs = parseInputTs(toTsInput.value);
  state.includeRaw = rawToggle.checked;
  const params = new URLSearchParams();
  params.set("market_index", state.market.index);
  params.set("token_id", state.token);
  params.set("limit", state.limit);
  params.set("offset", state.offset);
  params.set("sort", state.sort);
  if (state.fromTs !== null) params.set("from_ts", state.fromTs);
  if (state.toTs !== null) params.set("to_ts", state.toTs);
  if (state.includeRaw) params.set("raw", "1");

  const payload = await fetchJson(`/api/sports/points?${params.toString()}`);
  state.rows = payload.rows || [];
  state.total = payload.total || 0;
  state.summaryMinTs = payload.min_ts;
  state.summaryMaxTs = payload.max_ts;
  buildTable();
  drawChart();
  updatePageInfo();
  updateSummary();
}

function resetFilters() {
  fromTsInput.value = "";
  toTsInput.value = "";
  rawToggle.checked = false;
  sortSelect.value = "asc";
  limitSelect.value = "500";
  state.offset = 0;
  loadPoints();
}

marketQuery.addEventListener("input", () => applyMarketFilter());
marketSelect.addEventListener("change", () => {
  selectMarket(parseInt(marketSelect.value, 10));
});
tokenSelect.addEventListener("change", () => {
  state.token = tokenSelect.value;
});
loadBtn.addEventListener("click", () => {
  state.offset = 0;
  loadPoints();
});
resetBtn.addEventListener("click", resetFilters);

prevBtn.addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  loadPoints();
});
nextBtn.addEventListener("click", () => {
  if (state.offset + state.limit < state.total) {
    state.offset += state.limit;
    loadPoints();
  }
});

async function init() {
  await loadSummary();
  await loadMarkets();
  if (state.markets.length > 0) {
    await selectMarket(parseInt(marketSelect.value, 10));
    await loadPoints();
  }
}

init();
