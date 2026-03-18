const FRAMEWORK_OPTIONS = ["standard", "langgpt", "co-star", "xml"];

const state = {
  conversationId: null,
  currentPrompt: "",
  framework: "standard",
  maxTurns: 0,
  currentTurn: 0,
  settings: null,
  promptEditing: false,
  promptOptions: null,
  resolvedConfig: null,
  activeSelection: null,
};

let historyContextMenu = null;
let historyContextTarget = null;

const el = {
  appShell: document.getElementById("appShell"),
  historyList: document.getElementById("historyList"),
  chatBox: document.getElementById("chatBox"),
  answerInput: document.getElementById("answerInput"),
  customInputHint: document.getElementById("customInputHint"),
  promptEmpty: document.getElementById("promptEmpty"),
  promptReadonly: document.getElementById("promptReadonly"),
  promptEditor: document.getElementById("promptEditor"),
  progressLabel: document.getElementById("progressLabel"),
  frameworkGrid: document.getElementById("frameworkGrid"),
  toggleHistoryBtn: document.getElementById("toggleHistoryBtn"),
  mobileTabs: document.getElementById("mobileTabs"),
  settingsModal: document.getElementById("settingsModal"),

  modeSelect: document.getElementById("modeSelect"),
  scenarioSelect: document.getElementById("scenarioSelect"),
  personalitySelect: document.getElementById("personalitySelect"),
  templateSelect: document.getElementById("templateSelect"),
  verbosityInput: document.getElementById("verbosityInput"),
  verbosityValue: document.getElementById("verbosityValue"),
  resolvedConfigLabel: document.getElementById("resolvedConfigLabel"),

  newConversationBtn: document.getElementById("newConversationBtn"),
  openSettingsBtn: document.getElementById("openSettingsBtn"),
  closeSettingsBtn: document.getElementById("closeSettingsBtn"),
  cancelSettingsBtn: document.getElementById("cancelSettingsBtn"),
  saveSettingsBtn: document.getElementById("saveSettingsBtn"),

  sendBtn: document.getElementById("sendBtn"),
  forceBtn: document.getElementById("forceBtn"),
  editPromptBtn: document.getElementById("editPromptBtn"),
  savePromptBtn: document.getElementById("savePromptBtn"),
  copyPromptBtn: document.getElementById("copyPromptBtn"),

  apiKeyInput: document.getElementById("apiKeyInput"),
  baseUrlInput: document.getElementById("baseUrlInput"),
  modelInput: document.getElementById("modelInput"),
  maxTurnsInput: document.getElementById("maxTurnsInput"),
  defaultFrameworkSelect: document.getElementById("defaultFrameworkSelect"),
};

