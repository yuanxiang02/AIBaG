const state = {
  problem: null,
  catalog: [],
  latestReview: null,
  conversation: [],
  busy: false,
  aiAvailable: true,
  progress: JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}"),
  drafts: JSON.parse(localStorage.getItem("aibag_code_drafts_v1") || "{}"),
};

const elements = {
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
  prevProblem: document.querySelector("#prev-problem"),
  nextProblem: document.querySelector("#next-problem"),
  randomProblem: document.querySelector("#random-problem"),
  queuePos: document.querySelector("#problem-queue-pos"),
  number: document.querySelector("#problem-number"),
  category: document.querySelector("#problem-category"),
  title: document.querySelector("#problem-title"),
  customBadge: document.querySelector("#problem-custom-badge"),
  editCustomProblem: document.querySelector("#edit-custom-problem"),
  difficulty: document.querySelector("#problem-difficulty"),
  language: document.querySelector("#problem-language"),
  description: document.querySelector("#problem-description"),
  examplesSection: document.querySelector("#examples-section"),
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
  selfGradeBar: document.querySelector("#self-grade-bar"),
  copyAnswer: document.querySelector("#copy-answer"),
  closeAnswer: document.querySelector("#close-answer"),
  referenceAnswer: document.querySelector("#reference-answer"),
  referenceAnswerContent: document.querySelector("#reference-answer-content"),
  submit: document.querySelector("#submit-code"),
  submitNote: document.querySelector("#submit-note"),
  coachLog: document.querySelector("#coach-log"),
  reviewState: document.querySelector("#review-state"),
  clearCoach: document.querySelector("#clear-coach"),
  coachInput: document.querySelector("#coach-input"),
  sendCoach: document.querySelector("#send-coach"),
  quickActions: document.querySelector(".coach-quick-actions"),
  coachEmpty: document.querySelector("#coach-empty"),
  optimizeAction: document.querySelector("#optimize-action"),
  followUpAction: document.querySelector("#follow-up-action"),
};

function sessionKey(problemId) {
  return `aibag_session_chat_${problemId}`;
}

function saveSessionChat() {
  if (!state.problem) return;
  try {
    sessionStorage.setItem(
      sessionKey(state.problem.id),
      JSON.stringify({
        conversation: state.conversation,
        latestReview: state.latestReview,
      })
    );
  } catch (_err) {
    // Ignore sessionStorage quota issues
  }
}

function loadSessionChat(problemId) {
  try {
    const raw = sessionStorage.getItem(sessionKey(problemId));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_err) {
    return null;
  }
}

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

function resolveActiveQueue() {
  const allIds = state.catalog.map((item) => item.id);
  try {
    const raw = sessionStorage.getItem("aibag_filtered_ids_v1");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.ids) && parsed.ids.includes(state.problem?.id)) {
        return { label: parsed.label || "当前筛选", ids: parsed.ids };
      }
    }
  } catch (_err) {
    // ignore
  }
  return { label: "题库", ids: allIds };
}

function updateNavigationButtons() {
  if (!state.problem || !state.catalog.length) return;
  const { label, ids } = resolveActiveQueue();
  const idx = ids.indexOf(state.problem.id);
  if (elements.prevProblem) {
    elements.prevProblem.disabled = idx <= 0;
    elements.prevProblem.dataset.targetId = idx > 0 ? ids[idx - 1] : "";
  }
  if (elements.nextProblem) {
    elements.nextProblem.disabled = idx < 0 || idx >= ids.length - 1;
    elements.nextProblem.dataset.targetId =
      idx >= 0 && idx < ids.length - 1 ? ids[idx + 1] : "";
  }
  if (elements.queuePos) {
    if (idx >= 0 && ids.length > 0) {
      elements.queuePos.hidden = false;
      elements.queuePos.textContent = `${label} ${idx + 1} / ${ids.length}`;
    } else {
      elements.queuePos.hidden = true;
    }
  }
}

function syncSelfGradeButtons() {
  if (!elements.selfGradeBar || !state.problem) return;
  const currentVerdict = state.progress[state.problem.id]?.verdict || "";
  elements.selfGradeBar.querySelectorAll("button[data-verdict]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.verdict === currentVerdict);
  });
}

