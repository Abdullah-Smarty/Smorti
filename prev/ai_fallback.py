from __future__ import annotations

import os
import re
import csv
import difflib
from typing import Optional, List, Dict, Set, Tuple, Any

from groq import Groq
from dotenv import load_dotenv
from prompts.smorti import SMARTI_SYSTEM_PROMPT

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY not found. Check your .env file.")

client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Official links (truth)
# ----------------------------
SHOP_URL_AR = "https://shop.smart.sa/ar"
RETURN_POLICY_URL = "https://shop.smart.sa/p/OYDNm"
WARRANTY_POLICY_URL = "https://shop.smart.sa/ar/p/ErDop"

JEDDAH_MAP = "https://maps.app.goo.gl/PhENEtgDbGsace158"
RIYADH_MAP = "https://maps.app.goo.gl/Hq7wrDydx3jQN2bE9n"

CATEGORY_URLS = {
    "tablets_reading": "https://shop.smart.sa/ar/category/EdyrGY",
    "interactive_screens": "https://shop.smart.sa/ar/category/YYKKAR",
    "computer_accessories": "https://shop.smart.sa/ar/category/AxRPaD",
    "software": "https://shop.smart.sa/ar/category/QvKYzR",
}

BRAND_SYSTEM = SMARTI_SYSTEM_PROMPT.strip()
PRODUCTS_CSV_PATH = os.getenv("PRODUCTS_CSV_PATH", "data/products_enriched.csv")

# ----------------------------
# URL sanitizer (EXACT allowlist)
# ----------------------------
URL_RE = re.compile(r"https?://[^\s\)\]\}\>,،؛!؟\"']+", re.I)

def _sanitize_links_exact(text: str, allowed_exact: Set[str]) -> str:
    if not text:
        return text

    def repl(m: re.Match) -> str:
        u = m.group(0).strip().rstrip(").,،؛;!؟?\"'")
        return u if u in allowed_exact else ""

    out = URL_RE.sub(repl, text)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out

