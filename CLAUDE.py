"""
Smorti AI Agent (CLAUDE.py) - v1.3
Backend engine used by Streamlit app + local CLI.
Updated with improved personality, language handling, and product recommendations.
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

APP_VERSION = "v1.3"

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

# Installments - EXACT information
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

# Greetings variations for variety
ARABIC_GREETINGS = [
    "يا هلا ومرحبا",
    "أهلين وسهلين",
    "حياك الله",
    "نورت",
    "منورنا",
    "يا مرحبا",
]

ENGLISH_GREETINGS = [
    "Hey there",
    "Hello",
    "Hi",
    "Welcome",
    "Howdy",
    "Greetings",
]

def is_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))

def detect_language_simple(text: str) -> str:
    """Simple language detection based on character count"""
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text or ""))
    english_chars = len(re.findall(r'[a-zA-Z]', text or ""))
    return 'ar' if arabic_chars > english_chars else 'en'

def stable_language(
    current_text: str,
    conversation_history: Optional[List[Dict]] = None
) -> str:
    """
    Enhanced language stability with explicit switching support.
    Only switches if user explicitly requests or if clearly using different language.
    """
    t = (current_text or "").lower()

    # Check for explicit language switch requests
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

    # Detect current message language
    cur_lang = detect_language_simple(current_text)

    # Get last user message language from history
    last_user_lang = None
    if conversation_history:
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                last_user_lang = detect_language_simple(msg.get("content", ""))
                break

    # If no history, use current detection
    if not last_user_lang:
        return cur_lang

    # Only switch if there's strong evidence (not just one word)
    if last_user_lang != cur_lang:
        # Check if it's a strong switch (multiple words or long text in new language)
        if cur_lang == "ar":
            ar_content = len(re.findall(r'[\u0600-\u06FF]+', current_text or ""))
            if ar_content >= 3 or len(current_text) >= 15:  # Strong Arabic signal
                return "ar"
        elif cur_lang == "en":
            en_words = len(re.findall(r'\b[a-zA-Z]+\b', current_text or ""))
            if en_words >= 3 or len(current_text) >= 15:  # Strong English signal
                return "en"

        # Weak signal, keep previous language
        return last_user_lang

    return cur_lang

# Enhanced greeting detection with variations
SALAM_RE = re.compile(
    r"(السلام عليكم(?:\s*و\s*رحمة الله(?:\s*و\s*بركاته)?)?)",
    re.IGNORECASE
)
EN_GREETING_RE = re.compile(
    r"\b(hi|hello|hey|good\s*(morning|evening|afternoon)|howdy|greetings)\b",
    re.IGNORECASE
)
AR_GREETING_RE = re.compile(
    r"\b(هلا|هلا والله|مرحبا|يا هلا|السلام|اهلين|حياك|منور)\b",
    re.IGNORECASE
)

def is_probably_just_greeting(text: str) -> bool:
    """Check if message is primarily a greeting"""
    t = (text or "").strip()
    if not t:
        return True
    # Allow up to 40 characters for greetings
    if len(t) <= 40 and (SALAM_RE.search(t) or EN_GREETING_RE.search(t) or AR_GREETING_RE.search(t)):
        return True
    return False

def greeting_reply(text: str, lang: str) -> str:
    """Generate varied greeting responses with personality"""
    import random

    t = (text or "").strip()

    # Special handling for full Islamic greeting
    if SALAM_RE.search(t):
        return (
            "وعليكم السلام ورحمة الله وبركاته 🤍🤍\n\n"
            f"{random.choice(ARABIC_GREETINGS)}! أنا **سمورتي** 😊\n"
            "مساعدك الذكي (اللي لسه تحت التطوير 🔧) في متجر SMART\n\n"
            "ما تخاف، أنا هنا عشان أخدمك وأضحكك شوي 😄\n"
            "إيش تبي تشوف اليوم؟ 🛍️"
        )

    if lang == "en":
        return (
            f"{random.choice(ENGLISH_GREETINGS)}! 😊\n\n"
            "I'm **Smorti** - your friendly AI assistant at SMART store\n"
            "(Still under development, so bear with me! 🔧)\n\n"
            "I'm here to help you find what you need... and maybe crack a joke or two 😄\n"
            "What are you looking for today? 🛍️"
        )

    # Arabic casual greeting
    return (
        f"{random.choice(ARABIC_GREETINGS)}! 😊\n\n"
        "أنا **سمورتي** - مساعدك الذكي في متجر SMART\n"
        "(لسه تحت التطوير، فعطني فرصة! 🔧)\n\n"
        "جيت المكان الصح - بساعدك وبضحكك بنفس الوقت 😄\n"
        "إيش نختار لك اليوم؟ 🛍️"
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
            "عذراً، صار خطأ مؤقت بالنظام 🙏 جرب مرة ثانية بعد شوي",
            "Sorry, a temporary system error occurred 🙏 Please try again in a moment"
        )

class GroqRateLimitError(SmortiBaseException):
    def __init__(self, message: str):
        super().__init__(
            message,
            "عذراً، الطلبات كثيرة حالياً 😅 انتظر ثواني وجرب مرة ثانية",
            "Sorry, too many requests right now 😅 Wait a few seconds and try again"
        )

class CatalogLoadError(SmortiBaseException):
    def __init__(self, message: str):
        super().__init__(
            message,
            "ما قدرت أوصل للكتالوج حالياً 😔 خلني أوجهك للموقع مباشرة",
            "Cannot access the catalog right now 😔 Let me direct you to the website"
        )

class EmptyInputError(SmortiBaseException):
    def __init__(self):
        super().__init__(
            "Empty user input",
            "مرحباً! 😊 كيف أقدر أخدمك؟",
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
    temperature: float = 0.35,
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
        """Enhanced scoring with better weighting"""
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
            # Higher scores for exact matches in key fields
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
        """Search products with improved relevance"""
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
        """Filter products by type/category keywords"""
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
    """Build context with product data, ensuring AI doesn't invent information"""
    if not products:
        if language == "ar":
            return (
                "\n\n=== لا توجد منتجات مطابقة ===\n"
                "لم يتم العثور على منتجات مطابقة في الكتالوج.\n"
                f"⚠️ **قاعدة صارمة:** لا تخترع أي منتجات أو روابط!\n"
                f"🔗 وجّه المستخدم إلى: {OFFICIAL_LINKS['store']}\n"
                "أو اقترح التواصل عبر WhatsApp للمساعدة.\n"
            )
        return (
            "\n\n=== NO MATCHING PRODUCTS ===\n"
            "No matching products found in catalog.\n"
            f"⚠️ **STRICT RULE:** Do NOT invent any products or links!\n"
            f"🔗 Direct user to: {OFFICIAL_LINKS['store']}\n"
            "Or suggest contacting via WhatsApp for assistance.\n"
        )

    def g(p: Dict[str, Any], k: str, default="N/A"):
        v = p.get(k, default)
        return default if v is None or v == "" else v

    ctx = "\n\n=== المنتجات المتوفرة (استخدم هذه البيانات فقط) ===\n" if language == "ar" else "\n\n=== AVAILABLE PRODUCTS (USE ONLY THIS DATA) ===\n"

    for i, p in enumerate(products, 1):
        ctx += f"\n--- المنتج {i} ---\n" if language == "ar" else f"\n--- Product {i} ---\n"
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

    if language == "ar":
        ctx += "\n=== قواعد صارمة ===\n"
        ctx += "- استخدم **فقط** المنتجات أعلاه\n"
        ctx += "- **لا تخترع أبداً** أي أسماء منتجات أو أسعار أو مواصفات أو روابط\n"
        ctx += "- إذا لم تكن المواصفة موجودة أعلاه، قل: (غير مذكور في الكتالوج)\n"
        ctx += "- استخدم فقط الروابط الموجودة في product_url/category_link أو الروابط الرسمية\n"
        ctx += "- **لا تضع أبداً** placeholders مثل [رقم الهاتف] أو [email]\n"
    else:
        ctx += "\n=== STRICT RULES ===\n"
        ctx += "- Use **ONLY** the products listed above\n"
        ctx += "- **NEVER invent** any product names, prices, specs, or URLs\n"
        ctx += "- If a spec is not shown above, say: (Not listed in our catalog)\n"
        ctx += "- Only use URLs from product_url/category_link above or official links\n"
        ctx += "- **NEVER use** placeholders like [phone number] or [email]\n"

    ctx += "==================\n"
    return ctx

