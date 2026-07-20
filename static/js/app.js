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

const PIPLY_EMOJI_CATEGORIES = {
  "Smajlíci": [
    "😀","😃","😄","😁","😆","😅","🤣","😂","🙂","🙃","😉","😊","😇","🥰","😍","🤩",
    "😘","😗","😚","😙","😋","😛","😜","🤪","😝","🤑","🤗","🤭","🤫","🤔","🤐","🤨",
    "😐","😑","😶","😏","😒","🙄","😬","🤥","😌","😔","😪","🤤","😴","😷","🤒","🤕",
    "🤢","🤮","🤧","🥵","🥶","🥴","😵","🤯","🤠","🥳","🥸","😎","🤓","🧐","😕","😟",
    "🙁","☹️","😮","😯","😲","😳","🥺","😦","😧","😨","😰","😥","😢","😭","😱","😖",
    "😣","😞","😓","😩","😫","🥱","😤","😡","😠","🤬","😈","👿","💀","☠️","💩","🤡",
  ],
  "Gesta": [
    "👋","🤚","🖐️","✋","🖖","👌","🤌","🤏","✌️","🤞","🤟","🤘","🤙","👈","👉","👆",
    "🖕","👇","☝️","👍","👎","✊","👊","🤛","🤜","👏","🙌","👐","🤲","🙏","✍️","💅",
    "🤳","💪","🦾","🦵","🦶","👂","👃","🧠","🫀","🫁","👀","👁️","👅","👄",
  ],
  "Srdce": [
    "❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💔","❤️‍🔥","❤️‍🩹","💕","💞","💓",
    "💗","💖","💘","💝","💟","♥️","💯","💢","💥","💫","💦","💨","🕳️","💣","💬","👁️‍🗨️",
  ],
  "Zvířata": [
    "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐻‍❄️","🐨","🐯","🦁","🐮","🐷","🐽","🐸",
    "🐵","🙈","🙉","🙊","🐒","🐔","🐧","🐦","🐤","🦆","🦅","🦉","🦇","🐺","🐗","🐴",
    "🦄","🐝","🪱","🐛","🦋","🐌","🐞","🐜","🪰","🐢","🐍","🦎","🦖","🦕","🐙","🦑",
    "🦐","🦞","🦀","🐡","🐠","🐟","🐬","🐳","🐋","🦈","🐊","🐅","🐆","🦓","🦍","🦧",
    "🐘","🦛","🦏","🐪","🐫","🦒","🦘","🐃","🐂","🐄","🐎","🐖","🐑","🐐","🦌","🐕",
    "🐩","🦮","🐕‍🦺","🐈","🐈‍⬛","🐓","🦃","🦤","🦚","🦜","🦢","🦩","🕊️","🐇","🦝","🦨",
    "🦡","🦫","🦦","🦥","🐁","🐀","🐿️","🦔",
  ],
  "Jídlo": [
    "🍏","🍎","🍐","🍊","🍋","🍌","🍉","🍇","🍓","🫐","🍈","🍒","🍑","🥭","🍍","🥥",
    "🥝","🍅","🍆","🥑","🥦","🥬","🥒","🌶️","🫑","🌽","🥕","🫒","🧄","🧅","🥔","🍠",
    "🥐","🥯","🍞","🥖","🥨","🧀","🥚","🍳","🧈","🥞","🧇","🥓","🥩","🍗","🍖","🌭",
    "🍔","🍟","🍕","🫓","🥪","🥙","🧆","🌮","🌯","🫔","🥗","🥘","🫕","🍝","🍜","🍲",
    "🍛","🍣","🍱","🥟","🦪","🍤","🍙","🍚","🍘","🍥","🥠","🥮","🍢","🍡","🍧","🍨",
    "🍦","🥧","🧁","🍰","🎂","🍮","🍭","🍬","🍫","🍿","🍩","🍪","🌰","🥜","🍯","🥛",
    "🍼","☕","🍵","🧃","🥤","🧋","🍶","🍺","🍻","🥂","🍷","🥃","🍸","🍹","🧉","🍾",
  ],
  "Aktivity": [
    "⚽","🏀","🏈","⚾","🥎","🎾","🏐","🏉","🥏","🎱","🪀","🏓","🏸","🏒","🏑","🥍",
    "🏏","🪃","🥅","⛳","🪁","🏹","🎣","🤿","🥊","🥋","🎽","🛹","🛼","🛷","⛸️","🥌",
    "🎿","⛷️","🏂","🪂","🏋️","🤼","🤸","⛹️","🤺","🤾","🏌️","🏇","🧘","🏄","🏊","🤽",
    "🚣","🧗","🚵","🚴","🏆","🥇","🥈","🥉","🏅","🎖️","🏵️","🎗️","🎫","🎟️","🎪","🤹",
    "🎭","🩰","🎨","🎬","🎤","🎧","🎼","🎹","🥁","🎷","🎺","🎸","🪕","🎻","🎲","♟️",
    "🎯","🎳","🎮","🎰","🧩",
  ],
  "Cestování": [
    "🚗","🚕","🚙","🚌","🚎","🏎️","🚓","🚑","🚒","🚐","🛻","🚚","🚛","🚜","🦯","🦽",
    "🦼","🛴","🚲","🛵","🏍️","🛺","🚨","🚔","🚍","🚘","🚖","🚡","🚠","🚟","🚃","🚋",
    "🚞","🚝","🚄","🚅","🚈","🚂","🚆","🚇","🚊","🚉","✈️","🛫","🛬","🛩️","💺","🛰️",
    "🚀","🛸","🚁","🛶","⛵","🚤","🛥️","🛳️","⛴️","🚢","⚓","🪝","⛽","🚧","🚦","🚥",
    "🗺️","🗿","🗽","🗼","🏰","🏯","🏟️","🎡","🎢","🎠","⛲","⛱️","🏖️","🏝️","🏜️","🌋",
    "⛰️","🏔️","🗻","🏕️","⛺","🏠","🏡","🏘️","🏚️","🏗️","🏭","🏢","🏬","🏣","🏤","🏥",
    "🏦","🏨","🏪","🏫","🏩","💒","🏛️","⛪","🕌","🕍","🛕","🕋","⛩️",
  ],
  "Objekty": [
    "⌚","📱","💻","⌨️","🖥️","🖨️","🖱️","🖲️","🕹️","🗜️","💽","💾","💿","📀","📼","📷",
    "📸","📹","🎥","📞","☎️","📟","📠","📺","📻","🎙️","🎚️","🎛️","🧭","⏱️","⏲️","⏰",
    "🕰️","⌛","⏳","📡","🔋","🪫","🔌","💡","🔦","🕯️","🪔","🧯","🛢️","💸","💵","💴",
    "💶","💷","🪙","💰","💳","💎","⚖️","🪜","🧰","🪛","🔧","🔨","⚒️","🛠️","⛏️","🪚",
    "🔩","⚙️","🪤","🧱","⛓️","🧲","🔫","💣","🧨","🪓","🔪","🗡️","⚔️","🛡️","🚬","⚰️",
    "🪦","⚱️","🏺","🔮","📿","🧿","💈","⚗️","🔭","🔬","🕳️","🩹","💊","💉","🩸","🧬",
    "🦠","🧫","🧪","🌡️","🧹","🪠","🧺","🧻","🚽","🚰","🚿","🛁","🛀","🧼","🪥","🪒",
    "🧴","🛎️","🔑","🗝️","🚪","🪑","🛋️","🛏️","🛌","🧸","🪆","🖼️","🪞","🪟","🛍️","🛒",
  ],
  "Symboly": [
    "✅","❌","❎","➕","➖","➗","♾️","‼️","⁉️","❓","❔","❗","❕","〰️","💱","💲",
    "⚠️","🚸","🔱","⚜️","🔰","♻️","✅","🈯","💹","❇️","✳️","❎","🌐","💠","Ⓜ️","🌀",
    "💤","🏧","🚾","♿","🅿️","🛗","🈳","🈂️","🛂","🛃","🛄","🛅","🚹","🚺","🚼","⚧️",
    "🚻","🚮","🎦","📶","🈁","🔣","🔤","🔡","🔠","🆖","🆗","🆙","🆒","🆕","🆓","0️⃣",
    "1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟","🔢","#️⃣","*️⃣","⏏️","▶️","⏸️",
    "⏯️","⏹️","⏺️","⏭️","⏮️","⏩","⏪","⏫","⏬","◀️","🔼","🔽","➡️","⬅️","⬆️","⬇️",
    "↗️","↘️","↙️","↖️","↕️","↔️","↩️","↪️","⤴️","⤵️","🔀","🔁","🔂","🔄","🔃","🎵",
    "🎶","➰","➿","✔️","☑️","🔘","🔴","🟠","🟡","🟢","🔵","🟣","🟤","⚫","⚪","🟥",
    "🟧","🟨","🟩","🟦","🟪","🟫","⬛","⬜","◼️","◻️","◾","◽","▪️","▫️","🔺","🔻",
    "🔸","🔹","🔶","🔷","🔳","🔲",
  ],
  "Vlajky": [
    "🏁","🚩","🎌","🏴","🏳️","🏳️‍🌈","🏳️‍⚧️","🏴‍☠️","🇨🇿","🇸🇰","🇩🇪","🇦🇹","🇵🇱","🇬🇧","🇺🇸","🇫🇷",
    "🇮🇹","🇪🇸","🇵🇹","🇳🇱","🇧🇪","🇨🇭","🇸🇪","🇳🇴","🇩🇰","🇫🇮","🇮🇪","🇬🇷","🇭🇺","🇷🇴","🇺🇦","🇷🇺",
    "🇹🇷","🇯🇵","🇰🇷","🇨🇳","🇮🇳","🇧🇷","🇲🇽","🇨🇦","🇦🇺","🇿🇦","🇪🇺",
  ],
};

