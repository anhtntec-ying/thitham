"""
App chat dễ thương chạy trên Streamlit, lưu dữ liệu trên Supabase.
- Mỗi người tự đăng ký tên + mật khẩu (cần "mã phòng" để chặn người lạ).
- Tin nhắn tự cập nhật mỗi 3 giây.
"""
import hashlib
import html
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import httpx
import time

# Tự thử lại khi kết nối tới Supabase bị ngắt giữa chừng (hay gặp sau khi app để yên một lúc)
try:
    from postgrest import SyncQueryRequestBuilder as _QB

    if not getattr(_QB.execute, "_retry", False):
        _orig_execute = _QB.execute

        def _execute_retry(self):
            for attempt in range(3):
                try:
                    return _orig_execute(self)
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    time.sleep(0.3 * (attempt + 1))

        _execute_retry._retry = True
        _QB.execute = _execute_retry
except Exception:
    pass

APP_NAME = "Thì thầm"                  # đổi tên app ở đây
APP_TAGLINE = "chỗ tụi mình tám chuyện"  # dòng chữ nhỏ dưới tên
APP_ICON = "🐥"                        # icon của app
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="centered")

# Mỗi người được gán 1 con vật + màu nền cố định theo tên
AVATARS = [
    ("🐰", "#FFD6E0"), ("🐻", "#FFE8C7"), ("🐱", "#E4D9FF"), ("🐸", "#D5F2E3"),
    ("🐼", "#E8EEF2"), ("🦊", "#FFDCC7"), ("🐥", "#FFF3B8"), ("🐨", "#DCEBFA"),
    ("🐹", "#F9E0D0"), ("🐧", "#D7E9F7"),
]


def avatar_of(name: str):
    return AVATARS[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(AVATARS)]


