"""
App chat dễ thương chạy trên Streamlit, lưu dữ liệu trên Supabase.
- Mỗi người tự đăng ký tên + mật khẩu (cần "mã phòng" để chặn người lạ).
- Tin nhắn tự cập nhật mỗi 3 giây.
"""
import hashlib
import html
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

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
  --main: #FFD43B;
  --main-deep: #F0B400;
  --cream: #FFFBEA;
  --ink: #5A4520;
  --muted: #A88F55;
  --line: #F8E6A0;
}

/* Nền chấm bi */
.stApp {
  background-color: var(--cream);
  background-image: radial-gradient(#F6E3A0 1.6px, transparent 1.6px);
  background-size: 24px 24px;
  color: var(--ink);
}
header[data-testid="stHeader"] { background: transparent; }

.stApp p, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp h1, .stApp h2, .stApp h3,
.stApp [data-baseweb="tab"], .brand, .chat-box {
  font-family: 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', sans-serif;
}

/* Tên app */
.brand { display: flex; align-items: center; gap: 12px; margin: 4px 0 14px; }
.brand .logo {
  width: 56px; height: 56px; border-radius: 18px; background: #fff;
  border: 2px solid var(--line); display: grid; place-items: center;
  font-size: 30px; transform: rotate(-6deg);
}
.brand h1 { font-size: 34px; font-weight: 700; color: var(--ink); margin: 0; padding: 0; line-height: 1; }
.brand p { margin: 2px 0 0; color: var(--muted); font-size: 15px; }
.me-chip {
  display: inline-flex; align-items: center; gap: 6px; background: #fff;
  border: 2px solid var(--line); border-radius: 999px; padding: 2px 12px 2px 4px;
  font-size: 14px; color: var(--ink);
}
.me-chip .ava { width: 26px; height: 26px; font-size: 15px; }

/* Khung đăng nhập */
[data-testid="stForm"] {
  background: #fff; border: 2px solid var(--line); border-radius: 24px; padding: 18px;
}
[data-baseweb="input"] { border-radius: 14px !important; }

/* Tab thành dạng viên thuốc */
[data-baseweb="tab-list"] { gap: 8px; }
[data-baseweb="tab"] {
  background: #fff; border: 2px solid var(--line) !important;
  border-radius: 999px; padding: 2px 18px !important; height: auto;
}
[data-baseweb="tab"][aria-selected="true"] { background: var(--main); border-color: var(--main) !important; }
[data-baseweb="tab"][aria-selected="true"] p { color: var(--ink) !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }

/* Nút bấm tròn trịa, có "đáy" như kẹo */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  background: var(--main); color: var(--ink); border: none; border-radius: 999px;
  font-weight: 700; box-shadow: 0 3px 0 var(--main-deep);
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  background: var(--main-deep); color: var(--ink);
}
.stButton > button:active, [data-testid="stFormSubmitButton"] > button:active {
  transform: translateY(2px); box-shadow: 0 1px 0 var(--main-deep);
}

/* Ô nhập tin nhắn */
[data-testid="stChatInput"] > div {
  border-radius: 999px !important; border: 2px solid var(--line) !important; background: #fff !important;
}

