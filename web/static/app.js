const state = {
  user: null,
  endpoint: null,
  limit: 500,
  offset: 0,
  total: 0,
  query: "",
  fromTs: "",
  toTs: "",
  eventPriceMaxPoints: 250,
  eventPriceRef: null,
  eventPriceCollapsed: true,
  view: "full",
  sort: "desc",
  visibleColumns: new Set(),
  columnFilters: {},
  forceAllColumns: true,
  lastRows: [],
  lastColumns: [],
  lastColumnsKey: "",
  sortColumn: "",
  sortDirection: "asc",
  columnOrder: [],
  activeConfig: "默认",
  headerDrag: {
    source: null,
  },
  columnWidths: {},
  configs: {},
  pageStateMemory: {},
};

const userSelect = document.getElementById("userSelect");
const endpointSelect = document.getElementById("endpointSelect");
const queryInput = document.getElementById("queryInput");
const fromTsInput = document.getElementById("fromTsInput");
const toTsInput = document.getElementById("toTsInput");
const applyBtn = document.getElementById("applyBtn");
const resetBtn = document.getElementById("resetBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const limitSelect = document.getElementById("limitSelect");
const sortSelect = document.getElementById("sortSelect");
const columnGrid = document.getElementById("columnGrid");
const showAllBtn = document.getElementById("showAllBtn");
const hideAllBtn = document.getElementById("hideAllBtn");
const clearFiltersBtn = document.getElementById("clearFiltersBtn");
const saveConfigBtn = document.getElementById("saveConfigBtn");
const savedHint = document.getElementById("savedHint");
const configSelect = document.getElementById("configSelect");
const saveAsBtn = document.getElementById("saveAsBtn");
const deleteConfigBtn = document.getElementById("deleteConfigBtn");
const totalCount = document.getElementById("totalCount");
const pageInfo = document.getElementById("pageInfo");
const endpointTotal = document.getElementById("endpointTotal");
const endpointRange = document.getElementById("endpointRange");
const positionsValue = document.getElementById("positionsValue");
const tradedMarkets = document.getElementById("tradedMarkets");
const generatedAt = document.getElementById("generatedAt");
const fetchedAt = document.getElementById("fetchedAt");
const tableHead = document.getElementById("tableHead");
const tableBody = document.getElementById("tableBody");
const loadingBar = document.getElementById("loadingBar");
const loadingText = document.getElementById("loadingText");
const eventPriceTitle = document.getElementById("eventPriceTitle");
const eventPriceMeta = document.getElementById("eventPriceMeta");
const eventPriceChart = document.getElementById("eventPriceChart");
const eventPriceSection = document.getElementById("eventPriceSection");
const eventPriceToggleBtn = document.getElementById("eventPriceToggleBtn");
const eventPriceMaxPointsInput = document.getElementById("eventPriceMaxPoints");
const eventPriceApplyBtn = document.getElementById("eventPriceApplyBtn");
const eventPriceClearBtn = document.getElementById("eventPriceClearBtn");
let eventPriceChartInstance = null;
let eventPriceLineSeriesCache = [];
let eventSharesSeriesCache = [];

function viewMemoryKey(user, endpoint) {
  if (!user || !endpoint) return "";
  return `${user}::${endpoint}`;
}

function snapshotCurrentViewState() {
  if (!state.user || !state.endpoint) return;
  const key = viewMemoryKey(state.user, state.endpoint);
  if (!key) return;
  state.pageStateMemory[key] = {
    query: queryInput.value.trim(),
    fromTs: fromTsInput.value.trim(),
    toTs: toTsInput.value.trim(),
    limit: state.limit,
    sort: state.sort,
    eventPriceMaxPoints: state.eventPriceMaxPoints,
    activeConfig: state.activeConfig,
  };
}

function restoreViewStateForCurrentTarget() {
  const key = viewMemoryKey(state.user, state.endpoint);
  if (!key) return;
  const mem = state.pageStateMemory[key];
  if (!mem) return;
  state.query = mem.query || "";
  state.fromTs = mem.fromTs || "";
  state.toTs = mem.toTs || "";
  state.limit = Number.isFinite(mem.limit) ? mem.limit : state.limit;
  state.sort = mem.sort || state.sort;
  state.eventPriceMaxPoints = Number.isFinite(mem.eventPriceMaxPoints)
    ? mem.eventPriceMaxPoints
    : state.eventPriceMaxPoints;
  if (mem.activeConfig) state.activeConfig = mem.activeConfig;
  queryInput.value = state.query;
  fromTsInput.value = state.fromTs;
  toTsInput.value = state.toTs;
  limitSelect.value = String(state.limit);
  sortSelect.value = state.sort;
  if (eventPriceMaxPointsInput) {
    eventPriceMaxPointsInput.value = String(state.eventPriceMaxPoints);
  }
}

function captureLayoutState() {
  return {
    visibleColumns: Array.from(state.visibleColumns),
    columnFilters: { ...state.columnFilters },
    sortColumn: state.sortColumn,
    sortDirection: state.sortDirection,
    columnOrder: [...state.columnOrder],
    columnWidths: { ...state.columnWidths },
    forceAllColumns: state.forceAllColumns,
  };
}

function applyLayoutState(layout) {
  if (!layout) return;
  state.visibleColumns = new Set(layout.visibleColumns || []);
  state.columnFilters = { ...(layout.columnFilters || {}) };
  state.sortColumn = layout.sortColumn || "";
  state.sortDirection = layout.sortDirection || "asc";
  state.columnOrder = [...(layout.columnOrder || [])];
  state.columnWidths = { ...(layout.columnWidths || {}) };
  state.forceAllColumns = !!layout.forceAllColumns;
}

function formatTs(ts) {
  if (!ts) return "-";
  const dt = new Date(ts * 1000);
  return dt.toISOString().replace("T", " ").slice(0, 19);
}

function formatTsMsUtc(tsMs) {
  if (!Number.isFinite(tsMs)) return "-";
  const dt = new Date(tsMs);
  return dt.toISOString().replace("T", " ").slice(0, 19);
}

function formatNumber(val, digits = 2) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  return Number(val).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function toFiniteNumber(val) {
  if (typeof val === "number" && Number.isFinite(val)) return val;
  if (typeof val === "string" && val.trim() !== "") {
    const n = Number(val);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function readRowTs(row) {
  const keys = ["timestamp", "ts", "time", "createdAt", "created_at", "resolvedAt"];
  for (const k of keys) {
    const n = toFiniteNumber(row[k]);
    if (n !== null) return n;
  }
  return null;
}

function readNearestPrice(seriesData, tsMs) {
  if (!Array.isArray(seriesData) || seriesData.length === 0 || !Number.isFinite(tsMs)) return null;
  let lo = 0;
  let hi = seriesData.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (seriesData[mid][0] < tsMs) lo = mid + 1;
    else hi = mid;
  }
  const i = lo;
  const cand = [];
  if (i >= 0 && i < seriesData.length) cand.push(seriesData[i]);
  if (i - 1 >= 0) cand.push(seriesData[i - 1]);
  if (cand.length === 0) return null;
  cand.sort((a, b) => Math.abs(a[0] - tsMs) - Math.abs(b[0] - tsMs));
  return cand[0][1];
}

function normalizeAxisTsMs(raw) {
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    const asNum = Number(trimmed);
    if (Number.isFinite(asNum)) return asNum;
    const parsed = Date.parse(trimmed);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function getEventPriceMaxPoints() {
  const raw = eventPriceMaxPointsInput ? Number(eventPriceMaxPointsInput.value) : state.eventPriceMaxPoints;
  const n = Number.isFinite(raw) ? Math.trunc(raw) : state.eventPriceMaxPoints;
  const clamped = Math.max(1, Math.min(1000000, n));
  state.eventPriceMaxPoints = clamped;
  if (eventPriceMaxPointsInput) eventPriceMaxPointsInput.value = String(clamped);
  return clamped;
}

function ensureEventChart() {
  if (!eventPriceChart) return null;
  if (typeof window.echarts === "undefined") return null;
  if (!eventPriceChartInstance) {
    eventPriceChartInstance = window.echarts.init(eventPriceChart, null, { renderer: "svg" });
  }
  return eventPriceChartInstance;
}

function disposeEventChart() {
  try {
    if (eventPriceChartInstance) eventPriceChartInstance.dispose();
  } catch {
    // ignore dispose errors and rebuild lazily
  }
  eventPriceChartInstance = null;
}

async function reloadEventChartCanvasData() {
  disposeEventChart();
  await waitNextPaint();
  await loadEventPriceChart();
}

function hexToRgb(hex) {
  const cleaned = String(hex || "").replace("#", "");
  if (!cleaned || (cleaned.length !== 6 && cleaned.length !== 3)) return null;
  const full = cleaned.length === 3
    ? cleaned.split("").map((c) => `${c}${c}`).join("")
    : cleaned;
  const intVal = Number.parseInt(full, 16);
  if (!Number.isFinite(intVal)) return null;
  return {
    r: (intVal >> 16) & 255,
    g: (intVal >> 8) & 255,
    b: intVal & 255,
  };
}

function rgbToHex(r, g, b) {
  const clamp = (n) => Math.max(0, Math.min(255, Math.round(n)));
  return `#${[clamp(r), clamp(g), clamp(b)].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
}

function mixHex(hexA, hexB, ratio) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  if (!a || !b) return hexA;
  const t = Math.max(0, Math.min(1, ratio));
  return rgbToHex(
    a.r + (b.r - a.r) * t,
    a.g + (b.g - a.g) * t,
    a.b + (b.b - a.b) * t,
  );
}

function rgbaFromHex(hex, alpha) {
  const rgb = hexToRgb(hex);
  if (!rgb) return `rgba(127,140,141,${alpha})`;
  const a = Math.max(0, Math.min(1, alpha));
  return `rgba(${rgb.r},${rgb.g},${rgb.b},${a})`;
}

function drawEventPriceSeries(seriesList, tradeMarkers = [], positionSeries = []) {
  const chart = ensureEventChart();
  if (!chart) return;
  const normalized = Array.isArray(seriesList) ? seriesList : [];
  const tokenPalette = [
    "#1f77b4", "#e67e22", "#16a085", "#c0392b", "#7f8c8d", "#2e86de", "#d35400", "#27ae60",
  ];
  const tokenAliasMap = new Map();
  let tokenIdx = 1;
  for (const item of normalized) {
    const tokenId = String(item?.token_id || "").trim();
    if (!tokenId) continue;
    if (!tokenAliasMap.has(tokenId)) tokenAliasMap.set(tokenId, `token${tokenIdx++}`);
  }
  const tokenStyleMap = new Map();
  for (const [tokenId, alias] of tokenAliasMap.entries()) {
    const idx = Number.parseInt(String(alias).replace("token", ""), 10) || 1;
    const base = tokenPalette[(idx - 1) % tokenPalette.length];
    tokenStyleMap.set(tokenId, {
      base,
      clobBorder: mixHex(base, "#ffffff", 0.05),
      clobFill: rgbaFromHex(base, 0.12),
      tradesBorder: mixHex(base, "#000000", 0.18),
      tradesFill: rgbaFromHex(base, 0.55),
      buyColor: mixHex(base, "#ffffff", 0.18),
      sellColor: mixHex(base, "#000000", 0.18),
    });
  }

  const pointSeries = normalized.map((item, idx) => {
    const tokenId = String(item?.token_id || "").trim();
    const tokenAlias = tokenAliasMap.get(tokenId) || `token${idx + 1}`;
    const style = tokenStyleMap.get(tokenId) || {
      clobBorder: "#7f8c8d",
      clobFill: "rgba(127,140,141,0.12)",
      tradesBorder: "#5f6c6d",
      tradesFill: "rgba(127,140,141,0.55)",
    };
    const source = String(item.source || "").trim().toLowerCase();
    const isTrades = source === "trades";
    const data = (Array.isArray(item.points) ? item.points : [])
      .filter((pt) => typeof pt.ts === "number" && typeof pt.price === "number")
      .map((pt) => [pt.ts * 1000, pt.price])
      .sort((a, b) => a[0] - b[0]);
    return {
      name: `${tokenAlias}(${source || "unknown"})`,
      source,
      tokenId,
      type: "scatter",
      yAxisIndex: 0,
      symbol: "circle",
      symbolSize: isTrades ? 10 : 5,
      itemStyle: {
        color: isTrades ? style.tradesFill : style.clobFill,
        borderColor: isTrades ? style.tradesBorder : style.clobBorder,
        borderWidth: isTrades ? 1.5 : 1,
      },
      data,
      z: isTrades ? 5 : 7,
      zlevel: 0,
      progressive: 0,
    };
  }).filter((s) => s.data.length > 0).sort((a, b) => {
    const at = a.source === "trades" ? 0 : 1;
    const bt = b.source === "trades" ? 0 : 1;
    if (at !== bt) return at - bt;
    return String(a.name).localeCompare(String(b.name));
  });
  eventPriceLineSeriesCache = pointSeries.map((s) => ({ name: s.name, data: s.data }));

  const sharesLineSeries = (Array.isArray(positionSeries) ? positionSeries : []).map((item) => {
    const tokenId = String(item?.token_id || "").trim();
    const tokenAlias = tokenAliasMap.get(tokenId) || String(item?.token_alias || tokenId.slice(0, 8) || "token");
    const style = tokenStyleMap.get(tokenId) || { base: "#7f8c8d" };
    const data = (Array.isArray(item?.points) ? item.points : [])
      .filter((pt) => typeof pt?.ts === "number" && typeof pt?.shares === "number")
      .map((pt) => [pt.ts * 1000, pt.shares])
      .sort((a, b) => a[0] - b[0]);
    return {
      name: `${tokenAlias}(shares)`,
      type: "line",
      yAxisIndex: 1,
      step: "end",
      showSymbol: false,
      smooth: false,
      lineStyle: { color: mixHex(style.base, "#ffffff", 0.18), width: 1.4, opacity: 0.85 },
      data,
      z: 4,
      zlevel: 0,
      progressive: 0,
    };
  }).filter((s) => s.data.length > 0);
  eventSharesSeriesCache = sharesLineSeries.map((s) => ({ name: s.name, data: s.data }));

  const markerByTokenSide = new Map();
  for (const marker of Array.isArray(tradeMarkers) ? tradeMarkers : []) {
    if (!marker || typeof marker !== "object") continue;
    if (typeof marker.ts !== "number" || typeof marker.price !== "number") continue;
    const tokenId = String(marker.asset || "").trim();
    const side = String(marker.side || "").trim().toUpperCase();
    if (!tokenId || (side !== "BUY" && side !== "SELL")) continue;
    const tokenAlias = tokenAliasMap.get(tokenId) || tokenId.slice(0, 8) || "token";
    const key = `${tokenId}::${side}`;
    if (!markerByTokenSide.has(key)) markerByTokenSide.set(key, { tokenId, tokenAlias, side, tsList: [] });
    markerByTokenSide.get(key).tsList.push(marker.ts * 1000);
  }
  const markerSeries = Array.from(markerByTokenSide.values()).map((g) => {
    const style = tokenStyleMap.get(g.tokenId) || { buyColor: "#9aa7a8", sellColor: "#5f6c6d" };
    const isBuy = g.side === "BUY";
    return {
      name: `${g.tokenAlias}(${g.side}-line)`,
      type: "line",
      yAxisIndex: 0,
      data: [],
      showSymbol: false,
      lineStyle: { opacity: 0 },
      tooltip: { show: false },
      markLine: {
        symbol: "none",
        silent: true,
        animation: false,
        label: { show: false },
        lineStyle: {
          color: isBuy ? style.buyColor : style.sellColor,
          width: isBuy ? 1.2 : 1.1,
          type: isBuy ? "solid" : "dashed",
          opacity: 0.5,
        },
        data: g.tsList.map((x) => ({ xAxis: x })),
      },
      z: 3,
      zlevel: 0,
      progressive: 0,
    };
  });

  chart.setOption({
    animation: false,
    grid: { left: 56, right: 56, top: 48, bottom: 72 },
    legend: {
      top: 8,
      type: "scroll",
      data: [...pointSeries.map((s) => s.name), ...sharesLineSeries.map((s) => s.name), ...markerSeries.map((s) => s.name)],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params) => {
        if (!Array.isArray(params) || params.length === 0) return "";
        const tsRaw = params[0]?.axisValue ?? params[0]?.axisValueLabel ?? params[0]?.value?.[0];
        let tsMs = normalizeAxisTsMs(tsRaw);
        if (!Number.isFinite(tsMs)) {
          for (const item of params) {
            const cand = normalizeAxisTsMs(item?.value?.[0]);
            if (Number.isFinite(cand)) {
              tsMs = cand;
              break;
            }
          }
        }
        const title = Number.isFinite(tsMs) ? formatTsMsUtc(tsMs) : "";
        const lines = [title];
        for (const s of eventPriceLineSeriesCache) {
          const val = readNearestPrice(s.data, tsMs);
          lines.push(`${s.name}: ${val === null ? "-" : Number(val).toFixed(4)}`);
        }
        for (const s of eventSharesSeriesCache) {
          const val = readNearestPrice(s.data, tsMs);
          lines.push(`${s.name}: ${val === null ? "-" : Number(val).toFixed(4)}`);
        }
        return lines.join("<br/>");
      },
    },
    xAxis: {
      type: "time",
      name: "时间",
      nameLocation: "middle",
      nameGap: 36,
      axisLabel: {
        hideOverlap: true,
        formatter: (val) => {
          if (!Number.isFinite(val)) return "";
          const s = formatTsMsUtc(val);
          return s.slice(5, 16);
        },
      },
    },
    yAxis: [
      { type: "value", name: "价格", min: 0, max: 1, position: "left", axisLabel: { formatter: (val) => Number(val).toFixed(2) } },
      { type: "value", name: "持仓份额", position: "right", axisLabel: { formatter: (val) => Number(val).toFixed(2) }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      { type: "slider", xAxisIndex: 0, bottom: 20, filterMode: "none" },
    ],
    series: [...pointSeries, ...sharesLineSeries, ...markerSeries],
  }, {
    notMerge: true,
    lazyUpdate: false,
    replaceMerge: ["series", "xAxis", "yAxis", "legend", "dataZoom", "tooltip", "grid"],
  });
}

function syncEventPriceCollapsedUI() {
  const card = eventPriceSection?.querySelector(".chart-card");
  if (card) {
    card.classList.toggle("collapsed", state.eventPriceCollapsed);
  }
  if (eventPriceToggleBtn) {
    eventPriceToggleBtn.textContent = state.eventPriceCollapsed ? "展开图表" : "收起图表";
  }
}

function waitNextPaint() {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(resolve);
    });
  });
}

function clearEventPriceHint(msg) {
  if (eventPriceTitle) eventPriceTitle.textContent = "事件价格历史";
  if (eventPriceMeta) eventPriceMeta.textContent = msg;
  const chart = ensureEventChart();
  if (!chart) return;
  chart.setOption({
    graphic: {
      type: "text",
      left: "center",
      top: "middle",
      style: {
        text: msg || "暂无价格点数据",
        fill: "#857153",
        fontSize: 12,
      },
    },
    grid: { left: 56, right: 56, top: 48, bottom: 72 },
    xAxis: [{ type: "time" }],
    yAxis: [
      { type: "value", min: 0, max: 1, position: "left" },
      { type: "value", position: "right" },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      { type: "slider", xAxisIndex: 0, bottom: 20, filterMode: "none" },
    ],
    series: [],
  }, {
    notMerge: true,
    lazyUpdate: false,
    replaceMerge: ["series", "graphic", "xAxis", "yAxis", "dataZoom", "grid"],
  });
}

async function loadEventPriceChart() {
  if (state.eventPriceCollapsed) {
    return;
  }
  if (!state.user || !state.endpoint || state.endpoint !== "activity") {
    clearEventPriceHint("仅 activity 页面支持");
    return;
  }
  if (!Array.isArray(state.lastRows) || state.lastRows.length === 0) {
    if (
      state.eventPriceRef
      && (state.eventPriceRef.condition_id || state.eventPriceRef.slug)
    ) {
      // Reuse last resolved single-event identity so "刷新CLOB图" can work without reloading table.
    } else {
      clearEventPriceHint("当前筛选无记录，无法判断单一事件");
      return;
    }
  }
  const conditionSet = new Set();
  const slugSet = new Set();
  let conditionId = "";
  let eventSlug = "";
  const tradeMarkers = [];
  for (const row of state.lastRows || []) {
    if (!row || typeof row !== "object") continue;
    const c = String(row.conditionId || "").trim().toLowerCase();
    const s = String(row.eventSlug || row.slug || "").trim().toLowerCase();
    if (c) {
      conditionSet.add(c);
      if (!conditionId) conditionId = c;
    }
    if (s) {
      slugSet.add(s);
      if (!eventSlug) eventSlug = s;
    }
    const side = String(row.side || "").trim().toUpperCase();
    const ts = readRowTs(row);
    const price = toFiniteNumber(row.price) ?? toFiniteNumber(row.avgPrice);
    const size = toFiniteNumber(row.size);
    if ((side === "BUY" || side === "SELL") && ts !== null && price !== null) {
      tradeMarkers.push({
        side,
        ts,
        price,
        size: Number.isFinite(size) ? size : null,
        outcome: String(row.outcome || "").trim(),
        asset: String(row.asset || "").trim(),
      });
    }
  }
  const singleByCondition = conditionSet.size === 1;
  const singleBySlug = slugSet.size === 1;
  if (singleByCondition || singleBySlug) {
    if (!singleByCondition) conditionId = "";
    if (!singleBySlug) eventSlug = "";
    state.eventPriceRef = { condition_id: conditionId, slug: eventSlug };
  } else if (state.eventPriceRef && (state.eventPriceRef.condition_id || state.eventPriceRef.slug)) {
    conditionId = String(state.eventPriceRef.condition_id || "").trim().toLowerCase();
    eventSlug = String(state.eventPriceRef.slug || "").trim().toLowerCase();
  } else {
    clearEventPriceHint("当前页不是单一事件，暂不展示价格图");
    return;
  }

  const maxPoints = getEventPriceMaxPoints();
  const params = new URLSearchParams({ clob_max_points: String(maxPoints) });
  if (conditionId) params.append("condition_id", conditionId);
  if (eventSlug) params.append("event_slug", eventSlug);

  try {
    const data = await fetchJson(`/api/user/${state.user}/event_price_points?${params.toString()}`);
    if (!data || !data.available) {
      if (data && data.reason === "event_identity_conflict") {
        clearEventPriceHint("事件标识冲突：condition_id 与 event_slug 不一致，请重置筛选后重试");
        return;
      }
      clearEventPriceHint("当前单一事件暂无价格历史数据");
      return;
    }
    const event = data.event || {};
    const title = event.title || event.slug || event.condition_id || "单事件";
    state.eventPriceRef = {
      condition_id: String(event.condition_id || conditionId || "").trim().toLowerCase(),
      slug: String(event.slug || eventSlug || "").trim().toLowerCase(),
    };
    if (eventPriceTitle) eventPriceTitle.textContent = `事件价格历史: ${title}`;
    const series = Array.isArray(data.series) ? data.series : [];
    const pointsTotal = series.reduce((acc, item) => {
      const count = Array.isArray(item.points) ? item.points.length : 0;
      return acc + count;
    }, 0);
    const sourceCounter = {};
    for (const item of series) {
      const source = String(item?.source || "unknown").trim().toLowerCase() || "unknown";
      sourceCounter[source] = (sourceCounter[source] || 0) + 1;
    }
    const sourceDesc = Object.entries(sourceCounter)
      .map(([k, v]) => `${k}:${v}`)
      .join(" / ");
    const positionByToken = new Map();
    const conditionTokens = new Map();
    const orderedRows = [...(state.lastRows || [])].sort((a, b) => {
      const ta = readRowTs(a);
      const tb = readRowTs(b);
      return (ta ?? 0) - (tb ?? 0);
    });
    let lastTradeTs = null;
    for (const row of orderedRows) {
      if (!row || typeof row !== "object") continue;
      const rowCondition = String(row.conditionId || "").trim().toLowerCase();
      const rowSlug = String(row.eventSlug || row.slug || "").trim().toLowerCase();
      if (conditionId && rowCondition && rowCondition !== conditionId) continue;
      if (eventSlug && rowSlug && rowSlug !== eventSlug) continue;
      const ts = readRowTs(row);
      if (!Number.isFinite(ts)) continue;
      const actionType = String(row.type || "").trim().toUpperCase();
      const side = String(row.side || "").trim().toUpperCase();
      const tokenId = String(row.asset || "").trim();
      const size = toFiniteNumber(row.size);
      if (actionType === "TRADE" && (side === "BUY" || side === "SELL")) {
        lastTradeTs = lastTradeTs === null ? ts : Math.max(lastTradeTs, ts);
        if (!tokenId || size === null) continue;
        const delta = side === "BUY" ? size : -size;
        if (!positionByToken.has(tokenId)) {
          positionByToken.set(tokenId, { token_id: tokenId, token_alias: tokenId.slice(0, 8), current: 0, points: [] });
        }
        if (rowCondition) {
          if (!conditionTokens.has(rowCondition)) conditionTokens.set(rowCondition, new Set());
          conditionTokens.get(rowCondition).add(tokenId);
        }
        const entry = positionByToken.get(tokenId);
        entry.current += delta;
        entry.points.push({ ts, shares: entry.current });
        continue;
      }
      if (actionType === "REDEEM" && rowCondition) {
        const touched = conditionTokens.get(rowCondition);
        if (!touched) continue;
        for (const t of touched) {
          const entry = positionByToken.get(t);
          if (!entry) continue;
          entry.current = 0;
          entry.points.push({ ts, shares: 0 });
        }
      }
    }
    const sharesCutoffHours = 4;
    const cutoffTs = Number.isFinite(lastTradeTs) ? lastTradeTs + sharesCutoffHours * 3600 : null;
    const positionSeries = Array.from(positionByToken.values()).map((v) => ({
      token_id: v.token_id,
      token_alias: v.token_alias,
      points: (Array.isArray(v.points) ? v.points : [])
        .filter((p) => typeof p?.ts === "number" && typeof p?.shares === "number")
        .filter((p) => (cutoffTs === null ? true : p.ts <= cutoffTs)),
    }));
    if (eventPriceMeta) {
      eventPriceMeta.textContent = `系列 ${series.length} 条(${sourceDesc})，展示点 ${pointsTotal} 个；持仓线 ${positionSeries.length} 条`;
    }
    drawEventPriceSeries(series, tradeMarkers, positionSeries);
  } catch {
    clearEventPriceHint("价格数据加载失败");
  }
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return await res.json();
}

function setLoading(isLoading, text = "加载中...") {
  if (loadingBar) loadingBar.classList.toggle("hidden", !isLoading);
  if (loadingText) loadingText.textContent = text;
  const controls = [
    userSelect, endpointSelect, queryInput, fromTsInput, toTsInput,
    applyBtn, resetBtn, prevBtn, nextBtn, limitSelect, sortSelect,
    showAllBtn, hideAllBtn, clearFiltersBtn, saveConfigBtn,
    configSelect, saveAsBtn, deleteConfigBtn, eventPriceMaxPointsInput, eventPriceApplyBtn,
  ];
  controls.forEach((el) => {
    if (el) el.disabled = isLoading;
  });
}

function clearViewForLoading(message = "加载中...") {
  tableHead.innerHTML = "";
  tableBody.innerHTML = `<tr><td colspan="1">${message}</td></tr>`;
  totalCount.textContent = "-";
  pageInfo.textContent = "-";
  endpointTotal.textContent = "-";
  endpointRange.textContent = "-";
  positionsValue.textContent = "-";
  tradedMarkets.textContent = "-";
  generatedAt.textContent = "-";
  fetchedAt.textContent = "-";
}

function updateSummary(meta) {
  totalCount.textContent = state.total.toString();
  const pageStart = state.offset + 1;
  const pageEnd = Math.min(state.offset + state.limit, state.total);
  pageInfo.textContent = state.total === 0 ? "-" : `${pageStart}-${pageEnd}`;
  generatedAt.textContent = meta && meta.generated_at ? formatTs(meta.generated_at) : "-";
  fetchedAt.textContent = meta && meta.fetched_at ? formatTs(meta.fetched_at) : "-";
}

function updateEndpointSummary(meta) {
  if (!meta) {
    endpointTotal.textContent = "-";
    endpointRange.textContent = "-";
    return;
  }
  const total = meta.total;
  endpointTotal.textContent = total === null || total === undefined ? "-" : total.toString();
  if (meta.min_ts && meta.max_ts) {
    endpointRange.textContent = `${formatTs(meta.min_ts)} ~ ${formatTs(meta.max_ts)}`;
  } else if (meta.min_ts || meta.max_ts) {
    endpointRange.textContent = formatTs(meta.min_ts || meta.max_ts);
  } else {
    endpointRange.textContent = "-";
  }
}

function updateMetrics(metrics) {
  if (!metrics) {
    positionsValue.textContent = "-";
    tradedMarkets.textContent = "-";
    return;
  }
  const value = Array.isArray(metrics.positions_value) && metrics.positions_value.length > 0
    ? metrics.positions_value[0].value
    : metrics.positions_value && metrics.positions_value.value;
  positionsValue.textContent = value === undefined ? "-" : formatNumber(value, 4);

  const traded = metrics.traded_markets && metrics.traded_markets.traded !== undefined
    ? metrics.traded_markets.traded
    : metrics.traded_markets && metrics.traded_markets.traded_markets;
  tradedMarkets.textContent = traded === undefined ? "-" : formatNumber(traded, 0);
}

function formatCellValue(col, val) {
  if (val === null || val === undefined) return "";
  const lowerCol = col.toLowerCase();
  if (typeof val === "number" && (lowerCol.includes("timestamp") || lowerCol.endsWith("at") || lowerCol === "time")) {
    if (val > 1000000000 && val < 2000000000) {
      return formatTs(val);
    }
  }
  if (typeof val === "string" && val.length <= 10 && val.match(/^\d+$/)) {
    const num = parseInt(val, 10);
    if (num > 1000000000 && num < 2000000000) {
      return formatTs(num);
    }
  }
  if (typeof val === "number") {
    return formatNumber(val, 6);
  }
  if (typeof val === "object") {
    return JSON.stringify(val);
  }
  return String(val);
}

function sortRows(rows) {
  // Keep activity ordering fully backend-driven to avoid page-level reordering glitches.
  if (state.endpoint === "activity") return rows;
  if (!state.sortColumn) return rows;
  const col = state.sortColumn;
  const dir = state.sortDirection === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const av = a[col];
    const bv = b[col];
    if (av === undefined || av === null) return 1;
    if (bv === undefined || bv === null) return -1;
    if (col === "timestamp" || col === "createdAt" || col === "created_at" || col === "time") {
      const an = typeof av === "number" ? av : Number(av);
      const bn = typeof bv === "number" ? bv : Number(bv);
      if (!Number.isNaN(an) && !Number.isNaN(bn) && an !== bn) return (an - bn) * dir;
      const atx = String(a.transactionHash || "");
      const btx = String(b.transactionHash || "");
      if (atx < btx) return -1 * dir;
      if (atx > btx) return 1 * dir;
      return 0;
    }
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
    const as = String(av).toLowerCase();
    const bs = String(bv).toLowerCase();
    if (as < bs) return -1 * dir;
    if (as > bs) return 1 * dir;
    return 0;
  });
}


function orderColumns(columns) {
  return [...columns].sort((a, b) => String(a).localeCompare(String(b)));
}

function toNumber(val) {
  if (typeof val === "number" && Number.isFinite(val)) return val;
  if (typeof val === "string" && val.trim() !== "") {
    const n = Number(val);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function normalizeOutcomeIndex(raw) {
  if (typeof raw === "number" && Number.isInteger(raw)) return raw;
  if (typeof raw === "string" && /^[0-9]+$/.test(raw)) return parseInt(raw, 10);
  return null;
}

function formatShares(val) {
  const text = Number(val).toFixed(2).replace(/\.?0+$/, "");
  return text === "-0" ? "0" : text;
}

function parseSharesSummaryText(text) {
  const out = new Map();
  const raw = String(text || "").trim();
  if (!raw) return out;
  const parts = raw.split(",");
  for (const part of parts) {
    const seg = String(part || "").trim();
    if (!seg) continue;
    const idx = seg.indexOf(":");
    if (idx <= 0) continue;
    const label = seg.slice(0, idx).trim().toLowerCase();
    const val = toFiniteNumber(seg.slice(idx + 1).trim());
    if (!label || val === null) continue;
    out.set(label, val);
  }
  return out;
}

function estimateSharesSummaryForPage(rows) {
  const cumulative = new Map();
  const cumulativePosition = new Map();
  const cumulativeCost = new Map();
  const knownOutcomes = new Map();
  const conditionPrefix = (conditionId) => `${conditionId}::`;
  const makeKey = (conditionId, outcomeKey) => `${conditionId}::${outcomeKey}`;
  const labelFromOutcome = (outcome, outcomeIndex) => {
    if (outcome) return outcome;
    if (outcomeIndex !== null && outcomeIndex !== undefined) return `#${outcomeIndex}`;
    return "ALL";
  };
  const outcomeInfoFromRow = (row) => {
    const outcome = String(row.outcome || "").trim();
    let outcomeIndex = normalizeOutcomeIndex(row.outcomeIndex);
    if (outcomeIndex === 999) outcomeIndex = null;
    if (outcomeIndex !== null) {
      const label = labelFromOutcome(outcome, outcomeIndex);
      return { key: `idx:${outcomeIndex}|label:${label}`, label };
    }
    if (outcome) return { key: `name:${outcome}|label:${outcome}`, label: outcome };
    return { key: "all:unknown|label:ALL", label: "ALL" };
  };

  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (!row || typeof row !== "object") continue;
    const conditionId = String(row.conditionId || "").trim();
    if (!conditionId) continue;
    const info = outcomeInfoFromRow(row);
    if (info.key.startsWith("all:unknown")) continue;
    if (!knownOutcomes.has(conditionId)) knownOutcomes.set(conditionId, new Map());
    knownOutcomes.get(conditionId).set(info.key, info.label);
  }

  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (!row || typeof row !== "object") continue;
    row.shares_summary = "";

    const actionType = String(row.type || "").toUpperCase();
    const conditionId = String(row.conditionId || "").trim();
    if (!conditionId) continue;
    const size = toNumber(row.size);
    if (size === null) continue;

    if (actionType === "TRADE") {
      const side = String(row.side || "").toUpperCase();
      const delta = side === "BUY" ? size : side === "SELL" ? -size : 0;
      if (delta !== 0) {
        const outcome = outcomeInfoFromRow(row);
        const key = makeKey(conditionId, outcome.key);
        cumulative.set(key, (cumulative.get(key) || 0) + delta);
        const price = toNumber(row.price);
        if (price !== null) {
          let pos = cumulativePosition.get(key) || 0;
          let cost = cumulativeCost.get(key) || 0;
          if (pos === 0 || (pos > 0 && delta > 0) || (pos < 0 && delta < 0)) {
            pos += delta;
            cost += delta * price;
          } else {
            const absPos = Math.abs(pos);
            const absDelta = Math.abs(delta);
            if (absDelta < absPos) {
              const avg = cost / pos;
              pos += delta;
              cost = avg * pos;
            } else if (absDelta === absPos) {
              pos = 0;
              cost = 0;
            } else {
              const remain = pos + delta;
              pos = remain;
              cost = remain * price;
            }
          }
          cumulativePosition.set(key, pos);
          cumulativeCost.set(key, cost);
        }
      }
    } else if (actionType === "SPLIT" || actionType === "MERGE") {
      const delta = actionType === "SPLIT" ? size : -size;
      const conditionKnown = knownOutcomes.get(conditionId);
      if (conditionKnown && conditionKnown.size > 0) {
        Array.from(conditionKnown.keys()).forEach((outcomeKey) => {
          const key = makeKey(conditionId, outcomeKey);
          const prevPos = cumulativePosition.get(key) || 0;
          const prevCost = cumulativeCost.get(key) || 0;
          const nextPos = prevPos + delta;
          cumulative.set(key, (cumulative.get(key) || 0) + delta);
          if (prevPos === 0) {
            if (nextPos === 0) {
              cumulativePosition.set(key, 0);
              cumulativeCost.set(key, 0);
            } else {
              cumulativePosition.set(key, nextPos);
              // No trade price for split/merge-only position; keep unknown cost at 0.
              cumulativeCost.set(key, 0);
            }
          } else {
            if (nextPos === 0) {
              cumulativePosition.set(key, 0);
              cumulativeCost.set(key, 0);
            } else {
              const avg = prevCost / prevPos;
              cumulativePosition.set(key, nextPos);
              cumulativeCost.set(key, avg * nextPos);
            }
          }
        });
      } else {
        const key = makeKey(conditionId, "all:unknown|label:ALL");
        const prevPos = cumulativePosition.get(key) || 0;
        const prevCost = cumulativeCost.get(key) || 0;
        const nextPos = prevPos + delta;
        cumulative.set(key, (cumulative.get(key) || 0) + delta);
        if (prevPos === 0) {
          cumulativePosition.set(key, nextPos);
          cumulativeCost.set(key, 0);
        } else if (nextPos === 0) {
          cumulativePosition.set(key, 0);
          cumulativeCost.set(key, 0);
        } else {
          const avg = prevCost / prevPos;
          cumulativePosition.set(key, nextPos);
          cumulativeCost.set(key, avg * nextPos);
        }
      }
    } else if (actionType === "REDEEM") {
      const prefix = conditionPrefix(conditionId);
      Array.from(cumulative.keys()).forEach((k) => {
        if (k.startsWith(prefix)) cumulative.set(k, 0);
      });
      Array.from(cumulativePosition.keys()).forEach((k) => {
        if (k.startsWith(prefix)) {
          cumulativePosition.set(k, 0);
          cumulativeCost.set(k, 0);
        }
      });
    } else {
      continue;
    }

    const prefix = conditionPrefix(conditionId);
    const pieces = [];
    const avgPieces = [];
    const conditionKnown = knownOutcomes.get(conditionId) || new Map();
    Array.from(conditionKnown.keys())
      .sort((a, b) => a.localeCompare(b))
      .forEach((outcomeKey) => {
        const v = cumulative.get(makeKey(conditionId, outcomeKey)) || 0;
        const label = conditionKnown.get(outcomeKey) || outcomeKey.split("|label:")[1] || "ALL";
        pieces.push(`${label}:${formatShares(v)}`);
        const key = makeKey(conditionId, outcomeKey);
        const pos = cumulativePosition.get(key) || 0;
        const cost = cumulativeCost.get(key) || 0;
        if (pos !== 0 && cost !== 0) {
          const avg = Math.abs((cumulativeCost.get(key) || 0) / pos);
          avgPieces.push(`${label}:${avg.toFixed(4)}`);
        }
      });
    Array.from(cumulative.entries())
      .filter(([k]) => k.startsWith(prefix))
      .sort((a, b) => a[0].localeCompare(b[0]))
      .forEach(([k, v]) => {
        const outcomeKey = k.slice(prefix.length);
        if (conditionKnown.has(outcomeKey)) return;
        const label = outcomeKey.split("|label:")[1] || "ALL";
        pieces.push(`${label}:${formatShares(v)}`);
        const pos = cumulativePosition.get(k) || 0;
        const cost = cumulativeCost.get(k) || 0;
        if (pos !== 0 && cost !== 0) {
          const avg = Math.abs((cumulativeCost.get(k) || 0) / pos);
          avgPieces.push(`${label}:${avg.toFixed(4)}`);
        }
      });
    row.shares_summary = pieces.join(", ");
    row.shares_summary_avg = avgPieces.length > 0 ? `均价 ${avgPieces.join(", ")}` : "";
  }
}