# ---------- Giao diện (CSS) ----------
st.markdown(
    """
<style>
:root {
  --main: #FFD43B;      /* màu nhấn: vàng gà con */
  --main-deep: #D9A800;
  --on-main: #1F1F1F;   /* chữ trên nền vàng */
  --bg: #1F1F1F;        /* nền app */
  --surface: #2B2B2B;   /* thẻ, khung, bong bóng người khác */
  --field: #333333;     /* ô nhập */
  --ink: #EDEDED;       /* chữ chính */
  --muted: #9A9A9A;     /* chữ phụ */
  --line: #3D3D3D;      /* viền */
}

/* Nền tối */
.stApp { background: var(--bg); color: var(--ink); }
header[data-testid="stHeader"] { background: transparent; }

.stApp p, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp h1, .stApp h2, .stApp h3,
.stApp [data-baseweb="tab"], .brand, .chat-box {
  font-family: 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', sans-serif;
}

/* Tên app */
.brand { display: flex; align-items: center; gap: 12px; margin: 4px 0 14px; }
.brand .logo {
  width: 56px; height: 56px; border-radius: 18px; background: var(--surface);
  border: 1px solid var(--line); display: grid; place-items: center;
  font-size: 30px; transform: rotate(-6deg);
}
.brand h1 { font-size: 34px; font-weight: 700; color: var(--ink); margin: 0; padding: 0; line-height: 1; }
.brand p { margin: 2px 0 0; color: var(--muted); font-size: 15px; }
.me-chip {
  display: inline-flex; align-items: center; gap: 6px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 999px; padding: 2px 12px 2px 4px;
  font-size: 14px; color: var(--ink);
}
.me-chip .ava { width: 26px; height: 26px; font-size: 15px; }

/* Khung đăng nhập */
[data-testid="stForm"] {
  background: var(--surface); border: 1px solid var(--line); border-radius: 24px; padding: 18px;
}
[data-baseweb="input"] { border-radius: 14px !important; }

/* Tab thành dạng viên thuốc */
[data-baseweb="tab-list"] { gap: 8px; }
[data-baseweb="tab"] {
  background: var(--surface); border: 1px solid var(--line) !important;
  border-radius: 999px; padding: 2px 18px !important; height: auto;
}
[data-baseweb="tab"][aria-selected="true"] { background: var(--main); border-color: var(--main) !important; }
[data-baseweb="tab"][aria-selected="true"] p { color: var(--on-main) !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }

/* Nút bấm tròn trịa, có "đáy" như kẹo */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  background: var(--main); color: var(--on-main); border: none; border-radius: 999px;
  font-weight: 700; box-shadow: 0 3px 0 var(--main-deep);
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  background: var(--main-deep); color: var(--on-main);
}
.stButton > button:active, [data-testid="stFormSubmitButton"] > button:active {
  transform: translateY(2px); box-shadow: 0 1px 0 var(--main-deep);
}

/* Ô nhập tin nhắn */
[data-testid="stChatInput"] > div {
  border-radius: 999px !important; border: 1px solid var(--line) !important; background: var(--field) !important;
}

/* Khung tin nhắn: column-reverse để luôn cuộn sẵn ở tin mới nhất */
.chat-box {
  height: 62vh; overflow-y: auto; display: flex; flex-direction: column-reverse;
  gap: 4px; padding: 16px 12px; background: #242424;
  border: 1px solid var(--line); border-radius: 26px;
}
.row { display: flex; gap: 8px; align-items: flex-end; }
.row.me { flex-direction: row-reverse; }
.row.first { margin-top: 10px; }
.ava {
  width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center;
  font-size: 19px; flex-shrink: 0;
}
.ava.hidden { visibility: hidden; }
.wrap { max-width: 75%; display: flex; flex-direction: column; }
.row.me .wrap { align-items: flex-end; }
.name { font-size: 13px; font-weight: 700; color: var(--muted); margin: 0 0 1px 12px; }
.bubble {
  padding: 7px 15px; border-radius: 20px; font-size: 16px; line-height: 1.45;
  overflow-wrap: anywhere;
}
.row.other .bubble { background: var(--surface); border: 1px solid var(--line); color: var(--ink); border-bottom-left-radius: 6px; }
.row.me .bubble { background: #383838; color: var(--ink); border: 1px solid #454545; border-bottom-right-radius: 6px; }
.time { font-size: 11px; color: var(--muted); margin: 1px 10px 0; }
.empty { margin: auto; text-align: center; color: var(--muted); font-size: 16px; }
.empty span { font-size: 44px; display: block; }
.bubble.big { background: transparent !important; border: none !important; font-size: 40px; line-height: 1.15; padding: 0 4px; }

/* Nút mở bảng icon */
[data-testid="stPopover"] button {
  background: var(--surface); border: 1px solid var(--line); border-radius: 999px; color: var(--ink);
}
[data-testid="stPopover"] button:hover { border-color: var(--main); color: var(--main); }

/* Sảnh & phòng */
.section { font-weight: 700; font-size: 18px; margin: 16px 0 6px; color: var(--ink); }
.room-card {
  display: flex; gap: 12px; align-items: center; background: var(--surface);
  border: 1px solid var(--line); border-radius: 20px; padding: 10px 14px;
}
.room-ico {
  width: 44px; height: 44px; border-radius: 14px; background: var(--main); color: var(--on-main);
  display: grid; place-items: center; font-weight: 700; font-size: 20px; flex-shrink: 0;
}
.room-info { min-width: 0; flex: 1; }
.room-name { font-weight: 700; font-size: 17px; display: flex; align-items: center; gap: 8px; }
.room-last { color: var(--muted); font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge { background: #FF6B6B; color: #fff; font-size: 12px; font-weight: 700; border-radius: 999px; padding: 0 8px; line-height: 20px; }
.room-title { font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 10px; color: var(--ink); }
.room-title .room-ico { width: 38px; height: 38px; font-size: 18px; border-radius: 12px; }
.member { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
.member .ava { width: 28px; height: 28px; font-size: 16px; }
.lobby-empty {
  text-align: center; color: var(--muted); background: var(--surface);
  border: 1px dashed var(--line); border-radius: 20px; padding: 22px 12px;
}
.lobby-empty span { font-size: 40px; display: block; }

/* Ép màu tối đồng bộ cho ô nhập, nhãn, popup */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { color: var(--ink) !important; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="input"] input,
[data-testid="stChatInput"] textarea, [data-testid="stChatInput"] > div {
  background: var(--field) !important; color: var(--ink) !important; -webkit-text-fill-color: var(--ink);
}
[data-baseweb="input"] { border: 1px solid var(--line) !important; }
[data-baseweb="input"] button svg { fill: var(--muted); }
[data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
[data-testid="stCheckbox"] p { color: var(--ink) !important; }
[data-baseweb="input"] input::placeholder, [data-testid="stChatInput"] textarea::placeholder { color: var(--muted) !important; -webkit-text-fill-color: var(--muted); }
[data-testid="stPopoverBody"] { background: var(--surface) !important; color: var(--ink) !important; }

/* Tab dạng viên thuốc (cho cả bản Streamlit mới) */
button[role="tab"] {
  background: var(--surface) !important; border: 1px solid var(--line) !important;
  border-radius: 999px !important; padding: 2px 18px !important; margin-right: 8px;
}
button[role="tab"] p { color: var(--ink) !important; font-weight: 600; }
button[role="tab"][aria-selected="true"] { background: var(--main) !important; border-color: var(--main) !important; }
button[role="tab"][aria-selected="true"] p { color: var(--on-main) !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none !important; }
</style>
""",
    unsafe_allow_html=True,
)


def brand(extra: str = ""):
    st.markdown(
        f'<div class="brand"><div class="logo">{APP_ICON}</div>'
        f'<div><h1>{APP_NAME}</h1><p>{APP_TAGLINE}</p></div></div>{extra}',
        unsafe_allow_html=True,
    )


