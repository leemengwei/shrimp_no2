const fileSelect = document.getElementById("file-select");
const loadBtn = document.getElementById("load-btn");
const clearBtn = document.getElementById("clear-btn");
const exportBtn = document.getElementById("export-btn");
const statusEl = document.getElementById("status");
const tableInfo = document.getElementById("table-info");
const recordsBody = document.getElementById("records-body");

const statScanned = document.getElementById("stat-scanned");
const statMatched = document.getElementById("stat-matched");
const statShown = document.getElementById("stat-shown");

const sumSizeEl = document.getElementById("sum-size");
const sumNotionalEl = document.getElementById("sum-notional");
const avgPriceEl = document.getElementById("avg-price");
const countActionEl = document.getElementById("count-action");
const countSideEl = document.getElementById("count-side");
const netOutcomeEl = document.getElementById("net-outcome");

const inputAction = document.getElementById("filter-action");
const inputSide = document.getElementById("filter-side");
const inputOutcome = document.getElementById("filter-outcome");
const inputType = document.getElementById("filter-type");
const inputMarket = document.getElementById("filter-market");
const inputQuery = document.getElementById("filter-q");
const inputStart = document.getElementById("filter-start");
const inputEnd = document.getElementById("filter-end");
const inputLimit = document.getElementById("filter-limit");
const inputFast = document.getElementById("filter-fast");
const inputCumA = document.getElementById("cum-outcome-a");
const inputCumB = document.getElementById("cum-outcome-b");
const cumHeaderA = document.getElementById("cum-header-a");
const cumHeaderB = document.getElementById("cum-header-b");

let currentRecords = [];

const formatNumber = (value) => {
  if (Number.isNaN(value) || value === null || value === undefined) return "-";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(value);
};

const formatCurrency = (value) => {
  if (Number.isNaN(value) || value === null || value === undefined) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
};

const splitNumberParts = (value) => {
  if (Number.isNaN(value) || value === null || value === undefined) return null;
  const text = String(value);
  const [intPart, fracPart] = text.split(".");
  return { intPart, fracPart };
};

const appendMutedNumber = (cell, value) => {
  const parts = splitNumberParts(value);
  if (!parts) {
    cell.textContent = "-";
    return;
  }
  const intSpan = document.createElement("span");
  intSpan.textContent = parts.intPart;
  cell.appendChild(intSpan);
  if (parts.fracPart !== undefined) {
    const fracSpan = document.createElement("span");
    fracSpan.className = "num-frac";
    fracSpan.textContent = `.${parts.fracPart}`;
    cell.appendChild(fracSpan);
  }
};

const cleanFloat = (value, precision = 12) => {
  if (Number.isNaN(value) || value === null || value === undefined) return value;
  const num = Number(value);
  if (!Number.isFinite(num)) return value;
  return Number(num.toPrecision(precision));
};

const normalizeText = (value) => String(value || "").trim().toUpperCase();

const safeNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

const getCumTargets = () => {
  const rawA = String(inputCumA?.value || "").trim();
  const rawB = String(inputCumB?.value || "").trim();
  const labelA = rawA || "Outcome A";
  const labelB = rawB || "Outcome B";
  return {
    labelA,
    labelB,
    normA: normalizeText(rawA || labelA),
    normB: normalizeText(rawB || labelB),
  };
};

const updateCumHeaders = () => {
  const { labelA, labelB } = getCumTargets();
  if (cumHeaderA) cumHeaderA.textContent = `Cum Size (${labelA})`;
  if (cumHeaderB) cumHeaderB.textContent = `Cum Size (${labelB})`;
};

const sideMultiplier = (side) => {
  const normalized = String(side || "").toUpperCase();
  if (normalized === "SELL") return -1;
  if (normalized === "BUY") return 1;
  return 1;
};