function buildTable(rows, columnsOverride) {
  tableHead.innerHTML = "";
  tableBody.innerHTML = "";

  if (!rows || rows.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="1">无数据</td></tr>`;
    return;
  }

  const allColumns = columnsOverride && columnsOverride.length > 0
    ? columnsOverride
    : Object.keys(rows[0]);

  if (state.visibleColumns.size === 0 && state.forceAllColumns) {
    allColumns.forEach((col) => state.visibleColumns.add(col));
    state.forceAllColumns = false;
  }

  const order = state.columnOrder.length > 0 ? state.columnOrder : orderColumns(allColumns);
  const columns = order.filter((col) => allColumns.includes(col) && state.visibleColumns.has(col));
  const displayColumns = ["#"].concat(columns);
  const canClientSort = state.endpoint !== "activity";
  for (const col of displayColumns) {
    const th = document.createElement("th");
    th.textContent = col;
    th.className = col === "#" ? "index-col" : (canClientSort ? "sortable" : "");
    if (col !== "#" && state.columnWidths[col]) {
      th.style.width = `${state.columnWidths[col]}px`;
    }
    if (state.sortColumn === col) {
      th.dataset.sort = state.sortDirection;
    }
    if (col !== "#" && canClientSort) th.addEventListener("click", () => {
      if (state.sortColumn === col) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortColumn = col;
        state.sortDirection = "asc";
      }
      buildTable(state.lastRows, state.lastColumns);
      markConfigDirty();
    });
    if (col !== "#") {
      const resizer = document.createElement("span");
      resizer.className = "col-resizer";
      resizer.addEventListener("mousedown", (e) => startResize(e, th, col));
      th.appendChild(resizer);
    }
    tableHead.appendChild(th);
  }
  enableHeaderDrag();

  const sortedRows = sortRows(rows);
  for (let i = 0; i < sortedRows.length; i += 1) {
    const row = sortedRows[i];
    const tr = document.createElement("tr");
    const idxTd = document.createElement("td");
    idxTd.className = "index-col";
    idxTd.textContent = (state.offset + i + 1).toString();
    tr.appendChild(idxTd);
    for (const col of columns) {
      const td = document.createElement("td");
      const val = row[col];
      const lowerCol = col.toLowerCase();
      if (typeof val === "string" && val.startsWith("http") && (lowerCol.includes("icon") || lowerCol.includes("image"))) {
        const img = document.createElement("img");
        img.src = val;
        img.alt = col;
        img.className = "thumb";
        td.appendChild(img);
      } else if (col === "shares_summary") {
        const main = document.createElement("div");
        main.textContent = formatCellValue(col, val);
        td.appendChild(main);
        const avgText = row.shares_summary_avg || "";
        if (avgText) {
          const sub = document.createElement("div");
          sub.className = "shares-summary-sub";
          sub.textContent = avgText;
          td.appendChild(sub);
        }
      } else {
        td.textContent = formatCellValue(col, val);
      }
      tr.appendChild(td);
    }
    tableBody.appendChild(tr);
  }
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function storageKey() {
  if (!state.user || !state.endpoint) return null;
  return `pm_columns_${state.user}_${state.endpoint}`;
}

async function persistColumnState() {
  if (!state.user || !state.endpoint) return;
  if (state.activeConfig === "默认") {
    state.activeConfig = "自定义";
    refreshConfigSelect();
  }
  const payload = {
    name: state.activeConfig,
    visible: Array.from(state.visibleColumns),
    filters: state.columnFilters,
    sortColumn: state.sortColumn,
    sortDirection: state.sortDirection,
    columnOrder: state.columnOrder,
    columnWidths: state.columnWidths,
    savedAt: Date.now(),
  };
  state.configs[state.activeConfig] = payload;
  await fetchJson(`/api/user/${state.user}/configs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: state.endpoint,
      active: state.activeConfig,
      config: payload,
    }),
  });
  if (savedHint) {
    savedHint.textContent = `已保存 ${new Date(payload.savedAt).toLocaleString()}`;
  }
}