EMOJI_PICKER = r"""
<style>
  * { box-sizing: border-box; margin: 0; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: transparent; }
  .picker { background: #2B2B2B; border: 1px solid #3D3D3D; border-radius: 20px; overflow: hidden; }
  .title { font-size: 13px; font-weight: 700; color: #9A9A9A; padding: 8px 12px 2px; }
  .grid {
    height: 208px; overflow-y: auto; padding: 4px 8px 8px;
    display: grid; grid-template-columns: repeat(auto-fill, minmax(38px, 1fr));
  }
  .grid button {
    font-size: 25px; line-height: 1; height: 40px; border: none; background: none;
    border-radius: 10px; cursor: pointer;
    font-family: 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif;
  }
  .grid button:hover { background: #3A3A3A; }
  .grid button.pop { animation: pop .25s ease; }
  @keyframes pop { 50% { transform: scale(1.35); } }
  .empty { grid-column: 1 / -1; color: #9A9A9A; font-size: 14px; text-align: center; padding-top: 70px; }
  .tabs { display: flex; justify-content: space-around; border-top: 1px solid #3D3D3D; background: #242424; }
  .tabs button {
    flex: 1; font-size: 19px; padding: 6px 0; border: none; background: none; cursor: pointer;
    opacity: .45; font-family: 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif;
  }
  .tabs button.on { opacity: 1; box-shadow: inset 0 -3px 0 #FFD43B; }
</style>
<div class="picker">
  <div class="title" id="title"></div>
  <div class="grid" id="grid"></div>
  <div class="tabs" id="tabs"></div>
</div>
<script>
const CATS = [
  ["🕘", "Hay dùng", null],
  ["😀", "Mặt cười", "😀 😃 😄 😁 😆 😅 🤣 😂 🙂 🙃 😉 😊 😇 🥰 😍 🤩 😘 😗 😚 😙 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🤫 🤔 🤐 🤨 😐 😑 😶 😏 😒 🙄 😬 😌 😔 😪 🤤 😴 😷 🤒 🤕 🤢 🤮 🥵 🥶 🥴 😵 🤯 🤠 🥳 😎 🤓 🧐 😕 😟 🙁 😮 😯 😲 😳 🥺 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 👿 💀 💩 🤡 👻 👽 🤖"],
  ["👋", "Cử chỉ", "👋 🤚 ✋ 🖖 👌 🤌 🤏 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 👐 🤲 🙏 💪 🫶 👀 👄 💋 🙆 🙅 🙋 🤷 🤦 💃 🕺 👯 🧘"],
  ["🐻", "Động vật & thiên nhiên", "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🙈 🙉 🙊 🐔 🐧 🐦 🐤 🐥 🦆 🦉 🐺 🐴 🦄 🐝 🐛 🦋 🐌 🐞 🐢 🐍 🐙 🦑 🦀 🐠 🐟 🐬 🐳 🦈 🐊 🦒 🐘 🦔 🐾 🌸 🌷 🌹 🌻 🌼 🍀 🌈 ☀️ 🌙 ⭐ ✨ ⚡ 🔥 ❄️ ☔"],
  ["🍓", "Đồ ăn & thức uống", "🍏 🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🌽 🥕 🥔 🍞 🥐 🧀 🥚 🍳 🥓 🍗 🍖 🌭 🍔 🍟 🍕 🥪 🌮 🍜 🍝 🍣 🍱 🍤 🍙 🍚 🍡 🍦 🍩 🍪 🎂 🍰 🧁 🍫 🍬 🍭 🍮 ☕ 🧋 🍵 🍺 🍻 🥂 🍷 🍹"],
  ["⚽", "Hoạt động & đi chơi", "⚽ 🏀 🏈 ⚾ 🎾 🏐 🏓 🏸 🥊 🎯 🎮 🎲 🧩 🎨 🎬 🎤 🎧 🎸 🎹 🎁 🎈 🎉 🎊 🏆 🥇 🚗 🚕 🛵 🚲 ✈️ 🚀 🏖️ 🏝️ 🏔️ 🏠 🏫 🏥 🎡 🎢 🗽 🗼"],
  ["💡", "Đồ vật", "📱 💻 ⌚ 📷 💡 📚 ✏️ 📌 📎 ✂️ 🔑 🔒 💰 💸 💳 🛒 🎀 👑 💄 💍 👗 👟 🧸 🪄 🕯️ ⏰ 📅 📝 💌 📦"],
  ["❤️", "Biểu tượng", "❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💯 💢 💥 💫 💦 💨 💬 💭 💤 ✅ ❌ ❗ ❓ ⚠️ 🆗 🆒 🆕 🔴 🟠 🟡 🟢 🔵 🟣 ⚫ ⚪"],
];

const grid = document.getElementById("grid");
const tabs = document.getElementById("tabs");
const title = document.getElementById("title");
let current = 1;

function getRecent() {
  try { return JSON.parse(localStorage.getItem("recentEmoji") || "[]"); } catch (e) { return []; }
}
function saveRecent(e) {
  try {
    const r = [e, ...getRecent().filter(x => x !== e)].slice(0, 32);
    localStorage.setItem("recentEmoji", JSON.stringify(r));
  } catch (err) {}
}

// Chèn emoji vào ô nhập tin nhắn của Streamlit, đúng vị trí con trỏ
function insert(e, btn) {
  const doc = window.parent.document;
  const ta = doc.querySelector('[data-testid="stChatInputTextArea"]')
          || doc.querySelector('[data-testid="stChatInput"] textarea');
  if (!ta) return;
  const start = ta.selectionStart ?? ta.value.length;
  const end = ta.selectionEnd ?? ta.value.length;
  const value = ta.value.slice(0, start) + e + ta.value.slice(end);
  const setter = Object.getOwnPropertyDescriptor(
    window.parent.HTMLTextAreaElement.prototype, "value").set;
  setter.call(ta, value);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  const pos = start + e.length;
  // Trên điện thoại không focus để khỏi bật bàn phím che mất bảng icon
  if (!window.matchMedia("(pointer: coarse)").matches) ta.focus();
  ta.setSelectionRange(pos, pos);
  saveRecent(e);
  btn.classList.remove("pop"); void btn.offsetWidth; btn.classList.add("pop");
}

function render() {
  const [, name, list] = CATS[current];
  title.textContent = name;
  const items = list ? list.split(" ") : getRecent();
  grid.innerHTML = "";
  if (!items.length) {
    grid.innerHTML = '<div class="empty">Chưa có icon nào dùng gần đây</div>';
  }
  items.forEach(e => {
    const b = document.createElement("button");
    b.textContent = e;
    b.onclick = () => insert(e, b);
    grid.appendChild(b);
  });
  grid.scrollTop = 0;
  [...tabs.children].forEach((t, i) => t.classList.toggle("on", i === current));
}

CATS.forEach(([icon, name], i) => {
  const t = document.createElement("button");
  t.textContent = icon;
  t.title = name;
  t.onclick = () => { current = i; render(); };
  tabs.appendChild(t);
});
if (getRecent().length) current = 0;
render();
</script>
"""