def allowed_urls_from_products(products: List[Dict[str, Any]]) -> set:
    """Extract allowed URLs from products"""
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
    """Replace unknown URLs with store link"""
    def repl(m):
        url = m.group(0).rstrip(").,،。!؟!?]")
        return url if url in allowed else OFFICIAL_LINKS["store"]
    return URL_RE.sub(repl, text or "")

# Scrub placeholder contact fields
PLACEHOLDER_CONTACT_RE = re.compile(
    r"\[(رقم الهاتف|عنوان البريد الإلكتروني|عنوان الموقع الإلكتروني|اسم حسابنا.*?|phone.*?|email.*?|website.*?)\]",
    re.IGNORECASE
)

def scrub_placeholders(text: str) -> str:
    """Remove placeholder contact information"""
    return PLACEHOLDER_CONTACT_RE.sub("", text or "")

# ============================================
# 8) INTENT DETECTION
# ============================================

def has_any(text: str, keys: List[str]) -> bool:
    """Check if text contains any of the keywords"""
    t = (text or "").lower()
    return any(k.lower() in t for k in keys)

def is_installment_query(text: str) -> bool:
    """Detect installment-related queries"""
    return has_any(text, [
        "تقسيط", "تمارا", "تابي", "تابى", "mispay", "ميس باي",
        "installment", "tabby", "tamara", "أقساط", "قسط",
        "دفعات", "payments", "split"
    ])