function markConfigDirty() {
  if (savedHint) {
    savedHint.textContent = state.activeConfig === "默认" ? "未保存（已偏离默认）" : "未保存";
  }
}

function loadColumnState() {
  const configs = state.configs || {};
  try {
    if (state.activeConfig === "默认") {
      state.visibleColumns = new Set();
      state.columnFilters = {};
      state.sortColumn = "";
      state.sortDirection = "asc";
      state.columnOrder = [];
      state.columnWidths = {};
      state.forceAllColumns = true;
      if (savedHint) savedHint.textContent = "默认配置";
      return;
    }
    const payload = configs[state.activeConfig];
    if (!payload) return;
    if (payload.visible && payload.visible.length > 0) {
      state.visibleColumns = new Set(payload.visible);
      state.forceAllColumns = false;
    } else {
      state.visibleColumns = new Set();
      state.forceAllColumns = true;
    }
    if (payload.filters) state.columnFilters = payload.filters;
    if (payload.sortColumn) state.sortColumn = payload.sortColumn;
    if (payload.sortDirection) state.sortDirection = payload.sortDirection;
    if (payload.columnOrder) state.columnOrder = payload.columnOrder;
    if (payload.columnWidths) state.columnWidths = payload.columnWidths;
    if (savedHint && payload.savedAt) {
      savedHint.textContent = `已保存 ${new Date(payload.savedAt).toLocaleString()}`;
    }
  } catch {
    return;
  }
}

