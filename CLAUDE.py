"""
Smorti AI Agent (CLAUDE.py) - v1.2
Backend engine used by Streamlit app + local CLI.

What’s new in v1.2 (based on your tests):
✅ If user asks for "شاشة" (screen) it won’t default to BOOX only — it will look for Monitors + Interactive Screens too.
✅ For gaming: it will suggest monitors / interactive screens we actually have in the CSV, and clearly say they *can* run games (but may not be “gaming-first”).
✅ No more made-up screen specs/links: the model is forced to use ONLY catalog fields; if spec isn’t in CSV it must say “غير مذكور في الكتالوج”.
✅ Contact info: no placeholders like [رقم الهاتف]. Only official links (store + WhatsApp).
✅ Personality: more playful + light sarcasm, mentions it’s an AI under development, asks for patience 🤍
✅ Poetry/story: more Arabic-literature friendly (allowed to be creative), but still MUST NOT invent product specs/links.

IMPORTANT:
- Streamlit will reflect these changes as soon as you commit+push CLAUDE.py and Streamlit Cloud redeploys.
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

APP_VERSION = "v1.2"

# Load environment variables from .env file (local). Streamlit Cloud uses st.secrets -> env.
load_dotenv()

# ============================================
# 1) LOGGING CONFIGURATION
# ============================================

def setup_logging():
    """Configure logging for local testing + Streamlit Cloud."""
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

# Installments (must be correct)
INSTALLMENT_FACTS_AR = (
    "💳 التقسيط المتوفر عندنا: Tabby / Tamara / MisPay.\n"
    "عادةً 4 دفعات بدون فوائد: 25% الآن والباقي على 3 أشهر.\n"
    "ويمكن تمديد المدة حسب مزوّد التقسيط.\n"
    "التفاصيل النهائية تظهر في صفحة الدفع عند إتمام الطلب."
)
INSTALLMENT_FACTS_EN = (
    "💳 Installments available: Tabby / Tamara / MisPay.\n"
    "Typically 4 payments with 0% interest: 25% now, the rest over 3 months.\n"
    "Some providers allow extending the period depending on the provider.\n"
    "Final details appear at checkout."
)

BATTERY_FACTS_AR = (
    "🔋 بطارية أجهزة الحبر الإلكتروني غالباً تدوم أيام (3–4 أيام بسهولة حسب الاستخدام).\n"
    "الأبيض والأسود غالباً يدوم أطول من الملون بسبب استهلاك أقل.\n"
    "المدة تختلف حسب الواي فاي/البلوتوث/الكتابة بالقلم."
)
BATTERY_FACTS_EN = (
    "🔋 E-ink devices usually last for days (often 3–4 days easily depending on usage).\n"
    "Monochrome typically lasts longer than color due to lower power draw.\n"
    "It varies with Wi-Fi/Bluetooth/pen usage."
)

LIFESPAN_FACTS_AR = (
    "⏳ عمر الجهاز يعتمد على استخدامك (دورات الشحن، الحرارة، كثافة الاستخدام).\n"
    "بشكل عام ومع استخدام طبيعي، غالباً يتجاوز 5 سنوات بسهولة."
)
LIFESPAN_FACTS_EN = (
    "⏳ Device lifespan depends on usage (charging cycles, heat, intensity).\n"
    "With normal use and care, it typically lasts 5+ years."
)

def is_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))

def detect_language_simple(text: str) -> str:
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text or ""))
    english_chars = len(re.findall(r'[a-zA-Z]', text or ""))
    return 'ar' if arabic_chars > english_chars else 'en'

def stable_language(
    current_text: str,
    conversation_history: Optional[List[Dict]] = None
) -> str:
    """
    Keep language stable:
    - Use last user language from history
    - Switch only if user explicitly asks OR current text is clearly the other language
    """
    t = (current_text or "").lower()

    # explicit user request
    if any(x in t for x in ["بالانجليزي", "بالإنجليزي", "english please", "in english", "speak english"]):
        return "en"
    if any(x in t for x in ["بالعربي", "بالعربية", "arabic please", "in arabic", "speak arabic"]):
        return "ar"

    cur = detect_language_simple(current_text)

    last_user_lang = None
    if conversation_history:
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                last_user_lang = detect_language_simple(msg.get("content", ""))
                break

    if not last_user_lang:
        return cur

    if last_user_lang != cur:
        # strong switch signals
        if cur == "ar" and is_arabic(current_text) and len(current_text) >= 8:
            return "ar"
        if cur == "en" and re.search(r"[a-zA-Z]{6,}", current_text or ""):
            return "en"
        return last_user_lang

    return cur

# Greeting rules
SALAM_RE = re.compile(r"(السلام عليكم(?:\s*و\s*رحمة الله(?:\s*و\s*بركاته)?)?)", re.IGNORECASE)
EN_GREETING_RE = re.compile(r"\b(hi|hello|hey|good (morning|evening)|howdy)\b", re.IGNORECASE)
AR_GREETING_RE = re.compile(r"\b(هلا|هلا والله|مرحبا|يا هلا|السلام)\b", re.IGNORECASE)

def is_probably_just_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if len(t) <= 35 and (SALAM_RE.search(t) or EN_GREETING_RE.search(t) or AR_GREETING_RE.search(t)):
        return True
    return False

def greeting_reply(text: str, lang: str) -> str:
    t = (text or "").strip()
    if SALAM_RE.search(t):
        return (
            "وعليكم السلام ورحمة الله وبركاته 🤍🤍\n"
            "هلا فيك! أنا سمورتي 😊 مساعد ذكي (تحت التطوير) في متجر SMART — عطِني فرصة وأضبطها معك 😄\n"
            "وش تبي نختار لك اليوم؟"
        )
    if lang == "en":
        return (
            "Hey! 😊 I’m Smorti — an AI assistant (still under development) at SMART store.\n"
            "Give me a chance and I’ll get smarter with your feedback 😄\n"
            "What are you looking for today?"
        )
    return (
        "يا هلا ومرحبا 😊 أنا سمورتي — مساعد ذكي (تحت التطوير) في متجر SMART.\n"
        "عطِني فرصة وبكون خفيف دم ومفيد بنفس الوقت 😄\n"
        "وش تبي اليوم؟"
    )

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
            "عذراً، صار خطأ مؤقت بالنظام 🙏 جرب مرة ثانية",
            "Sorry, a temporary system error occurred 🙏 Please try again"
        )

class GroqRateLimitError(SmortiBaseException):
    def __init__(self, message: str):
        super().__init__(
            message,
            "عذراً، الطلبات كثيرة حالياً. انتظر شوي وجرب مرة ثانية 😊",
            "Sorry, too many requests. Wait a moment and try again 😊"
        )

class CatalogLoadError(SmortiBaseException):
    def __init__(self, message: str):
        super().__init__(
            message,
            "ما قدرت أوصل للكتالوج حالياً 😔 خلّني أوجهك للموقع",
            "Cannot access catalog right now 😔 I'll direct you to the website"
        )

class EmptyInputError(SmortiBaseException):
    def __init__(self):
        super().__init__(
            "Empty user input",
            "مرحباً! 😊 وش أقدر أخدمك؟",
            "Hello! 😊 How can I help you?"
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
    temperature: float = 0.25,
    max_tokens: int = 850
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

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False
        )

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

        # Fill nulls defensively
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
            if t in str(product.get('name_en', '')).lower(): score += 4
            if t in str(product.get('name_ar', '')).lower(): score += 4
            if t in str(product.get('series', '')).lower(): score += 3
            if t in str(product.get('brand', '')).lower(): score += 2
            if t in joined: score += 1
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
            blob = " ".join([
                str(p.get('item_type', '')).lower(),
                str(p.get('category', '')).lower(),
                str(p.get('name_en', '')).lower(),
                str(p.get('name_ar', '')).lower(),
                str(p.get('short_desc', '')).lower(),
                str(p.get('keywords', '')).lower(),
            ])
            if any(k in blob for k in keys):
                out.append(p)
        return out

# ============================================
# 7) SAFETY: PRODUCT CONTEXT + URL SCRUBBING
# ============================================

def build_product_context(products: List[Dict[str, Any]], language: str) -> str:
    if not products:
        if language == "ar":
            return (
                "\n\n=== NO_MATCH ===\n"
                "لم يتم العثور على منتجات مطابقة داخل الكتالوج.\n"
                f"وجّه العميل للموقع: {OFFICIAL_LINKS['store']}\n"
                "ممنوع اختراع منتجات أو روابط.\n"
            )
        return (
            "\n\n=== NO_MATCH ===\n"
            "No matching products found in the catalog.\n"
            f"Direct to: {OFFICIAL_LINKS['store']}\n"
            "Do NOT invent products or links.\n"
        )

    def g(p: Dict[str, Any], k: str, default="N/A"):
        v = p.get(k, default)
        return default if v is None or v == "" else v

    ctx = "\n\n=== AVAILABLE PRODUCTS (USE ONLY THIS DATA) ===\n"
    for i, p in enumerate(products, 1):
        ctx += f"\n--- Product {i} ---\n"
        ctx += f"name_en: {g(p,'name_en')}\n"
        ctx += f"name_ar: {g(p,'name_ar')}\n"
        ctx += f"brand: {g(p,'brand')}\n"
        ctx += f"series: {g(p,'series')}\n"
        ctx += f"category: {g(p,'category')}\n"
        ctx += f"item_type: {g(p,'item_type')}\n"
        ctx += f"short_desc: {g(p,'short_desc')}\n"
        ctx += f"price_sar: {g(p,'price_sar')}\n"
        ctx += f"old_price_sar: {g(p,'old_price_sar')}\n"
        ctx += f"screen_size_in: {g(p,'screen_size_in')}\n"
        ctx += f"display_type: {g(p,'display_type')}\n"
        ctx += f"ram_gb: {g(p,'ram_gb')}\n"
        ctx += f"storage_gb: {g(p,'storage_gb')}\n"
        ctx += f"resolution_px: {g(p,'resolution_px')}\n"
        ctx += f"ppi: {g(p,'ppi')}\n"
        ctx += f"cpu: {g(p,'cpu')}\n"
        ctx += f"os: {g(p,'os')}\n"
        ctx += f"wifi: {g(p,'wifi')}\n"
        ctx += f"bluetooth: {g(p,'bluetooth')}\n"
        ctx += f"Battery_mah: {g(p,'Battery_mah')}\n"
        ctx += f"connectivity: {g(p,'connectivity')}\n"
        ctx += f"product_url: {g(p,'product_url')}\n"
        ctx += f"category_link: {g(p,'category_link')}\n"
        ctx += f"availability: {g(p,'availability')}\n"

    ctx += "\n=== HARD RULES ===\n"
    ctx += "- Use ONLY the products above.\n"
    ctx += "- NEVER invent any product names, prices, specs, or URLs.\n"
    ctx += "- If a spec is not shown above, say: (غير مذكور في الكتالوج) / (Not listed in our catalog).\n"
    ctx += "- Only include URLs that appear in product_url/category_link above, or official links.\n"
    ctx += "- NEVER output placeholders like [رقم الهاتف] or [email].\n"
    ctx += "==================\n"
    return ctx

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

def scrub_unknown_urls(text: str, allowed: set) -> str:
    def repl(m):
        url = m.group(0).rstrip(").,，。!؟!?]")
        return url if url in allowed else OFFICIAL_LINKS["store"]
    return URL_RE.sub(repl, text or "")

# Also scrub placeholder contact fields
PLACEHOLDER_CONTACT_RE = re.compile(r"\[(رقم الهاتف|عنوان البريد الإلكتروني|عنوان الموقع الإلكتروني|اسم حسابنا.*?)\]", re.IGNORECASE)

def scrub_placeholders(text: str) -> str:
    return PLACEHOLDER_CONTACT_RE.sub(OFFICIAL_LINKS["whatsapp"], text or "")

# ============================================
# 8) INTENTS
# ============================================

def has_any(text: str, keys: List[str]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keys)

def is_installment_query(text: str) -> bool:
    return has_any(text, ["تقسيط", "تمارا", "تابي", "تابى", "mispay", "ميس باي", "installment", "tabby", "tamara"])

def is_battery_query(text: str) -> bool:
    return has_any(text, ["بطارية", "battery", "تشحن", "شحن", "يدوم", "lasts", "مدة البطارية"])

def is_lifespan_query(text: str) -> bool:
    return has_any(text, ["عمر", "يعيش", "كم سنة", "virtual age", "lifespan", "how long will it last", "يدوم كم"])

def is_programs_query(text: str) -> bool:
    return has_any(text, ["ترخيص", "رخصة", "license", "software", "برنامج", "برامج", "spss", "matlab", "solidworks", "arcgis", "autocad"])

def is_monitor_or_screen_query(text: str) -> bool:
    # Treat generic "شاشة" as screen, not only BOOX
    return has_any(text, [
        "monitor", "monitors", "شاشة", "شاشه", "screen", "display", "لوحة عرض",
        "تفاعلية", "interactive", "sparq", "سبارك"
    ])

def is_gaming_query(text: str) -> bool:
    return has_any(text, ["gaming", "قيمينق", "قيمينج", "fps", "هرتز", "ps5", "xbox", "للألعاب", "للعب", "pc gaming"])

def is_boox_query(text: str) -> bool:
    return has_any(text, [
        "boox", "بوكس", "قارئ", "ebook", "e-book", "eink", "e-ink",
        "note air", "palma", "go 6", "go 7", "go color", "tab x", "tab ultra"
    ])

def is_poetry_or_story_request(text: str) -> bool:
    return has_any(text, ["قصيدة", "شعر", "قافية", "بيت شعر", "قصة", "سرد", "poem", "poetry", "story"])

def is_contact_query(text: str) -> bool:
    return has_any(text, ["تواصل", "اتواصل", "رقم", "واتساب", "whatsapp", "contact", "reach", "support"])

# ============================================
# 9) FALLBACK
# ============================================

def get_fallback_response(error: SmortiBaseException, language: str = 'ar') -> str:
    return error.user_message_ar if language == 'ar' else error.user_message_en

# ============================================
# 10) MAIN CHAT HANDLER (USED BY STREAMLIT)
# ============================================

def handle_chat_message(
    user_input: str,
    catalog: ProductCatalog,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    language: str = 'auto'
) -> str:
    """
    Core rules:
    - NEVER invent products/links/specs.
    - Screens: recommend monitors + interactive screens from CSV (even if not gaming-first),
      and mention they can run games but may not be “gaming-first”.
    - If user says “شاشة” don’t default to BOOX.
    - Software/licenses: describe generally what it does, but don’t invent license terms/specs.
    - Contact: only official links; no placeholders.
    - Humor: playful + light sarcasm, mention AI under development.
    - Poetry/story: more Arabic literature flair allowed, but NO invented specs/links.
    """
    try:
        if user_input is None or not user_input.strip():
            raise EmptyInputError()

        cleaned = user_input.strip()
        if len(cleaned) > 5000:
            cleaned = cleaned[:5000]

        if language == "auto":
            language = stable_language(cleaned, conversation_history)

        # Greeting override (your strict rule)
        if is_probably_just_greeting(cleaned):
            return greeting_reply(cleaned, language)

        # Load catalog best-effort
        try:
            catalog.load()
        except CatalogLoadError as e:
            logger.error(f"Catalog load error: {e.message}")

        # Build search results by intent
        search_results: List[Dict[str, Any]] = []
        catalog_context = ""
        allowed_urls = set(OFFICIAL_LINKS.values())

        # Contact queries: answer with official links (still model-generated style, but forced info)
        if is_contact_query(cleaned):
            if language == "ar":
                return (
                    "أكيد 🤍 تواصل معنا مباشرة عبر:\n"
                    f"• واتساب: {OFFICIAL_LINKS['whatsapp']}\n"
                    f"• المتجر: {OFFICIAL_LINKS['store']}\n"
                    "أنا سمورتي (مساعد AI تحت التطوير) وإذا لخبطت… قلّي وأعدّل نفسي 😄"
                )
            return (
                "Sure 🤍 You can reach us via:\n"
                f"• WhatsApp: {OFFICIAL_LINKS['whatsapp']}\n"
                f"• Store: {OFFICIAL_LINKS['store']}\n"
                "I’m Smorti (an AI assistant under development) — if I mess up, tell me and I’ll improve 😄"
            )

        # Screens / monitors / interactive screens (generic “شاشة” comes here)
        if is_monitor_or_screen_query(cleaned) or is_gaming_query(cleaned):
            base = catalog.search_products(cleaned, limit=30) if hasattr(catalog, "search_products") else []
            # filter for monitors + interactive screens
            filtered = catalog.filter_by_type(
                base,
                include_any=["monitor", "thinkvision", "lenovo", "sparq", "interactive", "تفاعلية", "شاشة", "screen"]
            )
            if not filtered:
                # fallback query: try to pull screens from catalog even if user didn’t specify
                base2 = catalog.search_products("monitor شاشة sparq", limit=30)
                filtered = catalog.filter_by_type(
                    base2,
                    include_any=["monitor", "thinkvision", "lenovo", "sparq", "interactive", "تفاعلية", "شاشة", "screen"]
                )
            search_results = filtered[:10]

        # Programs/licenses
        elif is_programs_query(cleaned):
            base = catalog.search_products(cleaned, limit=20)
            filtered = catalog.filter_by_type(base, include_any=["license", "ترخيص", "software", "برنامج", "program"])
            search_results = (filtered or base)[:10]

        # BOOX / reading
        elif is_boox_query(cleaned):
            base = catalog.search_products(cleaned, limit=20)
            filtered = catalog.filter_by_type(base, include_any=["boox", "eink", "e-ink", "قارئ", "note", "palma", "go", "tab"])
            search_results = (filtered or base)[:10]

        # General product-y
        else:
            productish = has_any(cleaned, ["سعر", "price", "بكم", "كم سعر", "مواصفات", "spec", "قارن", "best", "recommend", "اقترح", "device", "جهاز", "شاشة", "monitor", "ترخيص", "license"])
            if productish:
                search_results = catalog.search_products(cleaned, limit=10)

        # Build context
        if search_results:
            catalog_context = build_product_context(search_results, language)
            allowed_urls = allowed_urls_from_products(search_results)
        else:
            # if user likely asked for products but none found -> NO_MATCH rules
            if has_any(cleaned, ["boox", "بوكس", "شاشة", "monitor", "sparq", "تفاعلية", "ترخيص", "license", "برنامج", "سعر", "price"]):
                catalog_context = build_product_context([], language)
                allowed_urls = set(OFFICIAL_LINKS.values())

        # Creativity settings
        temp = 0.25
        if is_poetry_or_story_request(cleaned):
            # allow better poetry, but still with strict non-invention rules
            temp = 0.70

        # Business rules block (forces correct behavior but keeps response AI-generated)
        if language == "ar":
            business_rules = f"""
