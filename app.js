const state = {
  problems: [],
  current: null,
  latestReview: null,
  conversation: [],
  busy: false,
  progress: JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}"),
  drafts: JSON.parse(localStorage.getItem("aibag_code_drafts_v1") || "{}"),
};

const elements = {
  catalog: document.querySelector("#catalog-view"),
  problemView: document.querySelector("#problem-view"),
  problemList: document.querySelector("#problem-list"),
  problemCount: document.querySelector("#problem-count"),
  categoryFilter: document.querySelector("#category-filter"),
  difficultyFilter: document.querySelector("#difficulty-filter"),
  search: document.querySelector("#problem-search"),
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
  back: document.querySelector("#back-button"),
  number: document.querySelector("#problem-number"),
  category: document.querySelector("#problem-category"),
  title: document.querySelector("#problem-title"),
  difficulty: document.querySelector("#problem-difficulty"),
  language: document.querySelector("#problem-language"),
  description: document.querySelector("#problem-description"),
  examples: document.querySelector("#problem-examples"),
  constraints: document.querySelector("#problem-constraints"),
  tags: document.querySelector("#problem-tags"),
  sources: document.querySelector("#problem-sources"),
  editor: document.querySelector("#code-editor"),
  lineNumbers: document.querySelector("#line-numbers"),
  draftStatus: document.querySelector("#draft-status"),
  reset: document.querySelector("#reset-code"),
  submit: document.querySelector("#submit-code"),
  coachLog: document.querySelector("#coach-log"),
  reviewState: document.querySelector("#review-state"),
  coachInput: document.querySelector("#coach-input"),
  sendCoach: document.querySelector("#send-coach"),
  quickActions: document.querySelector(".coach-quick-actions"),
};