function renderColumnControls(columns) {
  columnGrid.innerHTML = "";
  const applyFilter = debounce(async (col, value) => {
    state.columnFilters[col] = value.trim();
    state.offset = 0;
    await loadRecords();
    markConfigDirty();
  }, 300);
  const ordered = state.columnOrder.length > 0
    ? state.columnOrder.filter((col) => columns.includes(col))
    : columns;
  ordered.forEach((col) => {
    const item = document.createElement("div");
    item.className = "column-item";
    item.dataset.col = col;

    const dragHandle = document.createElement("span");
    dragHandle.className = "drag-handle";
    dragHandle.title = "拖动排序";
    dragHandle.textContent = "⋮⋮";
    dragHandle.draggable = true;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.visibleColumns.has(col);
    checkbox.addEventListener("change", async () => {
      if (checkbox.checked) {
        state.visibleColumns.add(col);
      } else {
        state.visibleColumns.delete(col);
      }
      buildTable(state.lastRows, state.lastColumns);
      markConfigDirty();
    });

    const label = document.createElement("label");
    label.className = "column-label";
    label.textContent = col;

    const filter = document.createElement("input");
    filter.type = "text";
    filter.className = "column-filter";
    filter.placeholder = "筛选（逗号=或）";
    filter.value = state.columnFilters[col] || "";
    filter.addEventListener("input", () => {
      applyFilter(col, filter.value);
    });

    item.appendChild(dragHandle);
    item.appendChild(checkbox);
    item.appendChild(label);
    item.appendChild(filter);
    columnGrid.appendChild(item);
  });

  enableDragAndDrop();
}

