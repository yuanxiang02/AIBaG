const state = {
  problems: [],
  progress: JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}"),
};

const elements = {
  list: document.querySelector("#completed-list"),
  count: document.querySelector("#completed-count"),
  passCount: document.querySelector("#completed-pass"),
  avgScore: document.querySelector("#completed-avg"),
  filteredSummary: document.querySelector("#completed-filtered-summary"),
  kindFilter: document.querySelector("#completed-kind-filter"),
  verdictFilter: document.querySelector("#completed-verdict-filter"),
  search: document.querySelector("#completed-search"),
  exportBtn: document.querySelector("#export-progress"),
  clearBtn: document.querySelector("#clear-progress"),
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
};

async function request(endpoint) {
  const response = await fetch(endpoint);
  const data = await response.json().catch(() => ({ error: "后端返回了无法解析的结果" }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function direction(problem) {
  const base = { coding: "AI Infra", knowledge: "简答八股", algorithm: "力扣手撕" }[problem.kind] || problem.category;
  return problem.is_custom ? `${base} · 自建` : base;
}

function renderEmpty(message) {
  elements.list.replaceChildren();
  const row = document.createElement("tr");
  row.className = "empty-row";
  const cell = document.createElement("td");
  cell.colSpan = 5;
  cell.textContent = message;
  row.appendChild(cell);
  elements.list.appendChild(row);
}

function render() {
  const query = elements.search.value.trim().toLowerCase();
  const kindVal = elements.kindFilter?.value || "";
  const verdictVal = elements.verdictFilter?.value || "";
  const completed = state.problems.filter((problem) => state.progress[problem.id]);

  elements.count.textContent = String(completed.length);
  const passItems = completed.filter((p) => state.progress[p.id]?.verdict === "pass");
  if (elements.passCount) elements.passCount.textContent = String(passItems.length);
  if (elements.avgScore) {
    const totalScore = completed.reduce((acc, p) => acc + (Number(state.progress[p.id]?.score) || 0), 0);
    elements.avgScore.textContent = completed.length ? String(Math.round(totalScore / completed.length)) : "0";
  }

  const visible = completed.filter((problem) => {
    const rec = state.progress[problem.id];
    if (kindVal === "custom") {
      if (!problem.is_custom) return false;
    } else if (kindVal && problem.kind !== kindVal) {
      return false;
    }
    if (verdictVal && rec?.verdict !== verdictVal) return false;
    if (!query) return true;
    return `${problem.number} ${problem.title} ${problem.topic} ${(problem.tags || []).join(" ")}`
      .toLowerCase()
      .includes(query);
  });

  if (elements.filteredSummary) {
    elements.filteredSummary.textContent = `当前筛选共 ${visible.length} 条记录`;
  }

  if (!visible.length) {
    renderEmpty(completed.length ? "没有符合筛选条件的记录。" : "还没有做过的题，先去题库练一道吧。");
    return;
  }
  elements.list.replaceChildren();
  visible.forEach((problem) => {
    const progress = state.progress[problem.id];
    const row = document.createElement("tr");
    const destination = `/problem.html?id=${encodeURIComponent(problem.id)}`;
    const statusCell = document.createElement("td");
    statusCell.className = "status-col";
    const dot = document.createElement("span");
    dot.className = `completion-dot ${progress.verdict || ""}`;
    statusCell.appendChild(dot);
    const titleCell = document.createElement("td");
    const link = document.createElement("a");
    link.className = "problem-link";
    link.href = destination;
    const title = document.createElement("strong");
    title.textContent = `${String(problem.number).padStart(2, "0")}. ${problem.title}`;
    if (problem.is_custom) {
      const badge = document.createElement("span");
      badge.className = "custom-pill";
      badge.textContent = "自建";
      title.appendChild(badge);
    }
    const summary = document.createElement("span");
    summary.textContent = problem.summary;
    link.append(title, summary);
    titleCell.appendChild(link);
    const directionCell = document.createElement("td");
    directionCell.className = "track-label";
    directionCell.textContent = direction(problem);
    const recordCell = document.createElement("td");
    recordCell.className = "track-label";
    const verdict = { pass: "方向没问题", partial: "还差一点", retry: "需要重试" }[progress.verdict] || "已提交";
    recordCell.textContent = `${verdict} · ${progress.score ?? 0} 分 · ${progress.attempts || 1} 次`;
    const arrowCell = document.createElement("td");
    arrowCell.className = "row-arrow";
    arrowCell.textContent = "→";
    row.append(statusCell, titleCell, directionCell, recordCell, arrowCell);
    row.addEventListener("click", (event) => {
      if (!event.target.closest("a")) window.location.assign(destination);
    });
    elements.list.appendChild(row);
  });
}

async function initialize() {
  try {
    const [problems, config] = await Promise.all([request("/api/problems"), request("/api/config")]);
    state.problems = problems;
    const provider = new URL(config.base_url).host;
    elements.apiStatus.textContent = `${config.model} · ${provider}`;
    elements.apiDot.className = config.has_api_key ? "status-dot ok" : "status-dot warn";
    render();
  } catch (error) {
    elements.apiDot.className = "status-dot error";
    elements.apiStatus.textContent = "本地后端不可用";
    renderEmpty(error.message);
  }
}

elements.search.addEventListener("input", render);
elements.kindFilter?.addEventListener("change", render);
elements.verdictFilter?.addEventListener("change", render);
elements.exportBtn?.addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(state.progress, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aibag-practice-progress.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
});
elements.clearBtn?.addEventListener("click", () => {
  if (!Object.keys(state.progress).length) return;
  if (!window.confirm("确定清空当前浏览器的全部练习记录吗？此操作不可撤销。")) return;
  state.progress = {};
  localStorage.removeItem("aibag_code_progress_v1");
  render();
});

window.addEventListener("pageshow", () => {
  state.progress = JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}");
  if (state.problems.length) render();
});

initialize();