const sideClass = (side) => {
  const normalized = String(side || "").toUpperCase();
  if (normalized === "BUY") return "side-buy";
  if (normalized === "SELL") return "side-sell";
  return "";
};

const setStatus = (text) => {
  statusEl.textContent = text;
};

const listCountItems = (counts, target, formatter = (value) => value) => {
  target.innerHTML = "";
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    const li = document.createElement("li");
    li.textContent = "-";
    target.appendChild(li);
    return;
  }
  entries.forEach(([label, count]) => {
    const li = document.createElement("li");
    li.textContent = `${label}: ${formatter(count)}`;
    target.appendChild(li);
  });
};

const updateStats = (records, totals) => {
  statScanned.textContent = totals.totalScanned ?? "-";
  statMatched.textContent = totals.totalMatched ?? "-";
  statShown.textContent = records.length;

  const summary = totals.summary || {};
  sumSizeEl.textContent = formatNumber(summary.totalSizeSigned ?? 0);
  sumNotionalEl.textContent = formatCurrency(summary.totalNotionalSigned ?? 0);
  avgPriceEl.textContent = formatNumber(summary.avgPrice ?? 0);

  listCountItems(summary.counts?.action || {}, countActionEl);
  listCountItems(summary.counts?.side || {}, countSideEl);
  listCountItems(summary.netByOutcome || {}, netOutcomeEl, formatNumber);
};

const renderTable = (records) => {
  recordsBody.innerHTML = "";
  if (!records.length) {
    tableInfo.textContent = "No data.";
    return;
  }

  tableInfo.textContent = `Showing ${records.length} records.`;
  const fragment = document.createDocumentFragment();
  const { normA, normB } = getCumTargets();
  let runningA = 0;
  let runningB = 0;

  records.forEach((record) => {
    const row = document.createElement("tr");
    const sizeValue = safeNumber(record.size ?? 0);
    const signedSize = sizeValue * sideMultiplier(record.side);
    const outcome = normalizeText(record.outcome);
    const action = normalizeText(record.action);
    if (!Number.isNaN(signedSize)) {
      if (action === "MERGE") {
        runningA = cleanFloat(runningA - sizeValue);
        runningB = cleanFloat(runningB - sizeValue);
      } else if (normA && outcome === normA) {
        runningA = cleanFloat(runningA + signedSize);
      } else if (normB && outcome === normB) {
        runningB = cleanFloat(runningB + signedSize);
      }
    }
    const cells = [
      record.eventTimeLocal ?? "-",
      record.market ?? "-",
      record.side ?? "-",
      record.outcome ?? "-",
      formatNumber(record.price),
      formatNumber(record.size),
      record.action ?? "-",
      record.type ?? "-",
    ];
    cells.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });

    const cumYesCell = document.createElement("td");
    cumYesCell.classList.add("cum-cell", "cum-yes");
    appendMutedNumber(cumYesCell, cleanFloat(runningA));
    row.appendChild(cumYesCell);

    const cumNoCell = document.createElement("td");
    cumNoCell.classList.add("cum-cell", "cum-no");
    appendMutedNumber(cumNoCell, cleanFloat(runningB));
    row.appendChild(cumNoCell);

    const sideCell = row.children[2];
    if (sideCell) {
      const klass = sideClass(record.side);
      if (klass) sideCell.classList.add(klass);
    }
    fragment.appendChild(row);
  });

  recordsBody.appendChild(fragment);
};

const fetchFiles = async () => {
  const response = await fetch("/api/files");
  const payload = await response.json();
  fileSelect.innerHTML = "";
  payload.files.forEach((name, index) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (index === 0) option.selected = true;
    fileSelect.appendChild(option);
  });
};

