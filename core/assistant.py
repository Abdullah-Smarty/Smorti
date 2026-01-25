from __future__ import annotations

from typing import List, Set, Dict, Optional
import re

from core.state import ChatState
from core.text import detect_lang, strip_disallowed_links, normalize
from core.catalog import load_products, search_products, Product, group_products
from core.ai import ai_answer, ai_rewrite, build_grounding
from core.config import (
    SHOP_URL, CATEGORY_LINKS,
    RETURN_LINK, WARRANTY_LINK,
    JEDDAH_MAP, RIYADH_MAP
)

_PRODUCTS: List[Product] = load_products()


# ----------------------------
# Link allowlist (exact from CSV + official links)
# ----------------------------
def _allowed_links_from_products(products: List[Product]) -> Set[str]:
    allowed = {
        SHOP_URL, RETURN_LINK, WARRANTY_LINK,
        JEDDAH_MAP, RIYADH_MAP,
        *CATEGORY_LINKS.values(),
    }
    for p in products:
        if p.product_url:
            allowed.add(p.product_url.strip())
        if p.category_link:
            allowed.add(p.category_link.strip())
    return allowed

_ALLOWED_LINKS: Set[str] = _allowed_links_from_products(_PRODUCTS)

_ALLOWED_PREFIXES = (
    "https://shop.smart.sa/ar/category/",
    "https://shop.smart.sa/ar/",           # your real products are like /ar/PdWNBoQ
    "https://maps.app.goo.gl/",
)

# ----------------------------
# Intent detectors
# ----------------------------
def _low(t: str) -> str:
    return (t or "").strip().lower()

def _is_salam(t: str) -> bool:
    tl = normalize(t)
    return any(x in tl for x in ["السلام عليكم", "سلام عليكم", "السلام", "سلام"])

def _is_greeting(t: str) -> bool:
    tl = normalize(t)
    return any(x in tl for x in ["هلا", "هلاا", "مرحبا", "اهلا", "أهلا", "اهلين", "هاي", "hello", "hi", "مساء الخير", "صباح الخير", "مساء النور"])

def _is_smalltalk(t: str) -> bool:
    tl = normalize(t)
    return any(x in tl for x in ["كيف الحال", "كيفك", "اخبارك", "شلونك", "كيفك؟", "ايش الاخبار", "كيف حالك"])

def _wants_menu(t: str) -> bool:
    tl = normalize(t)
    keys = [
        "القائمة", "الاقسام", "الأقسام", "ايش عندكم", "وش عندكم",
        "وريني المنتجات", "ابي اشوف المنتجات", "ابي المنتجات",
        "menu", "categories", "what do you have", "show products",
    ]
    return any(k in tl for k in keys)

def _is_shipping_question(t: str) -> bool:
    tl = normalize(t)
    return any(k in tl for k in ["شحن", "توصيل", "يوصل", "مدة الشحن", "كم يوم", "delivery", "shipping"])

def _is_location_question(t: str) -> bool:
    tl = normalize(t)
    return any(k in tl for k in ["وين موقعكم", "موقعكم", "لوكيشن", "عنوان", "فرع", "فروع", "location", "address", "زيارة"])

def _is_warranty_question(t: str) -> bool:
    tl = normalize(t)
    return any(k in tl for k in ["ضمان", "warranty"])

def _is_return_question(t: str) -> bool:
    tl = normalize(t)
    return any(k in tl for k in ["استرجاع", "استبدال", "ارجاع", "سياسة الاسترجاع", "refund", "return"])

def _is_number_choice(t: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}", (t or "").strip()))

def _city_from_text(t: str) -> Optional[str]:
    tl = normalize(t)
    if "جده" in tl or "jeddah" in tl:
        return "jeddah"
    if "الرياض" in tl or "رياض" in tl or "riyadh" in tl:
        return "riyadh"
    return None

def _country_outside_ksa_hint(t: str) -> bool:
    tl = normalize(t)
    return any(k in tl for k in ["قطر", "الكويت", "الامارات", "الإمارات", "البحرين", "عمان", "uae", "qatar", "kuwait", "bahrain", "oman", "الخليج", "الصين", "china"])