function applySelfGrade(verdict) {
  if (!state.problem || !["pass", "partial", "retry"].includes(verdict)) return;
  const defaultScores = { pass: 92, partial: 72, retry: 45 };
  const prev = state.progress[state.problem.id];
  const score = prev?.mode === "ai" && prev?.verdict === verdict ? prev.score : defaultScores[verdict];
  state.progress[state.problem.id] = {
    verdict,
    score,
    attempts: (prev?.attempts || 0) + 1,
    updated_at: new Date().toISOString(),
    mode: "self",
  };
  localStorage.setItem("aibag_code_progress_v1", JSON.stringify(state.progress));
  const labels = { pass: "自评：已掌握", partial: "自评：待巩固", retry: "自评：需重试" };
  elements.reviewState.textContent = `${labels[verdict]} · ${score}分`;
  elements.reviewState.className = `review-state ${verdict}`;
  syncSelfGradeButtons();
}

function renderProblem(problem) {
  state.problem = problem;
  const isKnowledge = problem.kind === "knowledge";
  document.body.classList.toggle("knowledge-problem", isKnowledge);
  document.title = `${problem.title} · AIBaG`;
  elements.number.textContent = String(problem.number).padStart(2, "0");
  elements.category.textContent = problem.category.toUpperCase();
  elements.title.textContent = problem.title;
  if (elements.customBadge) {
    elements.customBadge.hidden = !problem.is_custom;
  }
  if (elements.editCustomProblem) {
    elements.editCustomProblem.hidden = !problem.is_custom;
    if (problem.is_custom) {
      elements.editCustomProblem.href = `/?edit_custom=${encodeURIComponent(problem.id)}`;
    }
  }
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
  elements.editor.placeholder = isKnowledge ? "用自己的话写下核心回答（支持 Cmd/Ctrl + Enter 提交）…" : "";
  elements.submitNote.textContent = isKnowledge
    ? "面试口述模式：讲清核心即可，支持 Cmd/Ctrl + Enter 快速提交。"
    : "白板模式：只做静态推理，不运行代码（Cmd/Ctrl + Enter 提交）。";
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
  const exampleItems = problem.examples || [];
  if (elements.examplesSection) {
    elements.examplesSection.hidden = exampleItems.length === 0;
  }
  exampleItems.forEach((example, index) => {
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
    const isExternalSource = /^https?:\/\//i.test(source.url || "");
    const sourceTitle = document.createElement(isExternalSource ? "a" : "strong");
    sourceTitle.textContent = source.title;
    if (isExternalSource) {
      sourceTitle.href = source.url;
      sourceTitle.target = "_blank";
      sourceTitle.rel = "noreferrer";
    }
    const note = document.createElement("p");
    note.textContent = `${source.license} · ${source.note}`;
    card.append(sourceTitle, note);
    elements.sources.appendChild(card);
  });

  elements.editor.value = state.drafts[problem.id] ?? problem.starter_code;
  updateLineNumbers();
  updateNavigationButtons();
  syncSelfGradeButtons();

  const cachedSession = loadSessionChat(problem.id);
  if (cachedSession && (cachedSession.latestReview || cachedSession.conversation?.length)) {
    state.latestReview = cachedSession.latestReview || null;
    state.conversation = cachedSession.conversation || [];
    if (state.latestReview) {
      renderReview(state.latestReview, false);
    }
    state.conversation.forEach((turn) => {
      appendCoachMessage(
        turn.role === "user" ? "我" : "面试官",
        turn.content,
        turn.role === "user" ? "user-turn" : "interviewer-turn"
      );
    });
  } else {
    const prevRecord = state.progress[problem.id];
    if (prevRecord) {
      const labels = { pass: "上次：方向没问题", partial: "上次：待巩固", retry: "上次：需重试" };
      elements.reviewState.textContent = `${labels[prevRecord.verdict] || "已练习"} (${prevRecord.score ?? 0}分)`;
      elements.reviewState.className = `review-state ${prevRecord.verdict || ""}`;
    }
  }
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

function renderReviewSummaryCard(review) {
  ensureCoachLog();
  const card = document.createElement("div");
  card.className = "coach-message review-summary";
  const scoreBadge = document.createElement("span");
  scoreBadge.className = "score";
  scoreBadge.textContent = `${review.score ?? 0} 分`;
  const heading = document.createElement("h3");
  const verdictTitles = {
    pass: "面试官评估：核心已掌握 (Pass)",
    partial: "面试官评估：方向正确，细节待补全 (Partial)",
    retry: "面试官评估：建议调整核心思路 (Retry)",
  };
  heading.textContent = verdictTitles[review.verdict] || "面试官评估";
  card.append(scoreBadge, heading);

  const list = document.createElement("ul");
  (review.strengths || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `亮点：${item}`;
    list.appendChild(li);
  });
  if (review.focus_issue) {
    const li = document.createElement("li");
    li.textContent = `当前聚焦：${review.focus_issue}`;
    list.appendChild(li);
  }
  if (list.children.length) {
    card.appendChild(list);
  }
  elements.coachLog.appendChild(card);
  elements.coachLog.scrollTop = elements.coachLog.scrollHeight;
}