/* Khung tin nhắn: column-reverse để luôn cuộn sẵn ở tin mới nhất */
.chat-box {
  height: 62vh; overflow-y: auto; display: flex; flex-direction: column-reverse;
  gap: 4px; padding: 16px 12px; background: rgba(255,255,255,.75);
  border: 2px solid var(--line); border-radius: 26px;
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
.row.other .bubble { background: #fff; border: 2px solid var(--line); color: var(--ink); border-bottom-left-radius: 6px; }
.row.me .bubble { background: var(--main); color: var(--ink); border-bottom-right-radius: 6px; }
.time { font-size: 11px; color: var(--muted); margin: 1px 10px 0; }
.empty { margin: auto; text-align: center; color: var(--muted); font-size: 16px; }
.empty span { font-size: 44px; display: block; }
.bubble.big { background: transparent !important; border: none !important; font-size: 40px; line-height: 1.15; padding: 0 4px; }

/* Nút mở bảng icon */
[data-testid="stPopover"] button {
  background: #fff; border: 2px solid var(--line); border-radius: 999px; color: var(--ink);
}
[data-testid="stPopover"] button:hover { border-color: var(--main); color: var(--main-deep); }

/* Sảnh & phòng */
.section { font-weight: 700; font-size: 18px; margin: 16px 0 6px; color: var(--ink); }
.room-card {
  display: flex; gap: 12px; align-items: center; background: #fff;
  border: 2px solid var(--line); border-radius: 20px; padding: 10px 14px;
}
.room-ico {
  width: 44px; height: 44px; border-radius: 14px; background: var(--main); color: var(--ink);
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
  text-align: center; color: var(--muted); background: rgba(255,255,255,.75);
  border: 2px dashed var(--line); border-radius: 20px; padding: 22px 12px;
}
.lobby-empty span { font-size: 40px; display: block; }
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
  .picker { background: #fff; border: 2px solid #F8E6A0; border-radius: 20px; overflow: hidden; }
  .title { font-size: 13px; font-weight: 700; color: #A88F55; padding: 8px 12px 2px; }
  .grid {
    height: 208px; overflow-y: auto; padding: 4px 8px 8px;
    display: grid; grid-template-columns: repeat(auto-fill, minmax(38px, 1fr));
  }
  .grid button {
    font-size: 25px; line-height: 1; height: 40px; border: none; background: none;
    border-radius: 10px; cursor: pointer;
    font-family: 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif;
  }
  .grid button:hover { background: #FFF3C4; }
  .grid button.pop { animation: pop .25s ease; }
  @keyframes pop { 50% { transform: scale(1.35); } }
  .empty { grid-column: 1 / -1; color: #A88F55; font-size: 14px; text-align: center; padding-top: 70px; }
  .tabs { display: flex; justify-content: space-around; border-top: 2px solid #F8E6A0; background: #FFFBEA; }
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
  body { margin: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: #5A4520; font-size: 14px; }
  button {
    font: inherit; font-weight: 700; color: #5A4520; background: #FFD43B; border: none;
    border-radius: 999px; padding: 6px 16px; box-shadow: 0 3px 0 #F0B400; cursor: pointer;
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


# ----- Phòng chat -----
def create_room(name: str, password: str, me: str):
    """Trả về (phòng, lỗi)."""
    if db().table("rooms").select("id").eq("name", name).execute().data:
        return None, "Tên phòng này có rồi, chọn tên khác nha."
    salt = os.urandom(16).hex()
    room = db().table("rooms").insert(
        {"name": name, "salt": salt, "pw_hash": hash_pw(password, salt), "created_by": me}
    ).execute().data[0]
    db().table("room_members").insert({"room_id": room["id"], "username": me}).execute()
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
    return {"id": rid, "name": name}, None


def my_rooms(me: str):
    res = (
        db().table("room_members").select("room_id, last_read_id, rooms(name)")
        .eq("username", me).order("joined_at").execute()
    )
    return [
        {"id": r["room_id"], "name": r["rooms"]["name"], "last_read": r["last_read_id"] or 0}
        for r in res.data
    ]


def room_members(room_id: int):
    res = (
        db().table("room_members").select("username")
        .eq("room_id", room_id).order("joined_at").execute()
    )
    return [r["username"] for r in res.data]


def leave_room(room_id: int, me: str):
    db().table("room_members").delete().eq("room_id", room_id).eq("username", me).execute()


def mark_read(room_id: int, me: str, msg_id: int):
    (
        db().table("room_members").update({"last_read_id": msg_id})
        .eq("room_id", room_id).eq("username", me).execute()
    )


def room_summary(room_id: int, last_read: int, me: str):
    """Tin cuối cùng + số tin chưa đọc của một phòng."""
    last = (
        db().table("messages").select("username, content, created_at")
        .eq("room_id", room_id).order("id", desc=True).limit(1).execute().data
    )
    unread = (
        db().table("messages").select("id", count="exact")
        .eq("room_id", room_id).gt("id", last_read).neq("username", me)
        .limit(1).execute().count
    ) or 0
    return (last[0] if last else None), unread


# ----- Tin nhắn -----
def send_message(room_id: int, username: str, content: str):
    db().table("messages").insert(
        {"room_id": room_id, "username": username, "content": content}
    ).execute()


def load_messages(room_id: int, limit: int = 200):
    res = (
        db().table("messages").select("id, username, content, created_at")
        .eq("room_id", room_id).order("id", desc=True).limit(limit).execute()
    )
    return list(reversed(res.data))


def global_max_id() -> int:
    r = db().table("messages").select("id").order("id", desc=True).limit(1).execute().data
    return r[0]["id"] if r else 0


def check_new(me: str, rooms, current_room_id=None):
    """Tìm tin mới ở mọi phòng mình tham gia để báo."""
    if "last_seen_id" not in st.session_state:
        st.session_state.last_seen_id = global_max_id()
        return
    ids = [r["id"] for r in rooms]
    if not ids:
        return
    fresh = (
        db().table("messages").select("id, room_id, username, content")
        .in_("room_id", ids).gt("id", st.session_state.last_seen_id)
        .order("id").limit(30).execute().data
    )
    if not fresh:
        return
    st.session_state.last_seen_id = fresh[-1]["id"]
    fresh = [m for m in fresh if m["username"] != me]
    if fresh:
        notify(fresh, {r["id"]: r["name"] for r in rooms}, current_room_id)


def fmt_time(iso: str) -> str:
    t = datetime.fromisoformat(iso).astimezone(VN_TZ)
    if t.date() == datetime.now(VN_TZ).date():
        return t.strftime("%H:%M")
    return t.strftime("%d/%m %H:%M")


def room_icon(name: str) -> str:
    return html.escape(name.strip()[:1].upper() or "#")


def enter_room(room):
    st.session_state.room = room
    st.session_state.last_seen_id = global_max_id()  # không báo lại tin cũ của phòng mới vào
    st.rerun()


def logout():
    for k in ("user", "room", "last_seen_id"):
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
            if st.form_submit_button("Đăng nhập", use_container_width=True):
                if login(u.strip(), p):
                    st.session_state.user = u.strip()
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
                        st.rerun()


# ---------- Sảnh: danh sách phòng ----------
@st.fragment(run_every=5)
def room_list():
    me = st.session_state.user
    rooms = my_rooms(me)
    check_new(me, rooms)

    if not rooms:
        st.markdown(
            f'<div class="lobby-empty"><span>{APP_ICON}</span>'
            "Bạn chưa ở phòng nào.<br>Tạo phòng mới hoặc vào phòng bạn bè gửi nha.</div>",
            unsafe_allow_html=True,
        )
        return

    for r in rooms:
        last, unread = room_summary(r["id"], r["last_read"], me)
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
@st.fragment(run_every=3)  # tự tải lại tin nhắn mỗi 3 giây
def message_list():
    me = st.session_state.user
    room = st.session_state.room
    rooms = my_rooms(me)
    current = next((r for r in rooms if r["id"] == room["id"]), None)
    if current is None:  # không còn là thành viên phòng này
        st.session_state.pop("room", None)
        st.rerun()

    check_new(me, rooms, room["id"])
    msgs = load_messages(room["id"])

    if msgs and msgs[-1]["id"] > current["last_read"]:
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
            st.session_state.pop("room", None)
            st.rerun()
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
                st.session_state.pop("room", None)
                st.rerun()

    message_list()

    c1, c2 = st.columns(2)
    with c1:
        with st.popover("😊 Icon", use_container_width=True):
            components.html(EMOJI_PICKER, height=300)
    with c2:
        with st.popover("🔔 Thông báo", use_container_width=True):
            components.html(PERMISSION_HTML, height=110)

    text = st.chat_input("Bạn muốn thì thầm gì?")
    if text and text.strip():
        send_message(room["id"], me, text.strip()[:2000])
        st.rerun()


# ---------- Điều hướng ----------
if "user" not in st.session_state:
    auth_screen()
elif "room" not in st.session_state:
    lobby_screen()
else:
    room_screen()
