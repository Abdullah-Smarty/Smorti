"""
Streamlit Web Interface for Smorti AI Assistant
Version: v1.2
Run with: streamlit run streamlit_app.py
"""

import streamlit as st
import sys
import os
import re
import html
import json
import time
import uuid
from pathlib import Path

# ----------------------------
# App version (change this when you release)
# ----------------------------
APP_VERSION = "v1.2"

def get_git_commit() -> str:
    # Streamlit Cloud usually clones a git repo, so this often works
    try:
        head = Path(".git") / "HEAD"
        if not head.exists():
            return ""
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            ref_path = Path(".git") / ref.split(" ", 1)[1].strip()
            if ref_path.exists():
                return ref_path.read_text().strip()[:7]
        # detached HEAD case
        return ref[:7]
    except Exception:
        return ""

GIT_SHA = get_git_commit()
DISPLAY_VERSION = f"{APP_VERSION} ({GIT_SHA})" if GIT_SHA else APP_VERSION

# ----------------------------
# Page configuration
# ----------------------------
st.set_page_config(
    page_title=f"Smorti {DISPLAY_VERSION}",
    page_icon="🤖",
    layout="centered"
)

# ----------------------------
# Load Streamlit Secrets early (Cloud) -> env vars
# ----------------------------
def load_secrets_to_env():
    for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        if k in st.secrets and not os.getenv(k):
            os.environ[k] = st.secrets[k]

load_secrets_to_env()

# ----------------------------
# Session ID (per user session) for logging
# ----------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# ----------------------------
# Path for local imports
# ----------------------------
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from your CLAUDE.py file (after env keys are set)
from CLAUDE import (
    ProductCatalog,
    handle_chat_message,
    logger
)

# ----------------------------
# Logging helpers
# (These logs show in Streamlit Cloud -> Manage app -> Logs)
# ----------------------------
def clip(s: str, n: int = 350) -> str:
    s = s or ""
    s = s.replace("\r", " ").replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s

def log_event(event: str, payload: dict):
    record = {
        "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sid": st.session_state.session_id,
        "event": event,
        **payload
    }
    line = json.dumps(record, ensure_ascii=False)

    # Guaranteed in Streamlit Cloud logs:
    print(line)

    # Also keep python logger:
    try:
        logger.info(line)
    except Exception:
        pass

    # Keep last few events inside session (optional sidebar debug)
    if "debug_events" not in st.session_state:
        st.session_state.debug_events = []
    st.session_state.debug_events.append(record)
    st.session_state.debug_events = st.session_state.debug_events[-40:]  # last 40

# ----------------------------
# Language + RTL/LTR helpers
# ----------------------------
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
EN_RE = re.compile(r"[A-Za-z]")

def detect_lang_simple(text: str) -> str:
    """Return 'ar' or 'en' based on which chars dominate."""
    text = text or ""
    ar = len(ARABIC_RE.findall(text))
    en = len(EN_RE.findall(text))
    return "ar" if ar > en else "en"

def user_requested_language_switch(text: str) -> str | None:
    """
    If the user clearly asks to switch language, respect it.
    Returns 'ar' / 'en' or None.
    """
    t = (text or "").lower().strip()
    # English requests
    if "english" in t or "in english" in t or "speak english" in t:
        return "en"
    # Arabic requests
    if "عربي" in t or "باللغة العربية" in t or "تكلم عربي" in t:
        return "ar"
    return None

# Persist conversation language to keep layout stable
if "chat_lang" not in st.session_state:
    st.session_state.chat_lang = None  # will set after first message

# ----------------------------
# Clickable links + nicer formatting
# ----------------------------
URL_RE = re.compile(r"(https?://[^\s<]+)")

def format_for_html(text: str) -> str:
    """
    - escapes html
    - converts **bold** -> <strong>
    - converts URLs -> clickable <a>
    - preserves new lines
    """
    text = text or ""

    # escape first
    safe = html.escape(text)

    # **bold** -> <strong>
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)

    # URLs -> anchors (keep url itself LTR even inside Arabic)
    def repl(m):
        url = m.group(1)
        url_clean = url.rstrip(").,،؛")  # trim common trailing punct
        trailing = url[len(url_clean):]
        return (
            f'<a href="{url_clean}" target="_blank" rel="noopener noreferrer">'
            f'<span class="linkltr">{url_clean}</span>'
            f"</a>{html.escape(trailing)}"
        )

    safe = URL_RE.sub(repl, safe)

    # new lines
    safe = safe.replace("\n", "<br>")
    return safe