const PIPLY_EMOJIS = Object.values(PIPLY_EMOJI_CATEGORIES).flat();

// --- Chat: odeslani zpravy (text/obrazek/gif) bez reloadu + polling ---

// --- Nastroj na vyber vyrezu (avatar / banner): tazenim ve fotce vybiras, co bude videt ---

function initRepositionTool(frameEl, imgEl, hiddenInput) {
  if (!frameEl || !imgEl || !hiddenInput) return;

  function parsePosition(str) {
    const parts = (str || "50% 50%").replace(/%/g, "").split(" ").map((s) => parseFloat(s));
    return { x: isNaN(parts[0]) ? 50 : parts[0], y: isNaN(parts[1]) ? 50 : parts[1] };
  }

  let pos = parsePosition(hiddenInput.value);
  let dragging = false;
  let startX = 0, startY = 0, startPos = pos;

  function apply() {
    imgEl.style.objectPosition = pos.x + "% " + pos.y + "%";
    hiddenInput.value = pos.x + "% " + pos.y + "%";
  }

  function down(clientX, clientY) {
    dragging = true;
    startX = clientX; startY = clientY; startPos = { ...pos };
    frameEl.classList.add("is-dragging");
  }
  function move(clientX, clientY) {
    if (!dragging) return;
    const rect = frameEl.getBoundingClientRect();
    const dx = ((clientX - startX) / rect.width) * 100;
    const dy = ((clientY - startY) / rect.height) * 100;
    pos.x = Math.min(100, Math.max(0, startPos.x - dx));
    pos.y = Math.min(100, Math.max(0, startPos.y - dy));
    apply();
  }
  function up() {
    dragging = false;
    frameEl.classList.remove("is-dragging");
  }

  frameEl.addEventListener("mousedown", (e) => { down(e.clientX, e.clientY); e.preventDefault(); });
  window.addEventListener("mousemove", (e) => move(e.clientX, e.clientY));
  window.addEventListener("mouseup", up);
  frameEl.addEventListener("touchstart", (e) => { const t = e.touches[0]; down(t.clientX, t.clientY); }, { passive: true });
  frameEl.addEventListener("touchmove", (e) => { const t = e.touches[0]; move(t.clientX, t.clientY); }, { passive: true });
  frameEl.addEventListener("touchend", up);

  // reset pozice na stred, kdyz se nahradi obrazek novym souborem
  return { resetCenter: () => { pos = { x: 50, y: 50 }; apply(); } };
}