=== BUSINESS FACTS (MUST BE CORRECT) ===
- {INSTALLMENT_FACTS_AR}
- {BATTERY_FACTS_AR}
- {LIFESPAN_FACTS_AR}

=== BEHAVIOR RULES (STRICT) ===
1) أنت سمورتي، مساعد ذكاء اصطناعي في متجر SMART (تحت التطوير) — خفيف ظل ومفيد، مزح بسيط وسخرية خفيفة بدون قلة أدب.
2) التزم بلغة العميل: إذا الكلام عربي رد عربي، وإذا إنجليزي رد إنجليزي. لا تغيّر فجأة بسبب كلمة واحدة.
3) إذا العميل يقول السلام عليكم (كامل) رد عليه كامل مع قلوب بيضاء 🤍.
4) الشاشات:
   - إذا العميل يطلب "شاشة" أو "مونيتور" أو "شاشة ألعاب": اعرض المونيتور/الشاشات التفاعلية الموجودة في الكتالوج.
   - قل بوضوح: (تقدر تلعب عليها ألعاب) لكن مو شرط تكون "Gaming-first" حسب المواصفات الموجودة.
5) أجهزة BOOX:
   - ممتازة للقراءة/الكتابة والعمل الخفيف.
   - ليست مخصصة للـMedia-heavy مثل التابلت العادي بسبب طبيعة شاشة الحبر الإلكتروني.