def _extract_place_short(t: str) -> Optional[str]:
    s = normalize(t)
    if 1 <= len(s.split()) <= 3:
        return s
    return None

# ----------------------------
# Helpers: product formatting
# ----------------------------
def _product_name(p: Product, lang: str) -> str:
    return p.name_ar if (lang == "ar" and p.name_ar) else (p.name_en or p.name_raw)

def _price_str(p: Product, lang: str) -> str:
    if p.price_sar is None:
        return "السعر غير متوفر" if lang == "ar" else "Price N/A"
    return f"{p.price_sar:.2f} ر.س" if lang == "ar" else f"{p.price_sar:.2f} SAR"

def _safe_url(p: Product) -> str:
    return p.product_url or p.category_link or SHOP_URL

# ----------------------------
# Grounding snippet (FACTS)
# ----------------------------
def _facts_snippet(user_text: str, lang: str, extra_products: Optional[List[Product]] = None) -> str:
    lines: List[str] = []
    # always include truth links
    lines.append(f"Store: {SHOP_URL}")
    lines.append(f"Return policy: {RETURN_LINK}")
    lines.append(f"Warranty policy: {WARRANTY_LINK}")
    lines.append(f"Location Jeddah: {JEDDAH_MAP}")
    lines.append(f"Location Riyadh: {RIYADH_MAP}")
    lines.append("Shipping inside KSA: RedBox / SMSA / Aramex (all cities).")
    lines.append("Shipping outside KSA (including GCC): DHL. Price/ETA shown at checkout; do not invent.")

    # categories
    if lang == "en":
        lines.append("Categories:")
        lines.append(f"- Tablets & eReaders: {CATEGORY_LINKS['tablets_readers']}")
        lines.append(f"- Interactive Screens: {CATEGORY_LINKS['interactive_screens']}")
        lines.append(f"- Computers & Accessories: {CATEGORY_LINKS['computers_accessories']}")
        lines.append(f"- Software: {CATEGORY_LINKS['software']}")
    else:
        lines.append("الأقسام:")
        lines.append(f"- الأجهزة اللوحية وأجهزة القراءة: {CATEGORY_LINKS['tablets_readers']}")
        lines.append(f"- الشاشات التفاعلية: {CATEGORY_LINKS['interactive_screens']}")
        lines.append(f"- الكمبيوتر وملحقاته: {CATEGORY_LINKS['computers_accessories']}")
        lines.append(f"- البرمجيات: {CATEGORY_LINKS['software']}")

    if extra_products:
        lines.append("Catalog matches:")
        for p in extra_products[:10]:
            lines.append(f"- {_product_name(p, lang)} | {_price_str(p, lang)} | {_safe_url(p)}")

    return "\n".join(lines).strip()

# ----------------------------
# Deterministic (must be correct) replies
# ----------------------------
def _factual_menu(lang: str) -> str:
    if lang == "en":
        return (
            "Sure 😊 Here are our categories:\n"
            f"1) Tablets & eReaders: {CATEGORY_LINKS['tablets_readers']}\n"
            f"2) Interactive Screens: {CATEGORY_LINKS['interactive_screens']}\n"
            f"3) Computers & Accessories: {CATEGORY_LINKS['computers_accessories']}\n"
            f"4) Software: {CATEGORY_LINKS['software']}\n"
            "Tell me the category name or number."
        )
    return (
        "أكيد 😊 هذي الأقسام المتوفرة عندنا:\n"
        f"1) الأجهزة اللوحية وأجهزة القراءة: {CATEGORY_LINKS['tablets_readers']}\n"
        f"2) الشاشات التفاعلية: {CATEGORY_LINKS['interactive_screens']}\n"
        f"3) الكمبيوتر وملحقاته: {CATEGORY_LINKS['computers_accessories']}\n"
        f"4) البرمجيات: {CATEGORY_LINKS['software']}\n"
        "اكتب رقم القسم أو اسمه."
    )

