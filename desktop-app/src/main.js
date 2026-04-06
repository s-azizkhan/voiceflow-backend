const HTTP_BASE = "http://localhost:8765";

let serverStatus = "offline"; // offline | online
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let lastRecordingBlobUrl = null;
let currentStream = null;
let audioPlayer = null;

// ── DOM refs ────────────────────────────────────────────────────────────────

const statusBadge = document.getElementById("status-badge");
const hint = document.getElementById("hint");
const liveDisplay = document.getElementById("live-display");
const currentLine = document.getElementById("current-line");
const toggleBtn = document.getElementById("toggle-btn");
const uploadBtn = document.getElementById("upload-btn");
const notification = document.getElementById("notification");
const resultArea = document.getElementById("result-area");
//const resultText = document.getElementById("result-text");
const copyBtn = document.getElementById("copy-btn");
const playBtn = document.getElementById("play-btn");

// ── Debug log helper ─────────────────────────────────────────────────────────
const DEBUG = true;
let logNr = 0;
function log(...args) {
  if (DEBUG) console.log("[VoiceFlow]", logNr++, ...args);
}

// ── Server health check ────────────────────────────────────────────────────────

async function checkServer() {
  log("checkServer: checking...");
  try {
    const isHealthy = await window.__TAURI__.core.invoke("check_server_health");
    log("checkServer: result =", isHealthy);
    if (isHealthy) {
      serverStatus = "online";
      statusBadge.textContent = "Online";
      statusBadge.className = "badge online";
      return true;
    }
  } catch (e) {
    console.warn("[VoiceFlow] Health check failed:", e);
  }
  serverStatus = "offline";
  statusBadge.textContent = "Offline";
  statusBadge.className = "badge offline";
  log("checkServer: server offline");
  return false;
}

async function ensureServer() {
  if (serverStatus === "online") return true;
  log("ensureServer: server not online, attempting start...");
  const started = await window.__TAURI__.core.invoke("start_server").catch(() => false);
  log("ensureServer: start_server returned =", started);
  if (started) {
    await new Promise(r => setTimeout(r, 1500));
  }
  return await checkServer();
}

// ── Tauri event listeners ──────────────────────────────────────────────────────

window.__TAURI__.event.listen("hotkey-start", async () => {
  log("EVENT: hotkey-start");
  if (!isRecording) await startRecording();
});

window.__TAURI__.event.listen("hotkey-stop", async () => {
  log("EVENT: hotkey-stop");
  if (isRecording) await stopRecording();
});

// ── Recording (MediaRecorder → REST API) ───────────────────────────────────

async function startRecording() {
  log("startRecording: called, isRecording=", isRecording);
  if (isRecording) return;
  if (!(await ensureServer())) {
    log("startRecording: ensureServer failed, showing notification");
    showNotification("Server unavailable");
    return;
  }

  try {
    currentStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    log("startRecording: mic permission granted");
  } catch (e) {
    log("startRecording: mic permission denied:", e.message);
    showNotification("Microphone access denied");
    return;
  }

  // Revoke old recording URL if exists
  if (lastRecordingBlobUrl) {
    URL.revokeObjectURL(lastRecordingBlobUrl);
    lastRecordingBlobUrl = null;
  }

  // Stop any existing recorder before creating a new one
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.ondataavailable = null;
    mediaRecorder.onstop = null;
    mediaRecorder.stop();
  }
  mediaRecorder = null;

  audioChunks = [];
  mediaRecorder = new MediaRecorder(currentStream, { mimeType: 'audio/webm;codecs=opus' });

  mediaRecorder.ondataavailable = (e) => {
    log("mediaRecorder: dataavailable", e.data.size);
    if (e.data.size > 0) audioChunks.push(e.data);
  };

  mediaRecorder.onstop = async () => {
    log("mediaRecorder: onstop");
    await handleRecordingStop();
  };

  mediaRecorder.start(100);
  isRecording = true;
  setRecordingUI(true);
  resultArea.hidden = true;
  liveDisplay.innerHTML = '<span class="hint">Recording...</span>';
}

async function stopRecording() {
  log("stopRecording: called, isRecording=", isRecording);
  if (!isRecording || !mediaRecorder) return;

  return new Promise((resolve) => {
    const stream = currentStream;
    const mr = mediaRecorder;
    // Prevent ondataavailable from firing after we start processing
    mr.ondataavailable = null;
    mr.onstop = async () => {
      log("mediaRecorder: onstop");
      stream.getTracks().forEach(t => t.stop());
      isRecording = false;
      mediaRecorder = null;
      setRecordingUI(false);
      await handleRecordingStop();
      resolve();
    };
    mr.stop();
  });
}

async function handleRecordingStop() {
  log("handleRecordingStop: audioChunks =", audioChunks.length);

  if (audioChunks.length === 0) {
    liveDisplay.innerHTML = '<span class="hint">No audio recorded</span>';
    return;
  }

  const blob = new Blob(audioChunks, { type: 'audio/webm' });
  audioChunks = []; // clear immediately to prevent stale data on next recording
  log("handleRecordingStop: blob size =", blob.size);

  if (blob.size === 0) {
    liveDisplay.innerHTML = '<span class="hint">No audio recorded</span>';
    return;
  }

  lastRecordingBlobUrl = URL.createObjectURL(blob);

  liveDisplay.innerHTML = '<span class="hint">Transcribing...</span>';

  const formData = new FormData();
  formData.append("file", blob, "recording.webm");

  try {
    const resp = await fetch(HTTP_BASE + "/transcribe/file", {
      method: "POST",
      body: formData,
    });
    log("handleRecordingStop: response status =", resp.status);

    const data = await resp.json();
    log("handleRecordingStop: response data =", data);
    const text = (data.text || "").trim();

    if (text) {
      liveDisplay.innerHTML = `<span class="live-text">${escapeHtml(text)}</span>`;
      injectOrCopy(text);
    } else {
      liveDisplay.innerHTML = '<span class="hint">No speech detected</span>';
    }
  } catch (e) {
    liveDisplay.innerHTML = '<span class="hint">Transcription failed</span>';
    console.error("[VoiceFlow] Transcription error:", e);
  }
}