function renderReview(review, persistSession = true) {
  renderReviewSummaryCard(review);
  appendCoachMessage("面试官", review.interviewer_response, "interviewer-turn");
  if (review.nudge) appendCoachMessage("给你一个小方向", review.nudge, "nudge-turn");
  if (review.follow_up) appendCoachMessage("接着聊一个问题", review.follow_up, "follow-up-turn");
  const labels = { pass: "方向没问题", partial: "再补一点", retry: "先调一下思路" };
  elements.reviewState.textContent = `${labels[review.verdict] || "看过了"} · ${review.score ?? 0}分`;
  elements.reviewState.className = `review-state ${review.verdict}`;
  if (persistSession) saveSessionChat();
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
  const aiDisabled = !state.aiAvailable;
  elements.submit.disabled = busy || aiDisabled;
  elements.sendCoach.disabled = busy || aiDisabled;
  elements.coachInput.disabled = busy || aiDisabled;
  elements.showAnswer.disabled = busy;
  elements.quickActions.querySelectorAll("button").forEach((button) => {
    button.disabled = busy || aiDisabled;
  });
}

function configureAIAvailability(config) {
  state.aiAvailable = config.ai_available ?? config.has_api_key;
  elements.apiStatus.textContent = state.aiAvailable
    ? "AI 面试官已就绪"
    : "标准答案可用 · AI 点评未配置";
  elements.apiStatus.title = state.aiAvailable
    ? "可以使用 AI 点评与追问"
    : "仍可查看标准答案并使用离线自评";
  elements.apiDot.className = state.aiAvailable ? "status-dot ok" : "status-dot warn";

  const unavailableHint = "请先在 .env 中配置 AI 服务；标准答案与自评功能仍可正常使用。";
  elements.submit.title = state.aiAvailable ? "" : unavailableHint;
  elements.sendCoach.title = state.aiAvailable ? "" : unavailableHint;
  elements.coachInput.title = state.aiAvailable ? "" : unavailableHint;
  elements.quickActions.querySelectorAll("button").forEach((button) => {
    button.title = state.aiAvailable ? "" : unavailableHint;
  });
  if (!state.aiAvailable) {
    elements.submitNote.textContent = "AI 点评尚未配置；你仍可查看标准答案，并记录自评掌握度。";
    if (elements.coachLog.querySelector(".coach-empty")) {
      elements.coachEmpty.textContent =
        "AI 追问尚未配置。你可以先完成作答，再通过标准答案与自评掌握度进行离线训练。";
    }
  }
  setBusy(false);
}

async function toggleReferenceAnswer() {
  if (!state.problem || state.busy) return;
  if (elements.referenceAnswerContent.textContent) {
    elements.referenceAnswer.hidden = !elements.referenceAnswer.hidden;
    return;
  }
  setBusy(true);
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
      updated_at: new Date().toISOString(),
      mode: "ai",
    };
    localStorage.setItem("aibag_code_progress_v1", JSON.stringify(state.progress));
    syncSelfGradeButtons();
    renderReview(review, true);
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
    saveSessionChat();
  } catch (error) {
    pending.remove();
    showRequestError(error);
  } finally {
    setBusy(false);
  }
}

function clearCoachSession() {
  if (!state.problem || state.busy) return;
  state.conversation = [];
  state.latestReview = null;
  try {
    sessionStorage.removeItem(sessionKey(state.problem.id));
  } catch (_err) {
    // ignore
  }
  elements.coachLog.replaceChildren();
  const empty = document.createElement("p");
  empty.id = "coach-empty";
  empty.className = "coach-empty";
  empty.textContent =
    state.problem.kind === "knowledge"
      ? "对话已清空。你可以先用自己的话回答，也可以要一点提示。"
      : "对话已清空。你可以直接写代码，也可以先要一点提示。";
  elements.coachLog.appendChild(empty);
  elements.reviewState.textContent = "还没提交";
  elements.reviewState.className = "review-state";
}