def _factual_warranty(lang: str) -> str:
    if lang == "en":
        return (
            "Warranty summary:\n"
            "- New products: 2 years (manufacturing defects).\n"
            "- Used products: 30 days.\n"
            f"Full policy: {WARRANTY_LINK}"
        )
    return (
        "سياسة الضمان باختصار:\n"
        "- الجديد: سنتين على العيوب المصنعية.\n"
        "- المستعمل: 30 يوم.\n"
        f"التفاصيل كاملة: {WARRANTY_LINK}"
    )

def _factual_return(lang: str) -> str:
    if lang == "en":
        return (
            "Return/Exchange summary:\n"
            "- 7 days if unopened in original condition.\n"
            "- Opened items may be treated as used (value may drop 20–30%).\n"
            "- Used products: exchange allowed within 30 days.\n"
            f"Full policy: {RETURN_LINK}"
        )
    return (
        "سياسة الاسترجاع/الاستبدال باختصار:\n"
        "- خلال 7 أيام إذا المنتج غير مفتوح وبحالته الأصلية.\n"
        "- إذا مفتوح: يُعامل كمستعمل وقد ينقص السعر 20–30%.\n"
        "- المستعمل: يسمح بالاستبدال خلال 30 يوم.\n"
        f"التفاصيل كاملة: {RETURN_LINK}"
    )

def _factual_location(text: str, state: ChatState) -> str:
    city = _city_from_text(text)

    if state.awaiting_location_city and city:
        state.awaiting_location_city = False

    if city == "jeddah":
        return f"أكيد 🤍 موقع فرع جدة:\n{JEDDAH_MAP}"
    if city == "riyadh":
        return f"أكيد 🤍 موقع فرع الرياض:\n{RIYADH_MAP}"

    state.awaiting_location_city = True
    return "أكيد 😊 أي فرع تقصد؟ جدة ولا الرياض؟"

def _factual_shipping(text: str, state: ChatState) -> str:
    tl = normalize(text)
    place = None

    if state.awaiting_shipping_place:
        place = tl
        state.awaiting_shipping_place = False
    else:
        place = _extract_place_short(text)

    outside = _country_outside_ksa_hint(text) or (state.shipping_scope == "outside")

    if place:
        if outside:
            if state.lang == "en":
                return f"Yes, we ship to {place}. Outside KSA shipping is via DHL. Price/ETA appear at checkout: {SHOP_URL}"
            return f"نعم، نوصل إلى {place}. خارج السعودية الشحن عبر DHL. السعر ومدة الشحن تظهر عند الدفع: {SHOP_URL}"
        else:
            if state.lang == "en":
                return f"Yes, we deliver to {place} داخل السعودية via RedBox / SMSA / Aramex. Price/ETA appear at checkout: {SHOP_URL}"
            return f"نعم، التوصيل إلى {place} داخل السعودية عبر RedBox / SMSA / Aramex. السعر ومدة الشحن تظهر عند الدفع: {SHOP_URL}"

    state.awaiting_shipping_place = True
    state.shipping_scope = "outside" if outside else "ksa"
    return "أكيد 👍 اكتب المدينة داخل السعودية أو الدولة خارج السعودية وبعطيك التفاصيل." if state.lang == "ar" else "Sure 👍 Tell me the city (inside KSA) or the country (outside KSA)."

# ----------------------------
# Catalog UI (groups -> items -> item)
# ----------------------------
def _render_groups(groups: Dict[str, List[Product]], lang: str) -> str:
    items = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
    lines: List[str] = []
    lines.append("تمام 👌 اختر سلسلة (اكتب رقم):" if lang == "ar" else "Nice 👌 Pick a series (reply with a number):")
    for i, (g, lst) in enumerate(items[:12], start=1):
        lines.append(f"{i}) {g} ({len(lst)} خيارات)" if lang == "ar" else f"{i}) {g} ({len(lst)} options)")
    return "\n".join(lines)

