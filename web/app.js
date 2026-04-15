const API_URL = "http://localhost:8000";
const SESSION_ID = crypto.randomUUID();

const chatContainer = document.getElementById("chatContainer");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

const SOURCE_TYPE_LABEL = {
  video: "VIDEO",
  document: "DOC",
  excel: "EXCEL",
  image: "IMAGE",
};

userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

function askSuggestion(btn) {
  userInput.value = btn.textContent;
  sendMessage();
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeWelcome() {
  const w = chatContainer.querySelector(".welcome-msg");
  if (w) w.remove();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function renderSourceCards(sources) {
  if (!sources || sources.length === 0) return "";
  const cards = sources
    .map((s) => {
      const typeKey = (s.source_type || "video").toLowerCase();
      const label = SOURCE_TYPE_LABEL[typeKey] || typeKey.toUpperCase();
      const displayName = s.chu_de || s.video || "";
      const time = s.time ? `<span class="timestamp">${escapeHtml(s.time)}</span>` : "";
      const scoreValue = (s.rerank_score ?? s.score ?? 0) * 100;
      const scoreBadge = `<span class="score-badge">${scoreValue.toFixed(0)}%</span>`;
      const inner = `
        <span class="source-type">[${label}]</span>
        <span class="source-name">${escapeHtml(displayName)}</span>
        ${time}
        ${scoreBadge}
      `;
      if (s.link) {
        return `<a class="source-card" href="${s.link}" target="_blank" rel="noopener">${inner}</a>`;
      }
      return `<div class="source-card">${inner}</div>`;
    })
    .join("");
  return `<div class="sources"><div class="sources-title">Nguồn tham khảo</div>${cards}</div>`;
}

function addMessage(role, text, sources, confidence) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatarText = role === "user" ? "B" : "AI";
  const sourcesHtml = role === "bot" ? renderSourceCards(sources) : "";
  const confidenceBadge =
    role === "bot" && confidence
      ? `<span class="confidence confidence-${confidence}">${confidence}</span>`
      : "";
  const copyBtn =
    role === "bot"
      ? `<button class="copy-btn" type="button" onclick="copyAnswer(this)">Copy</button>`
      : "";

  div.innerHTML = `
    <div class="avatar">${avatarText}</div>
    <div class="bubble">
      <div class="answer-text">${escapeHtml(text)}</div>
      ${confidenceBadge}
      ${sourcesHtml}
      ${copyBtn}
    </div>
  `;

  chatContainer.appendChild(div);
  scrollToBottom();
  return div;
}

function copyAnswer(btn) {
  const bubble = btn.closest(".bubble");
  if (!bubble) return;
  const text = bubble.querySelector(".answer-text")?.innerText || "";
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = "Đã copy";
    setTimeout(() => {
      btn.textContent = original;
    }, 1500);
  });
}
window.copyAnswer = copyAnswer;

function addTypingIndicator() {
  const div = document.createElement("div");
  div.className = "message bot";
  div.id = "typing";
  div.innerHTML = `
    <div class="avatar">AI</div>
    <div class="bubble">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>
  `;
  chatContainer.appendChild(div);
  scrollToBottom();
}

function removeTypingIndicator() {
  const el = document.getElementById("typing");
  if (el) el.remove();
}

let isSending = false;

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || isSending) return;

  isSending = true;
  removeWelcome();
  addMessage("user", text);

  userInput.value = "";
  userInput.style.height = "auto";
  sendBtn.disabled = true;

  addTypingIndicator();

  try {
    const res = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    });
    if (!res.ok || !res.body) throw new Error(`Server error: ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let botDiv = null;
    let answerEl = null;
    let accumulated = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames separated by blank line.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        const payload = JSON.parse(line.slice(5).trim());

        if (payload.type === "meta") {
          removeTypingIndicator();
          botDiv = addMessage("bot", "", payload.sources, payload.confidence);
          answerEl = botDiv.querySelector(".answer-text");
        } else if (payload.type === "delta") {
          accumulated += payload.text;
          if (answerEl) {
            answerEl.textContent = accumulated;
            scrollToBottom();
          }
        } else if (payload.type === "done") {
          if (answerEl) {
            answerEl.textContent = payload.answer || accumulated;
            scrollToBottom();
          }
        }
      }
    }

    if (!botDiv) {
      removeTypingIndicator();
      addMessage("bot", "(không có phản hồi)", null, null);
    }
  } catch (err) {
    removeTypingIndicator();
    addMessage("bot", `Lỗi kết nối: ${err.message}`, null, null);
  } finally {
    isSending = false;
    sendBtn.disabled = false;
    userInput.focus();
  }
}
window.sendMessage = sendMessage;
window.askSuggestion = askSuggestion;