async function initialize() {
  const problemId = new URLSearchParams(window.location.search).get("id");
  if (!problemId) {
    window.location.replace("/");
    return;
  }
  try {
    const [problem, config, catalog] = await Promise.all([
      request(`/api/problem?id=${encodeURIComponent(problemId)}`),
      request("/api/config"),
      request("/api/problems").catch(() => []),
    ]);
    state.catalog = Array.isArray(catalog) ? catalog : [];
    renderProblem(problem);
    configureAIAvailability(config);
  } catch (error) {
    elements.apiDot.className = "status-dot error";
    elements.apiStatus.textContent = "本地后端不可用";
    showRequestError(error);
  }
}

elements.editor.addEventListener("input", () => {
  updateLineNumbers();
  scheduleDraftSave();
});
elements.editor.addEventListener("scroll", () => {
  elements.lineNumbers.scrollTop = elements.editor.scrollTop;
});
elements.editor.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    submitCode();
    return;
  }
  if (event.key !== "Tab") return;
  event.preventDefault();
  const start = elements.editor.selectionStart;
  const end = elements.editor.selectionEnd;
  elements.editor.setRangeText("    ", start, end, "end");
  updateLineNumbers();
  scheduleDraftSave();
});
elements.reset.addEventListener("click", () => {
  if (
    !state.problem ||
    !window.confirm(state.problem.kind === "knowledge" ? "清空当前回答草稿？" : "将当前草稿恢复为初始模板？")
  )
    return;
  elements.editor.value = state.problem.starter_code;
  delete state.drafts[state.problem.id];
  localStorage.setItem("aibag_code_drafts_v1", JSON.stringify(state.drafts));
  elements.draftStatus.textContent = "已恢复模板";
  updateLineNumbers();
});
elements.showAnswer.addEventListener("click", toggleReferenceAnswer);
elements.selfGradeBar?.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-verdict]");
  if (btn) applySelfGrade(btn.dataset.verdict);
});
elements.copyAnswer?.addEventListener("click", async () => {
  const text = elements.referenceAnswerContent.textContent;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const prev = elements.copyAnswer.textContent;
    elements.copyAnswer.textContent = "已复制 ✓";
    setTimeout(() => {
      elements.copyAnswer.textContent = prev;
    }, 1200);
  } catch (_err) {
    // ignore clipboard failure
  }
});
elements.closeAnswer.addEventListener("click", () => {
  elements.referenceAnswer.hidden = true;
});
elements.submit.addEventListener("click", submitCode);
elements.clearCoach?.addEventListener("click", clearCoachSession);
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

elements.prevProblem?.addEventListener("click", () => {
  const target = elements.prevProblem.dataset.targetId;
  if (target) window.location.assign(`/problem.html?id=${encodeURIComponent(target)}`);
});
elements.nextProblem?.addEventListener("click", () => {
  const target = elements.nextProblem.dataset.targetId;
  if (target) window.location.assign(`/problem.html?id=${encodeURIComponent(target)}`);
});
elements.randomProblem?.addEventListener("click", () => {
  if (!state.catalog.length) return;
  const { ids } = resolveActiveQueue();
  const pool = ids.filter((id) => id !== state.problem?.id);
  const candidates = pool.length ? pool : ids;
  const pickedId = candidates[Math.floor(Math.random() * candidates.length)];
  if (pickedId) window.location.assign(`/problem.html?id=${encodeURIComponent(pickedId)}`);
});

window.addEventListener("keydown", (event) => {
  if (!event.altKey) return;
  if (event.key === "ArrowLeft" && elements.prevProblem?.dataset.targetId) {
    event.preventDefault();
    window.location.assign(`/problem.html?id=${encodeURIComponent(elements.prevProblem.dataset.targetId)}`);
  } else if (event.key === "ArrowRight" && elements.nextProblem?.dataset.targetId) {
    event.preventDefault();
    window.location.assign(`/problem.html?id=${encodeURIComponent(elements.nextProblem.dataset.targetId)}`);
  }
});

initialize();
