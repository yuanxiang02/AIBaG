const state = {
  problem: null,
  latestReview: null,
  conversation: [],
  busy: false,
  chromeAutoCollapsed: false,
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
  documentLabel: document.querySelector("#document-label"),
  modeNoteTitle: document.querySelector("#mode-note-title"),
  modeNoteText: document.querySelector("#mode-note-text"),
  answerFilename: document.querySelector("#answer-filename"),
  editor: document.querySelector("#code-editor"),
  lineNumbers: document.querySelector("#line-numbers"),
  draftStatus: document.querySelector("#draft-status"),
  reset: document.querySelector("#reset-code"),
  showAnswer: document.querySelector("#show-answer"),
  closeAnswer: document.querySelector("#close-answer"),
  referenceAnswer: document.querySelector("#reference-answer"),
  referenceAnswerContent: document.querySelector("#reference-answer-content"),
  submit: document.querySelector("#submit-code"),
  submitNote: document.querySelector("#submit-note"),
  coachLog: document.querySelector("#coach-log"),
  reviewState: document.querySelector("#review-state"),
  coachInput: document.querySelector("#coach-input"),
  sendCoach: document.querySelector("#send-coach"),
  quickActions: document.querySelector(".coach-quick-actions"),
  coachEmpty: document.querySelector("#coach-empty"),
  optimizeAction: document.querySelector("#optimize-action"),
  followUpAction: document.querySelector("#follow-up-action"),
  collapseChrome: document.querySelector("#collapse-chrome"),
  expandChrome: document.querySelector("#expand-chrome"),
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
  const isKnowledge = problem.kind === "knowledge";
  document.body.classList.toggle("knowledge-problem", isKnowledge);
  document.title = `${problem.title} · AIBaG`;
  elements.number.textContent = String(problem.number).padStart(2, "0");
  elements.category.textContent = problem.category.toUpperCase();
  elements.title.textContent = problem.title;
  elements.difficulty.textContent = problem.difficulty;
  elements.difficulty.className = `difficulty-pill difficulty ${problem.difficulty.toLowerCase()}`;
  elements.language.textContent = problem.language;
  elements.description.textContent = problem.description;
  elements.documentLabel.textContent = isKnowledge ? "INTERVIEW QUESTION" : "PROBLEM STATEMENT";
  elements.modeNoteTitle.textContent = isKnowledge ? "ORAL INTERVIEW MODE" : "WHITEBOARD MODE";
  elements.modeNoteText.textContent = isKnowledge
    ? "不用背标准答案。请用自己的话讲清核心概念、原因和边界；口语化表达完全可以。"
    : "不能运行代码、不能 print、不能使用 debugger。请直接推导 shape、边界条件和算法不变量。";
  elements.answerFilename.textContent = isKnowledge ? "answer.txt" : "solution.py";
  elements.editor.setAttribute("aria-label", isKnowledge ? "口头回答草稿" : "代码编辑器");
  elements.editor.placeholder = isKnowledge ? "用自己的话写下核心回答…" : "";
  elements.submitNote.textContent = isKnowledge
    ? "面试口述模式：讲清核心即可，不要求标准答案腔。"
    : "白板模式：只做静态推理，不运行代码。";
  elements.submit.textContent = isKnowledge ? "请面试官听一下" : "请面试官看一下";
  elements.reset.textContent = isKnowledge ? "清空" : "重置";
  elements.showAnswer.textContent = isKnowledge ? "查看标准回答" : "查看标准答案";
  elements.optimizeAction.textContent = isKnowledge ? "反问我一下" : "这块还能怎么改？";
  elements.optimizeAction.dataset.action = isKnowledge ? "counter" : "optimize";
  elements.followUpAction.textContent = isKnowledge ? "继续追问" : "继续问我";
  elements.coachEmpty.textContent = isKnowledge
    ? "你可以先用自己的话回答，也可以要一点提示。面试官只看核心意思，不要求“标准答案腔”。"
    : "你可以直接写代码，也可以先要一点提示。面试官会顺着你的思路聊，不要求“标准答案腔”。";
  elements.referenceAnswer.hidden = true;
  elements.referenceAnswerContent.textContent = "";

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
}

function setChromeCollapsed(collapsed) {
  document.body.classList.toggle("chrome-collapsed", collapsed);
  elements.expandChrome.setAttribute("aria-hidden", String(!collapsed));
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

function renderProficiency(pe) {
  const labels = {
    blank: "PE · 还没展开",
    exploring: "PE · 正在梳理",
    partial: "PE · 部分掌握",
    solid: "PE · 核心已掌握",
    misconception: "PE · 有个误区",
    blocked: "PE · 暂时卡住",
  };
  const classes = {
    blank: "retry",
    exploring: "partial",
    partial: "partial",
    solid: "pass",
    misconception: "retry",
    blocked: "retry",
  };
  elements.reviewState.textContent = labels[pe.state] || "PE · 正在判断";
  elements.reviewState.className = `review-state ${classes[pe.state] || "partial"}`;
  elements.reviewState.title = pe.evidence || pe.core_gap || "";
}

function setBusy(busy) {
  state.busy = busy;
  elements.submit.disabled = busy;
  elements.sendCoach.disabled = busy;
  elements.showAnswer.disabled = busy;
  elements.quickActions.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
}

async function toggleReferenceAnswer() {
  if (!state.problem || state.busy) return;
  if (elements.referenceAnswerContent.textContent) {
    elements.referenceAnswer.hidden = !elements.referenceAnswer.hidden;
    return;
  }
  const confirmed = window.confirm("标准答案会直接揭示完整实现和核心思路。确定要看吗？");
  if (!confirmed) return;
  setBusy(true);
  const originalLabel = elements.showAnswer.textContent;
  elements.showAnswer.textContent = "读取中…";
  try {
    const result = await request("/api/answer", {
      method: "POST",
      body: JSON.stringify({ problem_id: state.problem.id }),
    });
    elements.referenceAnswerContent.textContent = result.answer;
    elements.referenceAnswer.hidden = false;
    elements.referenceAnswer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    showRequestError(error);
  } finally {
    elements.showAnswer.textContent = originalLabel;
    setBusy(false);
  }
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
    optimize: state.problem.kind === "knowledge" ? "这块还能怎么补？" : "这块还能怎么改？",
    counter: "你可以反问我一下。",
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
    if (result.pe) renderProficiency(result.pe);
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
    const [problem, config] = await Promise.all([
      request(`/api/problem?id=${encodeURIComponent(problemId)}`),
      request("/api/config"),
    ]);
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
elements.editor.addEventListener("focus", () => {
  if (state.chromeAutoCollapsed) return;
  state.chromeAutoCollapsed = true;
  setChromeCollapsed(true);
});
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
  if (!state.problem || !window.confirm(state.problem.kind === "knowledge" ? "清空当前回答草稿？" : "将当前草稿恢复为初始模板？")) return;
  elements.editor.value = state.problem.starter_code;
  delete state.drafts[state.problem.id];
  localStorage.setItem("aibag_code_drafts_v1", JSON.stringify(state.drafts));
  elements.draftStatus.textContent = "已恢复模板";
  updateLineNumbers();
});
elements.showAnswer.addEventListener("click", toggleReferenceAnswer);
elements.closeAnswer.addEventListener("click", () => { elements.referenceAnswer.hidden = true; });
elements.collapseChrome.addEventListener("click", () => {
  state.chromeAutoCollapsed = true;
  setChromeCollapsed(true);
});
elements.expandChrome.addEventListener("click", () => {
  state.chromeAutoCollapsed = true;
  setChromeCollapsed(false);
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
