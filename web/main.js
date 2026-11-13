import { AudioPlayer } from "./audio_player.js";
import { Avatar } from "./avatar.js";
import { streamChat } from "./chat_client.js";

const DEFAULT_MODEL_URL = "/models/waifu.vrm";
const HISTORY_KEY = "waifu-chat-history";
const VOICE_KEY = "waifu-voice";
// Bỏ tag khi hiển thị lại lịch sử cũ (lịch sử lưu bản gốc còn tag)
const TAG_RE = /\[[a-zA-Z_]{1,16}\][ \t]*/g; // cùng cách bỏ dấu cách với app/emotion_tags.py

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const dropHint = $("drop-hint");
const statusEl = $("status");
const log = $("log");
const form = $("composer");
const input = $("input");
const sendBtn = form.querySelector("button");

const avatar = new Avatar(stage);
const player = new AudioPlayer({
  onLevel: (level) => avatar.setMouthLevel(level),
  // Có giọng thì đổi mặt đúng lúc câu đó được đọc, không phải lúc chữ hiện ra
  onSegmentStart: ({ emotion }) => emotion && avatar.setEmotion(emotion),
});

// ---------- Giọng nói ----------

const voiceBtn = $("voice-btn");
let voiceOn = localStorage.getItem(VOICE_KEY) !== "off"; // mặc định bật

function renderVoice() {
  voiceBtn.textContent = voiceOn ? "Giọng: bật" : "Giọng: tắt";
  voiceBtn.setAttribute("aria-pressed", String(voiceOn));
}
voiceBtn.addEventListener("click", () => {
  voiceOn = !voiceOn;
  localStorage.setItem(VOICE_KEY, voiceOn ? "on" : "off");
  if (voiceOn) player.unlock();
  else player.stop();
  renderVoice();
});
renderVoice();

// ---------- Nạp model ----------

async function loadModel(source) {
  statusEl.textContent = "Đang tải model...";
  try {
    await avatar.load(source);
    dropHint.classList.add("hidden");
    statusEl.textContent = "";
  } catch (err) {
    statusEl.textContent = `Không tải được model: ${err.message}`;
  }
}

async function tryDefaultModel() {
  const res = await fetch(DEFAULT_MODEL_URL, { method: "HEAD" }).catch(() => null);
  if (res?.ok) await loadModel(DEFAULT_MODEL_URL);
}

$("file-input").addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (file) loadModel(file);
});
stage.addEventListener("dragover", (e) => {
  e.preventDefault();
  stage.classList.add("dragging");
});
stage.addEventListener("dragleave", () => stage.classList.remove("dragging"));
stage.addEventListener("drop", (e) => {
  e.preventDefault();
  stage.classList.remove("dragging");
  const file = e.dataTransfer?.files[0];
  if (file?.name.toLowerCase().endsWith(".vrm")) loadModel(file);
  else statusEl.textContent = "Chỉ nhận file .vrm thôi nha";
});

// ---------- Chat ----------

let history = loadHistory();
let inFlight = null;

function loadHistory() {
  try {
    const raw = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return []; // dữ liệu cũ hỏng -> bắt đầu lại, không chặn app
  }
}
function saveHistory() {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function addBubble(role, text) {
  const li = document.createElement("li");
  li.className = `msg ${role}`;
  li.textContent = text;
  log.appendChild(li);
  log.scrollTop = log.scrollHeight;
  return li;
}

for (const turn of history) {
  addBubble(turn.role, turn.role === "assistant" ? turn.content.replace(TAG_RE, "").trim() : turn.content);
}

$("clear-btn").addEventListener("click", () => {
  inFlight?.controller.abort();
  player.stop();
  history = [];
  saveHistory();
  log.replaceChildren();
  avatar.setEmotion("neutral");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  if (inFlight) {
    // Chữ của lượt trước đã xong (chỉ còn đang tạo/đọc giọng) thì cho ngắt lời; còn đang viết chữ thì chờ
    if (!inFlight.textSaved) return;
    inFlight.controller.abort();
  }
  input.value = "";

  addBubble("user", text);
  history.push({ role: "user", content: text });
  saveHistory();

  const bubble = addBubble("assistant", "…");
  let shown = "";
  const turn = (inFlight = { controller: new AbortController(), textSaved: false });
  const { controller } = turn;
  const speak = voiceOn;
  let voiceFailed = false;
  sendBtn.disabled = true;
  player.stop(); // câu cũ đang đọc dở thì dừng
  if (speak) player.unlock(); // đang trong cú bấm của người dùng nên trình duyệt cho phát âm thanh
  avatar.setTalking(!speak);
  const saveReply = (raw) => {
    if (turn.textSaved) return;
    turn.textSaved = true;
    history.push({ role: "assistant", content: raw });
    saveHistory();
    sendBtn.disabled = false;
  };
  try {
    const raw = await streamChat(
      history,
      {
        onText: (t) => {
          shown += t;
          bubble.textContent = shown.trimStart() || "…";
          log.scrollTop = log.scrollHeight;
        },
        onEmotion: (em) => {
          if (!speak || voiceFailed) avatar.setEmotion(em);
        },
        onAudio: (segment) => player.enqueue(segment),
        onVoiceError: (message) => {
          voiceFailed = true;
          avatar.setTalking(true);
          addBubble("error", message);
        },
        onTextDone: saveReply,
      },
      { voice: speak, signal: controller.signal },
    );
    saveReply(raw);
  } catch (err) {
    // Bị ngắt sau khi chữ đã lưu (người dùng gửi tin mới lúc Mira còn nói): giữ nguyên câu trả lời
    if (!turn.textSaved) {
      bubble.remove();
      if (!controller.signal.aborted) addBubble("error", err.message);
      // Bỏ lượt user chưa có trả lời để lịch sử luôn xen kẽ user/assistant
      if (history.at(-1)?.role === "user") history.pop();
      saveHistory();
    }
  } finally {
    if (inFlight === turn) {
      inFlight = null;
      sendBtn.disabled = false;
      avatar.setTalking(false);
      input.focus();
    }
  }
});

// Báo sớm nếu "não" chưa sẵn sàng (Ollama chưa bật, chưa pull model, thiếu key) thay vì đợi gửi tin mới biết
async function checkBrain() {
  const health = await fetch("/api/health").then((r) => r.json()).catch(() => null);
  if (!health) return addBubble("error", "Không gọi được server. Server còn chạy không?");
  if (!health.ok) addBubble("error", health.problem);
  if (voiceOn && health.voice && !health.voice.ok) addBubble("error", health.voice.problem);
}

tryDefaultModel();
checkBrain();
input.focus();