def is_emoji_only(text: str) -> bool:
    """Tin nhắn chỉ toàn icon (tối đa vài cái) thì hiện to như iPhone."""
    s = text.replace(" ", "")
    return 0 < len(s) <= 12 and all(ord(c) > 0x2000 and not c.isalnum() for c in s)


# Chạy mỗi khi có tin mới: đếm chưa đọc trên tab, kêu "ting", hiện thông báo máy tính
NOTIFY_JS = r"""
<script>
const msgs = __DATA__;
const APP = __APP__;
const P = window.parent;
const doc = P.document;

// Khởi tạo 1 lần: khi quay lại tab thì xóa số tin chưa đọc
if (!P.__chatNoti) {
  P.__chatNoti = { unread: 0 };
  doc.addEventListener("visibilitychange", () => {
    if (!doc.hidden) { P.__chatNoti.unread = 0; doc.title = APP; }
  });
}
const S = P.__chatNoti;

if (doc.hidden) {
  S.unread += msgs.length;
  doc.title = "(" + S.unread + ") " + APP;
  try {
    if ("Notification" in P && P.Notification.permission === "granted") {
      msgs.forEach(m => {
        const n = new P.Notification(m.name, { body: m.text, tag: "chat-" + m.id });
        n.onclick = () => { P.focus(); n.close(); };
      });
    }
  } catch (e) {}
}

// Tiếng "ting ting"
try {
  const Ctx = P.AudioContext || P.webkitAudioContext;
  S.audio = S.audio || new Ctx();
  const ctx = S.audio;
  [880, 1320].forEach((f, i) => {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine"; o.frequency.value = f;
    const t = ctx.currentTime + i * 0.12;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.15, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
    o.connect(g); g.connect(ctx.destination);
    o.start(t); o.stop(t + 0.3);
  });
} catch (e) {}
</script>
"""

# Nút xin quyền hiện thông báo trên máy tính
PERMISSION_HTML = r"""
<style>
  body { margin: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: #EDEDED; font-size: 14px; }
  button {
    font: inherit; font-weight: 700; color: #1F1F1F; background: #FFD43B; border: none;
    border-radius: 999px; padding: 6px 16px; box-shadow: 0 3px 0 #D9A800; cursor: pointer;
  }
  p { margin: 0 0 8px; line-height: 1.4; }
</style>
<div id="box"></div>
<script>
const box = document.getElementById("box");
function show() {
  if (!("Notification" in window)) {
    box.innerHTML = "<p>Trình duyệt này chưa hỗ trợ thông báo hệ thống (ví dụ Safari trên iPhone). Bạn vẫn nhận được thông báo nhỏ và tiếng ting khi đang mở app.</p>";
    return;
  }
  const p = Notification.permission;
  if (p === "granted") {
    box.innerHTML = "<p>Đã bật ✅ Khi bạn chuyển sang tab khác, tin nhắn mới sẽ hiện thông báo ở góc màn hình.</p>";
  } else if (p === "denied") {
    box.innerHTML = "<p>Trình duyệt đang chặn thông báo. Bấm biểu tượng ổ khóa cạnh địa chỉ web → Notifications → Allow, rồi tải lại trang.</p>";
  } else {
    box.innerHTML = "<p>Nhận thông báo khi có tin mới lúc bạn đang ở tab khác.</p><button id='on'>🔔 Bật thông báo</button>";
    document.getElementById("on").onclick = async () => {
      const r = await Notification.requestPermission();
      if (r === "granted") {
        try { new window.parent.Notification("Đã bật thông báo 🔔", { body: "Có tin mới là mình báo liền!" }); } catch (e) {}
      }
      show();
    };
  }
}
show();
</script>
"""