# ----------------------------
# Normalize + fuzzy helpers
# ----------------------------
def normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه")
    # common boox typo
    t = t.replace("بوكس", "بووكس")
    t = re.sub(r"[^\w\s\.]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_query_hints(q: str) -> str:
    t = normalize(q)
    # بووكس قو -> boox go
    if "بووكس" in t and "قو" in t:
        t = t.replace("قو", "go")
    # لو كتب "جو" بدل Go
    if "بووكس" in t and "جو" in t:
        t = t.replace("جو", "go")
    return t

def detect_lang(user_text: str, current_lang: str = "ar") -> str:
    t = (user_text or "").strip()
    if not t:
        return current_lang
    ar = len(re.findall(r"[\u0600-\u06FF]", t))
    en = len(re.findall(r"[A-Za-z]", t))
    if en >= 10 and en > ar * 2:
        return "en"
    return "ar" if ar > 0 else current_lang

def _clean_output(text: str, max_lines: int = 10) -> str:
    if not text:
        return ""
    text = text.replace("**", "").replace("`", "")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out = "\n".join(lines[:max_lines]).strip()
    if out.strip().lower() == "none":
        return ""
    return out

def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except:
        return None

# ----------------------------
# Product load
# ----------------------------
class Product:
    __slots__ = (
        "name_en","name_ar","brand","category","category_name_ar","category_link",
        "series","price_sar","availability","screen_size_in","display_type",
        "ram_gb","storage_gb","short_desc","keywords","product_url","item_type"
    )
    def __init__(self, r: Dict[str,str]):
        self.name_en = (r.get("name_en") or "").strip()
        self.name_ar = (r.get("name_ar") or "").strip()
        self.brand = (r.get("brand") or "").strip()
        self.category = (r.get("category") or "").strip()
        self.category_name_ar = (r.get("category_name_ar") or "").strip()
        self.category_link = (r.get("category_link") or "").strip()
        self.series = (r.get("series") or "").strip()
        self.price_sar = _to_float(r.get("price_sar") or "")
        self.availability = (r.get("availability") or "").strip()  # might be empty
        self.screen_size_in = _to_float(r.get("screen_size_in") or "")
        self.display_type = (r.get("display_type") or "").strip()
        self.ram_gb = _to_float(r.get("ram_gb") or "")
        self.storage_gb = _to_float(r.get("storage_gb") or "")
        self.short_desc = (r.get("short_desc") or "").strip()
        self.keywords = (r.get("keywords") or "").strip()
        self.product_url = (r.get("product_url") or "").strip()
        self.item_type = (r.get("item_type") or "").strip()

    def best_name(self) -> str:
        return self.name_ar or self.name_en

def load_products(csv_path: str) -> List[Product]:
    if not os.path.exists(csv_path):
        return []
    items: List[Product] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            items.append(Product(r))
    return items

def build_allowed_links(products: List[Product]) -> Set[str]:
    allowed = {
        SHOP_URL_AR, RETURN_POLICY_URL, WARRANTY_POLICY_URL,
        JEDDAH_MAP, RIYADH_MAP,
        *CATEGORY_URLS.values(),
    }
    for p in products:
        if p.product_url.startswith("https://shop.smart.sa/"):
            allowed.add(p.product_url)
        if p.category_link.startswith("https://shop.smart.sa/"):
            allowed.add(p.category_link)
    return allowed

# ----------------------------
# Intent helpers
# ----------------------------
def wants_products(text: str) -> bool:
    t = normalize(text)
    keys = ["وريني", "اعطني", "المنتجات", "ايش عندكم", "ابغا اشوف", "ابرز المنتجات", "products", "show"]
    return any(k in t for k in map(normalize, keys))

def wants_tablets(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["اجهزه لوحيه", "اجهزة لوحية", "اجهزة القراءه", "قراءه", "ereader", "tablet"])

def wants_shipping(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["شحن", "توصيل", "shipping", "delivery", "يوصل", "مدة"])

def wants_location(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["موقع", "عنوان", "وين", "location", "address", "فرع"])

def wants_warranty(text: str) -> bool:
    t = normalize(text)
    return "ضمان" in t or "warranty" in t

def wants_return(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["استرجاع", "استبدال", "ارجاع", "refund", "return"])

def is_yes(text: str) -> bool:
    t = normalize(text)
    return t in {"ايه","ايوه","نعم","تمام","ok","okay","yep","yes","ابشر"} or t.startswith("اي") or t == "يس"

def is_boox_intent(text: str) -> bool:
    t = normalize(text)
    return ("boox" in t) or ("بووكس" in t)

def is_interactive_intent(text: str) -> bool:
    t = normalize(text)
    keys = ["شاشه", "شاشة", "تفاعليه", "تفاعلية", "sparq", "ideahub", "maxhub", "سبارك"]
    return any(normalize(k) in t for k in keys)

# ----------------------------
# Series / similarity resolution
# ----------------------------
SERIES_HINTS = {
    "go": ["go", "قو", "جو"],
    "palma": ["palma", "بالما", "بالمه"],
    "note air": ["note air", "نوت اير", "نوت اير", "اير"],
    "note": ["note", "نوت"],
    "tab": ["tab", "تاب"],
    "page": ["page", "بيج", "صفحه"],
    "poke": ["poke", "بوك"],
    "mira": ["mira", "ميرا"],
    "max": ["max", "ماكس"],
}

def extract_series_hint(text: str) -> Optional[str]:
    t = normalize_query_hints(text)
    for series, keys in SERIES_HINTS.items():
        for k in keys:
            if normalize(k) in t:
                return series
    return None

def score_product(q_norm: str, p: Product) -> float:
    hay = " ".join([
        normalize(p.name_en), normalize(p.name_ar),
        normalize(p.series), normalize(p.keywords),
        normalize(p.short_desc),
    ]).strip()

    if not hay:
        return 0.0

    if q_norm and q_norm in hay:
        return 1.0

    qt = set(q_norm.split())
    ht = set(hay.split())
    overlap = len(qt & ht) / max(1, len(qt))

    sim = difflib.SequenceMatcher(None, q_norm, hay).ratio()
    return 0.60 * sim + 0.40 * overlap

def search_products(query: str, products: List[Product], limit: int = 5) -> List[Product]:
    q = normalize_query_hints(query)
    series_hint = extract_series_hint(query)

    pool = products
    if series_hint:
        # filter by series/name if possible
        series_norm = normalize(series_hint)
        filtered = []
        for p in products:
            hay = " ".join([normalize(p.series), normalize(p.name_en), normalize(p.name_ar)])
            if series_norm in hay:
                filtered.append(p)
        if filtered:
            pool = filtered

    scored: List[Tuple[float, Product]] = []
    for p in pool:
        s = score_product(q, p)
        if s >= 0.28:
            scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]

