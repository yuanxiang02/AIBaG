const state = {
  problems: [],
  activeKind: "",
  activeDifficulty: "",
  activeStatus: "",
  visibleLimit: 80,
  progress: JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}"),
};

const elements = {
  list: document.querySelector("#problem-list"),
  trackTabs: document.querySelector(".track-tabs"),
  trackTitle: document.querySelector("#track-title"),
  filteredSummary: document.querySelector("#filtered-summary"),
  difficultyFilter: document.querySelector("#difficulty-filter"),
  statusFilter: document.querySelector("#status-filter"),
  search: document.querySelector("#problem-search"),
  pickRandom: document.querySelector("#pick-random"),
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
  loadMore: document.querySelector("#load-more"),
  statPracticed: document.querySelector("#stat-practiced"),
  statPass: document.querySelector("#stat-pass"),
  statCustom: document.querySelector("#stat-custom"),
  countAll: document.querySelector("#count-all"),
  countCoding: document.querySelector("#count-coding"),
  countKnowledge: document.querySelector("#count-knowledge"),
  countAlgorithm: document.querySelector("#count-algorithm"),
  countCustom: document.querySelector("#count-custom"),
  navOpenCustom: document.querySelector("#nav-open-custom"),
  heroOpenCustom: document.querySelector("#hero-open-custom"),
  openCustomModal: document.querySelector("#open-custom-modal"),
  customModal: document.querySelector("#custom-modal"),
  closeCustomModal: document.querySelector("#close-custom-modal"),
  cancelCustomModal: document.querySelector("#cancel-custom-modal"),
  modalTabs: document.querySelector(".modal-tabs"),
  singleForm: document.querySelector("#custom-single-form"),
  batchPanel: document.querySelector("#custom-batch-panel"),
  customTitle: document.querySelector("#custom-title"),
  customKind: document.querySelector("#custom-kind"),
  customDifficulty: document.querySelector("#custom-difficulty"),
  customCategory: document.querySelector("#custom-category"),
  customTags: document.querySelector("#custom-tags"),
  customDescription: document.querySelector("#custom-description"),
  customStarterWrap: document.querySelector("#custom-starter-wrap"),
  customStarter: document.querySelector("#custom-starter"),
  customReviewPoints: document.querySelector("#custom-review-points"),
  customAnswer: document.querySelector("#custom-answer"),
  customFormFeedback: document.querySelector("#custom-form-feedback"),
  submitCustomSingle: document.querySelector("#submit-custom-single"),
  fillBatchExample: document.querySelector("#fill-batch-example"),
  customFileInput: document.querySelector("#custom-file-input"),
  exportCustomJson: document.querySelector("#export-custom-json"),
  customBatchJson: document.querySelector("#custom-batch-json"),
  customBatchFeedback: document.querySelector("#custom-batch-feedback"),
  submitCustomBatch: document.querySelector("#submit-custom-batch"),
};

const TRACK_TITLES = {
  "": "全部题目",
  coding: "AI Infra",
  knowledge: "简答八股",
  algorithm: "力扣手撕",
  custom: "我的自建面经",
};

const BATCH_EXAMPLE_TEMPLATE = [
  {
    title: "DeepSeek MLA 相比 GQA 如何进一步压缩 KV Cache？",
    kind: "knowledge",
    difficulty: "Hard",
    category: "大模型推理面经",
    tags: ["MLA", "KV Cache", "DeepSeek", "自建面经"],
    description:
      "在长上下文推理中，KV Cache 往往成为显存与带宽瓶颈。请结合 Multi-head Latent Attention (MLA) 的低秩联合压缩机制与 Decoupled RoPE 设计，讲清它为什么能比 GQA 大幅降低 KV Cache，同时保持模型表达能力。",
    review_points: [
      "低秩潜在向量 c_t^{KV} 的压缩与投影矩阵吸收（矩阵乘法结合律）",
      "为什么 RoPE 与低秩吸收不兼容，需要采用 Decoupled RoPE",
      "推理阶段缓存内容与算力/带宽权衡",
    ],
    answer:
      "1. 核心思想：MLA 将 K 和 V 联合投影到低维潜在向量 c_t^{KV}，推理时仅缓存压缩后的潜在向量而非完整的多头 K/V。\n2. 矩阵吸收：在计算 Attention Score 时，解压矩阵 W^{UK} 可以与查询投影矩阵 W^Q 合并吸收，避免在推理时显式展开高维 K。\n3. Decoupled RoPE：由于旋转位置编码矩阵与 token 位置强相关，中间夹着 RoPE 时无法直接合并 W^Q 与 W^{UK}，因此 MLA 将小维度带 RoPE 的 k^R 与不带位置编码的低秩部分拼接。",
  },
  {
    title: "手撕带分组缩放的 Group-wise INT8 权重量化与反量化",
    kind: "coding",
    difficulty: "Medium",
    category: "AI Infra 算子面经",
    tags: ["Quantization", "INT8", "PyTorch", "自建面经"],
    description:
      "给定二维权重张量 weight (shape: [out_features, in_features]) 与 group_size，请按最后一维分组计算对称 INT8 量化（范围 [-127, 127]），返回 (q_weight, scale) 及反量化后的近似权重。",
    starter_code:
      "import torch\n\ndef group_quantize_int8(weight: torch.Tensor, group_size: int = 128):\n    # 返回 q_weight (int8), scale (fp32), dequant_weight\n    pass\n",
    review_points: [
      "正确 reshape 为 [..., num_groups, group_size] 并处理整除/边界",
      "按组求 absmax 并避免除零（clamp 最小阈值）",
      "round 与 clamp 到 [-127, 127] 并转回原 shape",
    ],
  },
];

