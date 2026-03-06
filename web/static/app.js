const state = {
  user: null,
  endpoint: null,
  limit: 500,
  offset: 0,
  total: 0,
  query: "",
  fromTs: "",
  toTs: "",
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

function formatTs(ts) {
  if (!ts) return "-";
  const dt = new Date(ts * 1000);
  return dt.toISOString().replace("T", " ").slice(0, 19);
}

function formatNumber(val, digits = 2) {
  if (val === null || val === undefined || Number.isNaN(val)) return "-";
  return Number(val).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return await res.json();
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
  if (!state.sortColumn) return rows;
  const col = state.sortColumn;
  const dir = state.sortDirection === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const av = a[col];
    const bv = b[col];
    if (av === undefined || av === null) return 1;
    if (bv === undefined || bv === null) return -1;
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
    const as = String(av).toLowerCase();
    const bs = String(bv).toLowerCase();
    if (as < bs) return -1 * dir;
    if (as > bs) return 1 * dir;
    return 0;
  });
}


function orderColumns(columns) {
  const preferred = [
    "timestamp",
    "createdAt",
    "created_at",
    "time",
    "type",
    "action",
    "title",
    "market",
    "slug",
    "eventSlug",
    "eventId",
    "conditionId",
    "outcome",
    "outcomeIndex",
    "side",
    "price",
    "avgPrice",
    "size",
    "usdcSize",
    "value",
    "initialValue",
    "currentValue",
    "cashPnl",
    "pnl",
    "percentPnl",
    "realizedPnl",
    "percentRealizedPnl",
    "resolvedAt",
  ];
  const seen = new Set();
  const ordered = [];
  preferred.forEach((key) => {
    if (columns.includes(key)) {
      ordered.push(key);
      seen.add(key);
    }
  });
  columns.forEach((key) => {
    if (!seen.has(key)) ordered.push(key);
  });
  return ordered;
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
  for (const col of displayColumns) {
    const th = document.createElement("th");
    th.textContent = col;
    th.className = col === "#" ? "index-col" : "sortable";
    if (col !== "#" && state.columnWidths[col]) {
      th.style.width = `${state.columnWidths[col]}px`;
    }
    if (state.sortColumn === col) {
      th.dataset.sort = state.sortDirection;
    }
    if (col !== "#") th.addEventListener("click", () => {
      if (state.sortColumn === col) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortColumn = col;
        state.sortDirection = "asc";
      }
      buildTable(state.lastRows, state.lastColumns);
      persistColumnState();
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

function loadColumnState() {
  const configs = state.configs || {};
  try {
    const payload = configs[state.activeConfig] || configs["默认"];
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
    persistColumnState();
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
      persistColumnState();
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
  const baseColumns = (data.all_columns && data.all_columns.length > 0)
    ? data.all_columns
    : (data.columns && data.columns.length > 0)
      ? data.columns
      : Object.keys((state.lastRows[0] || {}));
  state.lastColumns = baseColumns;
  let columnsUpdated = false;
  if (state.visibleColumns.size === 0 || state.forceAllColumns) {
    state.visibleColumns = new Set(state.lastColumns);
    state.forceAllColumns = false;
    columnsUpdated = true;
  } else {
    for (const col of state.lastColumns) {
      if (col.startsWith("shares_")) {
        if (!state.visibleColumns.has(col)) {
          state.visibleColumns.add(col);
          columnsUpdated = true;
        }
      }
    }
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
  if (columnsUpdated) {
    persistColumnState();
  }
  buildTable(state.lastRows, state.lastColumns);
  if (columnGrid.dataset.columnsKey !== state.lastColumnsKey) {
    renderColumnControls(state.lastColumns);
    columnGrid.dataset.columnsKey = state.lastColumnsKey;
  }
  await loadSummary();
  await loadEndpointSummary();
}

function resetFilters() {
  queryInput.value = "";
  fromTsInput.value = "";
  toTsInput.value = "";
  state.query = "";
  state.fromTs = "";
  state.toTs = "";
  state.offset = 0;
}

applyBtn.addEventListener("click", async () => {
  state.query = queryInput.value.trim();
  state.fromTs = fromTsInput.value.trim();
  state.toTs = toTsInput.value.trim();
  state.offset = 0;
  await loadRecords();
});

resetBtn.addEventListener("click", async () => {
  resetFilters();
  await loadRecords();
});

prevBtn.addEventListener("click", async () => {
  state.offset = Math.max(0, state.offset - state.limit);
  await loadRecords();
});

nextBtn.addEventListener("click", async () => {
  if (state.offset + state.limit < state.total) {
    state.offset += state.limit;
    await loadRecords();
  }
});

limitSelect.addEventListener("change", async (e) => {
  state.limit = parseInt(e.target.value, 10);
  state.offset = 0;
  await loadRecords();
});

sortSelect.addEventListener("change", async (e) => {
  state.sort = e.target.value;
  state.offset = 0;
  await loadRecords();
});

userSelect.addEventListener("change", async (e) => {
  state.user = e.target.value;
  state.offset = 0;
  state.visibleColumns = new Set();
  state.forceAllColumns = true;
  state.columnFilters = {};
  state.sortColumn = "";
  state.sortDirection = "asc";
  await loadEndpoints();
  await loadMetrics();
  await loadSummary();
  await loadConfigs();
  await loadRecords();
});

endpointSelect.addEventListener("change", async (e) => {
  state.endpoint = e.target.value;
  state.offset = 0;
  state.visibleColumns = new Set();
  state.forceAllColumns = true;
  state.columnFilters = {};
  state.sortColumn = "";
  state.sortDirection = "asc";
  await loadConfigs();
  await loadRecords();
});


showAllBtn.addEventListener("click", async () => {
  state.visibleColumns = new Set(state.lastColumns);
  state.forceAllColumns = false;
  buildTable(state.lastRows, state.lastColumns);
  persistColumnState();
});

hideAllBtn.addEventListener("click", async () => {
  state.visibleColumns = new Set();
  state.forceAllColumns = false;
  buildTable(state.lastRows, state.lastColumns);
  persistColumnState();
});

clearFiltersBtn.addEventListener("click", async () => {
  state.columnFilters = {};
  await loadRecords();
  persistColumnState();
});

saveConfigBtn.addEventListener("click", () => {
  persistColumnState();
});

function refreshConfigSelect() {
  const configs = state.configs || {};
  configSelect.innerHTML = "";
  const names = Object.keys(configs);
  if (!names.includes("默认")) names.unshift("默认");
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
  await loadRecords();
});

saveAsBtn.addEventListener("click", () => {
  const name = window.prompt("请输入配置名称");
  if (!name) return;
  state.activeConfig = name;
  persistColumnState();
  refreshConfigSelect();
});

deleteConfigBtn.addEventListener("click", () => {
  if (!state.configs) return;
  const name = state.activeConfig;
  delete state.configs[name];
  state.activeConfig = "默认";
  fetchJson(`/api/user/${state.user}/configs`, {
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
  state.activeConfig = data.active || "默认";
  state.configs = data.configs || {};
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
      persistColumnState();
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
      persistColumnState();
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
    persistColumnState();
  }
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}

(async function init() {
  await loadUsers();
  await loadEndpoints();
  await loadMetrics();
  await loadSummary();
  await loadConfigs();
  resetFilters();
  await loadRecords();
})();
