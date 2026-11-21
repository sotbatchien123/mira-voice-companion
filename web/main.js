import { AudioPlayer } from "./audio_player.js";
import { Avatar } from "./avatar.js";
import { streamChat } from "./chat_client.js";
import { MicError, MicRecorder } from "./mic.js";

const DEFAULT_MODEL_URL = "/models/waifu.vrm";
const HISTORY_KEY = "waifu-chat-history";
// Server chỉ dùng 40 lượt (MAX_HISTORY trong app/main.py); gửi dư 1 để server biết lịch sử bị cắt và bỏ lời Mira
// mồ côi ở đầu như trước
const SEND_TURNS = 41;
const KEEP_TURNS = 500; // localStorage có giới hạn ~5MB: lưu mãi thì vài tháng sau không lưu được nữa
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
  onSegmentStart: ({ text, emotion }) => {
    if (emotion) avatar.setEmotion(emotion);
    avatar.setSpeechText(text); // nhép miệng theo nguyên âm của đoạn đang đọc
  },
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
  if (history.length > KEEP_TURNS) history = history.slice(-KEEP_TURNS);
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

/**
 * Một lượt Mira nói: hiện chữ dần, phát giọng, lưu vào lịch sử. Dùng chung cho trả lời tin nhắn và lời Mira tự nói.
 * @returns {Promise<boolean>} true nếu Mira đã nói (false khi server báo chưa đến lúc hoặc lỗi)
 */
async function runMiraTurn({ url = "/api/chat", extra = {}, speak, pending = true, userBubble = null, userText = "" }) {
  let bubble = pending ? addBubble("assistant", "…") : null; // lời tự nói: chỉ hiện bong bóng khi có chữ thật
  let shown = "";
  // pending: trả lời tin của anh (false = Mira tự chào/hỏi thăm, tin của anh được chen ngang)
  const turn = (inFlight = { controller: new AbortController(), textSaved: false, pending });
  const { controller } = turn;
  let voiceFailed = false;
  player.stop(); // câu cũ đang đọc dở thì dừng
  if (speak) player.unlock();
  avatar.setTalking(!speak);
  const saveReply = (raw) => {
    if (turn.textSaved) return;
    turn.textSaved = true;
    history.push({ role: "assistant", content: raw });
    saveHistory();
    lastActivity = Date.now(); // đếm lại khoảng im từ lúc Mira nói xong, nhưng KHÔNG cho hỏi thăm lần nữa
    setTimeout(sendQueued); // tin anh gửi lúc Mira đang viết: gửi ngay bây giờ
  };
  try {
    const raw = await streamChat(
      history.slice(-SEND_TURNS),
      {
        onText: (t) => {
          shown += t;
          bubble ??= addBubble("assistant", "…");
          bubble.textContent = shown.trimStart() || "…";
          log.scrollTop = log.scrollHeight;
        },
        onEmotion: (em) => {
          if (!speak || voiceFailed) avatar.setEmotion(em);
        },
        onAudio: (segment) => {
          if (!turn.muted) player.enqueue(segment); // anh đã ngắt lời: phần giọng tới sau không được phát nữa
        },
        onVoiceError: (message) => {
          voiceFailed = true;
          avatar.setTalking(true);
          addBubble("error", message);
        },
        onTextDone: saveReply,
      },
      { voice: speak, signal: controller.signal, url, extra },
    );
    if (raw === null) {
      bubble?.remove();
      return false;
    }
    saveReply(raw);
    return true;
  } catch (err) {
    // Bị ngắt sau khi chữ đã lưu (người dùng gửi tin mới lúc Mira còn nói): giữ nguyên câu trả lời
    if (!turn.textSaved) {
      bubble?.remove();
      // Bỏ lượt user chưa có trả lời để lịch sử luôn xen kẽ user/assistant; bỏ cả bong bóng của nó cho khớp,
      // và trả chữ về ô nhập để anh gửi lại (không thì tải lại trang là tin biến mất)
      const dropped = url === "/api/chat" && history.at(-1)?.role === "user";
      if (dropped) {
        history.pop();
        userBubble?.remove();
        if (!input.value.trim()) input.value = userText;
      }
      if (!controller.signal.aborted && pending) {
        addBubble("error", dropped && userText ? `${err.message} (tin của anh vẫn ở ô nhập, gửi lại nha)` : err.message);
        setQueued(false); // "não" đang lỗi: đừng tự gửi tiếp tin đang chờ
      }
      saveHistory();
    }
    return false;
  } finally {
    if (inFlight === turn) {
      inFlight = null;
      lastExchange = Date.now(); // vừa có lượt trò chuyện: nói tiếp không cần gọi tên
      avatar.setTalking(false);
      if (pending) input.focus();
      setTimeout(sendQueued);
    }
  }
}

// Tin gửi lúc Mira còn đang viết câu trả lời: giữ trong ô nhập và gửi ngay khi viết xong (trước đây bị bỏ qua lặng lẽ;
// nút Gửi bị khóa nên Enter cũng không làm gì)
let queued = false;

