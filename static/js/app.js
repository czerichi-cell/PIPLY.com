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

// --- Feed: realtime banner "nove prispevky" bez automatickeho reloadu (nechceme skakat obsahem pod rukama) ---

(function initFeedRealtime() {
  const banner = document.getElementById("feed-new-posts-banner");
  const list = document.getElementById("feed-posts-list");
  if (!banner || !list || !window.PIPLY_FEED_CHECK_URL) return;

  let lastId = window.PIPLY_FEED_LAST_ID || 0;

  async function checkNew() {
    try {
      const res = await fetch(`${window.PIPLY_FEED_CHECK_URL}?after_id=${lastId}`);
      const data = await res.json();
      if (data.new_count > 0) {
        banner.textContent = data.new_count === 1 ? "1 nový příspěvek – klikni pro zobrazení" : `${data.new_count} nové příspěvky – klikni pro zobrazení`;
        banner.style.display = "block";
      }
    } catch (err) {
      // ticho
    }
  }

  banner.addEventListener("click", async () => {
    try {
      const res = await fetch(`${window.PIPLY_FEED_FRAGMENT_URL}?after_id=${lastId}`);
      const html = await res.text();
      const wrapper = document.createElement("div");
      wrapper.innerHTML = html;
      const newPosts = Array.from(wrapper.children);
      newPosts.reverse().forEach((el) => list.prepend(el));
      const ids = newPosts
        .map((el) => parseInt((el.id || "").replace("post-", ""), 10))
        .filter((n) => !isNaN(n));
      if (ids.length) lastId = Math.max(lastId, ...ids);
      banner.style.display = "none";
      initUploadZones(list);
    } catch (err) {
      // ticho
    }
  });

  setInterval(checkNew, 6000);
})();

// --- Zpravy: realtime refresh seznamu konverzaci na strance inboxu (mimo konkretni vlakno) ---

(function initInboxRealtime() {
  const list = document.getElementById("conversations-list");
  if (!list || !window.PIPLY_INBOX_REFRESH_URL) return;

  async function refresh() {
    try {
      const res = await fetch(window.PIPLY_INBOX_REFRESH_URL);
      const html = await res.text();
      list.innerHTML = html;
    } catch (err) {
      // ticho
    }
  }

  setInterval(refresh, 4000);
})();

// --- Toasty (docasna upozorneni v pravem hornim rohu, sama zmizi) ---

