# handlers/router.py
from __future__ import annotations
from typing import Callable, Optional

from core.state import ChatState
from core import config
from core.lang import detect_lang, is_salam_ar, is_salam_en, wants_human, normalize_basic
from core.safety import safe_unknown

from handlers.location import try_answer as location_try
from handlers.shipping import try_answer as shipping_try
from handlers.policies import returns_summary, warranty_summary
from handlers.ai_style import style_with_ai

# You will keep using your existing pipeline/menu/catalog_flow for catalog browsing:
# from handlers.pipeline import pipeline_reply  # if you prefer
# OR call your deterministic catalog route here

def greet(lang: str) -> str:
    if lang == "en":
        return (
            "Peace be upon you, and welcome 🤍\n"
            f"I’m {config.BOT_NAME_EN}, your Smart store assistant 😊\n"
            "How can I help today?"
        )
    return (
        "وعليكم السلام ورحمة الله وبركاته 🤍\n"
        f"حيّاك الله في سمارت! أنا {config.BOT_NAME_AR} مساعدك اليوم 😊\n"
        "كيف أقدر أخدمك؟"
    )

def route(
    user_text: str,
    state: ChatState,
    llm_generate: Optional[Callable[[str], str]] = None,
    ai_style_enabled: bool = True,
) -> str:
    t = (user_text or "").strip()
    if not t:
        return ""

    # update language (do not suddenly switch on product names)
    state.lang = detect_lang(t, state.lang)

    # Salam
    if state.lang == "ar" and is_salam_ar(t):
        raw = greet("ar")
        return style_with_ai(llm_generate, "ar", t, raw) if (ai_style_enabled and llm_generate) else raw

    if state.lang == "en" and is_salam_en(t):
        raw = greet("en")
        return style_with_ai(llm_generate, "en", t, raw) if (ai_style_enabled and llm_generate) else raw

    # Human handoff intent
    if wants_human(t):
        state.need_human = True
        raw = (
            f"أكيد 🤍 تم تحويل طلبك لموظف خدمة العملاء.\n"
            f"إذا تحب، تقدر تتواصل مباشرة عبر واتساب: {config.WHATSAPP_URL}\n"
            f"أو الإيميل: {config.EMAIL}"
        ) if state.lang == "ar" else (
            f"Sure 🤍 I’ll route you to a human agent.\n"
            f"WhatsApp: {config.WHATSAPP_URL}\n"
            f"Email: {config.EMAIL}"
        )
        return raw  # don’t AI-style handoff

    tl = normalize_basic(t)

    # Policies intent (simple keywords)
    if any(k in tl for k in ["استرجاع", "استبدال", "return policy", "returns", "refund"]):
        raw = returns_summary(state.lang)
        return style_with_ai(llm_generate, state.lang, t, raw) if (ai_style_enabled and llm_generate) else raw

    if any(k in tl for k in ["ضمان", "warranty"]):
        raw = warranty_summary(state.lang)
        return style_with_ai(llm_generate, state.lang, t, raw) if (ai_style_enabled and llm_generate) else raw

    # Location / Shipping
    raw = location_try(t, state)
    if raw:
        return style_with_ai(llm_generate, state.lang, t, raw) if (ai_style_enabled and llm_generate) else raw

    raw = shipping_try(t, state)
    if raw:
        return style_with_ai(llm_generate, state.lang, t, raw) if (ai_style_enabled and llm_generate) else raw

    # TODO: plug your deterministic catalog/menu pipeline here
    # raw = pipeline_reply(t, state, direct_ai=True)
    # if raw:
    #     return style_with_ai(llm_generate, state.lang, t, raw) if (ai_style_enabled and llm_generate) else raw

    # Safe unknown
    raw = safe_unknown(state.lang)
    return style_with_ai(llm_generate, state.lang, t, raw) if (ai_style_enabled and llm_generate) else raw