def notify(fresh, room_names, current_room_id=None):
    """Báo tin mới: toast trong app (trừ phòng đang mở) + tab/âm thanh/thông báo máy tính."""
    toasts = [m for m in fresh if m["room_id"] != current_room_id][-3:]
    for m in toasts:
        emoji, _ = avatar_of(m["username"])
        preview = m["content"][:50] + ("…" if len(m["content"]) > 50 else "")
        room = room_names.get(m["room_id"], "")
        st.toast(f"**{m['username']}** ở *{room}*: {preview}", icon=emoji)
    data = json.dumps(
        [{"id": m["id"],
          "name": f"{m['username']} · {room_names.get(m['room_id'], '')}",
          "text": m["content"][:100]} for m in fresh],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    components.html(
        NOTIFY_JS.replace("__DATA__", data).replace("__APP__", json.dumps(APP_NAME)),
        height=0,
    )


# ---------- Kết nối Supabase ----------
@st.cache_resource
def db():
    url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 200_000
    ).hex()


# ----- Tài khoản -----
def register(username: str, password: str) -> str | None:
    """Trả về thông báo lỗi, hoặc None nếu thành công."""
    exists = db().table("users").select("username").eq("username", username).execute()
    if exists.data:
        return "Tên này có người lấy mất rồi, chọn tên khác nha."
    salt = os.urandom(16).hex()
    db().table("users").insert(
        {"username": username, "salt": salt, "pw_hash": hash_pw(password, salt)}
    ).execute()
    return None


def login(username: str, password: str) -> bool:
    res = db().table("users").select("salt, pw_hash").eq("username", username).execute()
    if not res.data:
        return False
    row = res.data[0]
    return hash_pw(password, row["salt"]) == row["pw_hash"]


# ----- Ghi nhớ đăng nhập (cookie) -----
SESSION_COOKIE = "thitham_login"
SESSION_DAYS = 30


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    db().table("sessions").insert({
        "token_hash": token_hash(token),
        "username": username,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(),
    }).execute()
    return token


def restore_session():
    """Đọc cookie của trình duyệt, nếu còn hạn thì tự đăng nhập lại."""
    token = st.context.cookies.get(SESSION_COOKIE)
    if not token:
        return
    rows = (
        db().table("sessions").select("username, expires_at")
        .eq("token_hash", token_hash(token)).execute().data
    )
    if not rows or datetime.fromisoformat(rows[0]["expires_at"]) < datetime.now(timezone.utc):
        return
    st.session_state.user = rows[0]["username"]
    st.session_state.token = token
    # Gia hạn thêm mỗi lần quay lại
    db().table("sessions").update({
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    }).eq("token_hash", token_hash(token)).execute()
    st.session_state.set_cookie = token


def cookie_js(value: str, max_age: int):
    components.html(
        "<script>window.parent.document.cookie = "
        f"'{SESSION_COOKIE}={value}; max-age={max_age}; path=/; SameSite=Lax; Secure';</script>",
        height=0,
    )


def remember(username: str):
    token = create_session(username)
    st.session_state.token = token
    st.session_state.set_cookie = token


# ----- Phòng chat -----
@st.cache_data(ttl=60, show_spinner=False)
def my_rooms(me: str):
    """Danh sách phòng của mình (lưu tạm 60 giây để đỡ gọi database)."""
    res = (
        db().table("room_members").select("room_id, last_read_id, rooms(name)")
        .eq("username", me).order("joined_at").execute()
    )
    return [
        {"id": r["room_id"], "name": r["rooms"]["name"], "last_read": r["last_read_id"] or 0}
        for r in res.data
    ]


@st.cache_data(ttl=60, show_spinner=False)
def room_members(room_id: int):
    res = (
        db().table("room_members").select("username")
        .eq("room_id", room_id).order("joined_at").execute()
    )
    return [r["username"] for r in res.data]


def refresh_rooms():
    my_rooms.clear()
    room_members.clear()