async function request(endpoint, options = {}) {
  const response = await fetch(endpoint, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({ error: "后端返回了无法解析的结果" }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function difficultyClass(level) {
  return String(level || "").toLowerCase();
}

function filteredProblems() {
  const category = elements.categoryFilter.value;
  const difficulty = elements.difficultyFilter.value;
  const query = elements.search.value.trim().toLowerCase();
  return state.problems.filter((problem) => {
    const haystack = `${problem.title} ${problem.category} ${(problem.tags || []).join(" ")}`.toLowerCase();
    return (!category || problem.category === category)
      && (!difficulty || problem.difficulty === difficulty)
      && (!query || haystack.includes(query));
  });
}

function renderCatalog() {
  elements.problemList.replaceChildren();
  const problems = filteredProblems();
  if (!problems.length) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "没有符合当前筛选条件的题目。";
    row.appendChild(cell);
    elements.problemList.appendChild(row);
    return;
  }

  problems.forEach((problem) => {
    const row = document.createElement("tr");
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
    link.href = `#/problem/${encodeURIComponent(problem.id)}`;
    const title = document.createElement("strong");
    title.textContent = `${String(problem.number).padStart(2, "0")}. ${problem.title}`;
    const summary = document.createElement("span");
    summary.textContent = problem.summary;
    link.append(title, summary);
    titleCell.appendChild(link);

    const categoryCell = document.createElement("td");
    categoryCell.className = "track-label";
    categoryCell.textContent = problem.category;

    const difficultyCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `difficulty ${difficultyClass(problem.difficulty)}`;
    badge.textContent = problem.difficulty;
    difficultyCell.appendChild(badge);

    const actionCell = document.createElement("td");
    actionCell.className = "row-arrow";
    actionCell.textContent = "→";
    row.append(statusCell, titleCell, categoryCell, difficultyCell, actionCell);
    row.addEventListener("click", (event) => {
      if (!event.target.closest("a")) window.location.hash = `#/problem/${problem.id}`;
    });
    elements.problemList.appendChild(row);
  });
}

function appendDefinition(list, term, description) {
  const dt = document.createElement("dt");
  dt.textContent = term;
  const dd = document.createElement("dd");
  dd.textContent = description;
  list.append(dt, dd);
}

function renderProblem(problem) {
  state.current = problem;
  state.latestReview = null;
  state.conversation = [];
  elements.catalog.hidden = true;
  elements.problemView.hidden = false;
  document.title = `${problem.title} · AIBaG`;

  elements.number.textContent = String(problem.number).padStart(2, "0");
  elements.category.textContent = problem.category.toUpperCase();
  elements.title.textContent = problem.title;
  elements.difficulty.textContent = problem.difficulty;
  elements.difficulty.className = `difficulty-pill difficulty ${difficultyClass(problem.difficulty)}`;
  elements.language.textContent = problem.language;
  elements.description.textContent = problem.description;

  elements.examples.replaceChildren();
  (problem.examples || []).forEach((example, index) => {
    const card = document.createElement("div");
    card.className = "example-card";
    const list = document.createElement("dl");
    appendDefinition(list, `Input ${index + 1}`, example.input);
    appendDefinition(list, "Output", example.output);
    appendDefinition(list, "Notes", example.explanation);
    card.appendChild(list);
    elements.examples.appendChild(card);
  });

  elements.constraints.replaceChildren();
  (problem.constraints || []).forEach((constraint) => {
    const item = document.createElement("li");
    item.textContent = constraint;
    elements.constraints.appendChild(item);
  });

  elements.tags.replaceChildren();
  (problem.tags || []).forEach((tagName) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = tagName;
    elements.tags.appendChild(tag);
  });

  elements.sources.replaceChildren();
  (problem.sources || []).forEach((source) => {
    const card = document.createElement("div");
    card.className = "source-card";
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.title;
    const note = document.createElement("p");
    note.textContent = `${source.license} · ${source.note}`;
    card.append(link, note);
    elements.sources.appendChild(card);
  });

  elements.editor.value = state.drafts[problem.id] ?? problem.starter_code;
  updateLineNumbers();
  clearCoach();
  elements.editor.focus();
  document.querySelector(".problem-document").scrollTop = 0;
  document.querySelector(".coding-panel").scrollTop = 0;
}

function showCatalog() {
  state.current = null;
  elements.problemView.hidden = true;
  elements.catalog.hidden = false;
  document.title = "AIBaG · Algorithm Interview Lab";
  renderCatalog();
  window.scrollTo({ top: 0, behavior: "auto" });
}

function route() {
  const match = window.location.hash.match(/^#\/problem\/([^/]+)$/);
  if (!match) {
    showCatalog();
    return;
  }
  const problem = state.problems.find((item) => item.id === decodeURIComponent(match[1]));
  if (!problem) {
    window.location.hash = "#/problems";
    return;
  }
  renderProblem(problem);
}

function updateLineNumbers() {
  const count = Math.max(1, elements.editor.value.split("\n").length);
  elements.lineNumbers.textContent = Array.from({ length: count }, (_, index) => index + 1).join("\n");
  elements.lineNumbers.scrollTop = elements.editor.scrollTop;
}

let saveTimer;
function scheduleDraftSave() {
  clearTimeout(saveTimer);
  elements.draftStatus.textContent = "保存中…";
  saveTimer = setTimeout(() => {
    if (!state.current) return;
    state.drafts[state.current.id] = elements.editor.value;
    localStorage.setItem("aibag_code_drafts_v1", JSON.stringify(state.drafts));
    elements.draftStatus.textContent = "已保存到本机";
  }, 350);
}

function clearCoach() {
  elements.coachLog.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "coach-empty";
  empty.textContent = "提交代码后，这里只展示最关键的实现反馈。你也可以先请求一层提示。";
  elements.coachLog.appendChild(empty);
  elements.reviewState.textContent = "WAITING";
  elements.reviewState.className = "review-state";
  elements.coachInput.value = "";
}

function ensureCoachLog() {
  elements.coachLog.querySelector(".coach-empty")?.remove();
}

function appendCoachMessage(label, message, className = "") {
  ensureCoachLog();
  const block = document.createElement("div");
  block.className = `coach-message ${className}`.trim();
  const heading = document.createElement("strong");
  heading.textContent = label;
  const body = document.createElement("p");
  body.textContent = message;
  block.append(heading, body);
  elements.coachLog.appendChild(block);
  elements.coachLog.scrollTop = elements.coachLog.scrollHeight;
  return block;
}

function appendList(parent, title, items) {
  if (!items?.length) return;
  const heading = document.createElement("strong");
  heading.textContent = title;
  const list = document.createElement("ul");
  items.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  });
  parent.append(heading, list);
}

function renderReview(review) {
  ensureCoachLog();
  const block = document.createElement("div");
  block.className = "review-summary";
  const score = document.createElement("span");
  score.className = "score";
  score.textContent = `${review.score}/100`;
  const heading = document.createElement("h3");
  heading.textContent = review.summary;
  block.append(score, heading);
  appendList(block, "已经实现", review.covered);
  appendList(block, "关键缺口", review.key_gaps);
  appendList(block, "需要纠正", review.incorrect_points);
  if (review.next_focus) {
    const next = document.createElement("p");
    next.textContent = `下一步：${review.next_focus}`;
    block.appendChild(next);
  }
  if (review.interviewer_follow_up) {
    const followUp = document.createElement("p");
    followUp.textContent = `追问：${review.interviewer_follow_up}`;
    block.appendChild(followUp);
  }
  elements.coachLog.appendChild(block);
  elements.reviewState.textContent = review.verdict.toUpperCase();
  elements.reviewState.className = `review-state ${review.verdict}`;
  elements.coachLog.scrollTop = elements.coachLog.scrollHeight;
}

function setBusy(busy) {
  state.busy = busy;
  elements.submit.disabled = busy;
  elements.sendCoach.disabled = busy;
  elements.quickActions.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
}

function showRequestError(error) {
  appendCoachMessage("REQUEST ERROR", error.message || String(error), "error-message");
  elements.reviewState.textContent = "ERROR";
  elements.reviewState.className = "review-state retry";
}

