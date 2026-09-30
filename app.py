"""
App chat đơn giản chạy trên Streamlit, lưu dữ liệu trên Supabase.
- Mỗi người tự đăng ký tên + mật khẩu (cần "mã phòng" để chặn người lạ).
- Tin nhắn tự cập nhật mỗi 3 giây.
"""
import hashlib
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import create_client

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

st.set_page_config(page_title="Phòng chat", page_icon="💬", layout="centered")


# ---------- Kết nối Supabase ----------
@st.cache_resource
def db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 200_000
    ).hex()


def register(username: str, password: str) -> str | None:
    """Trả về thông báo lỗi, hoặc None nếu thành công."""
    exists = db().table("users").select("username").eq("username", username).execute()
    if exists.data:
        return "Tên này đã có người dùng. Chọn tên khác hoặc chuyển sang tab Đăng nhập."
    salt = os.urandom(16).hex()
    db().table("users").insert(
        {"username": username, "salt": salt, "pw_hash": hash_pw(password, salt)}
    ).execute()
    return None


def login(username: str, password: str) -> bool:
    res = (
        db().table("users").select("salt, pw_hash")
        .eq("username", username).execute()
    )
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
    st.title("💬 Phòng chat")
    room_code = st.secrets.get("ROOM_CODE", "")

    tab_login, tab_signup = st.tabs(["Đăng nhập", "Tạo tài khoản"])

    with tab_login:
        with st.form("login"):
            u = st.text_input("Tên hiển thị")
            p = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập", use_container_width=True):
                if login(u.strip(), p):
                    st.session_state.user = u.strip()
                    st.rerun()
                else:
                    st.error("Sai tên hoặc mật khẩu.")

    with tab_signup:
        with st.form("signup"):
            u = st.text_input("Chọn tên hiển thị")
            p = st.text_input("Chọn mật khẩu (tối thiểu 6 ký tự)", type="password")
            code = st.text_input("Mã phòng (hỏi người gửi link)", type="password")
            if st.form_submit_button("Tạo tài khoản", use_container_width=True):
                u = u.strip()
                if not room_code:
                    st.error("Chủ app chưa cài ROOM_CODE trong Secrets.")
                elif code != room_code:
                    st.error("Mã phòng không đúng.")
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
@st.fragment(run_every=3)  # tự tải lại khung tin nhắn mỗi 3 giây
def message_list():
    me = st.session_state.user
    msgs = load_messages()
    if not msgs:
        st.caption("Chưa có tin nhắn nào. Gửi câu đầu tiên đi!")
    for m in msgs:
        when = (
            datetime.fromisoformat(m["created_at"]).astimezone(VN_TZ)
            .strftime("%H:%M %d/%m")
        )
        is_me = m["username"] == me
        with st.chat_message("user" if is_me else "assistant",
                             avatar="🙂" if is_me else "👤"):
            st.markdown(f"**{m['username']}** · <small>{when}</small>",
                        unsafe_allow_html=True)
            st.text(m["content"])  # st.text để không render HTML lạ từ người khác


def chat_screen():
    me = st.session_state.user
    col1, col2 = st.columns([4, 1])
    col1.title("💬 Phòng chat")
    if col2.button("Đăng xuất"):
        del st.session_state.user
        st.rerun()
    st.caption(f"Bạn đang đăng nhập là **{me}**")

    message_list()

    text = st.chat_input("Nhập tin nhắn...")
    if text and text.strip():
        send_message(me, text.strip()[:2000])
        st.rerun()


if "user" in st.session_state:
    chat_screen()
else:
    auth_screen()
