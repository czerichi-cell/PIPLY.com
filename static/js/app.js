// Piply - klientský JS (bez frameworku, jen fetch + vanilla DOM)

// --- Vlastni confirm modal (nahrazuje ošklivý native confirm()) ---

let pendingConfirmAction = null;

function showConfirmModal(message, onConfirm) {
  const modal = document.getElementById("confirm-modal");
  if (!modal) { onConfirm(); return; }
  document.getElementById("confirm-modal-title").textContent = message;
  modal.style.display = "flex";
  pendingConfirmAction = onConfirm;
}

function hideConfirmModal() {
  const modal = document.getElementById("confirm-modal");
  if (modal) modal.style.display = "none";
  pendingConfirmAction = null;
}

document.addEventListener("DOMContentLoaded", () => {
  const okBtn = document.getElementById("confirm-modal-ok");
  const cancelBtn = document.getElementById("confirm-modal-cancel");
  const overlay = document.getElementById("confirm-modal");
  if (okBtn) okBtn.addEventListener("click", () => {
    const action = pendingConfirmAction;
    hideConfirmModal();
    if (action) action();
  });
  if (cancelBtn) cancelBtn.addEventListener("click", hideConfirmModal);
  if (overlay) overlay.addEventListener("click", (e) => {
    if (e.target === overlay) hideConfirmModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideConfirmModal();
  });
});

document.addEventListener("submit", (e) => {
  const form = e.target;
  if (form.dataset && form.dataset.confirm) {
    e.preventDefault();
    showConfirmModal(form.dataset.confirm, () => form.submit());
  }
});

// --- Hezci upload obrazku: drag&drop zona s nahledem ---

function initUploadZones(root) {
  (root || document).querySelectorAll("[data-upload-zone]").forEach((zone) => {
    if (zone.dataset.wired) return;
    zone.dataset.wired = "1";

    const input = zone.querySelector("input[type=file]");
    const emptyEl = zone.querySelector(".upload-empty");
    const previewEl = zone.querySelector(".upload-preview");
    const previewImg = zone.querySelector(".upload-preview-img");

    function showPreview(src) {
      if (previewImg) previewImg.src = src;
      if (previewEl) previewEl.style.display = "block";
      if (emptyEl) emptyEl.style.display = "none";
    }

    zone.addEventListener("click", () => input && input.click());

    if (input) {
      input.addEventListener("change", () => {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => showPreview(e.target.result);
        reader.readAsDataURL(file);
      });
    }

    ["dragover", "dragenter"].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.remove("dragover");
      })
    );
    zone.addEventListener("drop", (e) => {
      if (!input || !e.dataTransfer.files.length) return;
      input.files = e.dataTransfer.files;
      input.dispatchEvent(new Event("change"));
    });
  });
}

document.addEventListener("DOMContentLoaded", () => initUploadZones());

document.addEventListener("click", async (e) => {
  const likeBtn = e.target.closest(".like-btn");
  if (likeBtn) {
    const postId = likeBtn.dataset.postId;
    try {
      const res = await fetch(`/post/${postId}/like`, { method: "POST" });
      const data = await res.json();
      likeBtn.classList.toggle("liked", data.liked);
      likeBtn.querySelector(".like-count").textContent = data.count;
    } catch (err) {
      console.error("Like failed", err);
    }
    return;
  }

  const commentToggle = e.target.closest(".toggle-comments");
  if (commentToggle) {
    const postId = commentToggle.dataset.postId;
    const box = document.getElementById(`comments-${postId}`);
    if (box) box.style.display = box.style.display === "none" ? "block" : "none";
  }
});

// --- Emoji picker: staticka sada bez nutnosti externiho API ---

const PIPLY_EMOJIS = [
  "😀","😂","🥲","😉","😍","🥳","😎","🤔","😅","😭",
  "😱","🙄","😤","😴","🤝","👍","👎","👏","🙏","💪",
  "🔥","💯","✅","❌","⚠️","🚀","📈","📉","💰","💸",
  "🐂","🐻","⏰","🎯","🧠","☕","🍀","🙌","👀","💤",
];