(function initProfileRepositionTools() {
  const avatarFrame = document.getElementById("avatar-reposition-frame");
  const avatarImg = document.getElementById("avatar-reposition-img");
  const avatarPosInput = document.getElementById("avatar-position-input");
  const avatarFileInput = document.getElementById("avatar-file-input");
  if (!avatarFrame) return; // nejsme na strance Upravit profil

  const avatarTool = initRepositionTool(avatarFrame, avatarImg, avatarPosInput);
  avatarFileInput.addEventListener("change", () => {
    const file = avatarFileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      avatarImg.src = e.target.result;
      avatarTool && avatarTool.resetCenter();
    };
    reader.readAsDataURL(file);
  });

  const bannerFrame = document.getElementById("banner-reposition-frame");
  const bannerImg = document.getElementById("banner-reposition-img");
  const bannerPosInput = document.getElementById("banner-position-input");
  const bannerFileInput = document.getElementById("banner-file-input");
  const bannerSelect = document.getElementById("banner-select");
  const bannerTool = initRepositionTool(bannerFrame, bannerImg, bannerPosInput);

  bannerFileInput.addEventListener("change", () => {
    const file = bannerFileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      bannerImg.src = e.target.result;
      bannerFrame.style.display = "";
      bannerTool && bannerTool.resetCenter();
    };
    reader.readAsDataURL(file);
    if (bannerSelect) bannerSelect.value = ""; // vlastni soubor ma prednost pred vyberem z obchodu
  });

  if (bannerSelect) {
    bannerSelect.addEventListener("change", () => {
      const opt = bannerSelect.options[bannerSelect.selectedIndex];
      const imgUrl = opt.dataset.image;
      if (imgUrl) {
        bannerImg.src = imgUrl;
        bannerFrame.style.display = "";
        bannerTool && bannerTool.resetCenter();
      } else if (bannerSelect.value === "__none__") {
        bannerFrame.style.display = "none";
      }
    });
  }
})();