async function request(endpoint, options = {}) {
  const response = await fetch(endpoint, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({ error: "后端返回了无法解析的结果" }));
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function updateOverviewStats() {
  const problems = state.problems;
  const codingCount = problems.filter((p) => p.kind === "coding").length;
  const knowledgeCount = problems.filter((p) => p.kind === "knowledge").length;
  const algorithmCount = problems.filter((p) => p.kind === "algorithm").length;
  const customCount = problems.filter((p) => p.is_custom).length;

  if (elements.countAll) elements.countAll.textContent = String(problems.length);
  if (elements.countCoding) elements.countCoding.textContent = String(codingCount);
  if (elements.countKnowledge) elements.countKnowledge.textContent = String(knowledgeCount);
  if (elements.countAlgorithm) elements.countAlgorithm.textContent = String(algorithmCount);
  if (elements.countCustom) elements.countCustom.textContent = String(customCount);

  const practicedIds = Object.keys(state.progress);
  const passCount = practicedIds.filter((id) => state.progress[id]?.verdict === "pass").length;
  if (elements.statPracticed) elements.statPracticed.textContent = String(practicedIds.length);
  if (elements.statPass) elements.statPass.textContent = String(passCount);
  if (elements.statCustom) elements.statCustom.textContent = String(customCount);
}

function filteredProblems() {
  const query = elements.search.value.trim().toLowerCase();
  return state.problems.filter((problem) => {
    if (state.activeKind === "custom") {
      if (!problem.is_custom) return false;
    } else if (state.activeKind && problem.kind !== state.activeKind) {
      return false;
    }
    if (state.activeDifficulty && problem.difficulty !== state.activeDifficulty) {
      return false;
    }
    const record = state.progress[problem.id];
    if (state.activeStatus === "todo" && record) return false;
    if (state.activeStatus && state.activeStatus !== "todo" && record?.verdict !== state.activeStatus) {
      return false;
    }
    if (!query) return true;
    const numStr = String(problem.number).padStart(2, "0");
    const text = `${numStr} ${problem.number} ${problem.title} ${problem.category} ${problem.summary || ""} ${(problem.tags || []).join(" ")}`.toLowerCase();
    return text.includes(query);
  });
}

function renderEmpty(message) {
  elements.loadMore.hidden = true;
  elements.list.replaceChildren();
  const row = document.createElement("tr");
  row.className = "empty-row";
  const cell = document.createElement("td");
  cell.colSpan = 5;
  cell.textContent = message;
  row.appendChild(cell);
  elements.list.appendChild(row);
}

async function handleDeleteCustomProblem(problem, event) {
  event.stopPropagation();
  event.preventDefault();
  if (!window.confirm(`确定删除自建面经「${problem.title}」吗？`)) return;
  try {
    await request("/api/custom-problems/delete", {
      method: "POST",
      body: JSON.stringify({ id: problem.id }),
    });
    state.problems = await request("/api/problems");
    updateOverviewStats();
    renderProblems();
  } catch (error) {
    window.alert(error.message || "删除失败");
  }
}

function renderProblems() {
  const problems = filteredProblems();
  if (elements.filteredSummary) {
    elements.filteredSummary.textContent = `当前筛选共 ${problems.length} 道题`;
  }
  if (!problems.length) {
    renderEmpty(
      state.activeKind === "custom"
        ? "还没有自建面经，点击右上角「+ 提交自建面经」即可录入你的第一道专属题目。"
        : "没有符合当前筛选条件的题目。"
    );
    return;
  }
  elements.list.replaceChildren();
  problems.slice(0, state.visibleLimit).forEach((problem) => {
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
    if (problem.is_custom) {
      const customBadge = document.createElement("span");
      customBadge.className = "custom-pill";
      customBadge.textContent = "自建";
      title.appendChild(customBadge);
    }
    const summary = document.createElement("span");
    summary.textContent = problem.summary;
    link.append(title, summary);
    titleCell.appendChild(link);

    const categoryCell = document.createElement("td");
    categoryCell.className = "track-label";
    const kindLabel = {
      coding: "AI Infra",
      knowledge: "简答八股",
      algorithm: "力扣手撕",
    }[problem.kind] || problem.category;
    categoryCell.textContent = problem.is_custom ? `${kindLabel} · ${problem.category}` : kindLabel;

    const difficultyCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `difficulty ${problem.difficulty.toLowerCase()}`;
    badge.textContent = problem.difficulty;
    difficultyCell.appendChild(badge);

    const actionCell = document.createElement("td");
    actionCell.className = "row-arrow";
    if (problem.is_custom) {
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "row-delete-btn";
      delBtn.title = "删除这道自建题目";
      delBtn.textContent = "删除";
      delBtn.addEventListener("click", (event) => handleDeleteCustomProblem(problem, event));
      actionCell.appendChild(delBtn);
    } else {
      actionCell.textContent = "→";
    }
    row.append(statusCell, titleCell, categoryCell, difficultyCell, actionCell);
    row.addEventListener("click", (event) => {
      if (!event.target.closest("a") && !event.target.closest("button")) {
        window.location.assign(destination);
      }
    });
    elements.list.appendChild(row);
  });
  const remaining = Math.max(0, problems.length - state.visibleLimit);
  elements.loadMore.hidden = remaining === 0;
  elements.loadMore.textContent = remaining ? `加载更多（剩余 ${remaining}）` : "";
}

function showFeedback(target, message, isError = false) {
  if (!target) return;
  target.hidden = false;
  target.className = `form-feedback ${isError ? "error" : "ok"}`;
  target.textContent = message;
}

function openCustomDialog(tab = "single") {
  if (!elements.customModal) return;
  switchModalTab(tab);
  elements.customFormFeedback.hidden = true;
  elements.customBatchFeedback.hidden = true;
  if (typeof elements.customModal.showModal === "function") {
    elements.customModal.showModal();
  } else {
    elements.customModal.setAttribute("open", "open");
  }
}

function closeCustomDialog() {
  if (!elements.customModal) return;
  if (typeof elements.customModal.close === "function") {
    elements.customModal.close();
  } else {
    elements.customModal.removeAttribute("open");
  }
}

function switchModalTab(tab) {
  const isBatch = tab === "batch";
  elements.singleForm.hidden = isBatch;
  elements.batchPanel.hidden = !isBatch;
  elements.modalTabs.querySelectorAll("button[data-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
}

function syncStarterFieldVisibility() {
  const isKnowledge = elements.customKind.value === "knowledge";
  elements.customStarterWrap.hidden = isKnowledge;
}

async function submitSingleCustomProblem(event) {
  event.preventDefault();
  const payload = {
    title: elements.customTitle.value.trim(),
    kind: elements.customKind.value,
    difficulty: elements.customDifficulty.value,
    category: elements.customCategory.value.trim(),
    tags: elements.customTags.value.trim(),
    description: elements.customDescription.value.trim(),
    starter_code: elements.customStarter.value,
    review_points: elements.customReviewPoints.value.trim(),
    answer: elements.customAnswer.value.trim(),
  };
  elements.submitCustomSingle.disabled = true;
  try {
    const res = await request("/api/custom-problems", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.problems = await request("/api/problems");
    updateOverviewStats();
    state.activeKind = "custom";
    elements.trackTabs.querySelectorAll("button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.kind === "custom");
    });
    elements.trackTitle.textContent = TRACK_TITLES.custom;
    renderProblems();
    elements.singleForm.reset();
    syncStarterFieldVisibility();
    const createdItem = res.created?.[0];
    showFeedback(
      elements.customFormFeedback,
      `已成功加入自建面经「${createdItem?.title || payload.title}」！可关闭弹窗在列表中查看，或直接点击练习。`
    );
    setTimeout(() => closeCustomDialog(), 900);
  } catch (error) {
    showFeedback(elements.customFormFeedback, error.message || "保存失败", true);
  } finally {
    elements.submitCustomSingle.disabled = false;
  }
}

async function submitBatchCustomProblems() {
  const rawText = elements.customBatchJson.value.trim();
  if (!rawText) {
    showFeedback(elements.customBatchFeedback, "请先粘贴 JSON 内容或选择本地 JSON 文件。", true);
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(rawText);
  } catch (error) {
    showFeedback(elements.customBatchFeedback, `JSON 语法有误：${error.message}`, true);
    return;
  }
  const body = Array.isArray(parsed) ? { problems: parsed } : parsed;
  elements.submitCustomBatch.disabled = true;
  try {
    const res = await request("/api/custom-problems", {
      method: "POST",
      body: JSON.stringify(body),
    });
    state.problems = await request("/api/problems");
    updateOverviewStats();
    state.activeKind = "custom";
    elements.trackTabs.querySelectorAll("button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.kind === "custom");
    });
    elements.trackTitle.textContent = TRACK_TITLES.custom;
    renderProblems();
    showFeedback(elements.customBatchFeedback, `成功导入 ${res.count} 道自建题目！`);
    setTimeout(() => closeCustomDialog(), 900);
  } catch (error) {
    showFeedback(elements.customBatchFeedback, error.message || "批量导入失败", true);
  } finally {
    elements.submitCustomBatch.disabled = false;
  }
}

async function exportCustomBank() {
  try {
    const data = await request("/api/custom-problems");
    if (!data.problems?.length) {
      showFeedback(elements.customBatchFeedback, "当前还没有自建题目可导出。", true);
      return;
    }
    const blob = new Blob([JSON.stringify(data.problems, null, 2)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "aibag-custom-problems.json";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    showFeedback(elements.customBatchFeedback, `已导出 ${data.problems.length} 道自建面经。`);
  } catch (error) {
    showFeedback(elements.customBatchFeedback, error.message || "导出失败", true);
  }
}

async function initialize() {
  try {
    const [problems, config] = await Promise.all([request("/api/problems"), request("/api/config")]);
    state.problems = problems;
    updateOverviewStats();
    const provider = new URL(config.base_url).host;
    elements.apiStatus.textContent = `${config.model} · ${provider}`;
    elements.apiDot.className = config.has_api_key ? "status-dot ok" : "status-dot warn";
    if (!config.has_api_key) elements.apiStatus.textContent += " · key missing";
    renderProblems();
    if (new URLSearchParams(window.location.search).get("custom") === "1") {
      openCustomDialog("single");
    }
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
  state.visibleLimit = 80;
  elements.trackTabs.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
  elements.trackTitle.textContent = TRACK_TITLES[state.activeKind] || "全部题目";
  renderProblems();
});
elements.difficultyFilter?.addEventListener("change", () => {
  state.activeDifficulty = elements.difficultyFilter.value;
  state.visibleLimit = 80;
  renderProblems();
});
elements.statusFilter?.addEventListener("change", () => {
  state.activeStatus = elements.statusFilter.value;
  state.visibleLimit = 80;
  renderProblems();
});
elements.search.addEventListener("input", () => {
  state.visibleLimit = 80;
  renderProblems();
});
elements.pickRandom?.addEventListener("click", () => {
  const candidates = filteredProblems();
  if (!candidates.length) return;
  const picked = candidates[Math.floor(Math.random() * candidates.length)];
  window.location.assign(`/problem.html?id=${encodeURIComponent(picked.id)}`);
});
elements.loadMore.addEventListener("click", () => {
  state.visibleLimit += 80;
  renderProblems();
});

[elements.navOpenCustom, elements.heroOpenCustom, elements.openCustomModal].forEach((btn) => {
  btn?.addEventListener("click", () => openCustomDialog("single"));
});
elements.closeCustomModal?.addEventListener("click", closeCustomDialog);
elements.cancelCustomModal?.addEventListener("click", closeCustomDialog);
elements.customModal?.addEventListener("click", (event) => {
  if (event.target === elements.customModal) closeCustomDialog();
});
elements.modalTabs?.addEventListener("click", (event) => {
  const tabBtn = event.target.closest("button[data-tab]");
  if (tabBtn) switchModalTab(tabBtn.dataset.tab);
});
elements.customKind?.addEventListener("change", syncStarterFieldVisibility);
elements.singleForm?.addEventListener("submit", submitSingleCustomProblem);
elements.fillBatchExample?.addEventListener("click", () => {
  elements.customBatchJson.value = JSON.stringify(BATCH_EXAMPLE_TEMPLATE, null, 2);
  showFeedback(elements.customBatchFeedback, "已填入 2 道示例面经（含简答八股与 AI Infra 手撕），可直接点击批量导入。");
});
elements.customFileInput?.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const text = await file.text();
  elements.customBatchJson.value = text;
  showFeedback(elements.customBatchFeedback, `已读取文件 ${file.name}，请点击「批量导入题库」完成导入。`);
});
elements.exportCustomJson?.addEventListener("click", exportCustomBank);
elements.submitCustomBatch?.addEventListener("click", submitBatchCustomProblems);

window.addEventListener("pageshow", () => {
  state.progress = JSON.parse(localStorage.getItem("aibag_code_progress_v1") || "{}");
  if (state.problems.length) {
    updateOverviewStats();
    renderProblems();
  }
});

initialize();