function playLastRecording() {
  log("playLastRecording: url =", lastRecordingBlobUrl);
  if (!lastRecordingBlobUrl) {
    showNotification("No recording to play");
    return;
  }
  if (!audioPlayer) {
    audioPlayer = new Audio();
  }
  audioPlayer.src = lastRecordingBlobUrl;
  audioPlayer.play();
}

function injectOrCopy(text) {
  log("injectOrCopy: text =", text);
  const active = document.activeElement;
  log("injectOrCopy: activeElement =", active.tagName, active.id, active.className);
  if (
    active &&
    (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)
  ) {
    if (active.isContentEditable) {
      active.textContent = text;
      active.dispatchEvent(new InputEvent("input", { bubbles: true }));
    } else {
      const start = active.selectionStart ?? active.value.length;
      const end = active.selectionEnd ?? active.value.length;
      active.setRangeText(text, start, end, "end");
      active.dispatchEvent(new InputEvent("input", { bubbles: true }));
    }
    showNotification("Inserted");
  } else {
    log("injectOrCopy: no focused input, copying to clipboard");
    navigator.clipboard.writeText(text).then(() => {
      showNotification("Copied to clipboard!");
    });
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function setRecordingUI(recording) {
  log("setRecordingUI:", recording);
  if (recording) {
    statusBadge.textContent = "Recording";
    statusBadge.className = "badge listening";
    toggleBtn.textContent = "Stop Recording";
    toggleBtn.className = "btn btn-primary listening";
  } else {
    statusBadge.textContent = serverStatus === "online" ? "Online" : "Offline";
    statusBadge.className = serverStatus === "online" ? "badge online" : "badge offline";
    toggleBtn.textContent = "Start Recording";
    toggleBtn.className = "btn btn-primary";
  }
}

function showNotification(text) {
  log("showNotification:", text);
  notification.textContent = text;
  notification.hidden = false;
  notification.className = "notification";
  void notification.offsetWidth;
  notification.className = "notification";
  setTimeout(() => { notification.hidden = true; }, 2000);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Button handlers ───────────────────────────────────────────────────────────

toggleBtn.addEventListener("click", async () => {
  log("toggleBtn: click, isRecording=", isRecording);
  if (isRecording) {
    await stopRecording();
  } else {
    await startRecording();
  }
});

uploadBtn.addEventListener("click", async () => {
  log("uploadBtn: click");
  if (!(await ensureServer())) {
    showNotification("Server unavailable");
    return;
  }

  const { open } = window.__TAURI__.dialog;
  const selected = await open({
    multiple: false,
    filters: [{
      name: "Audio",
      extensions: ["wav", "mp3", "flac", "ogg", "m4a", "aac", "wma"],
    }],
  });

  if (!selected) {
    log("uploadBtn: no file selected");
    return;
  }

  log("uploadBtn: selected file =", selected);
  const filePath = selected;
  liveDisplay.innerHTML = '<span class="hint">Transcribing...</span>';

  try {
    const { readFile } = window.__TAURI__.fs;
    const contents = await readFile(filePath);
    const blob = new Blob([contents]);

    const formData = new FormData();
    formData.append("file", blob, filePath.split("/").pop());

    log("uploadBtn: posting to /transcribe/file");
    const resp = await fetch(HTTP_BASE + "/transcribe/file", {
      method: "POST",
      body: formData,
    });
    log("uploadBtn: response status =", resp.status);

    const data = await resp.json();
    log("uploadBtn: response data =", data);
    const text = (data.text || "").trim();

    if (text) {
      liveDisplay.innerHTML = `<span class="live-text">${escapeHtml(text)}</span>`;
      injectOrCopy(text);
    } else {
      liveDisplay.innerHTML = '<span class="hint">No speech detected</span>';
    }
  } catch (e) {
    liveDisplay.innerHTML = '<span class="hint">Upload failed</span>';
    console.error("[VoiceFlow] Upload error:", e);
  }
});

// ── Copy button ────────────────────────────────────────────────────────────────

copyBtn.addEventListener("click", () => {
  const text = liveDisplay.textContent;
  if (text) {
    navigator.clipboard.writeText(text).then(() => {
      showNotification("Copied!");
    });
  }
});

// ── Play button ────────────────────────────────────────────────────────────────

playBtn.addEventListener("click", () => {
  playLastRecording();
});

// ── Init ───────────────────────────────────────────────────────────────────────

async function init() {
  log("init: starting...");
  await checkServer();
  if (serverStatus === "online") {
    setRecordingUI(false);
  }

  setInterval(async () => {
    const wasOffline = serverStatus === "offline";
    await checkServer();
    if (wasOffline && serverStatus === "online") {
      setRecordingUI(isRecording);
    } else if (serverStatus === "offline" && !isRecording) {
      statusBadge.textContent = "Offline";
      statusBadge.className = "badge offline";
    }
  }, 5000);
  log("init: done");
}

init();