# ----------------------------
# Advisor flow (asks smart questions)
# ----------------------------
def advisor_next_question(slots: Dict[str, Any]) -> Optional[str]:
    # Ask 1 question at a time (simple & natural)
    if not slots.get("use_case"):
        return "حلو 👌 بتستخدمه أكثر لـ: قراءة فقط؟ ولا قراءة + ملاحظات/كتابة؟"
    if slots.get("display_pref") is None:
        return "تمام 😊 تفضل أي نوع شاشة؟ حبر إلكتروني أبيض وأسود (مريح للقراءة) ولا حبر ملون؟"
    if slots.get("screen_size") is None:
        return "كم تفضّل حجم الشاشة تقريباً؟ (مثلاً 6 / 7.8 / 10.3 / 13.3)"
    if slots.get("budget") is None:
        return "آخر سؤال 🤝 كم ميزانيتك تقريباً بالسعر؟ (مثلاً 1500 / 2500)"
    return None

def filter_by_slots(products: List[Product], slots: Dict[str, Any]) -> List[Product]:
    out = products

    # display preference
    pref = slots.get("display_pref")  # "mono" | "color" | None
    if pref in {"mono","color"}:
        tmp = []
        for p in out:
            dt = normalize(p.display_type or p.keywords or p.short_desc)
            if pref == "mono":
                if any(k in dt for k in ["mono", "monochrome", "ابيض", "اسود", "حبر اسود", "black and white"]):
                    tmp.append(p)
            else:
                if any(k in dt for k in ["color", "ملون", "كليدو", "kaleido"]):
                    tmp.append(p)
        if tmp:
            out = tmp

    # screen size (approx)
    sz = slots.get("screen_size")
    if isinstance(sz, (int, float)):
        tmp = []
        for p in out:
            if p.screen_size_in is None:
                continue
            if abs(p.screen_size_in - float(sz)) <= 0.6:
                tmp.append(p)
        if tmp:
            out = tmp

    # budget cap
    b = slots.get("budget")
    if isinstance(b, (int, float)):
        tmp = [p for p in out if (p.price_sar is not None and p.price_sar <= float(b))]
        if tmp:
            out = tmp

    return out

def render_product_options(products: List[Product], category_link_fallback: str) -> str:
    if not products:
        return f"ما لقيت خيارات مطابقة 100% 👀 تقدر تتصفح القسم هنا: {category_link_fallback}"

    lines = ["تمام 😊 هذي أفضل خيارات على طلبك:"]
    for i, p in enumerate(products[:3], start=1):
        price = f"{p.price_sar:.2f} SAR" if p.price_sar is not None else "السعر بالموقع"
        link = p.product_url or p.category_link or category_link_fallback
        lines.append(f"{i}) {p.best_name()} — {price}\n{link}")
    lines.append("تبغى أشرح لك فرقهم بسرعة؟ أو تختار رقم؟")
    return "\n".join(lines)