// --- Kalendar: detail udalosti po kliknuti na cip (popis, kdo je pozvany, akce) ---

(function initCalendarEventModal() {
  const overlay = document.getElementById("event-modal-overlay");
  if (!overlay) return;

  const loading = document.getElementById("event-modal-loading");
  const body = document.getElementById("event-modal-body");
  const iconEl = document.getElementById("event-modal-icon");
  const titleEl = document.getElementById("event-modal-title");
  const metaEl = document.getElementById("event-modal-meta");
  const notesEl = document.getElementById("event-modal-notes");
  const invitesEl = document.getElementById("event-modal-invites");
  const actionsEl = document.getElementById("event-modal-actions");
  const closeBtn = document.getElementById("event-modal-close");
  const monthKey = window.PIPLY_CALENDAR_MONTH_KEY || "";

  const STATUS_LABELS = {
    accepted: { text: "Přijato", cls: "invite-status-accepted" },
    pending: { text: "Čeká na odpověď", cls: "invite-status-pending" },
    declined: { text: "Odmítnuto", cls: "invite-status-declined" },
  };

  function closeModal() {
    overlay.classList.remove("open");
  }
  closeBtn.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

  async function openModal(eventId) {
    overlay.classList.add("open");
    loading.style.display = "block";
    body.style.display = "none";
    try {
      const res = await fetch(`/calendar/${eventId}/detail`);
      if (!res.ok) throw new Error("fetch failed");
      const data = await res.json();

      iconEl.textContent = data.icon;
      titleEl.textContent = data.title;
      titleEl.style.color = data.color;

      let metaHtml = data.date + (data.time ? " · " + data.time : "");
      if (!data.is_owner) metaHtml += ` · vytvořil(a) ${data.owner_name}`;
      metaEl.innerHTML = metaHtml;

      notesEl.textContent = data.notes || "";
      notesEl.style.display = data.notes ? "block" : "none";

      if (data.invites.length) {
        invitesEl.innerHTML = "<div class='event-modal-invites-title'>Pozvaní</div>" + data.invites.map((inv) => {
          const s = STATUS_LABELS[inv.status] || STATUS_LABELS.pending;
          return `<div class="event-modal-invite-row"><span>${inv.name}</span><span class="invite-status-pill ${s.cls}">${s.text}</span></div>`;
        }).join("");
        invitesEl.style.display = "block";
      } else {
        invitesEl.style.display = "none";
      }

      let actionsHtml = "";
      if (data.is_owner) {
        if (data.kind === "task") {
          actionsHtml += `
            <form method="post" action="/calendar/${data.id}/toggle">
              <input type="hidden" name="month_key" value="${monthKey}">
              <button type="submit" class="btn btn-secondary btn-sm">${data.is_done ? "Označit jako nesplněné" : "Označit jako splněné"}</button>
            </form>`;
        }
        actionsHtml += `
          <form method="post" action="/calendar/${data.id}/delete" data-confirm="Opravdu smazat tuto událost?">
            <input type="hidden" name="month_key" value="${monthKey}">
            <button type="submit" class="btn btn-ghost btn-sm" style="color:var(--red)">Smazat</button>
          </form>`;
      }
      actionsEl.innerHTML = actionsHtml;

      loading.style.display = "none";
      body.style.display = "block";
    } catch (err) {
      loading.textContent = "Nepodařilo se načíst detail.";
    }
  }

  // Delegovane kliknuti funguje jak pro cipy vykreslene serverem (uvnitr .calendar-grid,
  // pokud by tam nekdy byly), tak pro ty dynamicky vykreslene v panelu vybraneho dne.
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".calendar-event-chip");
    if (!chip) return;
    if (e.target.closest(".calendar-chip-check-form")) return;
    openModal(chip.dataset.eventId);
  });

  // --- Panel vybraneho dne: klik na cislo dne v mrizce ukaze udalosti toho dne dole ---

  const events = window.PIPLY_CALENDAR_EVENTS || {};
  const panelTitle = document.getElementById("calendar-day-panel-title");
  const panelList = document.getElementById("calendar-day-panel-list");
  const panelAddBtn = document.getElementById("calendar-day-panel-add");
  const addWrap = document.getElementById("calendar-add-wrap");
  const addToggleBtn = document.getElementById("calendar-add-toggle");
  const addDateInput = document.getElementById("calendar-add-date");
  let selectedDate = window.PIPLY_CALENDAR_SELECTED || window.PIPLY_CALENDAR_TODAY;

  function formatDateNice(dateStr) {
    const parts = dateStr.split("-");
    return `${parts[2]}. ${parts[1]}. ${parts[0]}`;
  }

  function chipHTML(e) {
    const checkHtml = (e.kind === "task" && e.is_mine)
      ? `<form method="post" action="/calendar/${e.id}/toggle" class="calendar-chip-check-form" onclick="event.stopPropagation()">
           <input type="hidden" name="month_key" value="${monthKey}">
           <button type="submit" class="calendar-chip-check">${e.is_done ? "✓" : ""}</button>
         </form>`
      : `<span class="calendar-event-icon">${e.icon}</span>`;
    const ownerHtml = !e.is_mine ? ` <span class="muted">(${e.owner_name})</span>` : "";
    return `
      <div class="calendar-event-chip calendar-event-chip-full ${e.kind === "task" ? "is-task" : ""} ${e.is_done ? "is-done" : ""} priority-${e.priority}"
           style="border-left-color:${e.color}" data-event-id="${e.id}">
        ${checkHtml}
        <span class="calendar-chip-title">${e.time ? `<b>${e.time}</b> ` : ""}${e.title}${ownerHtml}</span>
      </div>`;
  }

  function renderPanel() {
    panelTitle.textContent = formatDateNice(selectedDate) + (selectedDate === window.PIPLY_CALENDAR_TODAY ? " · Dnes" : "");
    const dayEvents = events[selectedDate] || [];
    if (!dayEvents.length) {
      panelList.innerHTML = '<p class="muted" style="padding:10px 0">Žádné události tento den.</p>';
    } else {
      panelList.innerHTML = dayEvents.map(chipHTML).join("");
    }
  }

  document.querySelectorAll(".calendar-daybtn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".calendar-daybtn.is-selected").forEach((b) => b.classList.remove("is-selected"));
      btn.classList.add("is-selected");
      selectedDate = btn.dataset.date;
      renderPanel();
    });
  });

  if (panelTitle) renderPanel();

  // --- Skryty/rozbaleny formular pro pridani udalosti ---

  function openAddForm(prefillDate) {
    addWrap.style.display = "block";
    if (prefillDate && addDateInput) addDateInput.value = prefillDate;
    addWrap.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  if (addToggleBtn) {
    addToggleBtn.addEventListener("click", () => {
      const isOpen = addWrap.style.display !== "none";
      addWrap.style.display = isOpen ? "none" : "block";
      if (!isOpen) addWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  if (panelAddBtn) {
    panelAddBtn.addEventListener("click", () => openAddForm(selectedDate));
  }
})();

function buildInviteCardHTML(invite) {
  let actionsHtml;
  if (invite.status === "pending" && invite.invitee_id === window.PIPLY_ME_ID) {
    actionsHtml = `
      <div class="invite-card-actions">
        <button type="button" class="btn btn-sm invite-respond-btn" data-action="accept">Přijmout</button>
        <button type="button" class="btn btn-ghost btn-sm invite-respond-btn" data-action="decline">Odmítnout</button>
      </div>`;
  } else if (invite.status === "pending") {
    actionsHtml = `<div class="invite-card-status">Čeká na odpověď</div>`;
  } else if (invite.status === "accepted") {
    actionsHtml = `<div class="invite-card-status invite-card-status-accepted">✓ Přijato</div>`;
  } else {
    actionsHtml = `<div class="invite-card-status invite-card-status-declined">✕ Odmítnuto</div>`;
  }
  return `
    <div class="invite-card" data-invite-id="${invite.id}">
      <div class="invite-card-header">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
        <span>Pozvánka do kalendáře</span>
      </div>
      <div class="invite-card-title">${(invite.title || "").replace(/</g, "&lt;")}</div>
      <div class="invite-card-meta">${invite.date || ""}${invite.time ? " · " + invite.time : ""}</div>
      ${invite.notes ? `<div class="invite-card-notes">${invite.notes.replace(/</g, "&lt;")}</div>` : ""}
      ${actionsHtml}
    </div>`;
}

function wireInviteButtons(container) {
  container.querySelectorAll(".invite-respond-btn").forEach((btn) => {
    if (btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", async () => {
      const card = btn.closest(".invite-card");
      const inviteId = card.dataset.inviteId;
      const action = btn.dataset.action;
      btn.disabled = true;
      try {
        const fd = new FormData();
        fd.append("action", action);
        const res = await fetch(`/calendar/invite/${inviteId}/respond`, { method: "POST", body: fd });
        const data = await res.json();
        const actionsDiv = card.querySelector(".invite-card-actions");
        if (data.status === "accepted") {
          actionsDiv.outerHTML = `<div class="invite-card-status invite-card-status-accepted">✓ Přijato</div>`;
        } else if (data.status === "declined") {
          actionsDiv.outerHTML = `<div class="invite-card-status invite-card-status-declined">✕ Odmítnuto</div>`;
        }
      } catch (err) {
        btn.disabled = false;
      }
    });
  });
}

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
  const emojiCategories = document.getElementById("emoji-categories");
  const emojiSearchInput = document.getElementById("emoji-search-input");

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
  wireInviteButtons(messagesBox);

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

    if (m.invite) {
      div.innerHTML = buildInviteCardHTML(m.invite);
    } else {
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
    }
    const time = document.createElement("div");
    time.className = "bubble-time";
    time.textContent = (m.created_at || "").slice(11, 16);
    div.appendChild(time);

    messagesBox.appendChild(div);
    if (m.invite) wireInviteButtons(div);
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

  // --- Emoji picker (kategorie + hledani) ---

  if (emojiBtn && emojiGrid) {
    const categoryNames = Object.keys(PIPLY_EMOJI_CATEGORIES);
    let activeCategory = categoryNames[0];

    function renderEmojiGrid() {
      const query = (emojiSearchInput.value || "").trim();
      emojiGrid.innerHTML = "";
      let list;
      if (query) {
        list = PIPLY_EMOJIS.filter((e) => e.includes(query));
      } else {
        list = PIPLY_EMOJI_CATEGORIES[activeCategory] || [];
      }
      if (!list.length) {
        emojiGrid.innerHTML = '<div class="picker-empty">Nic se nenašlo.</div>';
        return;
      }
      list.forEach((emoji) => {
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
    }

    categoryNames.forEach((name) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "emoji-cat-tab" + (name === activeCategory ? " active" : "");
      tab.textContent = name;
      tab.addEventListener("click", () => {
        activeCategory = name;
        emojiSearchInput.value = "";
        emojiCategories.querySelectorAll(".emoji-cat-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        renderEmojiGrid();
      });
      emojiCategories.appendChild(tab);
    });

    emojiSearchInput.addEventListener("input", renderEmojiGrid);
    renderEmojiGrid();

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

  document.addEventListener("click", (e) => {
    if (e.target.closest(".picker-popover")) return;
    closeAllPickers();
  });

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

// --- Cookie lista (klasicke upozorneni, zapamatuje si volbu v localStorage) ---

(function initCookieBanner() {
  const banner = document.getElementById("cookie-banner");
  if (!banner) return;
  const KEY = "piply_cookie_consent";

  try {
    if (localStorage.getItem(KEY)) return; // uz se rozhodl drive
  } catch (err) {
    return; // localStorage nedostupny (napr. striktni privacy mod) - radsi neobtezovat
  }

  banner.style.display = "flex";

  function dismiss(value) {
    try { localStorage.setItem(KEY, value); } catch (err) { /* ticho */ }
    banner.style.display = "none";
  }

  document.getElementById("cookie-accept").addEventListener("click", () => dismiss("accepted"));
  document.getElementById("cookie-decline").addEventListener("click", () => dismiss("declined"));
})();

// --- Postranni panel: rozbaleni na hover, jinak jen ikonky (jako na mobilnich appkach typu IG) ---

(function initSidebarCollapse() {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) return;

  let expandTimer = null;
  let collapseTimer = null;

  sidebar.addEventListener("mouseenter", () => {
    clearTimeout(collapseTimer);
    // maly zpozdeni, at rychly proklik na odkaz v panelu nezpusobi zablesk rozbaleni
    expandTimer = setTimeout(() => sidebar.classList.add("expanded"), 220);
  });
  sidebar.addEventListener("mouseleave", () => {
    clearTimeout(expandTimer);
    // delsi zpozdeni pred sbalenim, at to nemizi hned pri sebemensim odjeti mysi
    collapseTimer = setTimeout(() => sidebar.classList.remove("expanded"), 900);
  });
})();

// --- Mobilni vysuvne menu ---

(function initMobileDrawer() {
  const openBtn = document.getElementById("mobile-menu-open");
  const closeBtn = document.getElementById("mobile-menu-close");
  const overlay = document.getElementById("mobile-drawer-overlay");
  if (!openBtn || !overlay) return;

  openBtn.addEventListener("click", () => overlay.classList.add("open"));
  closeBtn.addEventListener("click", () => overlay.classList.remove("open"));
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.classList.remove("open");
  });
})();

// --- Prepinac svetly/tmavy rezim ---

(function initThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  const mobileBtn = document.getElementById("mobile-theme-toggle");
  if (!btn && !mobileBtn) return;

  const moonIcon = document.getElementById("theme-icon-moon");
  const sunIcon = document.getElementById("theme-icon-sun");
  const mobileMoonIcon = document.getElementById("mobile-theme-icon-moon");
  const mobileSunIcon = document.getElementById("mobile-theme-icon-sun");

  function syncIcons() {
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    if (moonIcon) moonIcon.style.display = isLight ? "none" : "block";
    if (sunIcon) sunIcon.style.display = isLight ? "block" : "none";
    if (mobileMoonIcon) mobileMoonIcon.style.display = isLight ? "none" : "block";
    if (mobileSunIcon) mobileSunIcon.style.display = isLight ? "block" : "none";
  }
  syncIcons();

  function toggle() {
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    if (isLight) {
      document.documentElement.removeAttribute("data-theme");
      try { localStorage.setItem("piply_theme", "dark"); } catch (err) { /* ticho */ }
    } else {
      document.documentElement.setAttribute("data-theme", "light");
      try { localStorage.setItem("piply_theme", "light"); } catch (err) { /* ticho */ }
    }
    syncIcons();
    document.dispatchEvent(new CustomEvent("piply-theme-changed", { detail: { light: !isLight } }));
  }

  if (btn) btn.addEventListener("click", toggle);
  if (mobileBtn) mobileBtn.addEventListener("click", toggle);

  // Pokud uzivatel jeste nikdy prepinac rucne nepouzil, sledujeme zmenu
  // systemoveho motivu zarizeni za behu (napr. automaticky tmavy rezim v noci)
  try {
    var savedPref = localStorage.getItem("piply_theme");
    if (savedPref !== "light" && savedPref !== "dark" && window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", (e) => {
        if (e.matches) {
          document.documentElement.setAttribute("data-theme", "light");
        } else {
          document.documentElement.removeAttribute("data-theme");
        }
        syncIcons();
        document.dispatchEvent(new CustomEvent("piply-theme-changed", { detail: { light: e.matches } }));
      });
    }
  } catch (err) { /* ticho */ }
})();