function setQueued(on) {
  queued = on;
  sendBtn.textContent = on ? "Chờ Mira…" : "Gửi";
  sendBtn.title = on ? "Mira đang trả lời dở, viết xong em gửi tin này ngay" : "";
}

function sendQueued() {
  if (!queued) return;
  setQueued(false);
  if (input.value.trim()) form.requestSubmit();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  if (inFlight) {
    if (!inFlight.textSaved && inFlight.pending) {
      setQueued(true); // đang trả lời tin trước của anh: chờ viết xong rồi gửi
      return;
    }
    // Chữ đã xong (chỉ còn đọc giọng), hoặc Mira đang tự chào/hỏi thăm (có thể treo lâu khi model nạp nguội):
    // tin của anh được ưu tiên
    inFlight.controller.abort();
  }
  input.value = "";
  markActivity();
  lastExchange = Date.now();
  const userBubble = addBubble("user", text);
  history.push({ role: "user", content: text });
  saveHistory();
  // đang trong cú bấm/phím của người dùng nên trình duyệt cho phát âm thanh
  await runMiraTurn({ speak: voiceOn, userBubble, userText: text });
});

// ---------- Mira chủ động: chào khi mở trang, hỏi thăm khi im lâu ----------

let lastActivity = Date.now();
let checkedIn = false; // đã hỏi thăm trong khoảng im này chưa
let checkinMinutes = 0;

/** Người dùng có hoạt động (gõ, gửi, nói): đếm lại khoảng im và cho phép hỏi thăm lần sau. */
function markActivity() {
  lastActivity = Date.now();
  checkedIn = false;
}

/** Mira tự nói. Trình duyệt chưa cho phát âm thanh (chưa bấm gì) thì nói bằng chữ + miệng giả lập. */
function askMira(kind) {
  return runMiraTurn({ url: "/api/proactive", extra: { kind }, speak: voiceOn && player.unlocked, pending: false });
}

function userIsBusy() {
  return Boolean(inFlight || player.playing || mic.manual || mic.inSpeech || input.value.trim() || document.hidden);
}

setInterval(async () => {
  if (!checkinMinutes || checkedIn || userIsBusy()) return;
  if (Date.now() - lastActivity < checkinMinutes * 60_000) return;
  checkedIn = true; // một lần cho mỗi khoảng im, dù server có trả 204
  await askMira("checkin");
}, 15_000);

input.addEventListener("input", markActivity);

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
  checkinMinutes = health.proactive?.checkin_minutes ?? 0;
  wake = health.wake ?? wake;
  refreshPlaceholder();
  // Server tự quyết có nên chào không (vắng đủ lâu, chưa chào gần đây); không thì trả 204 và không hiện gì
  if (health.ok && health.proactive?.greeting) await askMira("greet");
}

// ---------- Nghe giọng nói (STT) ----------

const micBtn = $("mic-btn");
const handsFreeBtn = $("handsfree-btn");
// Lựa chọn rảnh tay được nhớ, nhưng mic chỉ mở sau cú bấm đầu tiên của người dùng (luật của trình duyệt)
const handsFreeSaved = localStorage.getItem(HANDSFREE_KEY) === "on";
let handsFree = false;

// ---------- Từ đánh thức "Mira ơi" (spec 007) ----------
// Rảnh tay mà đã im quá cửa sổ trò chuyện thì chỉ nghe câu mở đầu bằng tên Mira (server nhận diện, kể cả khi
// STT nghe nhầm tên). Đang trò chuyện, Mira đang nói, hoặc bấm giữ để nói thì không cần.
const DEFAULT_PLACEHOLDER = "Nhắn gì đó cho cô ấy...";
const WAKE_PLACEHOLDER = "Rảnh tay: gọi “Mira ơi…” để nói chuyện";
let wake = { required: false, window_seconds: 60 };
let lastExchange = Date.now();
let utteranceNeedsWake = false; // quyết định lúc bắt đầu nói, để câu dài không bị đổi luật giữa chừng

function needsWake() {
  // Không xét "đang chờ trả lời": lời chào chủ động có thể treo lâu (model nạp nguội) khi anh không có mặt;
  // lượt anh vừa gửi đã tự mở cửa sổ qua lastExchange.
  if (!handsFree || !wake.required || mic.manual || player.playing) return false;
  return Date.now() - lastExchange > wake.window_seconds * 1000;
}

function refreshPlaceholder() {
  if (input.placeholder !== DEFAULT_PLACEHOLDER && input.placeholder !== WAKE_PLACEHOLDER) return;
  input.placeholder = needsWake() ? WAKE_PLACEHOLDER : DEFAULT_PLACEHOLDER;
}
setInterval(refreshPlaceholder, 2000);