# ----------------------------
# Facts block + system prompt
# ----------------------------
def _facts_block(lang: str) -> str:
    if lang == "en":
        return f"""
FACTS:
- Store: {SHOP_URL_AR}
- Return: {RETURN_POLICY_URL}
- Warranty: {WARRANTY_POLICY_URL}
- Locations: Jeddah {JEDDAH_MAP} | Riyadh {RIYADH_MAP}
- Shipping: Saudi (RedBox/SMSA/Aramex). Outside Saudi incl. GCC (DHL). Prices shown at checkout only.
- Product links MUST be exact from dataset.
""".strip()
    return f"""
حقائق:
- المتجر: {SHOP_URL_AR}
- الاسترجاع: {RETURN_POLICY_URL}
- الضمان: {WARRANTY_POLICY_URL}
- المواقع: جدة {JEDDAH_MAP} | الرياض {RIYADH_MAP}
- الشحن: داخل السعودية (RedBox/SMSA/Aramex) وخارجها (DHL). الأسعار تظهر عند الدفع فقط.
- روابط المنتجات لازم تكون من الداتا فقط (روابط دقيقة).
""".strip()

def _merge_system(lang: str, products_brief: Optional[str]) -> str:
    style_ar = """
أنت "سمورتي" مساعد متجر سمارت.
الأسلوب: شبابي، لطيف، طبيعي، بشوش 😄 (إيموجيز خفيفة).
ممنوع تقول كلام غريب مثل "لوحة لوحية بالألوان" — استخدم: "شاشة حبر إلكتروني ملونة" أو "أبيض وأسود".
ممنوع ذكر iOS أو مواصفات غير موجودة في الداتا.
لا تضف روابط إلا إذا كانت من الحقائق أو من الداتا.
ممنوع Markdown.
""".strip()

    style_en = """
You are "Smorti", Smart store assistant.
Tone: warm, casual, friendly (light emojis).
Never invent specs/OS/colors/links.
No markdown.
""".strip()

    style = style_en if lang == "en" else style_ar
    ref = f"\n\nPRODUCTS REFERENCE:\n{products_brief.strip()}" if products_brief else ""
    return f"{BRAND_SYSTEM}\n\n{_facts_block(lang)}{ref}\n\n{style}"