6) البرامج/التراخيص:
   - اشرح بشكل عام ماذا يفعل البرنامج (بدون اختراع شروط ترخيص/أنواع اشتراك).
   - إذا ما فيه تفاصيل ترخيص في الكتالوج قل: (غير مذكور في الكتالوج) ووجّه لرابط المنتج/قسم البرامج.
7) ممنوع اختراع أي منتج أو رابط أو مواصفة.
   - استخدم فقط بيانات AVAILABLE PRODUCTS.
   - أي مواصفة غير موجودة في الكتالوج → قل: "غير مذكور في الكتالوج".
8) ممنوع وضع placeholders مثل [رقم الهاتف] أو [email]. التواصل فقط عبر:
   - واتساب: {OFFICIAL_LINKS['whatsapp']}
   - المتجر: {OFFICIAL_LINKS['store']}
9) لو طلب قصيدة/قصة: مسموح إبداع لغوي عالي، لكن بدون أرقام/مواصفات غير موجودة أو روابط غير موجودة.
=============================
"""
        else:
            business_rules = f"""
=== BUSINESS FACTS (MUST BE CORRECT) ===
- {INSTALLMENT_FACTS_EN}
- {BATTERY_FACTS_EN}
- {LIFESPAN_FACTS_EN}

=== BEHAVIOR RULES (STRICT) ===
1) You are Smorti, an AI assistant at SMART store (under development) — playful, lightly sarcastic, but always helpful and polite.
2) Keep the user's language stable (Arabic/English). Don’t switch because of a single word.
3) If the user greets in Arabic salam, respond properly and use white hearts 🤍.
4) Screens:
   - If the user asks for "screen/monitor/gaming screen": show ONLY monitors/interactive screens that exist in the catalog.
   - Say clearly: it CAN run games, but it may not be gaming-first depending on catalog specs.
