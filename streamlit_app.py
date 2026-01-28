"""
v1.2
Streamlit Web Interface for Smorti AI Assistant
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
import random
from pathlib import Path
APP_VERSION = "v1.2"
# ----------------------------
# Page configuration
# ----------------------------
st.set_page_config(
    page_title="Smorti - SMART Store Assistant",
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
# Add the parent directory to the path so we can import from CLAUDE.py
# ----------------------------
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from your CLAUDE.py file (after env keys are set)
from CLAUDE import (
    ProductCatalog,
    handle_chat_message,
    logger
)

# ----------------------------
# Logging helpers (Streamlit Cloud -> Manage app -> Logs)
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
    print(line)  # guaranteed in Streamlit Cloud logs
    try:
        logger.info(line)
    except Exception:
        pass

    if "debug_events" not in st.session_state:
        st.session_state.debug_events = []
    st.session_state.debug_events.append(record)
    st.session_state.debug_events = st.session_state.debug_events[-60:]  # keep last 60

# ----------------------------
# Arabic / RTL helpers
# ----------------------------
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

def is_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))

def prettify_links(text: str) -> str:
    return re.sub(r"(https?://\S+)", r"\n\1", text or "")

def render_message(content: str):
    content = content or ""
    content = prettify_links(content)
    safe = html.escape(content).replace("\n", "<br>")

    if is_arabic(content):
        st.markdown(f'<div class="rtl">{safe}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ltr">{safe}</div>', unsafe_allow_html=True)

# ----------------------------
# Custom CSS for better Arabic support and styling
# ----------------------------
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: "Segoe UI", "Tahoma", "Arial", "Noto Naskh Arabic", "Noto Sans Arabic", sans-serif;
    }
    .stChatMessage {
        font-size: 16px;
        line-height: 1.6;
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
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# Session state
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Preferred language lock (to prevent sudden switching)
if "preferred_lang" not in st.session_state:
    st.session_state.preferred_lang = None  # 'ar' or 'en'

# ----------------------------
# Language decision (stable)
# ----------------------------
def lang_score(text: str) -> str:
    text = text or ""
    ar = len(re.findall(r"[\u0600-\u06FF]", text))
    en = len(re.findall(r"[A-Za-z]", text))
    if ar == 0 and en == 0:
        return "ar"  # default if empty/emoji only
    return "ar" if ar >= en else "en"

def user_requested_lang_switch(text: str):
    t = (text or "").lower()

    # explicit user request
    if any(p in t for p in ["speak english", "in english", "english please", "talk english", "بالانجليزي", "بالإنجليزي", "باللغة الانجليزية", "باللغة الإنجليزية"]):
        return "en"
    if any(p in t for p in ["بالعربي", "باللغة العربية", "arabic please", "in arabic", "speak arabic"]):
        return "ar"
    return None

# ----------------------------
# Greeting rules (Salam + hearts 🤍)
# ----------------------------
def normalize_ar(text: str) -> str:
    # light normalization (remove tatweel/diacritics-ish minimal)
    text = text or ""
    text = text.replace("ـ", "")
    return text.strip()

SALAM_RE = re.compile(r"(السلام\s+عليكم)(\s+ورحمة\s+الله)?(\s+وبركاته)?")

AR_GREETS = [
    "يا هلا 🤍 وش أقدر أساعدك فيه؟",
    "هلا والله 🤍 كيف أخدمك اليوم؟",
    "مرحبا 🤍 منور/منورة! وش تحتاج؟",
]
EN_GREETS = [
    "Hey 🤍 How can I help you today?",
    "Hello 🤍 What can I do for you?",
    "Hi 🤍 How can I help?",
]

def rule_based_reply(user_text: str, lang: str):
    t = normalize_ar(user_text)

    # Full salam reply ALWAYS
    if SALAM_RE.search(t):
        if lang == "en":
            # If user wrote salam but convo is English, still reply salam fully then continue in English
            return "وعليكم السلام ورحمة الله وبركاته 🤍🤍\nHello! I’m Smorti 😊 How can I help you today?"
        return "وعليكم السلام ورحمة الله وبركاته 🤍🤍\nهلا فيك! أنا سمورتي 😊 وش أقدر أساعدك فيه اليوم؟"

    # Basic greet (non-salam) — vary
    low = (user_text or "").lower().strip()
    if low in ["hi", "hello", "hey", "السلام", "مرحبا", "هلا", "يا هلا", "اهلا", "أهلا"]:
        return random.choice(EN_GREETS if lang == "en" else AR_GREETS)

    return None

# ----------------------------
# Paths + Catalog
# ----------------------------
ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "data" / "products_enriched.csv"

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
# System prompt (UPDATED per your requirements)
# ----------------------------
SYSTEM_PROMPT = """أنت سمورتي (Smorti)، مساعد ذكاء اصطناعي لمتجر SMART.
مهمتك تساعد العميل يختار المنتج/الحل المناسب من متجر SMART.