# ----------------------------
# Deterministic draft reply (truth)
# ----------------------------
def build_draft_reply(user_text: str, products: List[Product], state: Any = None) -> str:
    t = (user_text or "").strip()

    # Initialize state buckets if available
    if state is not None:
        if getattr(state, "advisor_slots", None) is None:
            state.advisor_slots = {}
        if getattr(state, "last_results_urls", None) is None:
            state.last_results_urls = []
        if getattr(state, "last_selected_url", None) is None:
            state.last_selected_url = None
        if getattr(state, "awaiting_advisor_question", None) is None:
            state.awaiting_advisor_question = False

    # Warranty / Return (always provide link)
    if wants_warranty(t):
        return (
            "أكيد يا بعدي 🤍\n"
            "الجديد: ضمان سنتين على العيوب المصنعية.\n"
            "المستعمل: 30 يوم.\n"
            f"التفاصيل هنا: {WARRANTY_POLICY_URL}"
        )

    if wants_return(t):
        return (
            "أكيد 🤍\n"
            "استرجاع/استبدال خلال 7 أيام إذا المنتج غير مفتوح وبحالته.\n"
            "لو تم فتحه يُعامل كمستعمل وقد ينخفض سعره حسب الحالة.\n"
            f"التفاصيل هنا: {RETURN_POLICY_URL}"
        )

    # Shipping (always include shop link)
    if wants_shipping(t):
        return (
            "أكيد ✅\n"
            "داخل السعودية: RedBox / SMSA / Aramex.\n"
            "وخارج السعودية (ومنها الخليج): DHL.\n"
            f"سعر ومدة الشحن تظهر عند الدفع: {SHOP_URL_AR}"
        )

    # Location
    if wants_location(t):
        low = normalize(t)
        if "جده" in low or "jeddah" in low:
            return f"تنورنا 🤍 موقع فرع جدة:\n{JEDDAH_MAP}"
        if "رياض" in low or "riyadh" in low:
            return f"حياك 🤍 موقع فرع الرياض:\n{RIYADH_MAP}"
        return "أكيد 😊 أي فرع تقصد؟ جدة ولا الرياض؟"

    # Products overview (no clutter)
    if wants_products(t):
        return (
            "حياك 😄 عندنا 4 أقسام رئيسية:\n"
            f"1) الأجهزة اللوحية وأجهزة القراءة: {CATEGORY_URLS['tablets_reading']}\n"
            f"2) الشاشات التفاعلية: {CATEGORY_URLS['interactive_screens']}\n"
            f"3) الكمبيوتر وملحقاته: {CATEGORY_URLS['computer_accessories']}\n"
            f"4) البرمجيات: {CATEGORY_URLS['software']}\n"
            "قلّي وش ناوي عليه وبأقترح لك خيارات مناسبة."
        )

    # If user says "ابغى جهاز" -> advisor starts (tablets by default if boox)
    if any(k in normalize(t) for k in ["ابغى جهاز", "ابي جهاز", "احتاج جهاز", "ابي قارئ", "قارئ", "eink", "بووكس"]):
        if state is not None:
            state.awaiting_advisor_question = True
        # set a default category preference
        cat_link = CATEGORY_URLS["tablets_reading"]
        return (
            "تمام يا بطل 😄 عشان أطلع لك أفضل خيار…\n"
            "بستخدمه أكثر لـ: قراءة فقط؟ ولا قراءة + ملاحظات/كتابة؟"
        )

    # Advisor: capture answers if we're in advisor mode
    if state is not None and getattr(state, "awaiting_advisor_question", False):
        slots = state.advisor_slots or {}

        # crude capture rules (you can expand)
        nt = normalize_query_hints(t)

        if not slots.get("use_case"):
            if any(x in nt for x in ["كتابه", "ملاحظات", "تدوين"]):
                slots["use_case"] = "notes"
            elif "قراءه" in nt or "قراءة" in (t or ""):
                slots["use_case"] = "read"
            else:
                # keep generic
                slots["use_case"] = "general"
            state.advisor_slots = slots
            q = advisor_next_question(slots)
            return q or "تمام 👍"

        if slots.get("display_pref") is None:
            if any(x in nt for x in ["ملون", "color", "كليدو", "kaleido"]):
                slots["display_pref"] = "color"
            elif any(x in nt for x in ["ابيض", "اسود", "أبيض", "أسود", "mono", "monochrome"]):
                slots["display_pref"] = "mono"
            else:
                slots["display_pref"] = "mono"  # default safe for reading
            state.advisor_slots = slots
            q = advisor_next_question(slots)
            return q or "تمام 👍"

        if slots.get("screen_size") is None:
            m = re.search(r"(\d{1,2}(?:\.\d)?)", nt)
            if m:
                slots["screen_size"] = float(m.group(1))
            else:
                slots["screen_size"] = None
            state.advisor_slots = slots
            q = advisor_next_question(slots)
            return q or "تمام 👍"

        if slots.get("budget") is None:
            m = re.search(r"(\d{3,5})", nt)
            if m:
                slots["budget"] = float(m.group(1))
            else:
                slots["budget"] = None
            state.advisor_slots = slots

            # now recommend
            pool = [p for p in products if (p.category_link == CATEGORY_URLS["tablets_reading"])]
            pool = filter_by_slots(pool, slots)
            # sort by price asc
            pool.sort(key=lambda x: (x.price_sar if x.price_sar is not None else 10**9))
            # record urls
            state.last_results_urls = [p.product_url for p in pool[:3] if p.product_url]
            state.last_selected_url = state.last_results_urls[0] if state.last_results_urls else None
            state.awaiting_advisor_question = False
            return render_product_options(pool, CATEGORY_URLS["tablets_reading"])

    # If user says yes after we showed options -> explain differences or show details of last selected
    if state is not None and is_yes(t) and getattr(state, "last_selected_url", None):
        url = state.last_selected_url
        p = next((x for x in products if x.product_url == url), None)
        if p:
            price = f"{p.price_sar:.2f} SAR" if p.price_sar is not None else "السعر بالموقع"
            # only say fields we have (no hallucination)
            parts = [f"{p.best_name()}", f"السعر: {price}"]
            if p.screen_size_in is not None:
                parts.append(f"الشاشة: {p.screen_size_in:g} بوصة")
            if p.ram_gb is not None or p.storage_gb is not None:
                rg = f"{int(p.ram_gb)}GB" if p.ram_gb is not None else ""
                sg = f"{int(p.storage_gb)}GB" if p.storage_gb is not None else ""
                if rg or sg:
                    parts.append(f"الذاكرة: {rg} / التخزين: {sg}".strip(" /"))
            parts.append(f"الرابط: {p.product_url}")
            parts.append("إذا تبغى تفاصيل أكثر (ألوان/نسخ) الأفضل تفتح صفحة المنتج 👌")
            return "\n".join(parts)

    # BOOX series (بووكس قو بدون رقم)
    if is_boox_intent(t) and not is_interactive_intent(t):
        series_hint = extract_series_hint(t)
        if series_hint:
            matches = search_products(t, products, limit=8)
            if state is not None:
                state.last_results_urls = [p.product_url for p in matches if p.product_url]
                state.last_selected_url = state.last_results_urls[0] if state.last_results_urls else None
            return render_product_options(matches, CATEGORY_URLS["tablets_reading"])
        # general boox -> guide to correct category + ask what they want
        return (
            "تمام 😄 أجهزة BOOX عندنا هنا:\n"
            f"{CATEGORY_URLS['tablets_reading']}\n"
            "تدور على أي سلسلة؟ (Go / Palma / Note Air / Note Max) 😉"
        )

    # Direct product lookup (Arabic/English)
    matches = search_products(t, products, limit=5)
    if matches:
        p = matches[0]
        if state is not None:
            state.last_results_urls = [x.product_url for x in matches if x.product_url]
            state.last_selected_url = p.product_url or None
        price = f"{p.price_sar:.2f} SAR" if p.price_sar is not None else "السعر بالموقع"
        link = p.product_url or p.category_link or SHOP_URL_AR
        return (
            "لقيته لك 👌\n"
            f"{p.best_name()}\n"
            f"السعر: {price}\n"
            f"الرابط: {link}\n"
            "تبغاني أطلع لك بدائل مشابهة بعد؟"
        )

    # Fallback
    return f"حياك 😊 اكتب اسم الموديل أو قلّي وش استخدامك، وبمشي معك خطوة خطوة. (المتجر: {SHOP_URL_AR})"

