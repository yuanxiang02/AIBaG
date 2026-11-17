const state = {
  questions: [],
  current: null,
  latestAnswer: "",
  latestReview: null,
  conversation: [],
  busy: false,
  progress: JSON.parse(localStorage.getItem("aibag_progress_v1") || "{}"),
};

const elements = {
  list: document.querySelector("#question-list"),
  search: document.querySelector("#question-search"),
  topicFilter: document.querySelector("#topic-filter"),
  random: document.querySelector("#random-question"),
  feed: document.querySelector("#chat-feed"),
  input: document.querySelector("#answer-input"),
  judge: document.querySelector("#judge-button"),
  chat: document.querySelector("#chat-button"),
  quickActions: document.querySelector("#quick-actions"),
  topic: document.querySelector("#question-topic"),
  difficulty: document.querySelector("#question-difficulty"),
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
  sidebar: document.querySelector(".sidebar"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({ error: "服务返回了无法解析的结果" }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function createMessage(role, text, options = {}) {
  const fragment = document.querySelector("#message-template").content.cloneNode(true);
  const article = fragment.querySelector(".message");
  const avatar = fragment.querySelector(".avatar");
  const label = fragment.querySelector(".message-label");
  const content = fragment.querySelector(".message-content");
  article.classList.add(role);
  if (options.id) article.dataset.messageId = options.id;
  avatar.textContent = role === "user" ? "YOU" : "AI";
  label.textContent = role === "user" ? "你的回答" : options.label || "AI 面试官";
  content.textContent = text;
  if (options.className) content.classList.add(options.className);
  elements.feed.appendChild(fragment);
  scrollToBottom();
  return elements.feed.lastElementChild;
}

function createQuestionMessage(question) {
  const article = createMessage("assistant", "", { label: "本轮题目" });
  const content = article.querySelector(".message-content");
  const card = document.createElement("div");
  card.className = "question-card";
  const number = document.createElement("span");
  number.className = "question-number";
  number.textContent = `${question.topic.toUpperCase()} · ${question.type === "scenario" ? "场景题" : "知识题"}`;
  const text = document.createElement("p");
  text.textContent = question.question;
  card.append(number, text);
  content.appendChild(card);
}

function appendListSection(parent, title, items, emptyText) {
  const section = document.createElement("section");
  section.className = "review-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const list = document.createElement("ul");
  const values = items && items.length ? items : [emptyText];
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  });
  section.append(heading, list);
  parent.appendChild(section);
}

function createReviewMessage(review) {
  const article = createMessage("assistant", "", { label: "核心思路 Review" });
  const content = article.querySelector(".message-content");
  const card = document.createElement("div");
  card.className = "review-card";

  const head = document.createElement("div");
  head.className = "review-head";
  const verdict = document.createElement("span");
  verdict.className = `verdict ${review.verdict}`;
  verdict.textContent = { pass: "核心通过", partial: "部分通过", retry: "建议重答" }[review.verdict];
  const summary = document.createElement("strong");
  summary.textContent = review.summary;
  const score = document.createElement("span");
  score.className = "review-score";
  score.append(document.createTextNode(review.score), Object.assign(document.createElement("small"), { textContent: " / 100" }));
  head.append(verdict, summary, score);

  const body = document.createElement("div");
  body.className = "review-body";
  appendListSection(body, "已经讲清楚", review.covered, "暂未识别到明确覆盖的核心点");
  appendListSection(body, "关键缺口", review.key_gaps, "没有关键遗漏");
  if (review.incorrect_points?.length) appendListSection(body, "需要纠正", review.incorrect_points, "");
  const next = document.createElement("div");
  next.className = "review-next";
  const nextFocus = document.createElement("p");
  nextFocus.textContent = review.next_focus ? `下一步建议：${review.next_focus}` : "可以让面试官继续追问，检查理解深度。";
  next.appendChild(nextFocus);
  if (review.interviewer_follow_up) {
    const followUp = document.createElement("p");
    followUp.className = "follow-up-question";
    followUp.textContent = `面试官可能追问：${review.interviewer_follow_up}`;
    next.appendChild(followUp);
  }
  body.appendChild(next);
  card.append(head, body);
  content.appendChild(card);
  scrollToBottom();
}

function scrollToBottom() {
  requestAnimationFrame(() => elements.feed.scrollTo({ top: elements.feed.scrollHeight, behavior: "smooth" }));
}

function filteredQuestions() {
  const query = elements.search.value.trim().toLowerCase();
  const topic = elements.topicFilter.value;
  return state.questions.filter((question) => {
    const haystack = `${question.topic} ${question.question} ${(question.tags || []).join(" ")}`.toLowerCase();
    return (!topic || question.topic === topic) && (!query || haystack.includes(query));
  });
}

function renderQuestionList() {
  elements.list.replaceChildren();
  filteredQuestions().forEach((question) => {
    const button = document.createElement("button");
    button.className = `question-item${state.current?.id === question.id ? " active" : ""}`;
    const title = document.createElement("strong");
    title.textContent = question.question;
    const meta = document.createElement("span");
    meta.textContent = `${question.topic} · ${question.difficulty}`;
    const mark = document.createElement("i");
    mark.className = `progress-mark ${state.progress[question.id]?.verdict || ""}`;
    button.append(title, meta, mark);
    button.addEventListener("click", () => selectQuestion(question));
    elements.list.appendChild(button);
  });
}

function selectQuestion(question) {
  state.current = question;
  state.latestAnswer = "";
  state.latestReview = null;
  state.conversation = [];
  elements.feed.replaceChildren();
  elements.input.value = "";
  elements.input.placeholder = "用自己的话解释核心思路，不需要写完整标准答案…";
  elements.quickActions.hidden = true;
  elements.chat.disabled = true;
  elements.topic.textContent = question.topic;
  elements.difficulty.textContent = question.difficulty;
  createQuestionMessage(question);
  renderQuestionList();
  elements.sidebar.classList.remove("open");
  elements.input.focus();
}

function setBusy(busy) {
  state.busy = busy;
  elements.judge.disabled = busy;
  elements.chat.disabled = busy || !state.latestReview;
  elements.input.disabled = busy;
  elements.quickActions.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
}

function showPending(label) {
  return createMessage("assistant", label, { id: "pending", className: "typing" });
}

function showError(error) {
  createMessage("assistant", error.message || String(error), { label: "请求失败", className: "error-message" });
}

async function submitForJudge() {
  if (!state.current || state.busy) return;
  const answer = elements.input.value.trim();
  if (!answer) {
    elements.input.focus();
    return;
  }
  createMessage("user", answer);
  const cumulativeAnswer = state.latestAnswer
    ? `${state.latestAnswer}\n\n补充回答：${answer}`
    : answer;
  state.latestAnswer = cumulativeAnswer;
  state.conversation.push({ role: "user", content: answer });
  elements.input.value = "";
  setBusy(true);
  const pending = showPending("正在检查核心思路");
  try {
    const review = await request("/api/judge", {
      method: "POST",
      body: JSON.stringify({ question_id: state.current.id, answer: cumulativeAnswer }),
    });
    pending.remove();
    state.latestReview = review;
    state.conversation.push({ role: "assistant", content: review.summary });
    state.progress[state.current.id] = {
      verdict: review.verdict,
      score: review.score,
      attempts: (state.progress[state.current.id]?.attempts || 0) + 1,
    };
    localStorage.setItem("aibag_progress_v1", JSON.stringify(state.progress));
    createReviewMessage(review);
    elements.quickActions.hidden = false;
    elements.input.placeholder = "继续回答追问，或者向面试官请求提示…";
    renderQuestionList();
  } catch (error) {
    pending.remove();
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function sendCoachMessage(action = "chat") {
  if (!state.current || state.busy) return;
  const message = action === "chat" ? elements.input.value.trim() : "";
  if (action === "chat" && !message) {
    elements.input.focus();
    return;
  }
  const actionLabels = {
    hint: "给我一点提示。",
    optimize: "我的回答哪个地方还可以优化？",
    follow_up: "请继续追问我一个问题。",
  };
  const shownMessage = message || actionLabels[action];
  createMessage("user", shownMessage);
  state.conversation.push({ role: "user", content: shownMessage });
  elements.input.value = "";
  setBusy(true);
  const pending = showPending("面试官正在思考");
  try {
    const result = await request("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        question_id: state.current.id,
        action,
        message,
        answer: state.latestAnswer,
        review: state.latestReview,
        history: state.conversation,
      }),
    });
    pending.remove();
    const reply = result.focus ? `${result.reply}\n\n思考方向：${result.focus}` : result.reply;
    createMessage("assistant", reply);
    state.conversation.push({ role: "assistant", content: result.reply });
  } catch (error) {
    pending.remove();
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function initialize() {
  try {
    const [questions, config] = await Promise.all([request("/api/questions"), request("/api/config")]);
    state.questions = questions;
    const topics = [...new Set(questions.map((question) => question.topic))].sort();
    topics.forEach((topic) => {
      const option = document.createElement("option");
      option.value = topic;
      option.textContent = topic;
      elements.topicFilter.appendChild(option);
    });
    const provider = new URL(config.base_url).host || config.base_url;
    elements.apiStatus.textContent = `${config.model} · ${provider}`;
    elements.apiDot.className = "status-dot ok";
    renderQuestionList();
    if (questions.length) selectQuestion(questions[0]);
  } catch (error) {
    elements.apiDot.className = "status-dot error";
    elements.apiStatus.textContent = "本地服务不可用";
    showError(error);
  }
}

elements.search.addEventListener("input", renderQuestionList);
elements.topicFilter.addEventListener("change", renderQuestionList);
elements.random.addEventListener("click", () => {
  const candidates = filteredQuestions();
  if (candidates.length) selectQuestion(candidates[Math.floor(Math.random() * candidates.length)]);
});
elements.judge.addEventListener("click", submitForJudge);
elements.chat.addEventListener("click", () => sendCoachMessage("chat"));
elements.quickActions.addEventListener("click", (event) => {
  const action = event.target.closest("button")?.dataset.action;
  if (action) sendCoachMessage(action);
});
elements.input.addEventListener("input", () => {
  elements.chat.disabled = state.busy || !state.latestReview || !elements.input.value.trim();
});
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    submitForJudge();
  }
});
elements.sidebarToggle.addEventListener("click", () => elements.sidebar.classList.toggle("open"));

initialize();
