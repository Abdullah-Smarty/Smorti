"""
Streamlit Web Interface for Smorti AI Assistant
Version: v1.3
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
# App version (under development)
# ----------------------------
APP_VERSION = "v0.31"

def get_git_commit() -> str:
    """Get git commit hash if available"""
    try:
        head = Path(".git") / "HEAD"
        if not head.exists():
            return ""
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            ref_path = Path(".git") / ref.split(" ", 1)[1].strip()
            if ref_path.exists():
                return ref_path.read_text().strip()[:7]
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
# Load Streamlit Secrets (optional for local testing)
# ----------------------------
def load_secrets_to_env():
    """Load secrets from Streamlit Cloud to environment variables (optional)"""
    try:
        for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
            if k in st.secrets and not os.getenv(k):
                os.environ[k] = st.secrets[k]
    except Exception:
        # Secrets not available (local testing) - will use .env file instead
        pass

load_secrets_to_env()

# ----------------------------
# Session ID for logging
# ----------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# ----------------------------
# Path for local imports
# ----------------------------
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from CLAUDE.py
from CLAUDE import (
    ProductCatalog,
    handle_chat_message,
    logger
)

# ----------------------------
# Logging helpers
# ----------------------------
def clip(s: str, n: int = 350) -> str:
    """Clip string for logging"""
    s = s or ""
    s = s.replace("\r", " ").replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s

def log_event(event: str, payload: dict):
    """Log event with timestamp and session ID"""
    record = {
        "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sid": st.session_state.session_id,
        "event": event,
        **payload
    }
    line = json.dumps(record, ensure_ascii=False)

    # Print to Streamlit Cloud logs
    print(line)

    # Also use python logger
    try:
        logger.info(line)
    except Exception:
        pass

    # Keep in session for debug
    if "debug_events" not in st.session_state:
        st.session_state.debug_events = []
    st.session_state.debug_events.append(record)
    st.session_state.debug_events = st.session_state.debug_events[-40:]

# ----------------------------
# Language detection
# ----------------------------
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
EN_RE = re.compile(r"[A-Za-z]")

def detect_lang_simple(text: str) -> str:
    """Simple language detection"""
    text = text or ""
    ar = len(ARABIC_RE.findall(text))
    en = len(EN_RE.findall(text))
    return "ar" if ar > en else "en"

def user_requested_language_switch(text: str) -> str | None:
    """Detect if user explicitly requested language switch"""
    t = (text or "").lower().strip()

    # English requests
    english_keywords = [
        "english", "in english", "speak english", "switch to english",
        "بالانجليزي", "بالإنجليزي"
    ]
    if any(kw in t for kw in english_keywords):
        return "en"

    # Arabic requests
    arabic_keywords = [
        "عربي", "بالعربي", "باللغة العربية", "تكلم عربي",
        "arabic", "in arabic", "speak arabic"
    ]
    if any(kw in t for kw in arabic_keywords):
        return "ar"

    return None

# Persist conversation language
if "chat_lang" not in st.session_state:
    st.session_state.chat_lang = None

# ----------------------------
# Enhanced text formatting with clickable links
# ----------------------------
URL_RE = re.compile(r"(https?://[^\s<>\[\]()]+)")

def format_for_html(text: str) -> str:
    """
    Enhanced text formatting:
    - Escapes HTML
    - Converts **bold** to <strong>
    - Makes URLs clickable with proper styling
    - Preserves newlines
    - Handles Arabic and English text properly
    """
    text = text or ""

    # Escape HTML first
    safe = html.escape(text)

    # Convert **bold** to <strong>
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)

    # Make URLs clickable with enhanced styling
    def make_link(match):
        url = match.group(1)
        # Clean trailing punctuation
        url_clean = url.rstrip(").,،؛!؟?")
        trailing = url[len(url_clean):]

        # Create styled link
        link_html = (
            f'<a href="{url_clean}" '
            f'target="_blank" '
            f'rel="noopener noreferrer" '
            f'class="custom-link">'
            f'{url_clean}'
            f'</a>{html.escape(trailing)}'
        )
        return link_html

    safe = URL_RE.sub(make_link, safe)

    # Preserve newlines
    safe = safe.replace("\n", "<br>")

    return safe

def render_message(content: str, preferred_lang: str):
    """
    Render message with proper direction and formatting.
    Handles mixed Arabic/English content gracefully.
    """
    preferred_lang = preferred_lang or detect_lang_simple(content)
    formatted_html = format_for_html(content)

    if preferred_lang == "ar":
        st.markdown(
            f'<div class="message-content rtl">{formatted_html}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="message-content ltr">{formatted_html}</div>',
            unsafe_allow_html=True
        )

# ----------------------------
# Enhanced CSS with better link styling
# ----------------------------
st.markdown(
    """
    <style>
    /* Font setup for Arabic support */
    html, body, [class*="css"] {
        font-family: "Segoe UI", "Tahoma", "Arial",
                     "Noto Naskh Arabic", "Noto Sans Arabic", sans-serif;
    }

    /* Chat message styling */
    .stChatMessage {
        font-size: 16px;
        line-height: 1.7;
    }

    /* Message content containers */
    .message-content {
        word-wrap: break-word;
        overflow-wrap: break-word;
        max-width: 100%;
    }

    /* RTL (Arabic) styling */
    .rtl {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
    }

    /* LTR (English) styling */
    .ltr {
        direction: ltr;
        text-align: left;
        unicode-bidi: plaintext;
    }

    /* Enhanced link styling */
    .custom-link {
        color: #1E88E5 !important;
        text-decoration: none !important;
        border-bottom: 1px solid #1E88E5 !important;
        transition: all 0.2s ease !important;
        word-break: break-all !important;
        direction: ltr !important;
        unicode-bidi: embed !important;
        display: inline !important;
    }

    .custom-link:hover {
        color: #1565C0 !important;
        border-bottom: 2px solid #1565C0 !important;
        background-color: rgba(30, 136, 229, 0.1) !important;
    }

    /* Ensure links don't break layout */
    a {
        word-break: break-word;
        overflow-wrap: break-word;
    }

    /* Strong/bold text */
    strong {
        font-weight: 600;
        color: inherit;
    }

    /* Button styling */
    .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 600;
    }

    /* Chat input */
    .stChatInput {
        border-radius: 12px;
    }

    /* Spinner */
    .stSpinner > div {
        border-color: #1E88E5 !important;
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

# Cache catalog
@st.cache_resource
def load_catalog():
    """Load and cache product catalog"""
    cat = ProductCatalog(str(CATALOG_PATH))
    cat.load()
    return cat

if "catalog" not in st.session_state:
    with st.spinner("🔄 جاري تحميل الكتالوج... / Loading catalog..."):
        try:
            st.session_state.catalog = load_catalog()
            log_event("catalog_loaded", {
                "catalog_path": str(CATALOG_PATH),
                "products_count": len(getattr(st.session_state.catalog, "products", []) or []),
            })
        except Exception as e:
            log_event("catalog_load_error", {
                "error": str(e),
                "catalog_path": str(CATALOG_PATH)
            })
            st.error("❌ خطأ في تحميل الكتالوج / Error loading catalog")
            st.exception(e)
            st.stop()

# ----------------------------
# Concise system prompt - focused on clarity
# ----------------------------
SYSTEM_PROMPT = """أنت سمورتي (Smorti)، مساعد ذكي مرح لمتجر SMART.

🎯 **القاعدة الذهبية:** أجب فقط على ما يُسأل - لا تعطي معلومات غير مطلوبة

**الشخصية:**
- مرح وودود 🤍
- نوّع ردودك (لا تكرر)
- خفيف ظل بدون مبالغة

**المنتجات:**
- استخدم فقط AVAILABLE PRODUCTS
- أرسل product_url (ليس الصفحة الرئيسية)
- إذا غير متأكد → أرسل category_link
- اقرأ المواصفات قبل التوصية

**معلومات خاصة (فقط إذا سُئلت):**
- تقسيط: Tabby/Tamara/MisPay (4 دفعات، 0%)
- بطارية BOOX: 3-4 أيام
- عمر الجهاز: 5+ سنوات
- **لا تذكر إلا إذا سأل المستخدم**

**التوصيات:**
- بطارية طويلة → ابحث عن Battery_mah كبير
- ألعاب → مونيتور/شاشة تفاعلية (ليس BOOX)
- قراءة → BOOX

**ممنوع:**
❌ تكرار معلومات
❌ معلومات غير مطلوبة
❌ اختراع منتجات/روابط
❌ استخدام الصفحة الرئيسية بدل روابط المنتجات

**الروابط:**
- المتجر: https://shop.smart.sa/ar
- واتساب: https://wa.me/966593440030
- الأجهزة: https://shop.smart.sa/ar/category/EdyrGY
- الشاشات: https://shop.smart.sa/ar/category/YYKKAR
- البرامج: https://shop.smart.sa/ar/category/QvKYzR
"""

# ----------------------------
# Header with improved title format
# ----------------------------
st.markdown(
    f"""
    <h1 style='text-align: center; margin-bottom: 0;'>
        🤖 Smorti - Smart Shop AI Assistant
    </h1>
    <p style='text-align: center; color: #666; font-size: 14px; margin-top: 5px;'>
        مساعدك الذكي المرح • Your Cheerful AI Assistant • <span style='font-size: 12px;'>v{DISPLAY_VERSION}</span>
    </p>
    """,
    unsafe_allow_html=True
)
st.markdown("---")

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.header("ℹ️ معلومات التطبيق / App Info")
    st.write("**Smorti AI Assistant**")
    st.write(f"الإصدار / Version: **{DISPLAY_VERSION}**")
    st.caption(f"Session ID: `{st.session_state.session_id}`")

    st.markdown("---")

    # Debug mode toggle
    debug = st.toggle("🪲 وضع التطوير / Debug Mode", value=False)

    st.markdown("---")

    # API Keys status
    st.subheader("🔐 حالة المفاتيح / API Keys Status")
    groq_status = "✅ متصل / Connected" if os.getenv("GROQ_API_KEY") else "❌ غير متصل / Not Connected"
    st.write(f"GROQ: {groq_status}")

    st.markdown("---")

    # Statistics
    st.subheader("📊 الإحصائيات / Statistics")
    if getattr(st.session_state.catalog, "products", None):
        st.metric("عدد المنتجات / Products", len(st.session_state.catalog.products))
    st.metric("عدد الرسائل / Messages", len(st.session_state.messages))

    # Current language
    if st.session_state.chat_lang:
        lang_display = "🇸🇦 العربية" if st.session_state.chat_lang == "ar" else "🇬🇧 English"
        st.metric("اللغة الحالية / Current Language", lang_display)

    # Debug events
    if debug and "debug_events" in st.session_state:
        st.markdown("---")
        st.subheader("📜 Debug Events (Last 10)")
        recent_events = st.session_state.debug_events[-10:]
        for event in reversed(recent_events):
            with st.expander(f"{event.get('event', 'unknown')} - {event.get('t', '')}"):
                st.json(event)

    st.markdown("---")

    # Changelog viewer
    st.subheader("📋 سجل التغييرات / Changelog")
    if st.button("📖 عرض التغييرات / View Changes", use_container_width=True):
        st.session_state.show_changelog = not st.session_state.get("show_changelog", False)

    if st.session_state.get("show_changelog", False):
        changelog_path = ROOT / "CHANGES_v1.3.md"
        if changelog_path.exists():
            with open(changelog_path, 'r', encoding='utf-8') as f:
                changelog_content = f.read()
            with st.expander("📝 Changelog Content", expanded=True):
                st.markdown(changelog_content)
        else:
            st.info("Changelog file not found. Please upload CHANGES_v1.3.md")

    st.markdown("---")

    # Reset button
    if st.button("🔄 إعادة تشغيل المحادثة / Reset Chat", use_container_width=True):
        log_event("chat_reset", {
            "messages_before": len(st.session_state.messages),
            "language": st.session_state.chat_lang
        })
        st.session_state.messages = []
        st.session_state.chat_lang = None
        st.rerun()

    st.markdown("---")
    st.caption("Made with 🤍 by SMART")

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
    # Detect language switch request
    requested = user_requested_language_switch(prompt)

    # Set or update language
    if st.session_state.chat_lang is None:
        # First message - set language
        st.session_state.chat_lang = requested or detect_lang_simple(prompt)
    elif requested:
        # Explicit switch requested
        st.session_state.chat_lang = requested

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user", avatar="🧑"):
        render_message(prompt, st.session_state.chat_lang)

    # Generate assistant response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("⏳ جاري الكتابة... / Thinking..."):
            try:
                # Build conversation history
                conversation_history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in st.session_state.messages[:-1]
                ]

                # Log user message
                log_event("user_message", {
                    "text": clip(prompt),
                    "chat_lang": st.session_state.chat_lang,
                    "history_len": len(conversation_history),
                })

                # Debug info
                if debug:
                    st.sidebar.subheader("🧾 آخر إدخال / Last Input")
                    st.sidebar.write(prompt)
                    st.sidebar.subheader("🧠 Conversation History (Last 6)")
                    st.sidebar.json(conversation_history[-6:])

                # Get AI response
                response = handle_chat_message(
                    user_input=prompt,
                    catalog=st.session_state.catalog,
                    system_prompt=SYSTEM_PROMPT,
                    conversation_history=conversation_history,
                    language=st.session_state.chat_lang
                )

                # Log response
                log_event("assistant_response", {
                    "text": clip(response),
                    "length": len(response) if response else 0,
                })

                # Display response
                render_message(response, st.session_state.chat_lang)

                # Add to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })

            except Exception as e:
                # Log error
                log_event("error", {
                    "error": str(e),
                    "prompt": clip(prompt)
                })

                # Display error
                st.error("❌ عذراً، حدث خطأ / Sorry, an error occurred")
                if debug:
                    st.exception(e)
                else:
                    st.write("يرجى المحاولة مرة أخرى / Please try again")

# ----------------------------
# Footer
# ----------------------------
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: #666; font-size: 14px;'>
        <p>Smorti {DISPLAY_VERSION} 🤍</p>
        <p style='font-size: 12px;'>مساعد ذكي تحت التطوير • AI Assistant Under Development</p>
    </div>
    """,
    unsafe_allow_html=True
)