✅ تعريف شخصيتك:
- أنت AI assistant (لا تدّعي أنك إنسان).
- أسلوبك ودود وخفيف دم، مع دعابة بسيطة أحياناً لكسر الرسمية (بدون مبالغة).
- ردود قصيرة وواضحة (WhatsApp-friendly).
- استخدم 🤍 كقلب دائمًا (تجنب القلوب الملونة).

✅ لغة الرد:
- رد بنفس لغة العميل الأساسية من بداية المحادثة (عربي/إنجليزي).
- لا تغيّر اللغة فجأة إذا العميل استخدم كلمة/مصطلح بلغة ثانية.
- غيّر اللغة فقط إذا العميل طلب بشكل واضح أو استمر يكتب بلغة ثانية أغلب الوقت.

✅ رد السلام:
إذا قال العميل: "السلام عليكم" أو "السلام عليكم ورحمة الله وبركاته"
أنت دائمًا ترد كامل:
"وعليكم السلام ورحمة الله وبركاته 🤍🤍"

=============================
معلومات مهمة (Technical Rules)
=============================

1) الأقساط (Installments) — معلومات ثابتة بدون اختراع:
- Tabby / Tamara / MisPay
- كلها 4 دفعات (٤ أشهر): تدفع 25% الآن والباقي على 3 أشهر
- 0% فائدة
- ممكن تمدّد المدة حسب مزود التقسيط المختار (بدون اختراع تفاصيل أكثر من كذا)
✅ إذا سأل العميل عن التقسيط: اذكر الثلاثة وأعطِ المعلومة أعلاه فقط.

2) توصيات حسب الاستخدام (Usage-based recommendations):
- أجهزة BOOX (حبر إلكتروني) ممتازة للقراءة + الكتابة + ملاحظات + PDF + دراسة.
- ليست مخصصة لمشاهدة الفيديو/الميديا لفترات طويلة مثل التابلت العادي، ولا للألعاب الثقيلة.
- إذا المستخدم قال: Gaming / بلايستيشن / PC Gaming / FPS:
  ✅ اقترح شاشات/مونيتورات أو شاشات تفاعلية حسب الطلب، ولا تقترح BOOX كحل أساسي للألعاب.

3) البرامج والتراخيص (Licenses / Software):
إذا العميل سأل عن برنامج/ترخيص (مثل SPSS / MATLAB / SolidWorks / ArcGIS …):
- أعطِ وصف مختصر “وش يسوي” البرنامج بشكل عام.
- اسأل سؤال واحد لتحديد احتياجه (مثلاً: طالب ولا شركة؟ استخدام شخصي ولا مؤسسي؟ نظام ويندوز/ماك؟)
- لا تخترع تفاصيل باقات/أسعار/أنواع رخص غير مذكورة.

4) العمر الافتراضي للأجهزة:
إذا سأل: "كم يعيش الجهاز؟"
- لا تعطي رقم محدد.
- قل يعتمد على الاستخدام والشحن (دورات الشحن).
- كقاعدة عامة: غالبًا يعيش أكثر من 5 سنوات بسهولة حسب الاستخدام.

5) البطارية (خصوصًا BOOX):
- عادة تدوم “أيام” على الشحنة الواحدة.
- غالباً 3–4 أيام بسهولة، وبعض الاستخدامات قد تصل أسبوع.
- أجهزة monochrome تدوم غالباً أكثر من الملونة لأن استهلاكها أقل.
- دائمًا قل: "يعتمد على الاستخدام" + أعط إطار آمن (أيام).