const api = {
  async createConversation(initial_idea, framework, config) {
    const res = await fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_idea, framework, config }),
    });
    if (!res.ok) throw new Error("Create conversation failed");
    return res.json();
  },

  async sendMessage(conversationId, content, force_generate = false) {
    const res = await fetch(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, force_generate }),
    });
    if (!res.ok) throw new Error("Send message failed");
    return res.json();
  },

  async listConversations() {
    const res = await fetch("/api/conversations");
    if (!res.ok) throw new Error("Load history failed");
    return res.json();
  },

  async getConversation(conversationId) {
    const res = await fetch(`/api/conversations/${conversationId}`);
    if (!res.ok) throw new Error("Read conversation failed");
    return res.json();
  },

  async deleteConversation(conversationId) {
    const res = await fetch(`/api/conversations/${conversationId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete conversation failed");
    return res.json();
  },

  async updatePrompt(conversationId, raw_text) {
    const res = await fetch(`/api/conversations/${conversationId}/prompt`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text }),
    });
    if (!res.ok) throw new Error("Save prompt failed");
    return res.json();
  },

  async getSettings() {
    const res = await fetch("/api/settings");
    if (!res.ok) throw new Error("Load settings failed");
    return res.json();
  },

  async updateSettings(payload) {
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Save settings failed");
    return res.json();
  },

  async getPromptOptions() {
    const res = await fetch("/api/config/prompt-options");
    if (!res.ok) throw new Error("Load prompt options failed");
    return res.json();
  },
};

function normalizeFramework(value) {
  const mapping = { structured: "xml", costar: "co-star", co_star: "co-star" };
  const candidate = mapping[String(value || "standard").toLowerCase()] || String(value || "standard").toLowerCase();
  return FRAMEWORK_OPTIONS.includes(candidate) ? candidate : "standard";
}

function normalizeTemplate(value) {
  return normalizeFramework(value);
}

function isTabletOrMobile() {
  return window.matchMedia("(max-width: 1024px)").matches;
}

function isMobile() {
  return window.matchMedia("(max-width: 760px)").matches;
}

function setMobilePane(pane) {
  const safePane = ["history", "chat", "prompt"].includes(pane) ? pane : "chat";
  el.appShell.classList.remove("pane-history", "pane-chat", "pane-prompt");
  el.appShell.classList.add(`pane-${safePane}`);

  el.mobileTabs.querySelectorAll(".mobile-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.pane === safePane);
  });
}

function addMessage(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = content;
  el.chatBox.appendChild(div);
  el.chatBox.scrollTop = el.chatBox.scrollHeight;
}

function clearActiveSelection() {
  if (!state.activeSelection) return;
  if (state.activeSelection.confirmBtn) state.activeSelection.confirmBtn.disabled = true;
  state.activeSelection = null;
}

function buildSelectionContent(selectedLabels, customInput) {
  const labels = (selectedLabels || []).map((item) => String(item || "").trim()).filter(Boolean);
  const custom = String(customInput || "").trim();

  if (!labels.length && !custom) return "";
  const parts = [];
  if (labels.length) parts.push(`已选项：${labels.join("；")}`);
  if (custom) parts.push(`补充：${custom}`);
  return parts.join("\n");
}

function syncActiveSelectionState() {
  if (!state.activeSelection || !state.activeSelection.confirmBtn) return;
  const selectedCount = state.activeSelection.selected.size;
  const customText = String(el.answerInput?.value || "").trim();
  state.activeSelection.confirmBtn.disabled = selectedCount < 1 && !customText;
}

function addAssistantTurn(turn) {
  if (!turn || !Array.isArray(turn.options) || turn.options.length < 1) return;
  clearActiveSelection();

  const card = document.createElement("div");
  card.className = "assistant-turn";

  const title = document.createElement("div");
  title.className = "assistant-turn-title";
  title.textContent = "请选择一个或多个选项，确认后进入下一轮。";
  card.appendChild(title);

  const source = String(turn.turn_source || "llm").toLowerCase();
  const reason = String(turn.fallback_reason || "none").toLowerCase();
  if (source === "fallback") {
    const status = document.createElement("div");
    status.className = "assistant-turn-status fallback";
    const detail = String(turn.fallback_detail || "").trim();
    status.textContent = detail
      ? `当前为回退模式（${reason}）：${detail}`
      : `当前为回退模式（${reason}）`;
    card.appendChild(status);
  }

  const options = document.createElement("div");
  options.className = "assistant-turn-options";
  const selected = new Set();

  turn.options.slice(0, 3).forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "assistant-option-btn";
    btn.type = "button";
    btn.textContent = item.label;
    btn.onclick = () => {
      const label = String(item.label || "").trim();
      if (!label) return;

      if (selected.has(label)) selected.delete(label);
      else selected.add(label);

      btn.classList.toggle("selected", selected.has(label));
      syncActiveSelectionState();
    };
    options.appendChild(btn);
  });

  const actionRow = document.createElement("div");
  actionRow.className = "assistant-turn-actions";

  if (turn.allow_custom !== false) {
    const custom = document.createElement("button");
    custom.className = "assistant-option-btn custom";
    custom.type = "button";
    custom.textContent = turn.custom_label || "自定义输入";
    custom.onclick = () => {
      if (el.customInputHint) el.customInputHint.classList.remove("hidden");
      el.answerInput.focus();
    };
    actionRow.appendChild(custom);
  }

  const confirm = document.createElement("button");
  confirm.className = "assistant-confirm-btn";
  confirm.type = "button";
  confirm.textContent = "确认选择";
  confirm.disabled = true;
  confirm.onclick = async () => {
    const payload = buildSelectionContent(Array.from(selected), el.answerInput.value);
    if (!payload) return;

    try {
      await submitAnswer(payload, false);
      confirm.disabled = true;
      selected.clear();
      options.querySelectorAll(".assistant-option-btn.selected").forEach((node) => node.classList.remove("selected"));
      clearActiveSelection();
    } catch (err) {
      alert(err.message || "Send failed");
    }
  };
  actionRow.appendChild(confirm);

  state.activeSelection = { selected, confirmBtn: confirm };
  syncActiveSelectionState();

  card.appendChild(options);
  card.appendChild(actionRow);
  el.chatBox.appendChild(card);
  el.chatBox.scrollTop = el.chatBox.scrollHeight;
}
function clearChat() {
  clearActiveSelection();
  el.chatBox.innerHTML = "";
}

function hideCustomHint() {
  if (el.customInputHint) el.customInputHint.classList.add("hidden");
}

function updateProgress() {
  if (!state.conversationId) {
    el.progressLabel.textContent = "进度 0/0";
    return;
  }
  const current = Math.max(0, Math.min(state.currentTurn || 0, state.maxTurns || 0));
  el.progressLabel.textContent = `进度 ${current}/${state.maxTurns || 0}`;
}

function setResolvedConfigLabel(config) {
  state.resolvedConfig = config || null;
  if (!config) {
    el.resolvedConfigLabel.textContent = "等待创建会话后显示最终配置";
    return;
  }

  const confidence = Number(config.confidence || 0).toFixed(2);
  el.resolvedConfigLabel.textContent = `最终配置：模式 ${config.mode} | 场景 ${config.scenario} | 人设 ${config.personality} | 模板 ${config.template} | 框架 ${config.framework} | 置信度 ${confidence}`;
}

function setConfigControlsDisabled(disabled) {
  [el.modeSelect, el.scenarioSelect, el.personalitySelect, el.templateSelect, el.verbosityInput].forEach((node) => {
    node.disabled = Boolean(disabled);
  });
}

function setPromptEditing(editing) {
  const canEdit = Boolean(state.conversationId && state.currentPrompt.trim());
  state.promptEditing = editing && canEdit;

  el.promptReadonly.classList.toggle("hidden", state.promptEditing || !canEdit);
  el.promptEditor.classList.toggle("hidden", !state.promptEditing);
  el.editPromptBtn.classList.toggle("hidden", state.promptEditing || !canEdit);
  el.savePromptBtn.classList.toggle("hidden", !state.promptEditing);
}

function setPrompt(content) {
  state.currentPrompt = content || "";
  el.promptReadonly.textContent = state.currentPrompt;
  el.promptEditor.value = state.currentPrompt;

  const hasPrompt = Boolean(state.currentPrompt.trim());
  el.promptEmpty.classList.toggle("hidden", hasPrompt);
  if (!hasPrompt) {
    el.promptReadonly.classList.add("hidden");
    el.promptEditor.classList.add("hidden");
    el.editPromptBtn.classList.add("hidden");
    el.savePromptBtn.classList.add("hidden");
    state.promptEditing = false;
    return;
  }

  setPromptEditing(false);
}

function setFrameworkUI() {
  el.frameworkGrid.querySelectorAll(".framework-card").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.framework === state.framework);
  });
}

function formatDate(raw) {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", { hour12: false, month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ensureHistoryContextMenu() {
  if (historyContextMenu) return;

  const menu = document.createElement("div");
  menu.className = "history-context-menu hidden";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "history-context-menu-btn danger";
  deleteBtn.textContent = "\u5220\u9664";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "history-context-menu-btn";
  cancelBtn.textContent = "\u53d6\u6d88";

  menu.appendChild(deleteBtn);
  menu.appendChild(cancelBtn);
  menu.addEventListener("click", (event) => event.stopPropagation());

  deleteBtn.onclick = async () => {
    if (!historyContextTarget) return;
    const targetId = historyContextTarget.id;
    closeHistoryContextMenu();

    try {
      await api.deleteConversation(targetId);
      if (state.conversationId === targetId) resetComposerForNewConversation();
      await refreshHistory();
    } catch (err) {
      alert(err.message || "Delete failed");
    }
  };

  cancelBtn.onclick = () => closeHistoryContextMenu();

  document.body.appendChild(menu);
  historyContextMenu = menu;
}

function openHistoryContextMenu(event, item) {
  ensureHistoryContextMenu();
  historyContextTarget = item;

  historyContextMenu.classList.remove("hidden");
  historyContextMenu.style.left = "0px";
  historyContextMenu.style.top = "0px";

  const menuWidth = historyContextMenu.offsetWidth || 160;
  const menuHeight = historyContextMenu.offsetHeight || 90;
  const margin = 8;

  const left = Math.min(event.clientX, window.innerWidth - menuWidth - margin);
  const top = Math.min(event.clientY, window.innerHeight - menuHeight - margin);

  historyContextMenu.style.left = `${Math.max(margin, left)}px`;
  historyContextMenu.style.top = `${Math.max(margin, top)}px`;
}

function closeHistoryContextMenu() {
  if (!historyContextMenu) return;
  historyContextMenu.classList.add("hidden");
  historyContextTarget = null;
}

function renderHistory(items) {
  el.historyList.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "history-item";

    const title = document.createElement("div");
    title.className = "history-item-title";
    title.textContent = String(item.initial_idea || "").slice(0, 42);

    const meta = document.createElement("div");
    meta.className = "history-item-meta";
    const statusLabel = item.status === "completed" ? "已完成" : "进行中";
    meta.textContent = `${statusLabel} · ${item.current_turn}/${item.max_turns} · ${item.scenario || "general"} · ${formatDate(item.created_at)}`;

    li.appendChild(title);
    li.appendChild(meta);
    li.onclick = () => loadConversation(item.id);
    li.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openHistoryContextMenu(event, item);
    });

    el.historyList.appendChild(li);
  });
}

async function refreshHistory() {
  const items = await api.listConversations();
  renderHistory(items);
}

function populatePromptOptions(options) {
  const scenarios = options.scenarios || [];
  const personalities = options.personalities || [];
  const templates = options.templates || [];

  el.scenarioSelect.innerHTML = '<option value="auto">Auto</option>';
  scenarios.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.name || item.id;
    el.scenarioSelect.appendChild(opt);
  });

  el.personalitySelect.innerHTML = '<option value="">Auto</option>';
  personalities.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.name || item.id;
    el.personalitySelect.appendChild(opt);
  });

  el.templateSelect.innerHTML = "";
  templates.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = normalizeTemplate(item.id);
    opt.textContent = item.name || item.id;
    el.templateSelect.appendChild(opt);
  });

  if (!el.templateSelect.value) el.templateSelect.value = state.framework;
}

function collectConversationConfig() {
  return {
    mode: el.modeSelect.value,
    scenario: el.scenarioSelect.value || "auto",
    personality: el.personalitySelect.value || null,
    template: normalizeTemplate(el.templateSelect.value || state.framework),
    verbosity: Number(el.verbosityInput.value || 5),
    framework: state.framework,
  };
}

function applyResolvedConfigToControls(config) {
  if (!config) return;
  el.modeSelect.value = config.mode || "auto";
  if ([...el.scenarioSelect.options].some((opt) => opt.value === config.scenario)) el.scenarioSelect.value = config.scenario;
  if ([...el.personalitySelect.options].some((opt) => opt.value === config.personality)) el.personalitySelect.value = config.personality;
  if ([...el.templateSelect.options].some((opt) => opt.value === normalizeTemplate(config.template))) el.templateSelect.value = normalizeTemplate(config.template);
  el.verbosityInput.value = Number(config.verbosity || 5);
  el.verbosityValue.textContent = String(el.verbosityInput.value);
}

function resetComposerForNewConversation() {
  state.conversationId = null;
  state.currentTurn = 0;
  state.maxTurns = 0;
  clearChat();
  hideCustomHint();
  setPrompt("");
  setResolvedConfigLabel(null);
  setConfigControlsDisabled(false);
  el.answerInput.value = "";

  if (state.settings) {
    state.framework = normalizeFramework(state.settings.default_framework);
    state.maxTurns = state.settings.max_turns;
    el.templateSelect.value = state.framework;
  } else {
    state.framework = "standard";
  }

  setFrameworkUI();
  updateProgress();
}

async function createConversationFromIdea(initialIdea) {
  const data = await api.createConversation(initialIdea, state.framework, collectConversationConfig());
  state.conversationId = data.conversation_id;
  state.framework = normalizeFramework(data.framework || data.resolved_config?.framework || state.framework);
  state.maxTurns = data.max_turns || state.maxTurns;
  state.currentTurn = data.current_turn || 1;

  clearChat();
  hideCustomHint();
  addMessage("user", initialIdea);
  addMessage("assistant", data.assistant_message);
  addAssistantTurn(data.assistant_turn);
  setFrameworkUI();
  updateProgress();
  setPrompt("");
  setResolvedConfigLabel(data.resolved_config || null);
  applyResolvedConfigToControls(data.resolved_config || null);
  setConfigControlsDisabled(true);
  await refreshHistory();
}

async function loadConversation(conversationId) {
  const data = await api.getConversation(conversationId);
  state.conversationId = data.id;
  state.framework = normalizeFramework(data.framework || data.resolved_config?.framework);
  state.maxTurns = data.max_turns;
  state.currentTurn = data.current_turn || 0;

  clearChat();
  hideCustomHint();
  data.messages.forEach((msg) => addMessage(msg.role, msg.content));

  if (data.generated_prompt?.raw_text) setPrompt(data.generated_prompt.raw_text);
  else setPrompt("");

  setResolvedConfigLabel(data.resolved_config || null);
  applyResolvedConfigToControls(data.resolved_config || null);
  setConfigControlsDisabled(true);

  setFrameworkUI();
  updateProgress();

  if (isTabletOrMobile()) el.appShell.classList.remove("history-open");
  if (isMobile()) setMobilePane("chat");
}

async function submitAnswer(content, forceGenerate = false) {
  const text = String(content || "").trim();

  if (!state.conversationId) {
    if (!text) return;
    el.answerInput.value = "";
    hideCustomHint();
    await createConversationFromIdea(text);

    if (!forceGenerate) return;

    const forceContent = "请直接生成";
    addMessage("user", forceContent);
    const data = await api.sendMessage(state.conversationId, forceContent, true);
    state.maxTurns = data.max_turns || state.maxTurns;
    setResolvedConfigLabel(data.resolved_config || state.resolvedConfig);

    if (data.completed) {
      clearActiveSelection();
      state.currentTurn = state.maxTurns;
      setPrompt(data.generated_prompt?.raw_text || "");
      addMessage("assistant", "已完成信息收集，结构化 Prompt 已生成。你可以在右侧继续编辑。");
      await refreshHistory();
    }

    updateProgress();
    return;
  }

  if (!text && !forceGenerate) return;
  const finalContent = text || "请直接生成";

  addMessage("user", finalContent);
  el.answerInput.value = "";
  hideCustomHint();

  const data = await api.sendMessage(state.conversationId, finalContent, forceGenerate);
  state.maxTurns = data.max_turns || state.maxTurns;
  setResolvedConfigLabel(data.resolved_config || state.resolvedConfig);

  if (data.completed) {
    clearActiveSelection();
    state.currentTurn = state.maxTurns;
    setPrompt(data.generated_prompt?.raw_text || "");
    addMessage("assistant", "已完成信息收集，结构化 Prompt 已生成。你可以在右侧继续编辑。");
    await refreshHistory();
    updateProgress();
    return;
  }

  state.currentTurn = data.current_turn || state.currentTurn;
  addMessage("assistant", data.assistant_message);
  addAssistantTurn(data.assistant_turn);
  updateProgress();
}

async function sendAnswer(forceGenerate = false) {
  if (!forceGenerate && state.activeSelection) {
    const selectedLabels = Array.from(state.activeSelection.selected || []);
    const merged = buildSelectionContent(selectedLabels, el.answerInput.value);
    if (merged) {
      await submitAnswer(merged, false);
      return;
    }
  }
  await submitAnswer(el.answerInput.value, forceGenerate);
}

async function savePrompt() {
  if (!state.conversationId) return;
  const content = el.promptEditor.value.trim();
  if (!content) return;
  await api.updatePrompt(state.conversationId, content);
  setPrompt(content);
  alert("Saved");
}

async function copyPrompt() {
  const content = state.promptEditing ? el.promptEditor.value : state.currentPrompt;
  if (!content.trim()) return;
  await navigator.clipboard.writeText(content);
  alert("Copied");
}

function fillSettingsForm(settings) {
  el.apiKeyInput.value = settings.api_key || "";
  el.baseUrlInput.value = settings.base_url || "";
  el.modelInput.value = settings.model || "";
  el.maxTurnsInput.value = settings.max_turns || 5;
  el.defaultFrameworkSelect.value = normalizeFramework(settings.default_framework);
}

function readSettingsForm() {
  const maxTurnsRaw = Number(el.maxTurnsInput.value || 5);
  const maxTurns = Math.max(1, Math.min(10, Number.isNaN(maxTurnsRaw) ? 5 : maxTurnsRaw));

  return {
    api_key: el.apiKeyInput.value.trim(),
    base_url: el.baseUrlInput.value.trim() || "https://api.deepseek.com",
    model: el.modelInput.value.trim() || "deepseek-chat",
    max_turns: maxTurns,
    default_framework: normalizeFramework(el.defaultFrameworkSelect.value),
  };
}

function openSettingsModal() {
  el.settingsModal.classList.remove("hidden");
}

function closeSettingsModal() {
  el.settingsModal.classList.add("hidden");
}

function toggleHistory() {
  if (isMobile()) {
    setMobilePane("history");
    return;
  }

  if (isTabletOrMobile()) {
    el.appShell.classList.toggle("history-open");
    return;
  }

  el.appShell.classList.toggle("history-collapsed");
}

async function loadSettings() {
  const settings = await api.getSettings();
  state.settings = settings;

  if (!state.conversationId) {
    state.framework = normalizeFramework(settings.default_framework);
    state.maxTurns = settings.max_turns;
    setFrameworkUI();
    updateProgress();
    if (!el.templateSelect.value) el.templateSelect.value = state.framework;
  }

  fillSettingsForm(settings);
}

async function loadPromptOptions() {
  const options = await api.getPromptOptions();
  state.promptOptions = options;
  populatePromptOptions(options);
}

function bindEvents() {
  el.newConversationBtn.onclick = () => resetComposerForNewConversation();
  el.toggleHistoryBtn.onclick = () => toggleHistory();

  el.openSettingsBtn.onclick = () => openSettingsModal();
  el.closeSettingsBtn.onclick = () => closeSettingsModal();
  el.cancelSettingsBtn.onclick = () => closeSettingsModal();

  el.saveSettingsBtn.onclick = async () => {
    try {
      const payload = readSettingsForm();
      const settings = await api.updateSettings(payload);
      state.settings = settings;
      fillSettingsForm(settings);

      if (!state.conversationId) {
        state.framework = normalizeFramework(settings.default_framework);
        state.maxTurns = settings.max_turns;
        setFrameworkUI();
        updateProgress();
      }

      closeSettingsModal();
      alert("Settings saved");
    } catch (err) {
      alert(err.message || "Save failed");
    }
  };

  el.settingsModal.addEventListener("click", (event) => {
    if (event.target === el.settingsModal) closeSettingsModal();
  });

  el.sendBtn.onclick = async () => {
    try {
      await sendAnswer(false);
    } catch (err) {
      alert(err.message || "Send failed");
    }
  };

  el.forceBtn.onclick = async () => {
    try {
      await sendAnswer(true);
    } catch (err) {
      alert(err.message || "Generate failed");
    }
  };

  el.answerInput.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();

    try {
      await sendAnswer(false);
    } catch (err) {
      alert(err.message || "Send failed");
    }
  });

  el.answerInput.addEventListener("input", () => {
    if (el.answerInput.value.trim()) hideCustomHint();
    syncActiveSelectionState();
  });

  el.editPromptBtn.onclick = () => setPromptEditing(true);
  el.savePromptBtn.onclick = async () => {
    try {
      await savePrompt();
    } catch (err) {
      alert(err.message || "Save failed");
    }
  };
  el.copyPromptBtn.onclick = async () => {
    try {
      await copyPrompt();
    } catch (err) {
      alert(err.message || "Copy failed");
    }
  };

  el.frameworkGrid.querySelectorAll(".framework-card").forEach((btn) => {
    btn.onclick = () => {
      if (state.conversationId) {
        alert("Current conversation is locked. Please create a new conversation to switch framework.");
        return;
      }
      state.framework = normalizeFramework(btn.dataset.framework);
      el.templateSelect.value = state.framework;
      setFrameworkUI();
    };
  });

  el.verbosityInput.addEventListener("input", () => {
    el.verbosityValue.textContent = String(el.verbosityInput.value);
  });

  el.templateSelect.addEventListener("change", () => {
    if (state.conversationId) return;
    state.framework = normalizeFramework(el.templateSelect.value);
    setFrameworkUI();
  });

  el.mobileTabs.querySelectorAll(".mobile-tab").forEach((btn) => {
    btn.onclick = () => setMobilePane(btn.dataset.pane);
  });

  window.addEventListener("resize", () => {
    if (!isMobile()) {
      el.appShell.classList.remove("pane-history", "pane-chat", "pane-prompt");
    } else if (!el.appShell.classList.contains("pane-history") && !el.appShell.classList.contains("pane-chat") && !el.appShell.classList.contains("pane-prompt")) {
      setMobilePane("chat");
    }

    if (!isTabletOrMobile()) {
      el.appShell.classList.remove("history-open");
    }
    closeHistoryContextMenu();
  });

  document.addEventListener("click", () => closeHistoryContextMenu());
  document.addEventListener("scroll", () => closeHistoryContextMenu(), true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeHistoryContextMenu();
  });
}

async function bootstrap() {
  bindEvents();
  if (isMobile()) {
    setMobilePane("chat");
  }

  try {
    await Promise.all([loadPromptOptions(), loadSettings()]);
    await refreshHistory();
    resetComposerForNewConversation();
  } catch (err) {
    alert(err.message || "Initialization failed");
  }
}

bootstrap();