def render_message(content: str, preferred_lang: str):
    """
    Render message with stable RTL/LTR based on preferred conversation language.
    This avoids the “scrambled” look when Arabic + English mix in one bubble.
    """
    preferred_lang = preferred_lang or detect_lang_simple(content)
    safe_html = format_for_html(content)

    if preferred_lang == "ar":
        st.markdown(f'<div class="rtl">{safe_html}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ltr">{safe_html}</div>', unsafe_allow_html=True)

# ----------------------------
# Custom CSS (Arabic support + stable layout)
# ----------------------------
st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: "Segoe UI", "Tahoma", "Arial",
                     "Noto Naskh Arabic", "Noto Sans Arabic", sans-serif;
    }

    .stChatMessage {
        font-size: 16px;
        line-height: 1.7;
    }

    .rtl {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
        word-break: break-word;
    }

    .ltr {
        direction: ltr;
        text-align: left;
        unicode-bidi: plaintext;
        word-break: break-word;
    }

    /* Force URLs to stay LTR so they don’t “flip” inside Arabic */
    .linkltr {
        direction: ltr;
        unicode-bidi: embed;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Initialize session state
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "data" / "products_enriched.csv"

# Cache catalog for stability + speed
@st.cache_resource
def load_catalog():
    cat = ProductCatalog(str(CATALOG_PATH))
    cat.load()
    return cat

if "catalog" not in st.session_state:
    with st.spinner("🔄 جاري تحميل الكتالوج..."):
        try:
            st.session_state.catalog = load_catalog()
            log_event("catalog_loaded", {
                "catalog_path": str(CATALOG_PATH),
                "products_count": len(getattr(st.session_state.catalog, "products", []) or []),
            })
        except Exception as e:
            log_event("catalog_load_error", {"error": str(e), "catalog_path": str(CATALOG_PATH)})
            st.error("❌ خطأ في تحميل الكتالوج. التفاصيل بالأسفل:")
            st.exception(e)
            st.stop()

# ----------------------------
# System prompt (keep yours, but make sure it says: do NOT invent links/products)
# ----------------------------
SYSTEM_PROMPT = """أنت سمورتي (Smorti)، مساعد الذكاء الاصطناعي لمتجر SMART.

مهم جداً:
- لا تخترع أي منتج أو رابط. الروابط يجب أن تكون فقط من (AVAILABLE PRODUCTS) أو من الروابط الرسمية أدناه.
- لا تذكر شاشات أو موديلات غير موجودة في البيانات.
- التزم بلغة العميل: إذا بدأ عربي رد عربي. إذا بدأ إنجليزي رد إنجليزي. لا تخلط لغتين في نفس الرد إلا إذا كان اسم موديل/شركة.

التقسيط المتاح (معلومة ثابتة):
- Tabby / Tamara / MisPay
- 4 دفعات (25% الآن والباقي على 3 أشهر)
- بدون فوائد 0%
- قد يمكن تمديد الفترة حسب مزود التقسيط

ملاحظة الاستخدام:
- أجهزة BOOX (حبر إلكتروني) ممتازة للقراءة والكتابة وملفات PDF، لكنها ليست الأفضل لمشاهدة الفيديو أو الألعاب مثل شاشات LCD.
- لو العميل يسأل عن شاشة/مونيتور للألعاب → اقترح مونيتور/شاشة مناسبة، وليس BOOX.
- لو يسأل عن الشاشات التفاعلية: وضّح أنها قوية للاجتماعات والترفيه والعمل وقد تُستخدم للألعاب لكن أسعارها أعلى لأنها AIO.

عمر الجهاز:
- لا تعطي رقم ثابت. قل يعتمد على الاستخدام، وغالباً يتجاوز 5 سنوات حسب دورات الشحن وطريقة الاستخدام.

البطارية:
- عادة BOOX تدوم أيام (3-4 أيام بسهولة) وقد تصل أسبوع حسب الاستخدام.
- الأبيض والأسود غالباً يدوم أطول من الملون بسبب استهلاك أقل.

الروابط الرسمية:
- المتجر: https://shop.smart.sa/ar
- قسم الأجهزة اللوحية: https://shop.smart.sa/ar/category/EdyrGY
- قسم الشاشات التفاعلية: https://shop.smart.sa/ar/category/YYKKAR
- قسم الكمبيوتر: https://shop.smart.sa/ar/category/AxRPaD
- قسم البرامج: https://shop.smart.sa/ar/category/QvKYzR
- واتساب: https://wa.me/966593440030
"""

# ----------------------------
# Header
# ----------------------------
st.title(f"🤖 Smorti - مساعد متجر SMART  •  {DISPLAY_VERSION}")
st.markdown("---")

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.header("ℹ️ معلومات التطبيق")
    st.write("**Smorti AI Assistant**")
    st.write(f"الإصدار: **{DISPLAY_VERSION}**")
    st.caption(f"Session ID: `{st.session_state.session_id}`")

    st.markdown("---")
    debug = st.toggle("🪲 Debug mode (إظهار التفاصيل)", value=False)

    st.markdown("---")
    st.subheader("🔐 حالة المفاتيح")
    st.write("GROQ_API_KEY:", "✅" if os.getenv("GROQ_API_KEY") else "❌")
    st.write("OPENAI_API_KEY:", "✅" if os.getenv("OPENAI_API_KEY") else "❌")

    st.markdown("---")
    st.subheader("📊 إحصائيات")
    if getattr(st.session_state.catalog, "products", None):
        st.metric("عدد المنتجات", len(st.session_state.catalog.products))
    st.metric("عدد الرسائل", len(st.session_state.messages))

    if debug and "debug_events" in st.session_state:
        st.markdown("---")
        st.subheader("📜 Debug events (آخر 40)")
        st.json(st.session_state.debug_events)

    st.markdown("---")
    if st.button("🔄 إعادة تشغيل المحادثة"):
        log_event("chat_reset", {"messages_before": len(st.session_state.messages)})
        st.session_state.messages = []
        st.session_state.chat_lang = None
        st.rerun()

# ----------------------------
# Display chat messages
# ----------------------------
for message in st.session_state.messages:
    role = "user" if message["role"] == "user" else "assistant"
    avatar = "🧑" if role == "user" else "🤖"
    with st.chat_message(role, avatar=avatar):
        render_message(message["content"], st.session_state.chat_lang or "ar")

# ----------------------------
# Chat input
# ----------------------------
if prompt := st.chat_input("اكتب رسالتك هنا... / Type your message here..."):
    # Decide / lock language early
    requested = user_requested_language_switch(prompt)
    if st.session_state.chat_lang is None:
        st.session_state.chat_lang = requested or detect_lang_simple(prompt)
    elif requested:
        st.session_state.chat_lang = requested

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar="🧑"):
        render_message(prompt, st.session_state.chat_lang)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("⏳ جاري الكتابة..."):
            try:
                conversation_history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in st.session_state.messages[:-1]
                ]

                log_event("user_message", {
                    "text": clip(prompt),
                    "chat_lang": st.session_state.chat_lang,
                    "history_len": len(conversation_history),
                })

                if debug:
                    st.sidebar.subheader("🧾 آخر إدخال")
                    st.sidebar.write(prompt)
                    st.sidebar.subheader("🧠 Conversation history (آخر 6)")
                    st.sidebar.json(conversation_history[-6:])

                # IMPORTANT: pass language preference to backend
                response = handle_chat_message(
                    user_input=prompt,
                    catalog=st.session_state.catalog,
                    system_prompt=SYSTEM_PROMPT,
                    conversation_history=conversation_history,
                    language=st.session_state.chat_lang  # <-- stable
                )

                log_event("assistant_response", {
                    "text": clip(response),
                    "len": len(response) if response else 0,
                })

                render_message(response, st.session_state.chat_lang)
                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                log_event("error", {"error": str(e), "prompt": clip(prompt)})
                st.error("❌ خطأ (تفاصيل):")
                st.exception(e)

# Footer
st.markdown("---")
st.caption(f"Smorti {DISPLAY_VERSION} 🤍")