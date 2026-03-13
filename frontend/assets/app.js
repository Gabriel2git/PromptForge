const state = {
  conversationId: null,
  currentPrompt: "",
};

const el = {
  ideaInput: document.getElementById("ideaInput"),
  answerInput: document.getElementById("answerInput"),
  chatBox: document.getElementById("chatBox"),
  promptEditor: document.getElementById("promptEditor"),
  historyList: document.getElementById("historyList"),
};

const api = {
  async createConversation(initial_idea) {
    const res = await fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_idea }),
    });
    if (!res.ok) throw new Error("创建会话失败");
    return res.json();
  },

  async sendMessage(conversationId, content, force_generate = false) {
    const res = await fetch(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, force_generate }),
    });
    if (!res.ok) throw new Error("发送消息失败");
    return res.json();
  },

  async listConversations() {
    const res = await fetch("/api/conversations");
    if (!res.ok) throw new Error("加载历史失败");
    return res.json();
  },

  async getConversation(conversationId) {
    const res = await fetch(`/api/conversations/${conversationId}`);
    if (!res.ok) throw new Error("读取会话失败");
    return res.json();
  },

  async updatePrompt(conversationId, raw_text) {
    const res = await fetch(`/api/conversations/${conversationId}/prompt`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text }),
    });
    if (!res.ok) throw new Error("保存失败");
    return res.json();
  },
};

function addMessage(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = content;
  el.chatBox.appendChild(div);
  el.chatBox.scrollTop = el.chatBox.scrollHeight;
}

function clearChat() {
  el.chatBox.innerHTML = "";
}

function renderHistory(items) {
  el.historyList.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${item.status === "completed" ? "已完成" : "进行中"} | ${item.initial_idea.slice(0, 26)}`;
    li.onclick = () => loadConversation(item.id);
    el.historyList.appendChild(li);
  });
}

async function refreshHistory() {
  const items = await api.listConversations();
  renderHistory(items);
}

async function loadConversation(conversationId) {
  const data = await api.getConversation(conversationId);
  state.conversationId = data.id;
  clearChat();
  data.messages.forEach((m) => addMessage(m.role, m.content));

  if (data.generated_prompt?.raw_text) {
    state.currentPrompt = data.generated_prompt.raw_text;
    el.promptEditor.value = state.currentPrompt;
  } else {
    state.currentPrompt = "";
    el.promptEditor.value = "";
  }
}

async function startConversation() {
  const idea = el.ideaInput.value.trim();
  if (!idea) return;

  const data = await api.createConversation(idea);
  state.conversationId = data.conversation_id;
  clearChat();
  addMessage("assistant", data.assistant_message);
  el.promptEditor.value = "";
  await refreshHistory();
}

async function sendAnswer(forceGenerate = false) {
  if (!state.conversationId) {
    alert("请先开始对话");
    return;
  }

  const content = el.answerInput.value.trim() || (forceGenerate ? "请直接生成" : "");
  if (!content) return;

  addMessage("user", content);
  el.answerInput.value = "";

  const data = await api.sendMessage(state.conversationId, content, forceGenerate);
  if (data.completed) {
    const prompt = data.generated_prompt.raw_text || "";
    state.currentPrompt = prompt;
    el.promptEditor.value = prompt;
    addMessage("assistant", "已完成信息收集，结构化提示词已生成。你可以在右侧继续编辑。");
    await refreshHistory();
    return;
  }

  addMessage("assistant", data.assistant_message);
}

async function savePrompt() {
  if (!state.conversationId) return;
  const content = el.promptEditor.value.trim();
  if (!content) return;
  await api.updatePrompt(state.conversationId, content);
  alert("已保存");
}

async function copyPrompt() {
  const content = el.promptEditor.value;
  if (!content.trim()) return;
  await navigator.clipboard.writeText(content);
  alert("已复制到剪贴板");
}

document.getElementById("startBtn").onclick = () => startConversation();
document.getElementById("sendBtn").onclick = () => sendAnswer(false);
document.getElementById("forceBtn").onclick = () => sendAnswer(true);
document.getElementById("savePromptBtn").onclick = () => savePrompt();
document.getElementById("copyPromptBtn").onclick = () => copyPrompt();
document.getElementById("newConversationBtn").onclick = () => {
  state.conversationId = null;
  clearChat();
  el.promptEditor.value = "";
  el.ideaInput.value = "";
  el.answerInput.value = "";
};

el.answerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendAnswer(false);
});

refreshHistory();
