# handlers/ai_style.py
from __future__ import annotations
from typing import Optional, Dict, Any
import json

from core import config
from core.safety import strip_disallowed_links

def build_style_prompt(lang: str, raw_answer: str, user_text: str, bot_name_ar: str, bot_name_en: str) -> str:
    persona_ar = (
        "أنت سمورتي مساعد سمارت. أسلوبك دافئ ولطيف وواضح. "
        "لا تخترع معلومات. لا تذكر أسعار أو سياسات غير مذكورة. "
        "إذا ما كنت متأكد، قل للمستخدم يراجع الموقع."
    )
    persona_en = (
        "You are Smorti, Smart store assistant. Warm, friendly, clear. "
        "Do not invent facts. Do not add new prices or policies. "
        "If unsure, direct the user to the website."
    )

    persona = persona_en if lang == "en" else persona_ar
    bot_name = bot_name_en if lang == "en" else bot_name_ar

    return f"""
{persona}

Rewrite the assistant reply to sound natural and welcoming, with max {config.MAX_EMOJIS} emojis.
IMPORTANT RULES:
- Keep the same meaning and facts.
- Do NOT add any new links. Use only links already present in RAW_ANSWER.
- Do NOT add prices, shipping fees, dates, or policies not in RAW_ANSWER.
- Output must be JSON with keys: text, lang, needs_human.
- lang must be "{lang}".

USER_TEXT:
{user_text}

RAW_ANSWER:
{raw_answer}
""".strip()

def parse_ai_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            return None
        if "text" not in obj or "lang" not in obj:
            return None
        return obj
    except Exception:
        return None

def style_with_ai(
    llm_generate,
    lang: str,
    user_text: str,
    raw_answer: str,
) -> str:
    """
    llm_generate(prompt)->str must be provided by you (Grok/Llama3 wrapper).
    """
    prompt = build_style_prompt(lang, raw_answer, user_text, config.BOT_NAME_AR, config.BOT_NAME_EN)
    out = llm_generate(prompt)

    obj = parse_ai_json(out or "")
    if not obj:
        return raw_answer

    styled = str(obj.get("text", "")).strip()
    if not styled:
        return raw_answer

    # Safety: remove any disallowed links (and if that empties important stuff, fallback)
    cleaned = strip_disallowed_links(styled)
    if cleaned.strip() == "":
        return raw_answer

    return cleaned