// --- Uvodni tutorial s maskotem (pro nove uzivatele + ty, co jim jeste nebyl zobrazen) ---

(function initTutorial() {
  const overlay = document.getElementById("tutorial-overlay");
  if (!overlay || !window.PIPLY_SHOW_TUTORIAL) return;

  const steps = [
    {
      img: "wave.png",
      title: "Vítej v Piply!",
      body: "Ahoj, já jsem tvůj průvodce. Za chvilku ti ukážu, co všechno appka umí – bude to rychlé, slibuju.",
    },
    {
      img: "thumbsup.png",
      title: "Deník obchodů",
      body: "V Deníku si zapisuješ obchody – ručně, nebo importem z MT4/MT5. Statistiky a grafy se počítají automaticky.",
    },
    {
      img: "tablet.png",
      title: "Feed a kamarádi",
      body: "Sdílej svoje obchody a myšlenky na Feedu, přidávej si kamarády a chatuj s nimi – i přes plovoucí okénko vpravo dole.",
    },
    {
      img: "jump.png",
      title: "Kalendář a výzvy",
      body: "V Kalendáři si plánuj úkoly a zvi kamarády na společné akce. Ve Výzvách sbírej body a utrácej je v Obchodě za odznaky.",
    },
    {
      img: "sign.png",
      title: "Novinky v reálném čase",
      body: "Na stránce Novinky sleduješ breaking news přímo z trhu – a appka tě na důležité zprávy sama upozorní.",
    },
    {
      img: "sit.png",
      title: "To je vše!",
      body: "Teď už víš, jak Piply funguje. Kdykoliv si tenhle průvodce můžeš znovu pustit přes ikonku otazníku dole v menu.",
    },
  ];

  let current = 0;
  const mascotEl = document.getElementById("tutorial-mascot");
  const titleEl = document.getElementById("tutorial-title");
  const bodyEl = document.getElementById("tutorial-body");
  const dotsEl = document.getElementById("tutorial-dots");
  const prevBtn = document.getElementById("tutorial-prev");
  const nextBtn = document.getElementById("tutorial-next");
  const skipBtn = document.getElementById("tutorial-skip");

  dotsEl.innerHTML = steps.map((_, i) => `<span class="tutorial-dot" data-i="${i}"></span>`).join("");

  function render() {
    const s = steps[current];
    mascotEl.src = window.PIPLY_MASCOT_BASE + s.img;
    titleEl.textContent = s.title;
    bodyEl.textContent = s.body;
    prevBtn.style.visibility = current === 0 ? "hidden" : "visible";
    nextBtn.textContent = current === steps.length - 1 ? "Dokončit" : "Další";
    dotsEl.querySelectorAll(".tutorial-dot").forEach((d, i) => {
      d.classList.toggle("active", i === current);
    });
  }

  async function finish() {
    overlay.style.display = "none";
    try {
      await fetch("/u/tutorial/complete", { method: "POST" });
    } catch (err) {
      // ticho
    }
  }

  nextBtn.addEventListener("click", () => {
    if (current === steps.length - 1) { finish(); return; }
    current++;
    render();
  });
  prevBtn.addEventListener("click", () => {
    if (current === 0) return;
    current--;
    render();
  });
  skipBtn.addEventListener("click", finish);
  dotsEl.addEventListener("click", (e) => {
    const dot = e.target.closest(".tutorial-dot");
    if (!dot) return;
    current = parseInt(dot.dataset.i, 10);
    render();
  });

  render();
  overlay.style.display = "flex";
})();

