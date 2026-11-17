const state = {
  problem: null,
  latestReview: null,
  conversation: [],
  busy: false,
  progress: JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}"),
  drafts: JSON.parse(localStorage.getItem("aibag_code_drafts_v1") || "{}"),
};

const elements = {
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
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

function appendDefinition(list, term, description) {
  const dt = document.createElement("dt");
  dt.textContent = term;
  const dd = document.createElement("dd");
  dd.textContent = description;
  list.append(dt, dd);
}

function renderProblem(problem) {
  state.problem = problem;
  document.title = `${problem.title} · AIBaG`;
  elements.number.textContent = String(problem.number).padStart(2, "0");
  elements.category.textContent = problem.category.toUpperCase();
  elements.title.textContent = problem.title;
  elements.difficulty.textContent = problem.difficulty;
  elements.difficulty.className = `difficulty-pill difficulty ${problem.difficulty.toLowerCase()}`;
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
  elements.editor.focus();
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
    if (!state.problem) return;
    state.drafts[state.problem.id] = elements.editor.value;
    localStorage.setItem("aibag_code_drafts_v1", JSON.stringify(state.drafts));
    elements.draftStatus.textContent = "已保存到本机";
  }, 350);
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

function renderReview(review) {
  appendCoachMessage("面试官", review.interviewer_response, "interviewer-turn");
  if (review.nudge) appendCoachMessage("给你一个小方向", review.nudge, "nudge-turn");
  if (review.follow_up) appendCoachMessage("接着聊一个问题", review.follow_up, "follow-up-turn");
  const labels = { pass: "方向没问题", partial: "再补一点", retry: "先调一下思路" };
  elements.reviewState.textContent = labels[review.verdict] || "看过了";
  elements.reviewState.className = `review-state ${review.verdict}`;
}

function setBusy(busy) {
  state.busy = busy;
  elements.submit.disabled = busy;
  elements.sendCoach.disabled = busy;
  elements.quickActions.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
}

function showRequestError(error) {
  appendCoachMessage("连接出了点问题", error.message || String(error), "error-message");
  elements.reviewState.textContent = "暂时没连上";
  elements.reviewState.className = "review-state retry";
}

async function submitCode() {
  if (!state.problem || state.busy) return;
  const code = elements.editor.value.trim();
  if (!code) {
    elements.editor.focus();
    return;
  }
  setBusy(true);
  const pending = appendCoachMessage("面试官", "我先看一下你的核心实现…", "pending-turn");
  try {
    const review = await request("/api/judge", {
      method: "POST",
      body: JSON.stringify({ problem_id: state.problem.id, code }),
    });
    pending.remove();
    state.latestReview = review;
    state.progress[state.problem.id] = {
      verdict: review.verdict,
      score: review.score,
      attempts: (state.progress[state.problem.id]?.attempts || 0) + 1,
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
  if (!state.problem || state.busy) return;
  const message = action === "chat" ? elements.coachInput.value.trim() : "";
  if (action === "chat" && !message) {
    elements.coachInput.focus();
    return;
  }
  const labels = {
    hint: "给我一点提示。",
    optimize: "这块还能怎么改？",
    follow_up: "你继续问我吧。",
    chat: message,
  };
  appendCoachMessage("我", labels[action], "user-turn");
  state.conversation.push({ role: "user", content: labels[action] });
  elements.coachInput.value = "";
  setBusy(true);
  const pending = appendCoachMessage("面试官", "嗯，我看一下…", "pending-turn");
  try {
    const result = await request("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        problem_id: state.problem.id,
        action,
        message,
        code: elements.editor.value,
        review: state.latestReview,
        history: state.conversation,
      }),
    });
    pending.remove();
    appendCoachMessage("面试官", result.reply, "interviewer-turn");
    state.conversation.push({ role: "assistant", content: result.reply });
  } catch (error) {
    pending.remove();
    showRequestError(error);
  } finally {
    setBusy(false);
  }
}

async function initialize() {
  const problemId = new URLSearchParams(window.location.search).get("id");
  if (!problemId) {
    window.location.replace("/");
    return;
  }
  try {
    const [problems, config] = await Promise.all([request("/api/problems"), request("/api/config")]);
    const problem = problems.find((item) => item.id === problemId);
    if (!problem) {
      window.location.replace("/");
      return;
    }
    const provider = new URL(config.base_url).host;
    elements.apiStatus.textContent = `${config.model} · ${provider}`;
    elements.apiDot.className = config.has_api_key ? "status-dot ok" : "status-dot warn";
    if (!config.has_api_key) elements.apiStatus.textContent += " · key missing";
    renderProblem(problem);
  } catch (error) {
    elements.apiDot.className = "status-dot error";
    elements.apiStatus.textContent = "本地后端不可用";
    showRequestError(error);
  }
}

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
  if (!state.problem || !window.confirm("将当前草稿恢复为初始模板？")) return;
  elements.editor.value = state.problem.starter_code;
  delete state.drafts[state.problem.id];
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

initialize();