5) BOOX:
   - Great for reading/writing/light productivity.
   - Not ideal for media-heavy viewing like normal tablets due to e-ink nature.
6) Software/licenses:
   - Explain what the software does at a high level, without inventing license terms/subscriptions.
   - If not in catalog, say: "Not listed in our catalog" and point to official links.
7) Never invent any product, URL, or spec.
   - Use ONLY AVAILABLE PRODUCTS.
   - If a spec is missing → say: "Not listed in our catalog."
8) No placeholders like [phone] or [email]. Contact only:
   - WhatsApp: {OFFICIAL_LINKS['whatsapp']}
   - Store: {OFFICIAL_LINKS['store']}
9) Poetry/story requests: higher creativity allowed, but no fake specs/links.
=============================
"""

        enhanced_prompt = cleaned + "\n\n" + business_rules + "\n\n" + catalog_context

        # Call model
        response = call_groq_api(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            temperature=temp,
            max_tokens=900
        )

        # Safety post-processing
        response = scrub_unknown_urls(response, allowed_urls)
        response = scrub_placeholders(response)

        return response

    except EmptyInputError as e:
        lang = 'ar' if is_arabic(user_input or "") else 'en'
        return get_fallback_response(e, lang)

    except GroqRateLimitError as e:
        lang = language if language in ("ar", "en") else "ar"
        return get_fallback_response(e, lang)

    except GroqAPIError as e:
        lang = language if language in ("ar", "en") else "ar"
        return get_fallback_response(e, lang)

    except Exception as e:
        logger.critical(f"UNEXPECTED ERROR: {e}", exc_info=True)
        return "عذراً، صار خطأ غير متوقع 😔" if language == "ar" else "Sorry, an unexpected error occurred 😔"


# ============================================
# 11) OPTIONAL: HEALTH CHECK (CLI)
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
    print("🤖 SMORTI AI AGENT - LOCAL CLI TEST")
    print("=" * 60)

    print("\n🏥 Running health check...")
    health = run_health_check('data/products_enriched.csv')
    for k, v in health.items():
        print(f"  {k}: {v}")

    catalog = ProductCatalog('data/products_enriched.csv')
    system_prompt = "You are Smorti, an AI assistant for SMART store. Follow the given rules."
    hist: List[Dict[str, str]] = []

    while True:
        user = input("\nYou: ").strip()
        if user.lower() in ("exit", "quit"):
            break
        ans = handle_chat_message(user, catalog, system_prompt, hist, language="auto")
        print("Smorti:", ans)
        hist.append({"role": "user", "content": user})
        hist.append({"role": "assistant", "content": ans})


if __name__ == "__main__":
    main()