let _piplyAudioCtx = null;
function _piplyGetAudioCtx() {
  if (!_piplyAudioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    _piplyAudioCtx = new Ctx();
  }
  return _piplyAudioCtx;
}

// Prohlizece zamykaji prehravani zvuku, dokud uzivatel se strankou neco neudela
// (klik, klavesa, dotyk). Proto AudioContext "odemkneme" hned pri prvni interakci,
// aby uz byl pripraveny, az prijde skutecna notifikace.
["click", "keydown", "touchstart"].forEach((evt) => {
  document.addEventListener(evt, () => {
    const ctx = _piplyGetAudioCtx();
    if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {});
  }, { once: true, passive: true });
});

function _piplyScheduleBeep(ctx) {
  const now = ctx.currentTime;
  const notes = [
    { freq: 880, start: 0, dur: 0.09 },
    { freq: 1318.5, start: 0.09, dur: 0.14 },
  ];
  notes.forEach((n) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = n.freq;
    gain.gain.setValueAtTime(0, now + n.start);
    gain.gain.linearRampToValueAtTime(0.22, now + n.start + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + n.start + n.dur);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now + n.start);
    osc.stop(now + n.start + n.dur + 0.02);
  });
}

function playNotificationSound() {
  if (!window.PIPLY_NOTIFY_SOUND_ENABLED) return;
  try {
    const ctx = _piplyGetAudioCtx();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      ctx.resume().then(() => _piplyScheduleBeep(ctx)).catch(() => {});
    } else {
      _piplyScheduleBeep(ctx);
    }
  } catch (err) {
    // ticho - napr. prohlizec jeste nepovolil audio pred prvni interakci
  }
}

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
          let title, body;
          if (latest.type === "message" && latest.actor_username) {
            href = window.PIPLY_WIDGET_SEND_URL_BASE
              ? window.PIPLY_WIDGET_SEND_URL_BASE.replace("__USER__", latest.actor_username)
              : "/notifications";
            title = "Nová zpráva";
            body = who ? `<b>${who}</b>` : "";
          } else {
            title = "Oznámení";
            body = (who ? `<b>${who}</b> ` : "") + (latest.message || "");
          }
          showToast(title, body, { href });
          playNotificationSound();
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

  function widgetBubbleHTML(m) {
    const inner = m.invite
      ? buildInviteCardHTML(m.invite)
      : `${m.image_url ? `<img class="bubble-image" src="${m.image_url}" alt="">` : ""}
         ${m.gif_url ? `<img class="bubble-gif" src="${m.gif_url}" alt="">` : ""}
         ${m.content ? m.content.replace(/</g, "&lt;") : ""}`;
    return `<div class="bubble ${m.mine ? 'bubble-mine' : 'bubble-theirs'}" data-msg-id="${m.id}">${inner}</div>`;
  }

  function renderMessages(container, messages) {
    container.innerHTML = messages.map(widgetBubbleHTML).join("");
    container.scrollTop = container.scrollHeight;
    wireInviteButtons(container);
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
                cont.insertAdjacentHTML("beforeend", widgetBubbleHTML(data2.message));
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
                cont.insertAdjacentHTML("beforeend", widgetBubbleHTML(m));
                wireInviteButtons(cont);
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