def create_room(name: str, password: str, me: str):
    """Trả về (phòng, lỗi)."""
    if db().table("rooms").select("id").eq("name", name).execute().data:
        return None, "Tên phòng này có rồi, chọn tên khác nha."
    salt = os.urandom(16).hex()
    room = db().table("rooms").insert(
        {"name": name, "salt": salt, "pw_hash": hash_pw(password, salt), "created_by": me}
    ).execute().data[0]
    db().table("room_members").insert({"room_id": room["id"], "username": me}).execute()
    refresh_rooms()
    return {"id": room["id"], "name": name}, None


def join_room(name: str, password: str, me: str):
    """Trả về (phòng, lỗi)."""
    res = db().table("rooms").select("id, salt, pw_hash").eq("name", name).execute()
    if not res.data or hash_pw(password, res.data[0]["salt"]) != res.data[0]["pw_hash"]:
        return None, "Sai tên phòng hoặc mật khẩu rồi."
    rid = res.data[0]["id"]
    already = (
        db().table("room_members").select("room_id")
        .eq("room_id", rid).eq("username", me).execute().data
    )
    if not already:
        db().table("room_members").insert({"room_id": rid, "username": me}).execute()
    refresh_rooms()
    return {"id": rid, "name": name}, None


def leave_room(room_id: int, me: str):
    db().table("room_members").delete().eq("room_id", room_id).eq("username", me).execute()
    refresh_rooms()


def mark_read(room_id: int, me: str, msg_id: int):
    st.session_state.setdefault("read_upto", {})[room_id] = msg_id
    (
        db().table("room_members").update({"last_read_id": msg_id})
        .eq("room_id", room_id).eq("username", me).execute()
    )


def last_read_of(room) -> int:
    return max(room["last_read"], st.session_state.get("read_upto", {}).get(room["id"], 0))


# ----- Tin nhắn -----
MSG_COLS = "id, room_id, username, content, created_at"


def send_message(room_id: int, username: str, content: str):
    db().table("messages").insert(
        {"room_id": room_id, "username": username, "content": content}
    ).execute()


def load_messages(room_id: int, limit: int = 100):
    res = (
        db().table("messages").select(MSG_COLS)
        .eq("room_id", room_id).order("id", desc=True).limit(limit).execute()
    )
    return list(reversed(res.data))


def global_max_id() -> int:
    r = db().table("messages").select("id").order("id", desc=True).limit(1).execute().data
    return r[0]["id"] if r else 0


def fetch_new(rooms):
    """1 truy vấn duy nhất: mọi tin mới ở các phòng của mình kể từ lần trước."""
    ids = [r["id"] for r in rooms]
    if not ids:
        return []
    return (
        db().table("messages").select(MSG_COLS)
        .in_("room_id", ids).gt("id", st.session_state.last_seen_id)
        .order("id").limit(50).execute().data
    )


def handle_new(me, rooms, fresh, current_room_id=None):
    if not fresh:
        return
    st.session_state.last_seen_id = max(st.session_state.last_seen_id, fresh[-1]["id"])
    others = [m for m in fresh if m["username"] != me]
    if others:
        notify(others, {r["id"]: r["name"] for r in rooms}, current_room_id)


def fmt_time(iso: str) -> str:
    t = datetime.fromisoformat(iso).astimezone(VN_TZ)
    if t.date() == datetime.now(VN_TZ).date():
        return t.strftime("%H:%M")
    return t.strftime("%d/%m %H:%M")


def room_icon(name: str) -> str:
    return html.escape(name.strip()[:1].upper() or "#")


def enter_room(room):
    st.session_state.room = room
    # Lấy mốc trước rồi mới tải tin, để không sót tin nào
    st.session_state.last_seen_id = global_max_id()
    st.session_state.room_msgs = load_messages(room["id"])
    st.rerun()


def leave_to_lobby():
    for k in ("room", "room_msgs"):
        st.session_state.pop(k, None)
    st.rerun()


def logout():
    token = st.session_state.pop("token", None)
    if token:
        db().table("sessions").delete().eq("token_hash", token_hash(token)).execute()
    st.session_state.clear_cookie = True
    for k in ("user", "room", "room_msgs", "last_seen_id", "read_upto"):
        st.session_state.pop(k, None)
    st.rerun()


def me_header():
    me = st.session_state.user
    emoji, color = avatar_of(me)
    col1, col2 = st.columns([3, 1], vertical_alignment="center")
    with col1:
        brand(
            f'<div class="me-chip"><span class="ava" style="background:{color}">{emoji}</span>'
            f"{html.escape(me)}</div>"
        )
    with col2:
        if st.button("Đăng xuất", use_container_width=True):
            logout()