async function submitCode() {
  if (!state.current || state.busy) return;
  const code = elements.editor.value.trim();
  if (!code) {
    elements.editor.focus();
    return;
  }
  setBusy(true);
  const pending = appendCoachMessage("DEEPSEEK", "正在检查核心实现…");
  try {
    const review = await request("/api/judge", {
      method: "POST",
      body: JSON.stringify({ problem_id: state.current.id, code }),
    });
    pending.remove();
    state.latestReview = review;
    state.progress[state.current.id] = {
      verdict: review.verdict,
      score: review.score,
      attempts: (state.progress[state.current.id]?.attempts || 0) + 1,
    };
    localStorage.setItem("aibag_code_progress_v1", JSON.stringify(state.progress));
    renderReview(review);
  } catch (error) {
    pending.remove();
    showRequestError(error);
  } finally {
    setBusy(false);
  }
}

async function sendCoach(action = "chat") {
  if (!state.current || state.busy) return;
  const message = action === "chat" ? elements.coachInput.value.trim() : "";
  if (action === "chat" && !message) {
    elements.coachInput.focus();
    return;
  }
  const labels = {
    hint: "给我一点提示。",
    optimize: "这份代码最应该优化哪里？",
    follow_up: "请像面试官一样继续追问。",
    chat: message,
  };
  const shownMessage = labels[action];
  appendCoachMessage("YOU", shownMessage);
  state.conversation.push({ role: "user", content: shownMessage });
  elements.coachInput.value = "";
  setBusy(true);
  const pending = appendCoachMessage("DEEPSEEK", "正在思考…");
  try {
    const result = await request("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        problem_id: state.current.id,
        action,
        message,
        code: elements.editor.value,
        review: state.latestReview,
        history: state.conversation,
      }),
    });
    pending.remove();
    const reply = result.focus ? `${result.reply}\n\n思考方向：${result.focus}` : result.reply;
    appendCoachMessage("INTERVIEWER", reply);
    state.conversation.push({ role: "assistant", content: result.reply });
  } catch (error) {
    pending.remove();
    showRequestError(error);
  } finally {
    setBusy(false);
  }
}

async function initialize() {
  elements.problemList.innerHTML = '<tr class="loading-row"><td colspan="5">正在读取 JSON 题库…</td></tr>';
  try {
    const [problems, config] = await Promise.all([request("/api/problems"), request("/api/config")]);
    state.problems = problems;
    elements.problemCount.textContent = String(problems.length).padStart(2, "0");
    [...new Set(problems.map((problem) => problem.category))].sort().forEach((category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = category;
      elements.categoryFilter.appendChild(option);
    });
    const provider = new URL(config.base_url).host;
    elements.apiStatus.textContent = `${config.model} · ${provider}`;
    elements.apiDot.className = config.has_api_key ? "status-dot ok" : "status-dot warn";
    if (!config.has_api_key) elements.apiStatus.textContent += " · key missing";
    renderCatalog();
    route();
  } catch (error) {
    elements.apiDot.className = "status-dot error";
    elements.apiStatus.textContent = "本地后端不可用";
    elements.problemList.replaceChildren();
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = error.message;
    row.appendChild(cell);
    elements.problemList.appendChild(row);
  }
}

elements.categoryFilter.addEventListener("change", renderCatalog);
elements.difficultyFilter.addEventListener("change", renderCatalog);
elements.search.addEventListener("input", renderCatalog);
elements.back.addEventListener("click", () => { window.location.hash = "#/problems"; });
elements.editor.addEventListener("input", () => { updateLineNumbers(); scheduleDraftSave(); });
elements.editor.addEventListener("scroll", () => { elements.lineNumbers.scrollTop = elements.editor.scrollTop; });
elements.editor.addEventListener("keydown", (event) => {
  if (event.key !== "Tab") return;
  event.preventDefault();
  const start = elements.editor.selectionStart;
  const end = elements.editor.selectionEnd;
  elements.editor.setRangeText("    ", start, end, "end");
  updateLineNumbers();
  scheduleDraftSave();
});
elements.reset.addEventListener("click", () => {
  if (!state.current || !window.confirm("将当前草稿恢复为初始模板？")) return;
  elements.editor.value = state.current.starter_code;
  delete state.drafts[state.current.id];
  localStorage.setItem("aibag_code_drafts_v1", JSON.stringify(state.drafts));
  elements.draftStatus.textContent = "已恢复模板";
  updateLineNumbers();
});
elements.submit.addEventListener("click", submitCode);
elements.quickActions.addEventListener("click", (event) => {
  const action = event.target.closest("button")?.dataset.action;
  if (action) sendCoach(action);
});
elements.sendCoach.addEventListener("click", () => sendCoach("chat"));
elements.coachInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendCoach("chat");
  }
});
window.addEventListener("hashchange", route);

initialize();