const buildQuery = () => {
  const params = new URLSearchParams();
  if (fileSelect.value) params.set("file", fileSelect.value);

  if (inputAction.value.trim()) params.set("action", inputAction.value.trim());
  if (inputSide.value.trim()) params.set("side", inputSide.value.trim());
  if (inputOutcome.value.trim()) params.set("outcome", inputOutcome.value.trim());
  if (inputType.value.trim()) params.set("type", inputType.value.trim());
  if (inputMarket.value.trim()) params.set("market", inputMarket.value.trim());
  if (inputQuery.value.trim()) params.set("q", inputQuery.value.trim());

  if (inputStart.value) params.set("start", inputStart.value);
  if (inputEnd.value) params.set("end", inputEnd.value);

  const limit = Number(inputLimit.value || 0);
  if (limit) params.set("limit", String(limit));
  if (inputFast.checked) params.set("fast", "1");

  return params.toString();
};

const loadRecords = async () => {
  setStatus("Loading...");
  const query = buildQuery();
  const response = await fetch(`/api/records?${query}`);
  const payload = await response.json();

  currentRecords = payload.records || [];
  updateStats(currentRecords, payload);
  renderTable(currentRecords);
  if (payload.truncated) {
    setStatus("Loaded (quick mode, partial stats).");
  } else {
    setStatus("Loaded.");
  }
};

const clearFilters = () => {
  inputAction.value = "";
  inputSide.value = "";
  inputOutcome.value = "";
  inputType.value = "";
  inputMarket.value = "";
  inputQuery.value = "";
  inputStart.value = "";
  inputEnd.value = "";
  inputLimit.value = "5000";
  inputFast.checked = true;
  if (inputCumA) inputCumA.value = "Yes";
  if (inputCumB) inputCumB.value = "No";
  updateCumHeaders();
};

const exportCsv = () => {
  if (!currentRecords.length) return;
  const { labelA, labelB, normA, normB } = getCumTargets();
  const headerA = `cumSize_${labelA.replaceAll(" ", "_")}`;
  const headerB = `cumSize_${labelB.replaceAll(" ", "_")}`;
  const headers = [
    "eventTimeLocal",
    "market",
    "side",
    "outcome",
    "price",
    "size",
    "action",
    "type",
    headerA,
    headerB,
  ];
  const rows = [headers.join(",")];
  let runningA = 0;
  let runningB = 0;
  currentRecords.forEach((record) => {
    const sizeValue = safeNumber(record.size ?? 0);
    const signedSize = sizeValue * sideMultiplier(record.side);
    const outcome = normalizeText(record.outcome);
    const action = normalizeText(record.action);
    if (!Number.isNaN(signedSize)) {
      if (action === "MERGE") {
        runningA = cleanFloat(runningA - sizeValue);
        runningB = cleanFloat(runningB - sizeValue);
      } else if (normA && outcome === normA) {
        runningA = cleanFloat(runningA + signedSize);
      } else if (normB && outcome === normB) {
        runningB = cleanFloat(runningB + signedSize);
      }
    }
    const row = [
      record.eventTimeLocal ?? "",
      record.market ?? "",
      record.side ?? "",
      record.outcome ?? "",
      record.price ?? "",
      record.size ?? "",
      record.action ?? "",
      record.type ?? "",
      Number.isNaN(runningA) ? "" : String(cleanFloat(runningA)),
      Number.isNaN(runningB) ? "" : String(cleanFloat(runningB)),
    ]
      .map((value) => `"${String(value).replaceAll('"', '""')}"`)
      .join(",");
    rows.push(row);
  });
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "trail_records.csv";
  link.click();
  URL.revokeObjectURL(url);
};

loadBtn.addEventListener("click", loadRecords);
clearBtn.addEventListener("click", () => {
  clearFilters();
  setStatus("Filters cleared.");
});
exportBtn.addEventListener("click", exportCsv);

if (inputCumA) inputCumA.addEventListener("input", updateCumHeaders);
if (inputCumB) inputCumB.addEventListener("input", updateCumHeaders);

fetchFiles().catch(() => {
  setStatus("Failed to load file list.");
});

updateCumHeaders();