// --- Chat: odeslani zpravy (text/obrazek/gif) bez reloadu + polling ---

(function initChat() {
  const win = document.getElementById("chat-window");
  if (!win) return;

  const messagesBox = document.getElementById("chat-messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const imageInput = document.getElementById("chat-image-input");
  const attachBtn = document.getElementById("chat-attach-btn");
  const attachPreview = document.getElementById("chat-attach-preview");
  const attachPreviewImg = document.getElementById("chat-attach-preview-img");
  const attachRemoveBtn = document.getElementById("chat-attach-remove");
  const errorBox = document.getElementById("chat-error");

  const emojiBtn = document.getElementById("emoji-btn");
  const emojiPicker = document.getElementById("emoji-picker");
  const emojiGrid = document.getElementById("emoji-grid");

  const gifBtn = document.getElementById("gif-btn");
  const gifPicker = document.getElementById("gif-picker");
  const gifSearchInput = document.getElementById("gif-search-input");
  const gifResults = document.getElementById("gif-results");

  let lastId = parseInt(win.dataset.lastId || "0", 10);
  let gifLoadedOnce = false;
  let gifSearchTimer = null;

  function scrollToBottom() {
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }
  scrollToBottom();

  function showError(msg) {
    if (!errorBox) return;
    errorBox.textContent = msg;
    errorBox.style.display = "block";
    setTimeout(() => { errorBox.style.display = "none"; }, 4000);
  }

  function closeAllPickers() {
    if (emojiPicker) emojiPicker.classList.remove("open");
    if (gifPicker) gifPicker.classList.remove("open");
  }

  function appendMessage(m) {
    if (m.id <= lastId && messagesBox.querySelector(`[data-msg-id="${m.id}"]`)) return;
    const div = document.createElement("div");
    div.className = "bubble " + (m.mine ? "bubble-mine" : "bubble-theirs");
    div.dataset.msgId = m.id;

    if (m.image_url) {
      const img = document.createElement("img");
      img.className = "bubble-image";
      img.src = m.image_url;
      div.appendChild(img);
    }
    if (m.gif_url) {
      const gif = document.createElement("img");
      gif.className = "bubble-gif";
      gif.src = m.gif_url;
      div.appendChild(gif);
    }
    if (m.content) {
      div.appendChild(document.createTextNode(m.content));
    }
    const time = document.createElement("div");
    time.className = "bubble-time";
    time.textContent = (m.created_at || "").slice(11, 16);
    div.appendChild(time);

    messagesBox.appendChild(div);
    lastId = Math.max(lastId, m.id);
  }

  // --- Priloha obrazku ---

  if (attachBtn) attachBtn.addEventListener("click", () => imageInput.click());
  if (imageInput) {
    imageInput.addEventListener("change", () => {
      const file = imageInput.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        attachPreviewImg.src = e.target.result;
        attachPreview.style.display = "flex";
      };
      reader.readAsDataURL(file);
    });
  }
  if (attachRemoveBtn) {
    attachRemoveBtn.addEventListener("click", () => {
      imageInput.value = "";
      attachPreview.style.display = "none";
    });
  }

  // --- Odeslani zpravy (spolecne pro text/obrazek i klik na gif) ---

  async function sendMessage(fd) {
    try {
      const res = await fetch(window.PIPLY_CHAT_URL, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok || data.error) {
        showError(data.error || "Zprávu se nepodařilo odeslat.");
        return false;
      }
      appendMessage(data.message);
      scrollToBottom();
      return true;
    } catch (err) {
      showError("Zprávu se nepodařilo odeslat, zkontroluj připojení.");
      return false;
    }
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const content = input.value.trim();
      const file = imageInput && imageInput.files[0];
      if (!content && !file) return;

      const fd = new FormData();
      fd.append("content", content);
      if (file) fd.append("image", file);

      input.value = "";
      if (imageInput) imageInput.value = "";
      if (attachPreview) attachPreview.style.display = "none";

      await sendMessage(fd);
    });
  }

  // --- Emoji picker ---

  if (emojiBtn && emojiGrid) {
    PIPLY_EMOJIS.forEach((emoji) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "emoji-item";
      b.textContent = emoji;
      b.addEventListener("click", () => {
        input.value += emoji;
        input.focus();
      });
      emojiGrid.appendChild(b);
    });

    emojiBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = !emojiPicker.classList.contains("open");
      closeAllPickers();
      if (willOpen) emojiPicker.classList.add("open");
    });
  }

  // --- GIF picker (Giphy pres backend proxy) ---

  if (gifBtn && gifPicker) {
    function renderGifs(gifs) {
      gifResults.innerHTML = "";
      if (!gifs || !gifs.length) {
        gifResults.innerHTML = '<div class="picker-empty">Nic se nenašlo.</div>';
        return;
      }
      gifs.forEach((g) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "gif-item";
        const img = document.createElement("img");
        img.src = g.preview_url;
        img.loading = "lazy";
        b.appendChild(img);
        b.addEventListener("click", async () => {
          closeAllPickers();
          const fd = new FormData();
          fd.append("content", "");
          fd.append("gif_url", g.url);
          await sendMessage(fd);
        });
        gifResults.appendChild(b);
      });
    }

    async function loadGifs(query) {
      gifResults.innerHTML = '<div class="picker-empty">Načítám…</div>';
      try {
        const url = query
          ? `${window.PIPLY_GIF_SEARCH_URL}?q=${encodeURIComponent(query)}`
          : window.PIPLY_GIF_SEARCH_URL;
        const res = await fetch(url);
        const data = await res.json();
        if (data.error === "not_configured") {
          gifResults.innerHTML = '<div class="picker-empty">GIPHY_API_KEY není nastavený, viz README.</div>';
          return;
        }
        if (data.error) {
          gifResults.innerHTML = '<div class="picker-empty">GIFy se teď nepodařilo načíst.</div>';
          return;
        }
        renderGifs(data.gifs);
      } catch (err) {
        gifResults.innerHTML = '<div class="picker-empty">GIFy se teď nepodařilo načíst.</div>';
      }
    }

    gifBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = !gifPicker.classList.contains("open");
      closeAllPickers();
      if (willOpen) {
        gifPicker.classList.add("open");
        if (!gifLoadedOnce) {
          gifLoadedOnce = true;
          loadGifs("");
        }
      }
    });

    if (gifSearchInput) {
      gifSearchInput.addEventListener("input", () => {
        clearTimeout(gifSearchTimer);
        gifSearchTimer = setTimeout(() => loadGifs(gifSearchInput.value.trim()), 350);
      });
    }
  }

  document.addEventListener("click", () => closeAllPickers());

  // --- Polling na nove prichozi zpravy ---

  async function poll() {
    try {
      const res = await fetch(`${window.PIPLY_POLL_URL_BASE}?after_id=${lastId}`);
      const data = await res.json();
      if (data.messages && data.messages.length) {
        data.messages.forEach((m) => appendMessage(m));
        scrollToBottom();
      }
    } catch (err) {
      // ticho - zkusime znovu za chvili
    }
  }

  setInterval(poll, 3000);
})();

// --- Globalni live pocitadla (zpravy, notifikace) - bez nutnosti reloadu stranky ---

(function initLiveCounts() {
  const msgBadge = document.getElementById("msg-badge");
  const notifBadge = document.getElementById("notif-badge");
  if (!msgBadge && !notifBadge) return;

  function setBadge(el, count) {
    if (!el) return;
    if (count > 0) {
      el.textContent = count;
      el.style.display = "";
    } else {
      el.style.display = "none";
    }
  }

  async function refreshCounts() {
    try {
      const res = await fetch("/api/live-counts");
      const data = await res.json();
      setBadge(msgBadge, data.unread_messages);
      setBadge(notifBadge, data.unread_notifications);
    } catch (err) {
      // ticho
    }
  }

  refreshCounts();
  setInterval(refreshCounts, 5000);
})();