function showToast(title, body, opts) {
  opts = opts || {};
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <div class="toast-title">${title}</div>
    ${body ? `<div class="toast-body">${body}</div>` : ""}
  `;
  if (opts.href) {
    toast.style.cursor = "pointer";
    toast.addEventListener("click", () => { window.location.href = opts.href; });
  }
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));

  const remove = () => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 250);
  };
  const timer = setTimeout(remove, opts.duration || 4500);
  toast.addEventListener("mouseenter", () => clearTimeout(timer));
}

// --- Globalni live pocitadla (zpravy, notifikace) - bez nutnosti reloadu stranky, + toast na nove notifikace ---

(function initLiveCounts() {
  const msgBadge = document.getElementById("msg-badge");
  const notifBadge = document.getElementById("notif-badge");
  const widgetBadge = document.getElementById("chat-widget-badge");
  if (!window.PIPLY_LOGGED_IN) return;

  let lastSeenNotifId = null;
  let firstRun = true;

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
      const res = await fetch(window.PIPLY_LIVE_COUNTS_URL || "/api/live-counts");
      const data = await res.json();
      setBadge(msgBadge, data.unread_messages);
      setBadge(notifBadge, data.unread_notifications);
      setBadge(widgetBadge, data.unread_messages);

      const latest = data.latest_notification;
      if (latest) {
        if (firstRun) {
          lastSeenNotifId = latest.id;
        } else if (lastSeenNotifId === null || latest.id > lastSeenNotifId) {
          lastSeenNotifId = latest.id;
          const who = latest.actor_display_name || latest.actor_username || "";
          let href = "/notifications";
          if (latest.type === "message" && latest.actor_username) {
            href = window.PIPLY_WIDGET_SEND_URL_BASE
              ? window.PIPLY_WIDGET_SEND_URL_BASE.replace("__USER__", latest.actor_username)
              : "/notifications";
          }
          showToast(who ? `<b>${who}</b>` : "Nová notifikace", latest.message || "", { href });
        }
      }
      firstRun = false;
    } catch (err) {
      // ticho
    }
  }

  refreshCounts();
  setInterval(refreshCounts, 5000);
})();

// --- Plovouci chat widget (bublina vpravo dole, jako u IG na pocitaci) ---

(function initChatWidget() {
  const widget = document.getElementById("chat-widget");
  const bubble = document.getElementById("chat-widget-bubble");
  const panel = document.getElementById("chat-widget-panel");
  const closeBtn = document.getElementById("chat-widget-close");
  const backBtn = document.getElementById("chat-widget-back");
  const title = document.getElementById("chat-widget-title");
  const body = document.getElementById("chat-widget-body");
  if (!widget || !window.PIPLY_LOGGED_IN) return;

  // Na strance Zprav uz je plnohodnotny chat - widget tam schovame, at se to nebije
  if (window.location.pathname.startsWith("/messages")) {
    widget.style.display = "none";
    return;
  }

  let pollTimer = null;
  let currentUsername = null;

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  function openPanel() {
    panel.style.display = "flex";
    bubble.classList.add("is-open");
    loadConversationList();
  }
  function closePanel() {
    panel.style.display = "none";
    bubble.classList.remove("is-open");
    stopPolling();
  }

  bubble.addEventListener("click", () => {
    if (panel.style.display === "none") openPanel(); else closePanel();
  });
  closeBtn.addEventListener("click", closePanel);
  backBtn.addEventListener("click", () => { stopPolling(); currentUsername = null; loadConversationList(); });

  async function loadConversationList() {
    title.textContent = "Zprávy";
    backBtn.style.display = "none";
    body.innerHTML = '<div class="chat-widget-loading">Načítám…</div>';
    try {
      const res = await fetch(window.PIPLY_WIDGET_CONV_LIST_URL);
      const html = await res.text();
      const wrap = document.createElement("div");
      wrap.className = "chat-widget-conv-list";
      wrap.innerHTML = html;
      body.innerHTML = "";
      body.appendChild(wrap);
      wrap.querySelectorAll(".conv-row").forEach((row) => {
        row.addEventListener("click", (e) => {
          e.preventDefault();
          const href = row.getAttribute("href") || "";
          const parts = href.split("/").filter(Boolean);
          const username = parts[parts.length - 1];
          if (username) openThread(username);
        });
      });
      if (!wrap.querySelector(".conv-row")) {
        body.innerHTML = '<div class="chat-widget-empty">Zatím žádné konverzace.</div>';
      }
    } catch (err) {
      body.innerHTML = '<div class="chat-widget-empty">Zprávy se nepodařilo načíst.</div>';
    }
  }

  function renderMessages(container, messages) {
    container.innerHTML = messages.map((m) => `
      <div class="bubble ${m.mine ? 'bubble-mine' : 'bubble-theirs'}">
        ${m.image_url ? `<img class="bubble-image" src="${m.image_url}" alt="">` : ""}
        ${m.gif_url ? `<img class="bubble-gif" src="${m.gif_url}" alt="">` : ""}
        ${m.content ? m.content.replace(/</g, "&lt;") : ""}
      </div>
    `).join("");
    container.scrollTop = container.scrollHeight;
  }

  async function openThread(username) {
    stopPolling();
    currentUsername = username;
    title.textContent = "…";
    backBtn.style.display = "";
    body.innerHTML = '<div class="chat-widget-loading">Načítám…</div>';

    try {
      const url = window.PIPLY_WIDGET_THREAD_URL_BASE.replace("__USER__", username);
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) {
        body.innerHTML = '<div class="chat-widget-empty">Konverzaci se nepodařilo načíst.</div>';
        return;
      }
      title.textContent = data.other.display_name;

      body.innerHTML = `
        <div class="chat-widget-messages" id="chat-widget-messages"></div>
        ${data.can_message ? `
          <form class="chat-widget-input-row" id="chat-widget-form">
            <input type="text" id="chat-widget-input" placeholder="Napiš zprávu…" maxlength="2000" autocomplete="off">
            <button type="submit" class="btn btn-sm">Odeslat</button>
          </form>
        ` : `<div class="chat-widget-empty">Tento uživatel nepřijímá zprávy.</div>`}
      `;
      const msgContainer = document.getElementById("chat-widget-messages");
      renderMessages(msgContainer, data.messages);
      let lastId = data.messages.length ? data.messages[data.messages.length - 1].id : 0;

      const form = document.getElementById("chat-widget-form");
      if (form) {
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const input = document.getElementById("chat-widget-input");
          const text = input.value.trim();
          if (!text) return;
          input.value = "";
          try {
            const sendUrl = window.PIPLY_WIDGET_SEND_URL_BASE.replace("__USER__", username);
            const fd = new FormData();
            fd.append("content", text);
            const res2 = await fetch(sendUrl, { method: "POST", body: fd });
            const data2 = await res2.json();
            if (data2.message) {
              lastId = data2.message.id;
              const cont = document.getElementById("chat-widget-messages");
              if (cont) {
                cont.innerHTML += `<div class="bubble bubble-mine">${(data2.message.content || "").replace(/</g, "&lt;")}</div>`;
                cont.scrollTop = cont.scrollHeight;
              }
            }
          } catch (err) {
            // ticho
          }
        });
      }

      pollTimer = setInterval(async () => {
        if (currentUsername !== username) return;
        try {
          const pollUrl = window.PIPLY_WIDGET_POLL_URL_BASE.replace("__USER__", username) + `?after_id=${lastId}`;
          const res3 = await fetch(pollUrl);
          const data3 = await res3.json();
          if (data3.messages && data3.messages.length) {
            const cont = document.getElementById("chat-widget-messages");
            data3.messages.forEach((m) => {
              lastId = Math.max(lastId, m.id);
              if (cont) {
                cont.innerHTML += `
                  <div class="bubble ${m.mine ? 'bubble-mine' : 'bubble-theirs'}">
                    ${m.image_url ? `<img class="bubble-image" src="${m.image_url}" alt="">` : ""}
                    ${m.gif_url ? `<img class="bubble-gif" src="${m.gif_url}" alt="">` : ""}
                    ${m.content ? m.content.replace(/</g, "&lt;") : ""}
                  </div>`;
              }
            });
            if (cont) cont.scrollTop = cont.scrollHeight;
          }
        } catch (err) {
          // ticho
        }
      }, 3000);
    } catch (err) {
      body.innerHTML = '<div class="chat-widget-empty">Konverzaci se nepodařilo načíst.</div>';
    }
  }
})();

// --- Plynulejsi prechody mezi strankami (fade, jen progresivni vylepseni) ---

(function initSmoothNav() {
  document.documentElement.classList.add("piply-loaded");

  document.addEventListener("click", (e) => {
    const link = e.target.closest("a");
    if (!link) return;
    if (link.target === "_blank" || link.hasAttribute("download")) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const href = link.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("http") || href.startsWith("mailto:")) return;
    if (link.closest("#chat-widget")) return;

    if (!document.startViewTransition) {
      e.preventDefault();
      document.documentElement.classList.add("piply-fading");
      setTimeout(() => { window.location.href = href; }, 90);
    }
  });
})();