# ----------------------------
# Public API
# ----------------------------
def ai_reply(
    user_text: str,
    products_brief: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    current_lang: str = "ar",
    state: Any = None,
) -> str:
    t = (user_text or "").strip()
    lang = detect_lang(t, current_lang=current_lang)

    products = load_products(PRODUCTS_CSV_PATH)
    allowed_links = build_allowed_links(products)

    draft = build_draft_reply(t, products, state=state)

    system = _merge_system(lang, products_brief)

    prompt = f"""
أعد صياغة الرد التالي بصياغة سمورتي:
- أسلوب شبابي بسيط ومباشر 😄 (إيموجيز خفيفة)
- لا تغيّر المعنى ولا تضف مواصفات/أسعار/روابط جديدة
- لا تخترع منتجات أو أقسام
- لا تستخدم Markdown
الرد:
{draft}
""".strip() if lang == "ar" else f"""
Rewrite the reply in a friendly, casual tone (light emojis).
Do NOT add or change facts/specs/prices/links.
No markdown.
Reply:
{draft}
""".strip()

    msgs = [{"role": "system", "content": system}]
    if history:
        msgs += history[-6:]
    msgs.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        temperature=0.25,
        max_tokens=170,
    )

    out = (resp.choices[0].message.content or "").strip()
    out = _clean_output(out, max_lines=12)
    out = _sanitize_links_exact(out, allowed_links)

    return out or _sanitize_links_exact(draft, allowed_links) or ("Hi! How can I help?" if lang == "en" else "ياهلا 😄 كيف أقدر أخدمك؟")