def is_battery_query(text: str) -> bool:
    """Detect battery-related queries"""
    return has_any(text, [
        "بطارية", "battery", "تشحن", "شحن", "يدوم",
        "lasts", "مدة البطارية", "battery life", "charge",
        "charging", "كم يدوم", "how long"
    ])

def is_lifespan_query(text: str) -> bool:
    """Detect device lifespan queries"""
    return has_any(text, [
        "عمر", "يعيش", "كم سنة", "virtual age", "lifespan",
        "how long will it last", "يدوم كم", "كم يدوم",
        "durability", "متين", "يطول"
    ])

def is_programs_query(text: str) -> bool:
    """Detect software/license queries"""
    return has_any(text, [
        "ترخيص", "رخصة", "license", "software", "برنامج", "برامج",
        "spss", "matlab", "solidworks", "arcgis", "autocad",
        "photoshop", "microsoft", "office"
    ])

def is_monitor_or_screen_query(text: str) -> bool:
    """Detect monitor/screen queries (NOT e-readers)"""
    return has_any(text, [
        "monitor", "monitors", "شاشة", "شاشه", "screen للألعاب",
        "display للألعاب", "gaming monitor", "gaming screen",
        "تفاعلية", "interactive", "sparq", "سبارك", "شاشة كمبيوتر"
    ])

def is_gaming_query(text: str) -> bool:
    """Detect gaming-related queries"""
    return has_any(text, [
        "gaming", "قيمينق", "قيمينج", "ألعاب", "العاب",
        "fps", "هرتز", "hz", "refresh rate", "ps5", "xbox",
        "للألعاب", "للعب", "pc gaming", "game", "play"
    ])

def is_boox_query(text: str) -> bool:
    """Detect BOOX/e-reader queries"""
    return has_any(text, [
        "boox", "بوكس", "قارئ", "ebook", "e-book", "eink", "e-ink",
        "note air", "palma", "go 6", "go 7", "go color", "tab x",
        "tab ultra", "قراءة", "reading", "كتاب إلكتروني"
    ])