def _render_items(items: List[Product], lang: str) -> str:
    lines: List[str] = []
    lines.append("هذي الخيارات (اكتب رقم المنتج):" if lang == "ar" else "Here are options (reply with a number):")
    for i, p in enumerate(items[:12], start=1):
        lines.append(f"{i}) {_product_name(p, lang)} — {_price_str(p, lang)}")
    return "\n".join(lines)

def _catalog_flow(text: str, state: ChatState) -> Optional[str]:
    if not _is_number_choice(text):
        return None

    n = int(text)

    if state.view_mode == "groups":
        if n < 1 or n > len(state.last_groups):
            return None
        group_name = state.last_groups[n - 1]
        ids = state.last_group_items.get(group_name, [])
        items = [p for p in _PRODUCTS if p.product_id in ids]
        state.view_mode = "items"
        state.last_items = [p.product_id for p in items[:12]]
        return _render_items(items, state.lang)

    if state.view_mode == "items":
        if n < 1 or n > len(state.last_items):
            return None
        pid = state.last_items[n - 1]
        p = next((x for x in _PRODUCTS if x.product_id == pid), None)
        if not p:
            return None

        url = _safe_url(p)
        if state.lang == "en":
            return f"Here you go 😊\n{_product_name(p,'en')}\nPrice: {_price_str(p,'en')}\nLink: {url}\nFor full specs/colors, please check the website."
        return f"تفضل 😊\n{_product_name(p,'ar')}\nالسعر: {_price_str(p,'ar')}\nالرابط: {url}\nللتفاصيل (مواصفات/ألوان) شوف الموقع."

    return None