async function loadUsers() {
  const data = await fetchJson("/api/users");
  userSelect.innerHTML = "";
  data.users.forEach((entry) => {
    const opt = document.createElement("option");
    opt.value = entry.id;
    opt.textContent = entry.label ? `${entry.id} (${entry.label})` : entry.id;
    userSelect.appendChild(opt);
  });
  if (data.users.length > 0) {
    state.user = data.users[0].id;
    userSelect.value = state.user;
  }
}

async function loadEndpoints() {
  if (!state.user) return;
  const data = await fetchJson(`/api/user/${state.user}/endpoints`);
  endpointSelect.innerHTML = "";
  data.endpoints.forEach((ep) => {
    const opt = document.createElement("option");
    opt.value = ep;
    opt.textContent = ep;
    endpointSelect.appendChild(opt);
  });
  if (data.endpoints.length > 0) {
    state.endpoint = data.endpoints[0];
    endpointSelect.value = state.endpoint;
  }
}

async function loadSummary() {
  if (!state.user) return;
  const data = await fetchJson(`/api/user/${state.user}/summary`);
  updateSummary(data);
}

async function loadMetrics() {
  if (!state.user) return;
  const data = await fetchJson(`/api/user/${state.user}/metrics`);
  updateMetrics(data);
}

async function loadEndpointSummary() {
  if (!state.user || !state.endpoint) return;
  const data = await fetchJson(`/api/user/${state.user}/endpoint_summary?endpoint=${state.endpoint}`);
  updateEndpointSummary(data);
}