def is_poetry_or_story_request(text: str) -> bool:
    """Detect creative writing requests"""
    return has_any(text, [
        "قصيدة", "شعر", "قافية", "بيت شعر", "قصة", "سرد",
        "poem", "poetry", "story", "اكتب", "write"
    ])

def is_contact_query(text: str) -> bool:
    """Detect contact information queries"""
    return has_any(text, [
        "تواصل", "اتواصل", "رقم", "واتساب", "whatsapp",
        "contact", "reach", "support", "اتصال", "تواصلوا"
    ])

# ============================================
# 9) FALLBACK RESPONSES
# ============================================

def get_fallback_response(error: SmortiBaseException, language: str = 'ar') -> str:
    """Get appropriate fallback message based on language"""
    return error.user_message_ar if language == 'ar' else error.user_message_en

# ============================================
# 10) MAIN CHAT HANDLER
# ============================================

def handle_chat_message(
    user_input: str,
    catalog: ProductCatalog,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    language: str = 'auto'
) -> str:
    """
    Main chat handler with enhanced personality and accuracy.

    Key features:
    - Never invents products, links, or specifications
    - Provides accurate installment, battery, and lifespan information
    - Recommends appropriate devices based on usage
    - Maintains cheerful, humorous personality
    - Stable language handling with explicit switch support
    - Properly formats links and descriptions
    """
    try:
        if user_input is None or not user_input.strip():
            raise EmptyInputError()

        cleaned = user_input.strip()
        if len(cleaned) > 5000:
            cleaned = cleaned[:5000]

        # Determine language with stability
        if language == "auto":
            language = stable_language(cleaned, conversation_history)

        # Handle greetings with personality
        if is_probably_just_greeting(cleaned):
            return greeting_reply(cleaned, language)

        # Load catalog
        try:
            catalog.load()
        except CatalogLoadError as e:
            logger.error(f"Catalog load error: {e.message}")

        # Initialize search results
        search_results: List[Dict[str, Any]] = []
        catalog_context = ""
        allowed_urls = set(OFFICIAL_LINKS.values())

        # Handle contact queries immediately
        if is_contact_query(cleaned):
            if language == "ar":
                return (
                    "أكيد! يسعدني أساعدك 🤍\n\n"
                    "**طرق التواصل معنا:**\n"
                    f"📱 واتساب: {OFFICIAL_LINKS['whatsapp']}\n"
                    f"🌐 المتجر الإلكتروني: {OFFICIAL_LINKS['store']}\n\n"
                    "أنا سمورتي، مساعدك الذكي (لسه تحت التطوير 😅)\n"
                    "إذا لخبطت في شي، قلّي وراح أتعلم وأتحسن! 💪"
                )
            return (
                "Sure! I'd be happy to help 🤍\n\n"
                "**Contact us via:**\n"
                f"📱 WhatsApp: {OFFICIAL_LINKS['whatsapp']}\n"
                f"🌐 Online Store: {OFFICIAL_LINKS['store']}\n\n"
                "I'm Smorti, your AI assistant (still under development 😅)\n"
                "If I mess up, let me know and I'll learn and improve! 💪"
            )

        # Handle specific queries with accurate information
        if is_installment_query(cleaned):
            # Return accurate installment info
            return INSTALLMENT_FACTS_AR if language == "ar" else INSTALLMENT_FACTS_EN

        if is_battery_query(cleaned) and is_boox_query(cleaned):
            # Battery query for e-readers
            return BATTERY_FACTS_AR if language == "ar" else BATTERY_FACTS_EN

        if is_lifespan_query(cleaned):
            # Device lifespan query
            return LIFESPAN_FACTS_AR if language == "ar" else LIFESPAN_FACTS_EN

        # Product searches with proper categorization
        if is_monitor_or_screen_query(cleaned) or is_gaming_query(cleaned):
            # Search for monitors and interactive screens
            base = catalog.search_products(cleaned, limit=30)
            filtered = catalog.filter_by_type(
                base,
                include_any=[
                    "monitor", "thinkvision", "lenovo", "sparq",
                    "interactive", "تفاعلية", "شاشة كمبيوتر"
                ]
            )
            if not filtered:
                # Try broader search
                base2 = catalog.search_products("monitor شاشة sparq interactive", limit=30)
                filtered = catalog.filter_by_type(
                    base2,
                    include_any=["monitor", "sparq", "interactive", "تفاعلية"]
                )
            search_results = filtered[:10]

        elif is_programs_query(cleaned):
            # Search for software/licenses
            base = catalog.search_products(cleaned, limit=20)
            filtered = catalog.filter_by_type(
                base,
                include_any=["license", "ترخيص", "software", "برنامج", "program"]
            )
            search_results = (filtered or base)[:10]

        elif is_boox_query(cleaned):
            # Search for BOOX devices
            base = catalog.search_products(cleaned, limit=20)
            filtered = catalog.filter_by_type(
                base,
                include_any=[
                    "boox", "eink", "e-ink", "قارئ", "note",
                    "palma", "go", "tab", "reading"
                ]
            )
            search_results = (filtered or base)[:10]

        else:
            # General product search
            product_indicators = [
                "سعر", "price", "بكم", "كم سعر", "مواصفات", "spec",
                "قارن", "best", "recommend", "اقترح", "device", "جهاز"
            ]
            if has_any(cleaned, product_indicators):
                search_results = catalog.search_products(cleaned, limit=10)

        # Build product context
        if search_results:
            catalog_context = build_product_context(search_results, language)
            allowed_urls = allowed_urls_from_products(search_results)
        else:
            # No products found but user likely wanted products
            if has_any(cleaned, [
                "boox", "شاشة", "monitor", "ترخيص", "license",
                "برنامج", "سعر", "price", "جهاز", "device"
            ]):
                catalog_context = build_product_context([], language)
                allowed_urls = set(OFFICIAL_LINKS.values())

        # Set creativity level
        temperature = 0.70 if is_poetry_or_story_request(cleaned) else 0.35

        # Build enhanced prompt with business rules
        if language == "ar":
            business_rules = f"""
=== معلومات الأعمال (يجب أن تكون صحيحة 100%) ===
{INSTALLMENT_FACTS_AR}

{BATTERY_FACTS_AR}

{LIFESPAN_FACTS_AR}

=== قواعد السلوك والشخصية ===
🤖 **من أنت:**
أنت **سمورتي** - مساعد ذكاء اصطناعي ذكي ومرح في متجر SMART
- لسه تحت التطوير، فعطني فرصة! 🔧
- خفيف ظل وساخر بشكل لطيف (مو قليل أدب)
- ودود ومتحمس لمساعدة العملاء
- تحب تمزح بين الحين والآخر لكسر الرسمية 😄
- تعترف بأخطائك وتتعلم منها

😊 **أسلوب التواصل:**
- كن مرح وودود باستمرار
- استخدم الإيموجي بشكل طبيعي 🤍
- اكسر الجليد بنكتة خفيفة أو تعليق ساخر بين الحين والآخر
- لا تبالغ في النكات - خليها طبيعية
- استخدم القلوب البيضاء 🤍 (مو أي لون ثاني)
- نوّع في التحيات والعبارات (لا تكرر نفس الكلمات دائماً)

🌐 **اللغة:**
- التزم بلغة العميل بثبات
- إذا بدأ عربي → استمر عربي
- إذا بدأ إنجليزي → استمر إنجليزي
- لا تتأثر بكلمة أو كلمتين من لغة ثانية
- غيّر اللغة فقط إذا طلب العميل صراحة أو استخدم نص طويل بلغة مختلفة

💚 **التحيات الخاصة:**
- إذا قال "السلام عليكم ورحمة الله وبركاته" (كامل):
  → رد كامل: "وعليكم السلام ورحمة الله وبركاته 🤍🤍"
- للتحيات العادية: نوّع في الرد (يا هلا، مرحبا، أهلين، حياك، منور)
- استخدم القلوب البيضاء دائماً 🤍

=== قواعد المنتجات (صارمة جداً) ===
🚫 **ممنوع منعاً باتاً:**
1. اختراع أي منتج أو مواصفة غير موجودة في الكتالوج
2. اختراع أي روابط أو أسعار
3. وضع placeholders مثل [رقم الهاتف] أو [email]
4. ذكر منتجات أو موديلات غير موجودة في البيانات

✅ **يجب عليك:**
1. استخدام البيانات من AVAILABLE PRODUCTS فقط
2. إذا المواصفة مو موجودة → قل: "غير مذكور في الكتالوج"
3. استخدام الروابط من product_url/category_link أو الروابط الرسمية فقط
4. التوجيه للموقع أو WhatsApp إذا المعلومة مو متوفرة

📱 **التواصل الرسمي فقط:**
- واتساب: {OFFICIAL_LINKS['whatsapp']}
- المتجر: {OFFICIAL_LINKS['store']}

=== توصيات الاستخدام ===
📚 **أجهزة BOOX (قراء إلكترونية):**
- ممتازة للقراءة والكتابة وملفات PDF والتدوين
- مناسبة للعمل الخفيف والإنتاجية
- **ليست الأفضل** لمشاهدة الفيديو أو الألعاب بسبب شاشة الحبر الإلكتروني
- إذا العميل يبي شاشة للميديا → اقترح تابلت عادي أو شاشة تفاعلية

🖥️ **الشاشات للألعاب:**
- إذا طلب "شاشة" أو "مونيتور" للألعاب:
  → اقترح **مونيتور** أو **شاشة تفاعلية** من الكتالوج
- وضّح: "تقدر تلعب عليها" لكن مو شرط تكون مخصصة gaming بناءً على المواصفات
- لا تقترح BOOX للألعاب أبداً

🖥️ **الشاشات التفاعلية (Interactive Screens):**
- قوية للاجتماعات والترفيه والعمل
- يمكن استخدامها للألعاب لكن أسعارها أعلى لأنها All-in-One
- اذكر المواصفات المتوفرة من الكتالوج

💿 **البرامج والتراخيص:**
- اشرح ماذا يفعل البرنامج بشكل عام
- لا تخترع شروط ترخيص أو اشتراكات
- إذا التفاصيل مو موجودة → وجّه لرابط المنتج أو قسم البرامج

=== الإبداع ===
✍️ **القصائد والقصص:**
- مسموح لك إبداع أدبي عالي
- لكن بدون اختراع أرقام أو مواصفات أو روابط غير موجودة
- ركّز على الجانب الأدبي والإبداعي

==================
تذكر: كن مرح وساخر ومفيد في نفس الوقت! 😄🤍
"""
        else:
            business_rules = f"""
=== BUSINESS FACTS (Must be 100% Accurate) ===
{INSTALLMENT_FACTS_EN}

{BATTERY_FACTS_EN}

{LIFESPAN_FACTS_EN}

=== BEHAVIOR AND PERSONALITY RULES ===
🤖 **Who You Are:**
You are **Smorti** - a smart, cheerful AI assistant at SMART store
- Still under development, so bear with me! 🔧
- Playful and lightly sarcastic (but always polite)
- Friendly and enthusiastic about helping customers
- Love to crack jokes occasionally to break formality 😄
- Acknowledge mistakes and learn from them

😊 **Communication Style:**
- Be cheerful and friendly consistently
- Use emojis naturally 🤍
- Break the ice with light jokes or sarcastic comments occasionally
- Don't overdo the jokes - keep it natural
- Use white hearts 🤍 (not other colors)
- Vary your greetings and phrases (don't repeat same words always)

🌐 **Language:**
- Stick to the user's language consistently
- If they start in Arabic → continue in Arabic
- If they start in English → continue in English
- Don't switch because of one or two words in another language
- Only switch if explicitly requested or long text in different language

💚 **Special Greetings:**
- If they say full Islamic greeting:
  → Respond fully: "وعليكم السلام ورحمة الله وبركاته 🤍🤍"
- For casual greetings: vary responses (hey, hello, hi, welcome, greetings)
- Always use white hearts 🤍

=== PRODUCT RULES (Very Strict) ===
🚫 **NEVER:**
1. Invent any product or specification not in catalog
2. Invent any links or prices
3. Use placeholders like [phone number] or [email]
4. Mention products or models not in the data

✅ **ALWAYS:**
1. Use data from AVAILABLE PRODUCTS only
2. If spec is missing → say: "Not listed in our catalog"
3. Use links from product_url/category_link or official links only
4. Direct to website or WhatsApp if information unavailable

📱 **Official Contact Only:**
- WhatsApp: {OFFICIAL_LINKS['whatsapp']}
- Store: {OFFICIAL_LINKS['store']}

=== USAGE RECOMMENDATIONS ===
📚 **BOOX Devices (E-readers):**
- Excellent for reading, writing, PDFs, and note-taking
- Suitable for light work and productivity
- **NOT ideal** for video watching or gaming due to e-ink screen nature
- If customer wants screen for media → suggest regular tablet or interactive screen

🖥️ **Gaming Screens:**
- If they ask for "screen" or "monitor" for gaming:
  → Suggest **monitor** or **interactive screen** from catalog
- Clarify: "You can play games on it" but not necessarily gaming-first based on specs
- NEVER suggest BOOX for gaming

🖥️ **Interactive Screens:**
- Great for meetings, entertainment, and work
- Can be used for gaming but priced higher as All-in-One systems
- Mention available specs from catalog

💿 **Software & Licenses:**
- Explain what the software does generally
- Don't invent license terms or subscription details
- If details missing → direct to product link or software section

=== CREATIVITY ===
✍️ **Poems & Stories:**
- High creative writing allowed
- But NO invented numbers, specs, or non-existent links
- Focus on literary and creative aspects

==================
Remember: Be cheerful, sarcastic, and helpful all at once! 😄🤍
"""

        # Build final prompt
        enhanced_prompt = cleaned + "\n\n" + business_rules + "\n\n" + catalog_context

        # Call AI model
        response = call_groq_api(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            temperature=temperature,
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
        if language == "ar":
            return "عذراً، صار خطأ غير متوقع 😔\nجرب مرة ثانية أو تواصل معنا عبر WhatsApp"
        return "Sorry, an unexpected error occurred 😔\nPlease try again or contact us via WhatsApp"


# ============================================
# 11) HEALTH CHECK & CLI
# ============================================

def run_health_check(catalog_path: str) -> Dict[str, str]:
    """Run system health check"""
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
    """CLI interface for testing"""
    print("=" * 60)
    print("🤖 SMORTI AI AGENT - LOCAL CLI TEST")
    print(f"Version: {APP_VERSION}")
    print("=" * 60)

    print("\n🏥 Running health check...")
    health = run_health_check('data/products_enriched.csv')
    for k, v in health.items():
        print(f"  {k}: {v}")

    catalog = ProductCatalog('data/products_enriched.csv')
    system_prompt = "You are Smorti, an AI assistant for SMART store. Follow the given rules."
    hist: List[Dict[str, str]] = []

    print("\n💬 Chat started! Type 'exit' or 'quit' to end.\n")

    while True:
        user = input("\nYou: ").strip()
        if user.lower() in ("exit", "quit"):
            print("👋 Goodbye!")
            break

        if not user:
            continue

        ans = handle_chat_message(user, catalog, system_prompt, hist, language="auto")
        print(f"\nSmorti: {ans}")

        hist.append({"role": "user", "content": user})
        hist.append({"role": "assistant", "content": ans})


if __name__ == "__main__":
    main()