# ---------- Màn hình đăng nhập ----------
def auth_screen():
    brand()
    room_code = st.secrets.get("ROOM_CODE", "")

    tab_login, tab_signup = st.tabs(["Đăng nhập", "Tạo tài khoản"])

    with tab_login:
        with st.form("login"):
            u = st.text_input("Tên của bạn")
            p = st.text_input("Mật khẩu", type="password")
            keep = st.checkbox("Ghi nhớ đăng nhập trên máy này", value=True)
            if st.form_submit_button("Đăng nhập", use_container_width=True):
                if login(u.strip(), p):
                    st.session_state.user = u.strip()
                    if keep:
                        remember(u.strip())
                    st.rerun()
                else:
                    st.error("Sai tên hoặc mật khẩu rồi.")

    with tab_signup:
        with st.form("signup"):
            u = st.text_input("Chọn một cái tên")
            p = st.text_input("Mật khẩu (ít nhất 6 ký tự)", type="password")
            code = st.text_input("Mã mời (hỏi người gửi link)", type="password")
            if st.form_submit_button("Tạo tài khoản", use_container_width=True):
                u = u.strip()
                if not room_code:
                    st.error("Chủ app chưa cài ROOM_CODE trong Secrets.")
                elif code != room_code:
                    st.error("Mã mời chưa đúng.")
                elif not (2 <= len(u) <= 30):
                    st.error("Tên cần từ 2 đến 30 ký tự.")
                elif len(p) < 6:
                    st.error("Mật khẩu cần ít nhất 6 ký tự.")
                else:
                    err = register(u, p)
                    if err:
                        st.error(err)
                    else:
                        st.session_state.user = u
                        remember(u)
                        st.rerun()


# ---------- Sảnh: danh sách phòng ----------
@st.fragment(run_every=8)
def room_list():
    me = st.session_state.user
    rooms = my_rooms(me)
    if "last_seen_id" not in st.session_state:
        st.session_state.last_seen_id = global_max_id()

    if not rooms:
        st.markdown(
            f'<div class="lobby-empty"><span>{APP_ICON}</span>'
            "Bạn chưa ở phòng nào.<br>Tạo phòng mới hoặc vào phòng bạn bè gửi nha.</div>",
            unsafe_allow_html=True,
        )
        return

    # 1 truy vấn: tin gần đây của tất cả các phòng → vừa làm xem trước, vừa đếm chưa đọc
    recent = (
        db().table("messages").select(MSG_COLS)
        .in_("room_id", [r["id"] for r in rooms])
        .order("id", desc=True).limit(300).execute().data
    )
    fresh = sorted(
        (m for m in recent if m["id"] > st.session_state.last_seen_id), key=lambda m: m["id"]
    )
    handle_new(me, rooms, fresh)

    for r in rooms:
        in_room = [m for m in recent if m["room_id"] == r["id"]]
        last = in_room[0] if in_room else None
        lr = last_read_of(r)
        unread = sum(1 for m in in_room if m["id"] > lr and m["username"] != me)
        if last:
            preview = html.escape(f'{last["username"]}: {last["content"]}'[:60])
            sub = f'{preview} · {fmt_time(last["created_at"])}'
        else:
            sub = "Chưa có tin nhắn nào"
        badge = f'<span class="badge">{unread if unread < 100 else "99+"}</span>' if unread else ""
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        c1.markdown(
            f'<div class="room-card"><div class="room-ico">{room_icon(r["name"])}</div>'
            f'<div class="room-info"><div class="room-name">{html.escape(r["name"])}{badge}</div>'
            f'<div class="room-last">{sub}</div></div></div>',
            unsafe_allow_html=True,
        )
        if c2.button("Vào", key=f"open_{r['id']}", use_container_width=True):
            enter_room({"id": r["id"], "name": r["name"]})


def lobby_screen():
    me = st.session_state.user
    me_header()

    st.markdown('<div class="section">Phòng của bạn</div>', unsafe_allow_html=True)
    room_list()

    st.markdown('<div class="section">Thêm phòng</div>', unsafe_allow_html=True)
    tab_join, tab_new = st.tabs(["Vào phòng có sẵn", "Tạo phòng mới"])

    with tab_join:
        with st.form("join_room"):
            name = st.text_input("Tên phòng")
            pw = st.text_input("Mật khẩu phòng", type="password")
            if st.form_submit_button("Vào phòng", use_container_width=True):
                room, err = join_room(name.strip(), pw, me)
                if err:
                    st.error(err)
                else:
                    enter_room(room)

    with tab_new:
        with st.form("new_room"):
            name = st.text_input("Đặt tên phòng (2–40 ký tự)")
            pw = st.text_input("Đặt mật khẩu phòng (ít nhất 4 ký tự)", type="password")
            st.caption("Muốn rủ ai vào thì gửi họ tên phòng + mật khẩu này. "
                       "Chat riêng 2 người: tạo phòng rồi chỉ gửi mật khẩu cho người đó.")
            if st.form_submit_button("Tạo phòng", use_container_width=True):
                name = name.strip()
                if not (2 <= len(name) <= 40):
                    st.error("Tên phòng cần từ 2 đến 40 ký tự.")
                elif len(pw) < 4:
                    st.error("Mật khẩu phòng cần ít nhất 4 ký tự.")
                else:
                    room, err = create_room(name, pw, me)
                    if err:
                        st.error(err)
                    else:
                        enter_room(room)

    with st.popover("🔔 Thông báo"):
        components.html(PERMISSION_HTML, height=110)


