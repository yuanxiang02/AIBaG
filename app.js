const state = {
  problems: [],
  activeKind: "",
  progress: JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}"),
};

const elements = {
  list: document.querySelector("#problem-list"),
  count: document.querySelector("#problem-count"),
  trackTabs: document.querySelector(".track-tabs"),
  trackTitle: document.querySelector("#track-title"),
  search: document.querySelector("#problem-search"),
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
};

async function request(endpoint) {
  const response = await fetch(endpoint);
  const data = await response.json().catch(() => ({ error: "后端返回了无法解析的结果" }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function filteredProblems() {
  const query = elements.search.value.trim().toLowerCase();
  return state.problems.filter((problem) => {
    const text = `${problem.title} ${problem.category} ${(problem.tags || []).join(" ")}`.toLowerCase();
    return (!state.activeKind || problem.kind === state.activeKind)
      && (!query || text.includes(query));
  });
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

function renderProblems() {
  const problems = filteredProblems();
  if (!problems.length) {
    renderEmpty("没有符合当前筛选条件的题目。");
    return;
  }
  elements.list.replaceChildren();
  problems.forEach((problem) => {
    const row = document.createElement("tr");
    const destination = `/problem.html?id=${encodeURIComponent(problem.id)}`;

    const statusCell = document.createElement("td");
    statusCell.className = "status-col";
    const dot = document.createElement("span");
    dot.className = `completion-dot ${state.progress[problem.id]?.verdict || ""}`;
    dot.title = state.progress[problem.id]
      ? `${state.progress[problem.id].verdict} · ${state.progress[problem.id].score} 分`
      : "尚未提交";
    statusCell.appendChild(dot);

    const titleCell = document.createElement("td");
    const link = document.createElement("a");
    link.className = "problem-link";
    link.href = destination;
    const title = document.createElement("strong");
    title.textContent = `${String(problem.number).padStart(2, "0")}. ${problem.title}`;
    const summary = document.createElement("span");
    summary.textContent = problem.summary;
    link.append(title, summary);
    titleCell.appendChild(link);

    const categoryCell = document.createElement("td");
    categoryCell.className = "track-label";
    categoryCell.textContent = {
      coding: "AI Infra",
      knowledge: "简答八股",
      algorithm: "力扣手撕",
    }[problem.kind] || problem.category;
    const difficultyCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `difficulty ${problem.difficulty.toLowerCase()}`;
    badge.textContent = problem.difficulty;
    difficultyCell.appendChild(badge);
    const actionCell = document.createElement("td");
    actionCell.className = "row-arrow";
    actionCell.textContent = "→";
    row.append(statusCell, titleCell, categoryCell, difficultyCell, actionCell);
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
    elements.count.textContent = String(problems.length).padStart(2, "0");
    const provider = new URL(config.base_url).host;
    elements.apiStatus.textContent = `${config.model} · ${provider}`;
    elements.apiDot.className = config.has_api_key ? "status-dot ok" : "status-dot warn";
    if (!config.has_api_key) elements.apiStatus.textContent += " · key missing";
    renderProblems();
  } catch (error) {
    elements.apiDot.className = "status-dot error";
    elements.apiStatus.textContent = "本地后端不可用";
    renderEmpty(error.message);
  }
}

elements.trackTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-kind]");
  if (!button) return;
  state.activeKind = button.dataset.kind;
  elements.trackTabs.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
  elements.trackTitle.textContent = button.textContent === "全部" ? "全部题目" : button.textContent;
  renderProblems();
});
elements.search.addEventListener("input", renderProblems);
window.addEventListener("pageshow", () => {
  state.progress = JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}");
  if (state.problems.length) renderProblems();
});

initialize();