# ----------------------------
# Main entry
# ----------------------------
def handle_message(user_text: str, state: ChatState) -> str:
    text = (user_text or "").strip()
    if not text:
        return ""

    # reset
    if text.lower() in {"/reset", "reset"}:
        state.reset()
        return "✅ تم تصفير الجلسة."

    # stable language
    state.lang = detect_lang(text, prev_lang=state.lang)

    # 0) greetings/smalltalk FIRST (prevents being stuck in catalog mode)
    if _is_salam(text) or _is_greeting(text) or _is_smalltalk(text):
        base = (
            "وعليكم السلام ورحمة الله وبركاته 😊 أنا سمورتي من سمارت. كيف أقدر أخدمك اليوم؟"
            if (_is_salam(text) and state.lang == "ar")
            else "هلا 😊 أنا سمورتي من سمارت. كيف أقدر أخدمك؟"
            if state.lang == "ar"
            else "Peace be upon you 😊 I’m Smorti from Smart. How can I help today?"
            if _is_salam(text)
            else "Hi 😊 I’m Smorti from Smart. How can I help?"
        )

        facts = _facts_snippet(text, state.lang)
        grounding = build_grounding(facts)

        out = ai_rewrite(text, base, grounding, history=state.history, lang=state.lang, last_bot_reply=state.last_bot_reply)
        out = strip_disallowed_links(out, allowed_exact=_ALLOWED_LINKS, allowed_prefixes=_ALLOWED_PREFIXES) or base

        state.push("user", text)
        state.push("assistant", out)
        state.last_bot_reply = out
        state.view_mode = "none"  # cancel catalog mode on greeting
        return out

    # 1) number selection flow
    picked = _catalog_flow(text, state)
    if picked:
        facts = _facts_snippet(text, state.lang)
        grounding = build_grounding(facts)
        out = ai_rewrite(text, picked, grounding, history=state.history, lang=state.lang, last_bot_reply=state.last_bot_reply)
        out = strip_disallowed_links(out, allowed_exact=_ALLOWED_LINKS, allowed_prefixes=_ALLOWED_PREFIXES) or picked

        state.push("user", text)
        state.push("assistant", out)
        state.last_bot_reply = out
        return out

    # 2) deterministic intents
    factual: Optional[str] = None

    if _is_location_question(text) or state.awaiting_location_city:
        factual = _factual_location(text, state)
        state.last_intent = "location"
        state.view_mode = "none"  # cancel catalog mode

    elif _is_shipping_question(text) or state.awaiting_shipping_place:
        factual = _factual_shipping(text, state)
        state.last_intent = "shipping"
        state.view_mode = "none"

    elif _is_warranty_question(text):
        factual = _factual_warranty(state.lang)
        state.last_intent = "warranty"
        state.view_mode = "none"

    elif _is_return_question(text):
        factual = _factual_return(state.lang)
        state.last_intent = "return"
        state.view_mode = "none"

    elif _wants_menu(text):
        factual = _factual_menu(state.lang)
        state.last_intent = "menu"
        state.view_mode = "none"

    # 3) product search/advisor (ONLY if user is asking about products)
    if factual is None:
        tl = normalize(text)

        # filters to avoid mixing BOOX vs screens
        brand_filter = "boox" if any(k in tl for k in ["boox", "بووكس", "بوكس"]) else None
        category_filter = None
        if any(k in tl for k in ["شاشه", "شاشة", "تفاعليه", "interactive"]):
            category_filter = "interactive_screens"
        if any(k in tl for k in ["برمجيات", "software", "license", "ترخيص"]):
            category_filter = "software"

        # hints for series focus
        series_hint = None
        if any(k in tl for k in ["go", "جو", "قو"]):
            series_hint = "GO"
        if any(k in tl for k in ["palma", "بالما"]):
            series_hint = "Palma"
        if any(k in tl for k in ["note air", "نوت اير", "اير"]):
            series_hint = "Air"

        hits = search_products(text, _PRODUCTS, limit=24, brand_filter=brand_filter, category_filter=category_filter, series_hint=series_hint)

        # If user asked very generally (like "بووكس" / "boox") -> show groups to avoid clutter
        wants_browse = any(k in tl for k in ["بووكس", "boox", "اجهزه", "devices", "products", "منتجات", "وريني", "ابي"])

        if hits and wants_browse:
            groups = group_products(hits, lang=state.lang)
            if len(hits) > 10 and len(groups) > 1:
                items_sorted = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
                state.view_mode = "groups"
                state.last_groups = [g for g, _ in items_sorted[:12]]
                state.last_group_items = {g: [p.product_id for p in lst] for g, lst in items_sorted[:12]}
                factual = _render_groups({g: lst for g, lst in items_sorted[:12]}, state.lang)
            else:
                state.view_mode = "items"
                state.last_items = [p.product_id for p in hits[:12]]
                factual = _render_items(hits[:12], state.lang)

        elif hits:
            # If user asked for a specific product/model -> give best match directly
            p = hits[0]
            url = _safe_url(p)
            if state.lang == "en":
                factual = f"Sure 😊 I found this:\n{_product_name(p,'en')}\nPrice: {_price_str(p,'en')}\nLink: {url}\nFor full specs/colors, please check the website."
            else:
                factual = f"أكيد 😊 لقيت لك هذا:\n{_product_name(p,'ar')}\nالسعر: {_price_str(p,'ar')}\nالرابط: {url}\nللتفاصيل (مواصفات/ألوان) شوف الموقع."
            state.view_mode = "none"

        else:
            factual = (
                f"ما لقيت هذا الاسم بالضبط عندنا 😅\n"
                f"اكتب اسم الموديل بشكل أقرب (عربي أو إنجليزي) أو قل لي تبغى أي قسم.\n"
                f"المتجر: {SHOP_URL}"
            ) if state.lang == "ar" else (
                f"I couldn't find that exact name 😅\n"
                f"Try a closer model name (Arabic or English) or tell me the category.\n"
                f"Store: {SHOP_URL}"
            )
            state.view_mode = "none"

    # 4) AI rewrite for tone (but facts remain)
    facts = _facts_snippet(text, state.lang)
    grounding = build_grounding(facts)

    state.push("user", text)

    out = ai_rewrite(text, factual, grounding, history=state.history, lang=state.lang, last_bot_reply=state.last_bot_reply)
    out = strip_disallowed_links(out, allowed_exact=_ALLOWED_LINKS, allowed_prefixes=_ALLOWED_PREFIXES) or factual

    state.push("assistant", out)
    state.last_bot_reply = out
    return out