# ---------- Màn hình trong phòng ----------
@st.fragment(run_every=3)  # mỗi 3 giây chỉ hỏi database đúng 1 lần: "có tin gì mới không?"
def message_list():
    me = st.session_state.user
    room = st.session_state.room
    rooms = my_rooms(me)
    if "room_msgs" not in st.session_state:
        st.session_state.last_seen_id = global_max_id()
        st.session_state.room_msgs = load_messages(room["id"])

    fresh = fetch_new(rooms)
    if fresh:
        have = {m["id"] for m in st.session_state.room_msgs}
        mine_room = [m for m in fresh if m["room_id"] == room["id"] and m["id"] not in have]
        if mine_room:
            st.session_state.room_msgs = (st.session_state.room_msgs + mine_room)[-100:]
        handle_new(me, rooms, fresh, room["id"])

    msgs = st.session_state.room_msgs
    current = next((r for r in rooms if r["id"] == room["id"]), None)
    if msgs and current and msgs[-1]["id"] > last_read_of(current):
        mark_read(room["id"], me, msgs[-1]["id"])

    if not msgs:
        st.markdown(
            f'<div class="chat-box"><div class="empty"><span>{APP_ICON}</span>'
            "Chưa ai nói gì cả.<br>Mở lời trước đi!</div></div>",
            unsafe_allow_html=True,
        )
        return

    rows, prev = [], None
    for m in msgs:
        name = m["username"]
        is_me = name == me
        first = name != prev  # tin đầu tiên của một lượt nói
        prev = name
        emoji, color = avatar_of(name)
        big = " big" if is_emoji_only(m["content"]) else ""
        text = html.escape(m["content"]).replace("\n", "<br>")
        name_html = (
            f'<div class="name">{html.escape(name)}</div>' if first and not is_me else ""
        )
        rows.append(
            f'<div class="row {"me" if is_me else "other"}{" first" if first else ""}">'
            f'<div class="ava{"" if first else " hidden"}" style="background:{color}">{emoji}</div>'
            f'<div class="wrap">{name_html}<div class="bubble{big}">{text}</div>'
            f'<div class="time">{fmt_time(m["created_at"])}</div></div></div>'
        )

    # column-reverse: tin mới nhất nằm đầu HTML nhưng hiện ở dưới cùng
    st.markdown(
        '<div class="chat-box">' + "".join(reversed(rows)) + "</div>",
        unsafe_allow_html=True,
    )


def room_screen():
    me = st.session_state.user
    room = st.session_state.room
    members = room_members(room["id"])

    c1, c2, c3 = st.columns([1.2, 3, 1.3], vertical_alignment="center")
    with c1:
        if st.button("← Phòng", use_container_width=True):
            leave_to_lobby()
    with c2:
        st.markdown(
            f'<div class="room-title"><div class="room-ico">{room_icon(room["name"])}</div>'
            f'{html.escape(room["name"])}</div>',
            unsafe_allow_html=True,
        )
    with c3:
        with st.popover(f"👥 {len(members)}", use_container_width=True):
            st.markdown(
                "".join(
                    f'<div class="member"><span class="ava" style="background:{avatar_of(u)[1]}">'
                    f"{avatar_of(u)[0]}</span>{html.escape(u)}{' (bạn)' if u == me else ''}</div>"
                    for u in members
                ),
                unsafe_allow_html=True,
            )
            st.caption("Rủ thêm người: gửi họ tên phòng + mật khẩu phòng.")
            if st.button("Rời phòng", use_container_width=True):
                leave_room(room["id"], me)
                leave_to_lobby()

    # Gửi tin trước khi vẽ khung chat, để tin mình hiện ra ngay trong cùng lượt
    text = st.chat_input("Bạn muốn thì thầm gì?")
    if text and text.strip():
        send_message(room["id"], me, text.strip()[:2000])

    message_list()

    c1, c2 = st.columns(2)
    with c1:
        with st.popover("😊 Icon", use_container_width=True):
            components.html(EMOJI_PICKER, height=300)
    with c2:
        with st.popover("🔔 Thông báo", use_container_width=True):
            components.html(PERMISSION_HTML, height=110)


# ---------- Điều hướng ----------
if "user" not in st.session_state and not st.session_state.get("cookie_checked"):
    st.session_state.cookie_checked = True
    try:
        restore_session()
    except Exception:
        pass  # lỗi đọc phiên thì cứ cho đăng nhập bình thường

if token := st.session_state.pop("set_cookie", None):
    cookie_js(token, SESSION_DAYS * 86400)
if st.session_state.pop("clear_cookie", False):
    cookie_js("", 0)

if "user" not in st.session_state:
    auth_screen()
elif "room" not in st.session_state:
    lobby_screen()
else:
    room_screen()