async function loadRecords() {
  if (!state.user || !state.endpoint) return;
  setLoading(true, `加载 ${state.endpoint} 数据中...`);
  try {
    const params = new URLSearchParams({
      endpoint: state.endpoint,
      limit: state.limit.toString(),
      offset: state.offset.toString(),
      view: state.view,
      sort: state.sort,
    });
    if (state.query) params.append("query", state.query);
    if (state.fromTs) params.append("from_ts", state.fromTs);
    if (state.toTs) params.append("to_ts", state.toTs);
    const activeFilters = Object.entries(state.columnFilters)
      .filter(([, val]) => val)
      .reduce((acc, [key, val]) => {
        acc[key] = val;
        return acc;
      }, {});
    if (Object.keys(activeFilters).length > 0) {
      params.append("filters", JSON.stringify(activeFilters));
    }

    const data = await fetchJson(`/api/user/${state.user}/records?${params.toString()}`);
    state.total = data.total || 0;
    state.lastRows = data.rows || [];
    if (state.endpoint === "activity") {
      estimateSharesSummaryForPage(state.lastRows);
    }
    const baseColumns = (data.all_columns && data.all_columns.length > 0)
      ? data.all_columns
      : (data.columns && data.columns.length > 0)
        ? data.columns
        : Object.keys((state.lastRows[0] || {}));
    if (state.endpoint === "activity" && !baseColumns.includes("shares_summary")) {
      state.lastColumns = [...baseColumns, "shares_summary"];
    } else {
      state.lastColumns = baseColumns;
    }
    let columnsUpdated = false;
    if (state.visibleColumns.size === 0 || state.forceAllColumns) {
      state.visibleColumns = new Set(state.lastColumns);
      state.forceAllColumns = false;
      columnsUpdated = true;
    }
    state.lastColumnsKey = state.lastColumns.join("|");
    if (state.columnOrder.length === 0) {
      state.columnOrder = orderColumns(state.lastColumns);
      columnsUpdated = true;
    } else {
      const existing = new Set(state.columnOrder);
      for (const col of state.lastColumns) {
        if (!existing.has(col)) {
          state.columnOrder.push(col);
          existing.add(col);
          columnsUpdated = true;
        }
      }
    }
    buildTable(state.lastRows, state.lastColumns);
    await loadEventPriceChart();
    renderColumnControls(state.lastColumns);
    columnGrid.dataset.columnsKey = state.lastColumnsKey;
    await loadSummary();
    await loadEndpointSummary();
  } finally {
    setLoading(false);
  }
}