const mic = new MicRecorder({
  onSpeechStart: () => {
    utteranceNeedsWake = needsWake();
    if (utteranceNeedsWake) return; // có thể chỉ là TV/người khác: chưa ngắt lời, chưa quay sang nghe
    interruptMira();
    avatar.setListening(true);
    markActivity();
  },
  onSpeechEnd: () => avatar.setListening(false),
  onUtterance: (pcm) => transcribeAndSend(pcm, utteranceNeedsWake),
  isAssistantSpeaking: () => player.playing,
});

/** Người dùng bắt đầu nói: Mira im ngay, và nếu chữ đã xong thì dừng luôn việc tạo giọng còn lại. */
function interruptMira() {
  player.stop();
  if (inFlight) inFlight.muted = true; // chữ vẫn viết tiếp, nhưng giọng của lượt này dừng hẳn
  if (inFlight?.textSaved) inFlight.controller.abort();
}

async function transcribeAndSend(pcm, requireWake = false) {
  micBtn.classList.add("busy");
  input.placeholder = "Đang nhận dạng...";
  try {
    const res = await fetch("/api/stt", { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail ?? `Server trả về ${res.status}`);
    if (requireWake && !body.wake) {
      input.placeholder = WAKE_PLACEHOLDER; // không phải gọi Mira: lặng lẽ bỏ qua
      return;
    }
    if (!body.text) {
      input.placeholder = "Không nghe rõ, anh nói lại nha...";
      return;
    }
    const draft = input.value.trim();
    input.value = draft ? `${draft} ${body.text}` : body.text; // đã có chữ đang chờ gửi thì nối thêm, không ghi đè
    form.requestSubmit(); // gửi như khi gõ: cùng luật chờ/ngắt lời, cùng lịch sử
  } catch (err) {
    addBubble("error", err.message);
  } finally {
    micBtn.classList.remove("busy");
    if (input.placeholder === "Đang nhận dạng...") input.placeholder = DEFAULT_PLACEHOLDER;
    refreshPlaceholder();
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
  input.placeholder = DEFAULT_PLACEHOLDER;
  refreshPlaceholder();
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
  refreshPlaceholder();
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

// ---------- Trí nhớ dài hạn ----------

const memoryDialog = $("memory-dialog");
const memoryList = $("memory-list");
const episodeList = $("episode-list");

async function memoryRequest(url, method = "GET") {
  const res = await fetch(url, { method });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Server trả về ${res.status}`);
  return body;
}

const ddmm = (isoDate) => isoDate.split("-").reverse().join("/");

/** Một dòng có nút "Quên": điều đã nhớ hoặc bản tóm tắt một buổi trò chuyện. */
function memoryRow(list, emptyText, { text, when, url }) {
  const li = document.createElement("li");
  const span = document.createElement("span");
  span.textContent = text; // textContent: chữ do model sinh ra, không chèn HTML
  const day = document.createElement("small");
  day.textContent = when;
  const forget = document.createElement("button");
  forget.type = "button";
  forget.textContent = "Quên";
  forget.addEventListener("click", async () => {
    try {
      await memoryRequest(url, "DELETE");
      li.remove();
      if (!list.children.length) fillList(list, [], emptyText);
    } catch (err) {
      addBubble("error", err.message);
    }
  });
  li.append(span, day, forget);
  return li;
}

function fillList(list, rows, emptyText) {
  list.replaceChildren();
  if (!rows.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = emptyText;
    list.append(li);
    return;
  }
  list.append(...rows.map((row) => memoryRow(list, emptyText, row)));
}

function renderMemory(facts, episodes = [], enabled = true) {
  const off = "Trí nhớ đang tắt (MEMORY_ENABLED=false).";
  fillList(memoryList, facts.map((f) => ({
    text: f.text, when: ddmm(f.said_on), url: `/api/memory/${encodeURIComponent(f.id)}`,
  })), enabled ? "Mira chưa nhớ gì. Kể cho em nghe về anh đi!" : off);
  fillList(episodeList, episodes.map((e) => ({
    text: e.summary, when: `${ddmm(e.date)} ${e.started}`, url: `/api/memory/episodes/${encodeURIComponent(e.id)}`,
  })), enabled ? "Chưa có buổi nào được tóm tắt." : off);
}

$("memory-btn").addEventListener("click", async () => {
  try {
    const { facts, episodes = [], enabled } = await memoryRequest("/api/memory");
    renderMemory(facts, episodes, enabled);
    memoryDialog.showModal();
  } catch (err) {
    addBubble("error", `Không đọc được trí nhớ: ${err.message}`);
  }
});
$("memory-close").addEventListener("click", () => memoryDialog.close());
$("memory-clear").addEventListener("click", async () => {
  if (!confirm("Mira sẽ quên hết mọi điều anh từng kể và mọi buổi trò chuyện. Chắc chưa?")) return;
  try {
    await memoryRequest("/api/memory", "DELETE");
    renderMemory([]);
  } catch (err) {
    addBubble("error", err.message);
  }
});

tryDefaultModel();
checkBrain();
input.focus();
