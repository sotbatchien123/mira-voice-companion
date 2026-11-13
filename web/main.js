import { AudioPlayer } from "./audio_player.js";
import { Avatar } from "./avatar.js";
import { streamChat } from "./chat_client.js";
import { MicError, MicRecorder } from "./mic.js";

const DEFAULT_MODEL_URL = "/models/waifu.vrm";
const HISTORY_KEY = "waifu-chat-history";
const VOICE_KEY = "waifu-voice";
const HANDSFREE_KEY = "waifu-handsfree";
// Bỏ tag khi hiển thị lại lịch sử cũ (lịch sử lưu bản gốc còn tag)
const TAG_RE = /\[[a-zA-Z_]{1,16}\][ \t]*/g; // cùng cách bỏ dấu cách với app/emotion_tags.py

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const dropHint = $("drop-hint");
const statusEl = $("status");
const log = $("log");
const form = $("composer");
const input = $("input");
const sendBtn = $("send-btn");

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
  if (health.stt && !health.stt.ok) {
    micBtn.disabled = true;
    handsFreeBtn.disabled = true;
    micBtn.title = health.stt.problem;
  }
}

// ---------- Nghe giọng nói (STT) ----------

const micBtn = $("mic-btn");
const handsFreeBtn = $("handsfree-btn");
// Lựa chọn rảnh tay được nhớ, nhưng mic chỉ mở sau cú bấm đầu tiên của người dùng (luật của trình duyệt)
const handsFreeSaved = localStorage.getItem(HANDSFREE_KEY) === "on";
let handsFree = false;
const mic = new MicRecorder({
  onSpeechStart: interruptMira,
  onUtterance: (pcm) => transcribeAndSend(pcm),
  isAssistantSpeaking: () => player.playing,
});

/** Người dùng bắt đầu nói: Mira im ngay, và nếu chữ đã xong thì dừng luôn việc tạo giọng còn lại. */
function interruptMira() {
  player.stop();
  if (inFlight?.textSaved) inFlight.controller.abort();
}

async function transcribeAndSend(pcm) {
  micBtn.classList.add("busy");
  input.placeholder = "Đang nhận dạng...";
  try {
    const res = await fetch("/api/stt", { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail ?? `Server trả về ${res.status}`);
    if (!body.text) {
      input.placeholder = "Không nghe rõ, anh nói lại nha...";
      return;
    }
    input.value = body.text;
    form.requestSubmit(); // gửi như khi gõ: cùng luật chờ/ngắt lời, cùng lịch sử
  } catch (err) {
    addBubble("error", err.message);
  } finally {
    micBtn.classList.remove("busy");
    if (input.placeholder === "Đang nhận dạng...") input.placeholder = "Nhắn gì đó cho cô ấy...";
  }
}

async function openMic() {
  try {
    await mic.start();
    return true;
  } catch (err) {
    addBubble("error", err instanceof MicError ? err.message : `Không mở được mic: ${err.message}`);
    return false;
  }
}

async function beginTalk() {
  if (micBtn.disabled || mic.manual) return;
  player.unlock(); // đang trong cú bấm: cho phép phát giọng trả lời
  if (!(await openMic())) return;
  micBtn.classList.add("listening");
  input.placeholder = "Đang nghe... thả ra để gửi";
  mic.startManual();
}

function endTalk() {
  if (!mic.manual) return;
  micBtn.classList.remove("listening");
  input.placeholder = "Nhắn gì đó cho cô ấy...";
  mic.stopManual();
  if (!handsFree) mic.stop(); // tắt đèn mic khi không dùng
}

micBtn.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  try {
    micBtn.setPointerCapture(e.pointerId); // kéo chuột ra ngoài nút vẫn nhận được lúc thả
  } catch {
    // không hỗ trợ capture: vẫn ghi âm bình thường
  }
  beginTalk();
});
micBtn.addEventListener("pointerup", endTalk);
micBtn.addEventListener("pointercancel", endTalk);

// Giữ Space khi ô nhập đang trống = bấm giữ để nói; đã gõ chữ thì Space vẫn là dấu cách
input.addEventListener("keydown", (e) => {
  if (e.code === "Space" && !input.value && !e.repeat) {
    e.preventDefault();
    beginTalk();
  }
});
input.addEventListener("keyup", (e) => {
  if (e.code === "Space") endTalk();
});

function renderHandsFree() {
  handsFreeBtn.textContent = handsFree ? "Rảnh tay: bật" : "Rảnh tay: tắt";
  handsFreeBtn.setAttribute("aria-pressed", String(handsFree));
}

async function setHandsFree(on) {
  if (on && !(await openMic())) on = false;
  handsFree = on;
  localStorage.setItem(HANDSFREE_KEY, on ? "on" : "off");
  mic.setHandsFree(on);
  if (!on && !mic.manual) mic.stop();
  renderHandsFree();
}

handsFreeBtn.addEventListener("click", () => {
  player.unlock();
  setHandsFree(!handsFree);
});
renderHandsFree();
if (handsFreeSaved) {
  handsFreeBtn.textContent = "Rảnh tay: bấm vào trang để bật";
  document.addEventListener(
    "pointerdown",
    (e) => {
      // Bấm đúng nút rảnh tay thì để handler click tự bật, tránh bật rồi lại tắt ngay
      if (e.target !== handsFreeBtn && !handsFree) setHandsFree(true);
    },
    { once: true },
  );
}

tryDefaultModel();
checkBrain();
input.focus();
