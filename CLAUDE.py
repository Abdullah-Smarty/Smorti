"""
Smorti AI Agent (CLAUDE.py) - v0.31 FIXED (STREAMLIT-SAFE)
ANTI-HALLUCINATION + STABLE PERSONA + CSV-ONLY PRODUCTS
Backend engine used by Streamlit app + local CLI.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Optional, Dict, Any, List, Tuple
import time
from datetime import datetime
import pandas as pd
import os
from dotenv import load_dotenv
import re

APP_VERSION = "v0.31"
load_dotenv()

# ============================================
# 1) LOGGING CONFIGURATION
# ============================================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[
            logging.FileHandler('smorti_errors.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('Smorti')

logger = setup_logging()

# ============================================
# 2) CONSTANTS / HELPERS
# ============================================

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
URL_RE = re.compile(r"https?://\S+")

OFFICIAL_LINKS = {
    "store": "https://shop.smart.sa/ar",
    "tablets": "https://shop.smart.sa/ar/category/EdyrGY",
    "interactive": "https://shop.smart.sa/ar/category/YYKKAR",
    "computer": "https://shop.smart.sa/ar/category/AxRPaD",
    "software": "https://shop.smart.sa/ar/category/QvKYzR",
    "whatsapp": "https://wa.me/966593440030",
}

# =========================
# FACTS (UNCHANGED)
# =========================

INSTALLMENT_FACTS_AR = (
    "💳 **التقسيط المتوفر:**\n"
    "نوفر لك التقسيط عبر **Tabby** و **Tamara** و **MisPay**\n\n"
    "📋 **التفاصيل:**\n"
    "• خطة 4 أشهر: ادفع 25% الآن والباقي على 3 أشهر\n"
    "• **بدون فوائد** - معدل فائدة 0%\n"
    "• يمكنك تمديد المدة حسب مزود التقسيط المختار\n"
    "• التفاصيل النهائية تظهر عند إتمام الطلب في صفحة الدفع 💰"
)

INSTALLMENT_FACTS_EN = (
    "💳 **Available Installment Plans:**\n"
    "We offer installments through **Tabby**, **Tamara**, and **MisPay**\n\n"
    "📋 **Details:**\n"
    "• 4-month plan: Pay 25% now, the rest over 3 months\n"
    "• **Zero interest** - 0% interest rate\n"
    "• You can extend the period depending on your chosen provider\n"
    "• Final details appear at checkout during payment 💰"
)

BATTERY_FACTS_AR = (
    "🔋 **عمر البطارية لأجهزة الحبر الإلكتروني:**\n"
    "أجهزتنا (خاصة BOOX) تدوم **أيام طويلة** على شحنة واحدة!\n\n"
    "⚡ **التفاصيل:**\n"
    "• عادة تدوم **3-4 أيام بسهولة** حسب الاستخدام\n"
    "• بعض الأجهزة قد تصل لـ **أسبوع كامل**\n"
    "• الأجهزة أحادية اللون (أبيض وأسود) تدوم **أطول** من الملونة بسبب استهلاك أقل للطاقة\n"
    "• المدة تعتمد على: الواي فاي، البلوتوث، استخدام القلم، والقراءة المكثفة 📚"
)

BATTERY_FACTS_EN = (
    "🔋 **E-ink Device Battery Life:**\n"
    "Our devices (especially BOOX) last **days** on a single charge!\n\n"
    "⚡ **Details:**\n"
    "• Typically lasts **3-4 days easily** depending on usage\n"
    "• Some devices can reach up to **a full week**\n"
    "• Monochrome devices last **longer** than color due to lower power consumption\n"
    "• Duration depends on: Wi-Fi, Bluetooth, pen usage, and intensive reading 📚"
)

LIFESPAN_FACTS_AR = (
    "⏳ **عمر الجهاز الافتراضي:**\n"
    "يعتمد العمر على طريقة استخدامك للجهاز، لكن مع الاستخدام الطبيعي:\n\n"
    "✅ **غالباً يدوم أكثر من 5 سنوات بسهولة**\n\n"
    "📌 العوامل المؤثرة:\n"
    "• دورات الشحن (كل ما قل الشحن المتكرر، كل ما طالت العمر)\n"
    "• طريقة الاستخدام (قراءة خفيفة مقابل استخدام مكثف)\n"
    "• العناية بالجهاز والحرارة المحيطة 🌡️"
)

LIFESPAN_FACTS_EN = (
    "⏳ **Virtual Device Lifespan:**\n"
    "The lifespan depends on how you use the device, but with normal use:\n\n"
    "✅ **It should easily last more than 5 years**\n\n"
    "📌 Factors affecting lifespan:\n"
    "• Charging cycles (less frequent charging = longer life)\n"
    "• Usage pattern (light reading vs. intensive use)\n"
    "• Device care and ambient temperature 🌡️"
)

WARRANTY_FACTS_AR = (
    "🛡️ **سياسة الضمان:**\n\n"
    "**ضمان المنتجات الجديدة:**\n"
    "• ضمان لمدة **سنتين** على جميع المنتجات التقنية\n"
    "• يشمل **العيوب المصنعية**\n"
    "• لا يشمل الأعطال بسبب **سوء الاستخدام** أو **الحوادث** أو **الصيانة غير المعتمدة**\n\n"
    "**ضمان المنتجات المستعملة:**\n"
    "• ضمان لمدة **30 يوم** على جميع المنتجات التقنية المستعملة\n"
    "• يشمل **العيوب المصنعية**\n"
    "• لا يشمل سوء الاستخدام/الحوادث/الصيانة غير المعتمدة أو الملاحظات المذكورة مسبقاً في الوصف ✅"
)

WARRANTY_FACTS_EN = (
    "🛡️ **Warranty Policy:**\n\n"
    "**New products:**\n"
    "• **2-year** warranty on all tech products\n"
    "• Covers **manufacturing defects**\n"
    "• Does NOT cover misuse, accidents, or unauthorized maintenance\n\n"
    "**Used products:**\n"
    "• **30-day** warranty on all used tech products\n"
    "• Covers **manufacturing defects**\n"
    "• Does NOT cover misuse/accidents/unauthorized maintenance or pre-mentioned notes in the description ✅"
)

SHIPPING_FACTS_AR = (
    "🚚 **التوصيل والشحن:**\n\n"
    "**داخل السعودية (المدن المحلية):**\n"
    "• **سمسا (SMSA)**\n"
    "• **رد بوكس (RedBox)**\n"
    "• **أراميكس (Aramex)**\n\n"
    "**خارج السعودية:**\n"
    "• **DHL فقط** 🌍\n\n"
    "📦 تكلفة ووقت التوصيل تظهر لك عند إتمام الطلب في صفحة الدفع."
)

SHIPPING_FACTS_EN = (
    "🚚 **Delivery & Shipping:**\n\n"
    "**Within Saudi Arabia (local cities):**\n"
    "• **SMSA**\n"
    "• **RedBox**\n"
    "• **Aramex**\n\n"
    "**Outside Saudi Arabia:**\n"
    "• **DHL only** 🌍\n\n"
    "📦 Delivery cost & ETA appear at checkout."
)

# =========================
# TONE HELPERS (no fake facts)
# =========================

def wrap_facts_ar(title: str, facts: str) -> str:
    return f"أكيد 🤍\n{title}\n\n{facts}"

def wrap_facts_en(title: str, facts: str) -> str:
    return f"Sure 🤍\n{title}\n\n{facts}"

# ============================================
# 2.1) TEXT NORMALIZATION
# ============================================

_AR_DIACRITICS = re.compile(r"[\u064B-\u065F\u0610-\u061A\u06D6-\u06ED]")
_AR_TATWEEL = "\u0640"

def normalize_arabic(text: str) -> str:
    s = (text or "").strip().lower()
    s = s.replace(_AR_TATWEEL, "")
    s = _AR_DIACRITICS.sub("", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي")
    s = re.sub(r"[^\w\u0600-\u06FF\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))

def detect_language_simple(text: str) -> str:
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text or ""))
    english_chars = len(re.findall(r'[a-zA-Z]', text or ""))
    return 'ar' if arabic_chars > english_chars else 'en'

def stable_language(current_text: str, conversation_history: Optional[List[Dict]] = None) -> str:
    t = (current_text or "").lower()
    english_requests = [
        "بالانجليزي", "بالإنجليزي", "in english", "speak english",
        "english please", "switch to english", "talk in english"
    ]
    arabic_requests = [
        "بالعربي", "بالعربية", "in arabic", "speak arabic",
        "arabic please", "switch to arabic", "تكلم عربي"
    ]
    if any(req in t for req in english_requests):
        return "en"
    if any(req in t for req in arabic_requests):
        return "ar"

    cur_lang = detect_language_simple(current_text)
    last_user_lang = None
    if conversation_history:
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                last_user_lang = detect_language_simple(msg.get("content", ""))
                break
    return last_user_lang or cur_lang

# ============================================
# 2.2) JOKES (no hallucination)
# ============================================

ARABIC_TECH_JOKES = [
    "ليش الـWi-Fi زعلان؟\nلأن الكل *يتصل فيه*… وما أحد *يسأل عنه* 🤍📶😂",
    "قالوا للمبرمج: اكتب كود نظيف…\nراح غسل اللابتوب 🧼💻😂",
    "المبرمج إذا قال: 'بس أصلح شي بسيط'…\nاعرف إن اليوم راح يطول 😭⌨️",
    "قلت للكمبيوتر: لا تشيل هم…\nقال: طيب بس لا تفتح 50 تبويب كروم مرة وحدة 😅🧠",
    "ليش السيرفر متوتر؟\nلأنه عليه ضغط… حرفياً (Load) 😅🖥️",
    "أكثر جملة تخوف في التقنية؟\n'It works on my machine' 😭🧩😂",
    "سألته: ليه تحب البرمجة؟\nقال: لأنها العلاقة الوحيدة اللي إذا خربت… تقدر تصلحها بـ (Ctrl+Z) 😄⌨️",
]

ENGLISH_TECH_JOKES = [
    "Why do programmers prefer dark mode?\nBecause light attracts bugs 🐛😄",
    "Debugging: where you remove one bug and add two new features 🐛✨",
    "‘It works on my machine’ — the most powerful spell in software engineering 😅🧩",
    "I told my computer I needed a break…\nIt said: 'No problem — I’ll go to sleep.' 😴💻",
    "Why did the developer go broke?\nBecause he used up all his cache 💸😂",
]

def is_joke_request(text: str) -> bool:
    t_raw = (text or "").lower().strip()
    t_ar = normalize_arabic(text)

    keys_ar = ["نكتة", "نكته", "ضحكني", "اضحكني", "طرفة", "ابغا نكتة", "ابغى نكتة", "قول نكتة", "قول نكته"]
    if any(k in t_ar for k in keys_ar):
        return True

    # catches: joke / jok / tell me a jok / funny / make me laugh
    if re.search(r"\bjok(e)?\b", t_raw) or "tell me a jok" in t_raw or "make me laugh" in t_raw or "funny" in t_raw:
        return True

    return False

def is_another_joke_request(text: str) -> bool:
    t_ar = normalize_arabic(text)
    t_raw = (text or "").lower()
    keys_ar = ["وحدة ثانية", "واحدة ثانية", "نكتة ثانية", "نكته ثانيه", "ثانية", "كمان", "زيادة"]
    keys_en = ["another", "another one", "one more", "more", "next"]
    return any(k in t_ar for k in keys_ar) or any(k in t_raw for k in keys_en)

def tell_joke(language: str) -> str:
    import random
    if language == "ar":
        return f"أكيد 😄🤍\n\n{random.choice(ARABIC_TECH_JOKES)}"
    return f"Sure 😄🤍\n\n{random.choice(ENGLISH_TECH_JOKES)}"

# ============================================
# 2.3) GREETINGS (introduce once)
# ============================================

EN_GREETING_RE = re.compile(
    r"\b(hi|hello|hey|good\s*(morning|evening|afternoon)|howdy|greetings)\b",
    re.IGNORECASE
)

def is_arabic_greeting_only(text: str) -> bool:
    s = normalize_arabic(text)
    if not s:
        return True
    tokens = s.split()
    if len(tokens) > 4:
        return False

    joined = " ".join(tokens)
    greeting_phrases = {
        "سلام", "سلام عليكم", "السلام عليكم", "عليكم السلام", "وعليكم السلام",
        "مرحبا", "هلا", "هلا والله", "اهلين", "اهلا", "يا هلا", "حياك", "منور", "منورنا",
    }
    if joined in greeting_phrases:
        return True
    if "السلام عليكم" in joined or "سلام عليكم" in joined:
        return True
    if joined.startswith("وعليكم السلام") or joined.startswith("عليكم السلام"):
        return True
    if re.search(r"\bسلام\w*\s+عليكم\w*\b", joined):
        return True
    return False

def is_probably_just_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if is_arabic(t) and is_arabic_greeting_only(t) and len(t) <= 80:
        return True
    if len(t) <= 80 and EN_GREETING_RE.search(t):
        return True
    return False

def _already_introduced_from_history(conversation_history: Optional[List[Dict]]) -> bool:
    if not conversation_history:
        return False
    for msg in conversation_history:
        if msg.get("role") == "assistant":
            return True
    return False

def intro_message(lang: str) -> str:
    if lang == "ar":
        return (
            "هلا 👋🤍\n"
            "أنا **سمورتي** — مساعد ذكي لمتجر سمارت 🛒\n"
            "تنبيه صغير: أنا **لسّه تحت التطوير** 😅 بس بوعدك أحاول أخدمك قد ما أقدر وبأوضح لك الموجود المتاح.\n\n"
            "قلّي وش تحتاج (جهاز قراءة / شاشة / برامج / سعر / مقارنة) وأنا أساعدك 😊"
        )
    return (
        "Hey! 👋🤍\n"
        "I’m **Smorti** — your AI assistant for SMART store 🛒\n"
        "Quick note: I’m **still under development** 😅 but I’ll do my best to help with what’s available.\n\n"
        "Tell me what you need (reading device / screen / software / price / comparison) and I’ll help 😊"
    )


def greeting_reply(lang: str, first_time: bool, original_text: str) -> str:
    if first_time:
        if lang == "ar":
            if is_arabic_greeting_only(original_text):
                return "وعليكم السلام ورحمة الله وبركاته 🤍\n\n" + intro_message("ar")
            return intro_message("ar")
        return intro_message("en")

    if lang == "ar" and is_arabic_greeting_only(original_text):
        return "وعليكم السلام ورحمة الله وبركاته 🤍\n\nنورت! كيف أقدر أساعدك؟ 😊"

    if lang == "ar":
        return "يا هلا 🤍 كيف أقدر أساعدك؟ 😊"
    return "Hey 🤍 How can I help you? 😊"

# ============================================
# 2.4) SESSION STATE HELPERS
# ============================================

def _get_session(session_state: Optional[Dict[str, Any]], session_id: Optional[str]) -> Dict[str, Any]:
    if session_state is None or not session_id:
        return {}
    sess = session_state.get(session_id)
    if not isinstance(sess, dict):
        sess = {}
        session_state[session_id] = sess
    return sess

def _set_session(session_state: Optional[Dict[str, Any]], session_id: Optional[str], key: str, value: Any) -> None:
    if session_state is None or not session_id:
        return
    sess = _get_session(session_state, session_id)
    sess[key] = value

# ============================================
# 2.5) URL SAFETY (no homepage fallback)
# ============================================

def allowed_urls_from_products(products: List[Dict[str, Any]]) -> set:
    allowed = set(OFFICIAL_LINKS.values())
    for p in products or []:
        u1 = str(p.get("product_url", "")).strip()
        u2 = str(p.get("category_link", "")).strip()
        if u1.startswith("http"):
            allowed.add(u1)
        if u2.startswith("http"):
            allowed.add(u2)
    return allowed

def scrub_unknown_urls(text: str, allowed: set, fallback_url: str, allow_store: bool = False) -> str:
    def repl(m):
        url = m.group(0).rstrip(").,،。!؟!?]")
        # If model outputs homepage and we don't allow it -> use fallback category
        if url == OFFICIAL_LINKS["store"] and (not allow_store):
            return fallback_url or OFFICIAL_LINKS["tablets"]
        return url if url in allowed else (fallback_url or OFFICIAL_LINKS["tablets"])
    return URL_RE.sub(repl, text or "")

PLACEHOLDER_CONTACT_RE = re.compile(
    r"\[(رقم الهاتف|عنوان البريد الإلكتروني|عنوان الموقع الإلكتروني|اسم حسابنا.*?|phone.*?|email.*?|website.*?)\]",
    re.IGNORECASE
)

def scrub_placeholders(text: str) -> str:
    return PLACEHOLDER_CONTACT_RE.sub("", text or "")

# ============================================
# 2.6) ACCESSORY FILTER (prevents pen tips)
# ============================================

def _product_blob(p: Dict[str, Any]) -> str:
    return " ".join([
        str(p.get('item_type', '')).lower(),
        str(p.get('category', '')).lower(),
        str(p.get('name_en', '')).lower(),
        str(p.get('name_ar', '')).lower(),
        str(p.get('short_desc', '')).lower(),
        str(p.get('keywords', '')).lower(),
    ])

ACCESSORY_TERMS = [
    "tip", "tips", "nib", "nibs", "replacement", "refill",
    "سنون", "رؤوس", "بديل", "تبديل", "قطع غيار",
    "cover", "case", "جراب", "حافظة", "كفر",
    "lamp", "light", "اضاءة", "إضاءة", "لمبة", "مصباح",
    "holder", "stand", "حامل",
]

def _exclude_accessories(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for p in products:
        blob = _product_blob(p)
        if any(t in blob for t in ACCESSORY_TERMS):
            continue
        out.append(p)
    return out

def _safe_float(x) -> float:
    try:
        m = re.search(r"(\d+(\.\d+)?)", str(x or ""))
        return float(m.group(1)) if m else -1.0
    except Exception:
        return -1.0

# ============================================
# 3) EXCEPTIONS
# ============================================

class SmortiBaseException(Exception):
    def __init__(self, message: str, user_message_ar: str, user_message_en: str):
        self.message = message
        self.user_message_ar = user_message_ar
        self.user_message_en = user_message_en
        super().__init__(self.message)

class GroqAPIError(SmortiBaseException):
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.original_error = original_error
        super().__init__(
            message,
            "صار عندي تعليق بسيط 😅🤍\nخلّنا نجرب مرة ثانية.",
            "A tiny hiccup happened 😅🤍\nLet’s try again."
        )

class GroqRateLimitError(SmortiBaseException):
    def __init__(self, message: str):
        super().__init__(
            message,
            "الطلبات كثيرة شوي حالياً 😅🤍\nانتظر ثواني وجرب مرة ثانية.",
            "Too many requests right now 😅🤍\nWait a few seconds and try again."
        )

class CatalogLoadError(SmortiBaseException):
    def __init__(self, message: str):
        super().__init__(
            message,
            "ما قدرت أوصل للكتالوج حالياً 😔🤍",
            "I can't reach the catalog right now 😔🤍"
        )

class EmptyInputError(SmortiBaseException):
    def __init__(self):
        super().__init__(
            "Empty user input",
            "هلا 🤍 اكتب لي سؤالك وبساعدك 😊",
            "Hey 🤍 Send me your question and I’ll help 😊"
        )

# ============================================
# 4) RETRY DECORATOR
# ============================================

def retry_groq_call(max_attempts=3, delay=2, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            last_error = None

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except GroqRateLimitError:
                    logger.warning(f"Rate limit hit on attempt {attempt}")
                    if attempt == max_attempts:
                        raise
                    time.sleep(current_delay * 3)
                    attempt += 1
                except GroqAPIError as e:
                    last_error = e
                    if attempt == max_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
                except Exception as e:
                    logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                    raise

            if last_error:
                raise last_error
        return wrapper
    return decorator

# ============================================
# 5) GROQ API CALL
# ============================================

@retry_groq_call(max_attempts=3, delay=2)
def call_groq_api(
    prompt: str,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    temperature: float = 0.10,
    max_tokens: int = 900
) -> str:
    try:
        from groq import Groq

        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise GroqAPIError("GROQ_API_KEY not found in environment variables")

        client = Groq(api_key=api_key)

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": prompt})

        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        create_kwargs = dict(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.85,
            stream=False
        )

        try:
            create_kwargs.update({
                "frequency_penalty": 0.5,
                "presence_penalty": 0.5,
            })
            response = client.chat.completions.create(**create_kwargs)
        except TypeError:
            create_kwargs.pop("frequency_penalty", None)
            create_kwargs.pop("presence_penalty", None)
            response = client.chat.completions.create(**create_kwargs)

        ai_response = response.choices[0].message.content
        if not ai_response or not ai_response.strip():
            raise GroqAPIError("Empty response from Groq API")

        return ai_response.strip()

    except Exception as e:
        msg = str(e).lower()
        if 'rate_limit' in msg or '429' in msg:
            raise GroqRateLimitError(str(e))
        if 'api key' in msg or '401' in msg or 'unauthorized' in msg:
            raise GroqAPIError(f"Invalid API key: {e}", e)
        if 'timeout' in msg or 'timed out' in msg:
            raise GroqAPIError(f"API timeout: {e}", e)
        if '503' in msg or '502' in msg:
            raise GroqAPIError(f"Service unavailable: {e}", e)
        raise GroqAPIError(f"API error: {e}", e)

# ============================================
# 6) PRODUCT CATALOG
# ============================================

class ProductCatalog:
    def __init__(self, csv_path: str, descriptions_txt_path: Optional[str] = None):
        self.csv_path = csv_path
        self.descriptions_txt_path = descriptions_txt_path
        self.df: Optional[pd.DataFrame] = None
        self.products: Optional[List[Dict[str, Any]]] = None
        self.last_loaded: Optional[datetime] = None

    def load(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        if self.products is not None and not force_reload:
            return self.products

        if not os.path.exists(self.csv_path):
            raise CatalogLoadError(f"Catalog file not found: {self.csv_path}")

        try:
            self.df = pd.read_csv(self.csv_path, encoding='utf-8')
        except Exception as e:
            raise CatalogLoadError(f"Failed to read CSV: {e}")

        if self.df is None or self.df.empty:
            raise CatalogLoadError("Catalog file is empty")

        fill_values = {
            'price_sar': 0,
            'old_price_sar': 0,
            'product_url': '',
            'category_link': '',
            'short_desc': '',
            'availability': 'unknown',
            'category': 'general',
            'screen_size_in': '',
            'display_type': '',
            'ram_gb': '',
            'storage_gb': '',
            'connectivity': '',
            'item_type': '',
            'resolution_px': '',
            'ppi': '',
            'cpu': '',
            'os': '',
            'bluetooth': '',
            'wifi': '',
            'Battery_mah': '',
            'audio_jack': '',
            'Micro_sd_slot': ''
        }
        for col, default_val in fill_values.items():
            if col in self.df.columns:
                self.df[col] = self.df[col].fillna(default_val)

        if 'product_id' in self.df.columns:
            self.df = self.df.drop_duplicates(subset=['product_id'], keep='first')

        self.products = self.df.to_dict('records')
        self.last_loaded = datetime.now()
        logger.info(f"✓ Loaded {len(self.products)} products")
        return self.products

    def _score_product(self, product: Dict[str, Any], terms: List[str]) -> int:
        score = 0
        fields = [
            str(product.get('name_en', '')).lower(),
            str(product.get('name_ar', '')).lower(),
            str(product.get('short_desc', '')).lower(),
            str(product.get('keywords', '')).lower(),
            str(product.get('brand', '')).lower(),
            str(product.get('series', '')).lower(),
            str(product.get('category', '')).lower(),
            str(product.get('item_type', '')).lower(),
        ]
        joined = " | ".join(fields)

        for t in terms:
            if not t:
                continue
            if t in str(product.get('name_en', '')).lower():
                score += 5
            if t in str(product.get('name_ar', '')).lower():
                score += 5
            if t in str(product.get('series', '')).lower():
                score += 4
            if t in str(product.get('brand', '')).lower():
                score += 3
            if t in str(product.get('item_type', '')).lower():
                score += 3
            if t in joined:
                score += 1

        return score

    def search_products(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if self.products is None:
            self.load()

        q = (query or "").lower()
        terms = re.findall(r"[a-zA-Z0-9\u0600-\u06FF]+", q)

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for p in self.products or []:
            s = self._score_product(p, terms)
            if s > 0:
                scored.append((s, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    def filter_by_type(self, products: List[Dict[str, Any]], include_any: List[str]) -> List[Dict[str, Any]]:
        keys = [k.lower() for k in include_any]
        out = []
        for p in products:
            blob = _product_blob(p)
            if any(k in blob for k in keys):
                out.append(p)
        return out

# ============================================
# 7) INTENT DETECTION
# ============================================

def has_any(text: str, keys: List[str]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keys)

def is_installment_query(text: str) -> bool:
    t = (text or "").lower()
    questions = [
        "كيف التقسيط", "وش التقسيط", "عندكم تقسيط",
        "تقسيط كيف", "عندكم تابي", "عندكم تمارا",
        "how is installment", "do you have installment",
        "you have tabby", "you have tamara"
    ]
    return any(q in t for q in questions)

def is_battery_query(text: str) -> bool:
    return has_any(text, [
        "بطارية", "battery", "تشحن", "شحن", "يدوم",
        "lasts", "مدة البطارية", "battery life", "charge",
        "charging", "كم يدوم", "how long"
    ])

def is_lifespan_query(text: str) -> bool:
    return has_any(text, [
        "عمر", "يعيش", "كم سنة", "virtual age", "lifespan",
        "how long will it last", "يدوم كم", "كم يدوم",
        "durability", "متين", "يطول"
    ])

def is_warranty_query(text: str) -> bool:
    return has_any(text, ["ضمان", "warranty", "كفالة", "ضمانكم", "مدة الضمان", "كم الضمان"])

def is_shipping_query(text: str) -> bool:
    return has_any(text, ["توصيل", "شحن", "delivery", "shipping", "يوصل", "تشحنون", "تشحن", "ارسلوا", "ارسال"])

def is_programs_query(text: str) -> bool:
    return has_any(text, [
        "ترخيص", "رخصة", "license", "software", "برنامج", "برامج",
        "spss", "matlab", "solidworks", "arcgis", "autocad",
        "photoshop", "microsoft", "office"
    ])

def is_monitor_or_screen_query(text: str) -> bool:
    return has_any(text, [
        "monitor", "monitors", "شاشة", "شاشه", "screen", "display",
        "gaming monitor", "gaming screen", "شاشة العاب", "شاشة للألعاب",
        "تفاعلية", "interactive", "sparq", "سبارك", "thinkvision", "lenovo"
    ])

def is_gaming_query(text: str) -> bool:
    return has_any(text, [
        "gaming", "قيمينق", "قيمينج", "ألعاب", "العاب",
        "fps", "هرتز", "hz", "refresh rate", "ps5", "xbox",
        "للألعاب", "للعب", "pc gaming", "game", "play"
    ])

def is_boox_query(text: str) -> bool:
    return has_any(text, [
        "boox", "بوكس", "قارئ", "ebook", "e-book", "eink", "e-ink",
        "note air", "palma", "go 6", "go 7", "go color", "tab x",
        "tab ultra", "قراءة", "reading", "كتاب إلكتروني"
    ])

def is_reading_device_intent(text: str) -> bool:
    return has_any(text, [
        "جهاز قراءة", "للقراءة", "قراءة الكتب", "قراءة كتاب", "كتب",
        "قارئ إلكتروني", "قارئ الكتروني", "ebook reader", "e-reader",
        "read books", "reading device", "device for reading"
    ])

def wants_big_screen(text: str) -> bool:
    t = normalize_arabic(text)
    return ("شاشه كبيره" in t) or ("شاشة كبيرة" in (text or "")) or has_any(text, ["large screen", "big screen", "اكبر شاشة", "أكبر شاشة"])

def is_notes_intent(text: str) -> bool:
    t_raw = (text or "").lower()
    t_ar = normalize_arabic(text)
    keys_ar = ["ملاحظات", "تدوين", "كتابة", "كتابه", "اكتب", "رسم", "نوت", "نوتس"]
    keys_en = ["notes", "note taking", "notetaking", "write", "writing", "draw", "sketch"]
    return any(k in t_ar for k in keys_ar) or any(k in t_raw for k in keys_en)

def detect_explicit_language_switch(text: str) -> Optional[str]:
    t = (text or "").lower().strip()
    if any(req in t for req in ["تكلم عربي", "بالعربي", "تكلم معاي بالعربي", "كلمني عربي"]):
        return "ar"
    if any(req in t for req in ["speak english", "in english", "بالانجليزي", "بالإنجليزي"]):
        return "en"
    return None

def is_contact_query(text: str) -> bool:
    return has_any(text, ["تواصل", "اتواصل", "رقم", "واتساب", "whatsapp", "contact", "reach", "support", "اتصال", "تواصلوا"])

# Important: accessory query should NOT catch general "pen/قلم" (prevents pen tips confusion)
def is_accessory_query(text: str) -> bool:
    t_raw = (text or "").lower()
    t_ar = normalize_arabic(text)

    # If user asks for notes, do NOT treat as accessories
    if is_notes_intent(text):
        return False

    # strong-only for tips/nibs etc.
    strong_ar = ["سنون", "رؤوس", "بديل", "قطع غيار"]
    strong_en = ["tips", "tip", "nibs", "nib", "replacement", "refill"]

    other_accessories = [
        "case", "cover", "جراب", "حافظة", "كفر",
        "lamp", "light", "اضاءة", "إضاءة", "لمبة", "مصباح",
        "holder", "stand", "حامل"
    ]

    if any(k in t_ar for k in strong_ar) or any(k in t_raw for k in strong_en):
        return True

    return any(acc in t_raw for acc in other_accessories) or any(acc in t_ar for acc in other_accessories)

# ============================================
# 8) FALLBACKS (accurate, non-random)
# ============================================

def fallback_product_links(language: str, topic: str) -> str:
    if topic == "reading":
        return OFFICIAL_LINKS["tablets"]
    if topic == "display":
        return OFFICIAL_LINKS["interactive"]
    if topic == "software":
        return OFFICIAL_LINKS["software"]
    return OFFICIAL_LINKS["store"]

def safe_fallback_message(language: str, topic: str) -> str:
    link = fallback_product_links(language, topic)
    if language == "ar":
        if topic == "reading":
            return f"تمام 🤍\nتقدر تتصفح أجهزة القراءة من هنا:\n🔗 {link}"
        if topic == "display":
            return f"تمام 🤍\nتقدر تتصفح الشاشات من هنا:\n🔗 {link}"
        if topic == "software":
            return f"تمام 🤍\nتقدر تتصفح التراخيص والبرامج من هنا:\n🔗 {link}"
        return f"تمام 🤍\n🔗 {link}"
    else:
        if topic == "reading":
            return f"Got it 🤍\nBrowse e-readers here:\n🔗 {link}"
        if topic == "display":
            return f"Got it 🤍\nBrowse screens here:\n🔗 {link}"
        if topic == "software":
            return f"Got it 🤍\nBrowse software/licenses here:\n🔗 {link}"
        return f"Got it 🤍\n🔗 {link}"

# ============================================
# 9) MAIN CHAT HANDLER
# ============================================

def handle_chat_message(
        user_input: str,
        catalog: ProductCatalog,
        system_prompt: str,
        conversation_history: Optional[List[Dict]] = None,
        language: str = 'auto',
        session_state: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
) -> str:
    try:
        if user_input is None or not user_input.strip():
            raise EmptyInputError()

        cleaned = user_input.strip()
        if len(cleaned) > 5000:
            cleaned = cleaned[:5000]

        if language == "auto":
            language = stable_language(cleaned, conversation_history)

        sess = _get_session(session_state, session_id)

        # intro tracking (works with either session_state or history)
        introduced = bool(sess.get("introduced", False)) or _already_introduced_from_history(conversation_history)

        # 1) jokes (including "another one")
        if is_joke_request(cleaned) or (is_another_joke_request(cleaned) and sess.get("last_intent") == "joke"):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "joke")
            return tell_joke(language)

        # 2) greeting
        if is_probably_just_greeting(cleaned):
            reply = greeting_reply(language, first_time=(not introduced), original_text=cleaned)
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "greeting")
            # do not reset mode on greeting
            return reply

        # 3) load catalog best-effort
        try:
            catalog.load()
        except CatalogLoadError as e:
            logger.error(f"Catalog load error: {e.message}")
            # still continue; but any product response should be safe fallback
            pass

        # 4) language switch
        lang_switch = detect_explicit_language_switch(cleaned)
        if lang_switch:
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "other")
            if lang_switch == "ar":
                return "تمام 🤍\nخلاص بكلمك عربي—وش تحتاج؟ 😊"
            return "Done 🤍\nSwitched to English—what do you need? 😊"

        # 5) contact query
        if is_contact_query(cleaned):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "facts")
            if language == "ar":
                return f"أكيد 🤍\n📱 واتساب: {OFFICIAL_LINKS['whatsapp']}"
            return f"Sure 🤍\n📱 WhatsApp: {OFFICIAL_LINKS['whatsapp']}"

        # 6) facts (keep content unchanged, improve framing only)
        if is_shipping_query(cleaned):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "facts")
            title = "تمام—هذي سياسة الشحن عندنا 👇" if language == "ar" else "Here’s our shipping info 👇"
            return wrap_facts_ar(title, SHIPPING_FACTS_AR) if language == "ar" else wrap_facts_en(title, SHIPPING_FACTS_EN)

        if is_warranty_query(cleaned):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "facts")
            title = "أكيد—هذي سياسة الضمان 👇" if language == "ar" else "Here’s our warranty policy 👇"
            return wrap_facts_ar(title, WARRANTY_FACTS_AR) if language == "ar" else wrap_facts_en(title, WARRANTY_FACTS_EN)

        if is_installment_query(cleaned):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "facts")
            title = "أكيد—هذي معلومات التقسيط 👇" if language == "ar" else "Here are the installment details 👇"
            return wrap_facts_ar(title, INSTALLMENT_FACTS_AR) if language == "ar" else wrap_facts_en(title, INSTALLMENT_FACTS_EN)

        if is_battery_query(cleaned) and (is_boox_query(cleaned) or is_reading_device_intent(cleaned)):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "facts")
            title = "تمام—هذي معلومات البطارية 👇" if language == "ar" else "Battery info 👇"
            return wrap_facts_ar(title, BATTERY_FACTS_AR) if language == "ar" else wrap_facts_en(title, BATTERY_FACTS_EN)

        if is_lifespan_query(cleaned):
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "facts")
            title = "أكيد—هذا عمر الجهاز الافتراضي 👇" if language == "ar" else "Lifespan info 👇"
            return wrap_facts_ar(title, LIFESPAN_FACTS_AR) if language == "ar" else wrap_facts_en(title, LIFESPAN_FACTS_EN)

        # ============================================
        # 7) TOPIC / MODE LOCK
        # ============================================

        mode = str(sess.get("mode", "") or "").strip()  # "reading" / "display" / "software" / ""

        wants_reading = is_reading_device_intent(cleaned) or is_boox_query(cleaned)
        wants_display = is_monitor_or_screen_query(cleaned) or is_gaming_query(cleaned)
        wants_software = is_programs_query(cleaned)

        # if user already in reading mode and asks "big screen" or "notes too", keep reading mode
        if mode == "reading" and (wants_big_screen(cleaned) or is_notes_intent(cleaned)):
            wants_display = False
            wants_reading = True

        # switch mode only on explicit request
        if wants_reading and not wants_display and not wants_software:
            mode = "reading"
        elif wants_display:
            mode = "display"
        elif wants_software:
            mode = "software"

        _set_session(session_state, session_id, "mode", mode)

        # ============================================
        # 8) CSV-ONLY: READING DEVICES (no Groq)
        # ============================================

        if mode == "reading" and not is_accessory_query(cleaned):
            base = catalog.search_products("boox eink قارئ ebook e-ink onyx", limit=70)
            filtered = catalog.filter_by_type(
                base,
                include_any=["boox", "onyx", "eink", "e-ink", "قارئ", "ebook", "e-book", "note", "palma", "go", "tab"]
            )
            filtered = _exclude_accessories(filtered)

            wants_notes = is_notes_intent(cleaned)
            if wants_notes:
                filtered_notes = catalog.filter_by_type(
                    filtered,
                    include_any=["note", "notes", "notetaking", "stylus", "pen", "wacom", "قلم", "ستايلس", "تدوين", "ملاحظات"]
                )
                filtered_notes = _exclude_accessories(filtered_notes)

                # If nothing in CSV clearly indicates notes support, don't guess.
                if not filtered_notes:
                    _set_session(session_state, session_id, "introduced", True)
                    _set_session(session_state, session_id, "last_intent", "products")
                    if language == "ar":
                        return (
                            "تمام 🤍\n"
                            "للأسف ما ظهر لي وصف واضح يدعم *الملاحظات/القلم* ضمن النتائج اللي طلعت لي.\n\n"
                            f"🔍 تقدر تتصفح كل أجهزة القراءة هنا:\n{OFFICIAL_LINKS['tablets']}\n\n"
                            "تبيني أرتّب لك الخيارات حسب **المقاس** ولا حسب **الميزانية**؟ 😊"
                        )
                    return (
                        "Got it 🤍\n"
                        "I couldn’t find clear catalog text confirming *notes/pen support* in the matches I pulled.\n\n"
                        f"🔍 Browse all e-readers here:\n{OFFICIAL_LINKS['tablets']}\n\n"
                        "Should I sort options by **screen size** or by **budget**? 😊"
                    )

                filtered = filtered_notes

            # Big screen preference
            if wants_big_screen(cleaned):
                filtered = sorted(filtered, key=lambda p: _safe_float(p.get("screen_size_in", "")), reverse=True)

            top = filtered[:3]
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "products")

            if not top:
                return safe_fallback_message(language, "reading")

            if language == "ar":
                msg = "أكيد 🤍 لقيت لك خيارات ممتازة:\n\n"
                for i, p in enumerate(top, 1):
                    name = p.get("name_ar") or p.get("name_en") or "غير مذكور"
                    price = p.get("price_sar", 0)
                    scr = p.get("screen_size_in", "")
                    storage = p.get("storage_gb", "")
                    url = (p.get("product_url") or "").strip()
                    if not url.startswith("http"):
                        url = OFFICIAL_LINKS["tablets"]

                    msg += f"**{i}) {name}**\n"
                    msg += f"• 💰 السعر: {price} ريال\n"
                    if scr:
                        msg += f"• 📏 الشاشة: {scr} بوصة\n"
                    if storage:
                        msg += f"• 💾 التخزين: {storage} GB\n"
                    msg += f"• 🔗 الرابط: {url}\n\n"

                msg += f"🔍 باقي الأجهزة هنا: {OFFICIAL_LINKS['tablets']}"
                return msg

            msg = "Sure 🤍 I found great options:\n\n"
            for i, p in enumerate(top, 1):
                name = p.get("name_en") or p.get("name_ar") or "Not listed"
                price = p.get("price_sar", 0)
                scr = p.get("screen_size_in", "")
                storage = p.get("storage_gb", "")
                url = (p.get("product_url") or "").strip()
                if not url.startswith("http"):
                    url = OFFICIAL_LINKS["tablets"]

                msg += f"**{i}) {name}**\n"
                msg += f"• 💰 Price: {price} SAR\n"
                if scr:
                    msg += f"• 📏 Screen: {scr} inches\n"
                if storage:
                    msg += f"• 💾 Storage: {storage} GB\n"
                msg += f"• 🔗 Link: {url}\n\n"

            msg += f"🔍 More devices: {OFFICIAL_LINKS['tablets']}"
            return msg

        # ============================================
        # 9) CSV-ONLY: DISPLAYS / GAMING SCREENS (no Groq)
        # ============================================

        if mode == "display":
            base = catalog.search_products(cleaned, limit=60)
            filtered = catalog.filter_by_type(
                base,
                include_any=[
                    "monitor", "monitors", "screen", "display",
                    "thinkvision", "lenovo", "gaming",
                    "sparq", "interactive",
                    "شاشة", "تفاعلية", "سبارك"
                ]
            )
            filtered = _exclude_accessories(filtered)

            # If user says "شاشة العاب" and catalog doesn't tag gaming, we still show best available screens
            top = filtered[:3]
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "products")

            if not top:
                return safe_fallback_message(language, "display")

            if language == "ar":
                msg = "أكيد 🤍 هذي خيارات شاشات ممكن تناسب الألعاب:\n\n"
                for i, p in enumerate(top, 1):
                    name = p.get("name_ar") or p.get("name_en") or "غير مذكور"
                    price = p.get("price_sar", 0)
                    scr = p.get("screen_size_in", "")
                    url = (p.get("product_url") or "").strip()
                    if not url.startswith("http"):
                        url = OFFICIAL_LINKS["interactive"]

                    msg += f"**{i}) {name}**\n"
                    msg += f"• 💰 السعر: {price} ريال\n"
                    if scr:
                        msg += f"• 📏 الشاشة: {scr} بوصة\n"
                    msg += f"• 🔗 الرابط: {url}\n\n"

                msg += f"🔍 باقي الشاشات هنا: {OFFICIAL_LINKS['interactive']}"
                return msg

            msg = "Sure 🤍 Here are screen options that can work for gaming:\n\n"
            for i, p in enumerate(top, 1):
                name = p.get("name_en") or p.get("name_ar") or "Not listed"
                price = p.get("price_sar", 0)
                scr = p.get("screen_size_in", "")
                url = (p.get("product_url") or "").strip()
                if not url.startswith("http"):
                    url = OFFICIAL_LINKS["interactive"]

                msg += f"**{i}) {name}**\n"
                msg += f"• 💰 Price: {price} SAR\n"
                if scr:
                    msg += f"• 📏 Screen: {scr} inches\n"
                msg += f"• 🔗 Link: {url}\n\n"

            msg += f"🔍 More screens: {OFFICIAL_LINKS['interactive']}"
            return msg

        # ============================================
        # 10) CSV-ONLY: SOFTWARE LICENSES (optional local)
        # ============================================

        if mode == "software":
            base = catalog.search_products(cleaned, limit=40)
            filtered = catalog.filter_by_type(
                base,
                include_any=["license", "ترخيص", "software", "برنامج", "program", "office", "microsoft"]
            )
            filtered = _exclude_accessories(filtered)

            top = filtered[:3]
            _set_session(session_state, session_id, "introduced", True)
            _set_session(session_state, session_id, "last_intent", "products")

            if not top:
                return safe_fallback_message(language, "software")

            if language == "ar":
                msg = "أكيد 🤍 هذي خيارات تراخيص/برامج:\n\n"
                for i, p in enumerate(top, 1):
                    name = p.get("name_ar") or p.get("name_en") or "غير مذكور"
                    price = p.get("price_sar", 0)
                    url = (p.get("product_url") or "").strip()
                    if not url.startswith("http"):
                        url = OFFICIAL_LINKS["software"]
                    msg += f"**{i}) {name}**\n• 💰 السعر: {price} ريال\n• 🔗 الرابط: {url}\n\n"
                msg += f"🔍 باقي التراخيص هنا: {OFFICIAL_LINKS['software']}"
                return msg

            msg = "Sure 🤍 Here are software/license options:\n\n"
            for i, p in enumerate(top, 1):
                name = p.get("name_en") or p.get("name_ar") or "Not listed"
                price = p.get("price_sar", 0)
                url = (p.get("product_url") or "").strip()
                if not url.startswith("http"):
                    url = OFFICIAL_LINKS["software"]
                msg += f"**{i}) {name}**\n• 💰 Price: {price} SAR\n• 🔗 Link: {url}\n\n"
            msg += f"🔍 More licenses: {OFFICIAL_LINKS['software']}"
            return msg

        # ============================================
        # 11) GROQ: only for non-product chat (safe style, no reintro)
        # ============================================

        _set_session(session_state, session_id, "introduced", True)
        _set_session(session_state, session_id, "last_intent", "llm")

        # pick fallback category for URL scrubbing (never homepage)
        if is_programs_query(cleaned):
            fallback_url = OFFICIAL_LINKS["software"]
            topic = "software"
        elif is_monitor_or_screen_query(cleaned) or is_gaming_query(cleaned):
            fallback_url = OFFICIAL_LINKS["interactive"]
            topic = "display"
        elif is_boox_query(cleaned) or is_reading_device_intent(cleaned):
            fallback_url = OFFICIAL_LINKS["tablets"]
            topic = "reading"
        else:
            fallback_url = OFFICIAL_LINKS["tablets"]
            topic = ""

        # Strong style rules to stop re-introduction + stop hallucination
        style_rules = (
            "STYLE RULES:\n"
            "- Do NOT re-introduce yourself (no 'I am Smorti' / 'أنا سمورتي') unless the user asks who you are.\n"
            "- Do NOT greet repeatedly.\n"
            "- Be warm, professional, lightly humorous.\n"
            "- If info is missing: ask ONE short clarifying question.\n"
            "- NEVER invent products, prices, specs, or links.\n"
            "- NEVER use the store homepage as a product link.\n"
        )

        temperature = 0.10

        response = call_groq_api(
            prompt=cleaned + "\n\n" + style_rules,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            temperature=temperature,
            max_tokens=900
        )

        # Post-processing safety
        allowed_urls = set(OFFICIAL_LINKS.values())
        response = scrub_unknown_urls(response, allowed_urls, fallback_url, allow_store=False)
        response = scrub_placeholders(response)

        # If Groq outputs a forbidden/hallucinated BOOX model name, do a safe fallback
        forbidden_markers = ["nova air", "poke 3", "max3", "note air 3", "tab ultra"]
        if any(f in (response or "").lower() for f in forbidden_markers):
            logger.error("🚨 Hallucination marker detected in LLM response. Using safe fallback.")
            return safe_fallback_message(language, topic or "reading")

        return response

    except EmptyInputError as e:
        lang = 'ar' if is_arabic(user_input or "") else 'en'
        return e.user_message_ar if lang == 'ar' else e.user_message_en

    except (GroqRateLimitError, GroqAPIError) as e:
        # Always accurate fallback (no random info)
        lang = language if language in ("ar", "en") else ('ar' if is_arabic(user_input or "") else 'en')
        topic = str(_get_session(session_state, session_id).get("mode", "") or "")
        if not topic:
            # infer topic from text
            if is_programs_query(user_input or ""):
                topic = "software"
            elif is_monitor_or_screen_query(user_input or "") or is_gaming_query(user_input or ""):
                topic = "display"
            else:
                topic = "reading"
        return safe_fallback_message(lang, topic)

    except Exception as e:
        logger.critical(f"UNEXPECTED ERROR: {e}", exc_info=True)
        lang = language if language in ("ar", "en") else ('ar' if is_arabic(user_input or "") else 'en')
        # Safe minimal message + correct category link
        topic = str(_get_session(session_state, session_id).get("mode", "") or "reading")
        if lang == "ar":
            return "صار شي غير متوقع 😔🤍\n" + safe_fallback_message("ar", topic)
        return "Something unexpected happened 😔🤍\n" + safe_fallback_message("en", topic)

# ============================================
# 12) HEALTH CHECK & CLI
# ============================================

def run_health_check(catalog_path: str) -> Dict[str, str]:
    health = {
        'timestamp': datetime.now().isoformat(),
        'groq_api': '❌ Not tested',
        'api_key': '❌ Missing',
        'catalog': '❌ Not loaded',
        'pandas': '❌ Not installed'
    }

    try:
        import pandas as _pd
        health['pandas'] = '✓ Installed'
    except ImportError:
        health['pandas'] = '❌ Not installed'

    health['api_key'] = '✓ Found' if os.getenv('GROQ_API_KEY') else '❌ Missing'

    try:
        cat = ProductCatalog(catalog_path)
        prods = cat.load()
        health['catalog'] = f'✓ Loaded ({len(prods)} products)'
    except Exception as e:
        health['catalog'] = f'❌ Error: {str(e)[:80]}'

    try:
        _ = call_groq_api(
            prompt="Say 'جاهز' in one word",
            system_prompt="You are a test bot.",
            temperature=0.1,
            max_tokens=10
        )
        health['groq_api'] = '✓ Working'
    except Exception as e:
        health['groq_api'] = f'❌ Error: {str(e)[:80]}'

    return health

def main():
    print("=" * 60)
    print("🤖 SMORTI AI AGENT - ANTI-HALLUCINATION VERSION")
    print(f"Version: {APP_VERSION}")
    print("=" * 60)

    print("\n🏥 Running health check...")
    health = run_health_check('data/products_enriched.csv')
    for k, v in health.items():
        print(f"  {k}: {v}")

    catalog = ProductCatalog('data/products_enriched.csv')
    system_prompt = (
        "You are Smorti for SMART store. "
        "Never invent products, prices, specs, or links. "
        "Do not re-introduce yourself unless asked who you are."
    )

    hist: List[Dict[str, str]] = []
    session_state: Dict[str, Any] = {}
    session_id = "cli"

    print("\n💬 Chat started! Type 'exit' to end.\n")

    while True:
        user = input("\nYou: ").strip()
        if user.lower() in ("exit", "quit"):
            print("👋 Goodbye!")
            break
        if not user:
            continue

        ans = handle_chat_message(
            user_input=user,
            catalog=catalog,
            system_prompt=system_prompt,
            conversation_history=hist,
            language="auto",
            session_state=session_state,
            session_id=session_id
        )
        print(f"\nSmorti: {ans}")

        hist.append({"role": "user", "content": user})
        hist.append({"role": "assistant", "content": ans})

if __name__ == "__main__":
    main()