=============================
قواعد صارمة — CRITICAL
=============================
1) لا تخترع أبداً أسعار أو مواصفات أو أسماء منتجات. استخدم فقط بيانات المنتجات المتاحة التي تُرسل لك.
2) دائماً أرفق رابط المنتج (product_url) إذا كان موجود.
3) إذا لم تجد منتج مطابق: قل بوضوح ووجّه للموقع، ولا تخترع.
4) قارن فقط بناءً على المواصفات الفعلية.
5) اذكر الخصم إذا موجود (old_price - current_price).
6) اقترح اكسسوارات متوافقة إذا مناسبة.
"""

# ----------------------------
# UI Header
# ----------------------------
st.title("🤖 Smorti - مساعد متجر SMART")
st.markdown("---")
st.caption(f"Smorti {APP_VERSION} 🤍")
# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.header("ℹ️ معلومات التطبيق")
    st.write("**Smorti AI Assistant**")
    st.write("نسخة تجريبية")
    st.sidebar.caption(f"Version: {APP_VERSION}")

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
    st.caption(f"Session ID: `{st.session_state.session_id}`")

    if debug and "debug_events" in st.session_state:
        st.markdown("---")
        st.subheader("📜 Debug events (آخر 60)")
        st.json(st.session_state.debug_events)

    st.markdown("---")
    if st.button("🔄 إعادة تشغيل المحادثة"):
        log_event("chat_reset", {"messages_before": len(st.session_state.messages)})
        st.session_state.messages = []
        st.session_state.preferred_lang = None
        st.rerun()

# ----------------------------
# Display chat messages
# ----------------------------
for message in st.session_state.messages:
    role = "user" if message["role"] == "user" else "assistant"
    avatar = "🧑" if role == "user" else "🤖"
    with st.chat_message(role, avatar=avatar):
        render_message(message["content"])

# ----------------------------
# Chat input
# ----------------------------
if prompt := st.chat_input("اكتب رسالتك هنا... / Type your message here..."):
    # Decide language (stable)
    requested = user_requested_lang_switch(prompt)
    if requested:
        st.session_state.preferred_lang = requested
        log_event("lang_switch_requested", {"to": requested, "text": clip(prompt)})
    elif st.session_state.preferred_lang is None:
        st.session_state.preferred_lang = lang_score(prompt)
        log_event("lang_locked_first_message", {"lang": st.session_state.preferred_lang, "text": clip(prompt)})

    lang = st.session_state.preferred_lang or "ar"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        render_message(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("⏳ جاري الكتابة..."):
            try:
                # Rule-based greetings (salam etc.) — bypass AI for correctness
                rb = rule_based_reply(prompt, lang)
                if rb:
                    log_event("rule_based_reply", {"lang": lang, "text": clip(prompt)})
                    render_message(rb)
                    st.session_state.messages.append({"role": "assistant", "content": rb})
                else:
                    # Build conversation history for API (exclude current user msg)
                    conversation_history = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in st.session_state.messages[:-1]
                    ]

                    log_event("user_message", {
                        "lang": lang,
                        "text": clip(prompt),
                        "history_len": len(conversation_history),
                        "is_arabic": is_arabic(prompt),
                    })

                    if debug:
                        st.sidebar.subheader("🧾 آخر إدخال")
                        st.sidebar.write(prompt)
                        st.sidebar.subheader("🧠 Conversation history (آخر 6)")
                        st.sidebar.json(conversation_history[-6:])

                    # IMPORTANT: pass locked language to backend to avoid switching
                    response = handle_chat_message(
                        user_input=prompt,
                        catalog=st.session_state.catalog,
                        system_prompt=SYSTEM_PROMPT,
                        conversation_history=conversation_history,
                        language=lang  # <--- LOCK LANGUAGE
                    )

                    log_event("assistant_response", {"lang": lang, "text": clip(response), "len": len(response or "")})

                    render_message(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                log_event("error", {"error": str(e), "prompt": clip(prompt), "lang": lang})
                st.error("❌ خطأ (تفاصيل):")
                st.exception(e)

st.markdown("---")
st.caption(" نسخة تجريبية 🤍")