"""
App chat dễ thương chạy trên Streamlit, lưu dữ liệu trên Supabase.
- Mỗi người tự đăng ký tên + mật khẩu (cần "mã phòng" để chặn người lạ).
- Tin nhắn tự cập nhật mỗi 3 giây.
"""
import hashlib
import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import create_client

APP_NAME = "Thì thầm"                  # đổi tên app ở đây
APP_TAGLINE = "chỗ tụi mình tám chuyện"  # dòng chữ nhỏ dưới tên
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

st.set_page_config(page_title=APP_NAME, page_icon="🫧", layout="centered")

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
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@400;500;600;700;800&display=swap');

:root {
  --pink: #FF8FAB;
  --pink-deep: #EE6A8F;
  --cream: #FFF6F0;
  --plum: #5B3A4F;
  --muted: #A58A99;
  --line: #F6D9E1;
}

/* Nền chấm bi */
.stApp {
  background-color: var(--cream);
  background-image: radial-gradient(#F8D3DE 1.6px, transparent 1.6px);
  background-size: 24px 24px;
  color: var(--plum);
}
header[data-testid="stHeader"] { background: transparent; }

.stApp p, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp h1, .stApp h2, .stApp h3,
.stApp [data-baseweb="tab"], .brand, .chat-box {
  font-family: 'Baloo 2', 'Nunito', system-ui, sans-serif;
}

/* Tên app */
.brand { display: flex; align-items: center; gap: 12px; margin: 4px 0 14px; }
.brand .logo {
  width: 56px; height: 56px; border-radius: 18px; background: #fff;
  border: 2px solid var(--line); display: grid; place-items: center;
  font-size: 30px; transform: rotate(-6deg);
}
.brand h1 { font-size: 34px; font-weight: 800; color: var(--plum); margin: 0; padding: 0; line-height: 1; }
.brand p { margin: 2px 0 0; color: var(--muted); font-size: 15px; }
.me-chip {
  display: inline-flex; align-items: center; gap: 6px; background: #fff;
  border: 2px solid var(--line); border-radius: 999px; padding: 2px 12px 2px 4px;
  font-size: 14px; color: var(--plum);
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
[data-baseweb="tab"][aria-selected="true"] { background: var(--pink); border-color: var(--pink) !important; }
[data-baseweb="tab"][aria-selected="true"] p { color: #fff !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }

/* Nút bấm tròn trịa, có "đáy" như kẹo */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  background: var(--pink); color: #fff; border: none; border-radius: 999px;
  font-weight: 700; box-shadow: 0 3px 0 var(--pink-deep);
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  background: var(--pink-deep); color: #fff;
}
.stButton > button:active, [data-testid="stFormSubmitButton"] > button:active {
  transform: translateY(2px); box-shadow: 0 1px 0 var(--pink-deep);
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
.row.other .bubble { background: #fff; border: 2px solid var(--line); color: var(--plum); border-bottom-left-radius: 6px; }
.row.me .bubble { background: var(--pink); color: #fff; border-bottom-right-radius: 6px; }
.time { font-size: 11px; color: var(--muted); margin: 1px 10px 0; }
.empty { margin: auto; text-align: center; color: var(--muted); font-size: 16px; }
.empty span { font-size: 44px; display: block; }
</style>
""",
    unsafe_allow_html=True,
)


def brand(extra: str = ""):
    st.markdown(
        f'<div class="brand"><div class="logo">🫧</div>'
        f'<div><h1>{APP_NAME}</h1><p>{APP_TAGLINE}</p></div></div>{extra}',
        unsafe_allow_html=True,
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


def send_message(username: str, content: str):
    db().table("messages").insert({"username": username, "content": content}).execute()


def load_messages(limit: int = 200):
    res = (
        db().table("messages").select("username, content, created_at")
        .order("id", desc=True).limit(limit).execute()
    )
    return list(reversed(res.data))


# ---------- Màn hình đăng nhập ----------
def auth_screen():
    brand()
    room_code = st.secrets.get("ROOM_CODE", "")

    tab_login, tab_signup = st.tabs(["Đăng nhập", "Tạo tài khoản"])

    with tab_login:
        with st.form("login"):
            u = st.text_input("Tên của bạn")
            p = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Vào phòng", use_container_width=True):
                if login(u.strip(), p):
                    st.session_state.user = u.strip()
                    st.rerun()
                else:
                    st.error("Sai tên hoặc mật khẩu rồi.")

    with tab_signup:
        with st.form("signup"):
            u = st.text_input("Chọn một cái tên")
            p = st.text_input("Mật khẩu (ít nhất 6 ký tự)", type="password")
            code = st.text_input("Mã phòng (hỏi người gửi link)", type="password")
            if st.form_submit_button("Tạo tài khoản", use_container_width=True):
                u = u.strip()
                if not room_code:
                    st.error("Chủ app chưa cài ROOM_CODE trong Secrets.")
                elif code != room_code:
                    st.error("Mã phòng chưa đúng.")
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


# ---------- Màn hình chat ----------
def fmt_time(iso: str) -> str:
    t = datetime.fromisoformat(iso).astimezone(VN_TZ)
    if t.date() == datetime.now(VN_TZ).date():
        return t.strftime("%H:%M")
    return t.strftime("%d/%m %H:%M")


@st.fragment(run_every=3)  # tự tải lại khung tin nhắn mỗi 3 giây
def message_list():
    me = st.session_state.user
    msgs = load_messages()

    if not msgs:
        st.markdown(
            '<div class="chat-box"><div class="empty"><span>🫧</span>'
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
        text = html.escape(m["content"]).replace("\n", "<br>")
        name_html = (
            f'<div class="name">{html.escape(name)}</div>' if first and not is_me else ""
        )
        rows.append(
            f'<div class="row {"me" if is_me else "other"}{" first" if first else ""}">'
            f'<div class="ava{"" if first else " hidden"}" style="background:{color}">{emoji}</div>'
            f'<div class="wrap">{name_html}<div class="bubble">{text}</div>'
            f'<div class="time">{fmt_time(m["created_at"])}</div></div></div>'
        )

    # column-reverse: tin mới nhất nằm đầu HTML nhưng hiện ở dưới cùng
    st.markdown(
        '<div class="chat-box">' + "".join(reversed(rows)) + "</div>",
        unsafe_allow_html=True,
    )


def chat_screen():
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
            del st.session_state.user
            st.rerun()

    message_list()

    text = st.chat_input("Nhắn gì đó đi...")
    if text and text.strip():
        send_message(me, text.strip()[:2000])
        st.rerun()


if "user" in st.session_state:
    chat_screen()
else:
    auth_screen()