function resetFilters() {
  queryInput.value = "";
  fromTsInput.value = "";
  toTsInput.value = "";
  state.query = "";
  state.fromTs = "";
  state.toTs = "";
  state.offset = 0;
  state.eventPriceRef = null;
  clearEventPriceHint("请筛选到单一事件后查看价格点");
}

applyBtn.addEventListener("click", async () => {
  state.query = queryInput.value.trim();
  state.fromTs = fromTsInput.value.trim();
  state.toTs = toTsInput.value.trim();
  state.offset = 0;
  clearViewForLoading("筛选中...");
  await loadRecords();
});

resetBtn.addEventListener("click", async () => {
  resetFilters();
  clearViewForLoading("重置并加载中...");
  await loadRecords();
});

if (eventPriceApplyBtn) {
  eventPriceApplyBtn.addEventListener("click", async () => {
    if (state.eventPriceCollapsed) return;
    getEventPriceMaxPoints();
    await reloadEventChartCanvasData();
  });
}

if (eventPriceMaxPointsInput) {
  eventPriceMaxPointsInput.addEventListener("change", async () => {
    if (state.eventPriceCollapsed) return;
    getEventPriceMaxPoints();
    await reloadEventChartCanvasData();
  });
}

if (eventPriceClearBtn) {
  eventPriceClearBtn.addEventListener("click", () => {
    disposeEventChart();
    if (eventPriceChart) eventPriceChart.innerHTML = "";
    if (eventPriceMeta) eventPriceMeta.textContent = "画布已清除，可点击“重新加载画布数据”";
  });
}

if (eventPriceToggleBtn) {
  eventPriceToggleBtn.addEventListener("click", async () => {
    state.eventPriceCollapsed = !state.eventPriceCollapsed;
    syncEventPriceCollapsedUI();
    if (!state.eventPriceCollapsed) {
      await waitNextPaint();
      if (eventPriceChartInstance) eventPriceChartInstance.resize();
      await loadEventPriceChart();
      if (eventPriceChartInstance) eventPriceChartInstance.resize();
    }
  });
}

prevBtn.addEventListener("click", async () => {
  state.offset = Math.max(0, state.offset - state.limit);
  clearViewForLoading("分页加载中...");
  await loadRecords();
});

nextBtn.addEventListener("click", async () => {
  if (state.offset + state.limit < state.total) {
    state.offset += state.limit;
    clearViewForLoading("分页加载中...");
    await loadRecords();
  }
});

limitSelect.addEventListener("change", async (e) => {
  state.limit = parseInt(e.target.value, 10);
  state.offset = 0;
  clearViewForLoading("更新分页中...");
  await loadRecords();
});

sortSelect.addEventListener("change", async (e) => {
  state.sort = e.target.value;
  state.offset = 0;
  clearViewForLoading("排序中...");
  await loadRecords();
});

userSelect.addEventListener("change", async (e) => {
  snapshotCurrentViewState();
  const carryLayout = captureLayoutState();
  state.user = e.target.value;
  state.offset = 0;
  state.visibleColumns = new Set(carryLayout.visibleColumns || []);
  state.forceAllColumns = !!carryLayout.forceAllColumns;
  state.columnFilters = { ...(carryLayout.columnFilters || {}) };
  state.sortColumn = carryLayout.sortColumn || "";
  state.sortDirection = carryLayout.sortDirection || "asc";
  state.columnOrder = [...(carryLayout.columnOrder || [])];
  state.columnWidths = { ...(carryLayout.columnWidths || {}) };
  state.lastRows = [];
  state.lastColumns = [];
  state.lastColumnsKey = "";
  state.eventPriceRef = null;
  tableHead.innerHTML = "";
  columnGrid.innerHTML = "";
  columnGrid.dataset.columnsKey = "";
  clearViewForLoading("用户切换中...");
  await loadEndpoints();
  await loadMetrics();
  await loadSummary();
  restoreViewStateForCurrentTarget();
  refreshConfigSelect();
  applyLayoutState(carryLayout);
  await loadRecords();
});

endpointSelect.addEventListener("change", async (e) => {
  snapshotCurrentViewState();
  state.endpoint = e.target.value;
  state.offset = 0;
  state.visibleColumns = new Set();
  state.forceAllColumns = true;
  state.columnFilters = {};
  state.sortColumn = "";
  state.sortDirection = "asc";
  state.lastRows = [];
  state.lastColumns = [];
  state.lastColumnsKey = "";
  state.eventPriceRef = null;
  tableHead.innerHTML = "";
  columnGrid.innerHTML = "";
  columnGrid.dataset.columnsKey = "";
  clearViewForLoading("端点切换中...");
  await loadConfigs();
  restoreViewStateForCurrentTarget();
  await loadRecords();
});


showAllBtn.addEventListener("click", async () => {
  state.visibleColumns = new Set(state.lastColumns);
  state.forceAllColumns = false;
  buildTable(state.lastRows, state.lastColumns);
  renderColumnControls(state.lastColumns);
  columnGrid.dataset.columnsKey = state.lastColumnsKey;
  markConfigDirty();
});

hideAllBtn.addEventListener("click", async () => {
  state.visibleColumns = new Set();
  state.forceAllColumns = false;
  buildTable(state.lastRows, state.lastColumns);
  renderColumnControls(state.lastColumns);
  columnGrid.dataset.columnsKey = state.lastColumnsKey;
  markConfigDirty();
});

clearFiltersBtn.addEventListener("click", async () => {
  state.columnFilters = {};
  clearViewForLoading("清除筛选中...");
  await loadRecords();
  markConfigDirty();
});

saveConfigBtn.addEventListener("click", async () => {
  await persistColumnState();
});

function refreshConfigSelect() {
  const configs = state.configs || {};
  configSelect.innerHTML = "";
  const names = Object.keys(configs);
  if (!names.includes("默认")) names.unshift("默认");
  if (!names.includes(state.activeConfig)) names.push(state.activeConfig);
  names.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    configSelect.appendChild(opt);
  });
  configSelect.value = state.activeConfig;
}

configSelect.addEventListener("change", async (e) => {
  state.activeConfig = e.target.value;
  loadColumnState();
  clearViewForLoading("应用配置中...");
  await loadRecords();
});

saveAsBtn.addEventListener("click", async () => {
  const name = window.prompt("请输入配置名称");
  if (!name) return;
  state.activeConfig = name;
  await persistColumnState();
  refreshConfigSelect();
});

deleteConfigBtn.addEventListener("click", async () => {
  if (!state.configs) return;
  const name = state.activeConfig;
  delete state.configs[name];
  state.activeConfig = "默认";
  await fetchJson(`/api/user/${state.user}/configs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: state.endpoint,
      action: "delete",
      name,
      active: state.activeConfig,
      config: {},
    }),
  });
  refreshConfigSelect();
  loadColumnState();
});

async function loadConfigs() {
  if (!state.user || !state.endpoint) return;
  const data = await fetchJson(`/api/user/${state.user}/configs?endpoint=${state.endpoint}`);
  state.columnOrder = [];
  state.visibleColumns = new Set();
  state.forceAllColumns = true;
  state.columnWidths = {};
  state.columnFilters = {};
  const memoryKey = viewMemoryKey(state.user, state.endpoint);
  const remembered = memoryKey ? state.pageStateMemory[memoryKey] : null;
  const rememberedActive = remembered && remembered.activeConfig ? remembered.activeConfig : "";
  state.configs = data.configs || {};
  if (rememberedActive && state.configs[rememberedActive]) {
    state.activeConfig = rememberedActive;
  } else {
    state.activeConfig = data.active || "默认";
  }
  refreshConfigSelect();
  loadColumnState();
}


function enableDragAndDrop() {
  const items = Array.from(columnGrid.querySelectorAll(".column-item"));
  let dragged = null;
  items.forEach((item) => {
    const handle = item.querySelector(".drag-handle");
    handle.addEventListener("dragstart", (e) => {
      dragged = item;
      item.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });
    handle.addEventListener("dragend", () => {
      item.classList.remove("dragging");
      dragged = null;
    });
    item.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
    });
    item.addEventListener("drop", (e) => {
      e.preventDefault();
      if (!dragged || dragged === item) return;
      const all = Array.from(columnGrid.children);
      const draggedIndex = all.indexOf(dragged);
      const targetIndex = all.indexOf(item);
      if (draggedIndex < targetIndex) {
        columnGrid.insertBefore(dragged, item.nextSibling);
      } else {
        columnGrid.insertBefore(dragged, item);
      }
      const newOrder = Array.from(columnGrid.querySelectorAll(".column-item")).map(
        (el) => el.dataset.col
      );
      state.columnOrder = newOrder;
      buildTable(state.lastRows, state.lastColumns);
      markConfigDirty();
    });
  });
}

function enableHeaderDrag() {
  const headers = Array.from(tableHead.querySelectorAll("th"));
  headers.forEach((th) => {
    if (th.textContent === "#") return;
    th.draggable = true;
    th.addEventListener("dragstart", () => {
      state.headerDrag.source = th.textContent;
      th.classList.add("dragging");
    });
    th.addEventListener("dragend", () => {
      th.classList.remove("dragging");
      state.headerDrag.source = null;
    });
    th.addEventListener("dragover", (e) => {
      e.preventDefault();
    });
    th.addEventListener("drop", (e) => {
      e.preventDefault();
      const source = state.headerDrag.source;
      const target = th.textContent;
      if (!source || source === target) return;
      const order = [...state.columnOrder];
      const from = order.indexOf(source);
      const to = order.indexOf(target);
      if (from === -1 || to === -1) return;
      order.splice(to, 0, order.splice(from, 1)[0]);
      state.columnOrder = order;
      buildTable(state.lastRows, state.lastColumns);
      markConfigDirty();
    });
  });
}

function startResize(e, th, col) {
  e.preventDefault();
  const startX = e.pageX;
  const startWidth = th.offsetWidth;
  function onMove(ev) {
    const newWidth = Math.max(60, startWidth + (ev.pageX - startX));
    th.style.width = `${newWidth}px`;
    state.columnWidths[col] = newWidth;
  }
  function onUp() {
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    markConfigDirty();
  }
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}

(async function init() {
  syncEventPriceCollapsedUI();
  window.addEventListener("resize", () => {
    if (eventPriceChartInstance) eventPriceChartInstance.resize();
  });
  await loadUsers();
  await loadEndpoints();
  await loadMetrics();
  await loadSummary();
  await loadConfigs();
  resetFilters();
  await loadRecords();
})();
