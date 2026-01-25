from __future__ import annotations

import os
import re
import secrets
from typing import Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq

from core.text import strip_disallowed_links

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY not found. Check your .env file.")

client = Groq(api_key=GROQ_API_KEY)

# If you have a system prompt file, import it. Otherwise keep a safe default.
try:
    from prompts.smorti import SMARTI_SYSTEM_PROMPT
    BRAND_SYSTEM = SMARTI_SYSTEM_PROMPT
except Exception:
    BRAND_SYSTEM = "You are Smorti, a warm helpful store assistant for Smart. Be concise and accurate."

def build_grounding(facts_text: str) -> str:
    """
    This is the SYSTEM message. Put strict rules here.
    """
    return f"""{BRAND_SYSTEM}

STRICT RULES:
- You MUST NOT invent links. Only use links that appear in FACTS below.
- You MUST NOT invent products, prices, specs. Only use provided product facts.
- If user asks about shipping price/ETA: say it appears at checkout (do not invent).
- Be warm and natural, but concise. 1-4 short lines.
- Use 0-2 emojis max.
- Never flip roles (never ask: "how can you help me").
- Arabic user -> Arabic. English user clearly -> English.

FACTS:
{facts_text}
""".strip()


def _clean_output(text: str) -> str:
    if not text:
        return ""
    text = text.replace("**", "").replace("`", "")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out = "\n".join(lines[:6]).strip()
    if out.strip().lower() == "none":
        return ""
    return out


def ai_answer(
    user_text: str,
    grounding: str,
    history: Optional[List[Dict[str, str]]] = None,
    lang: str = "ar",
) -> Dict[str, str]:
    """
    Free AI answer but bounded by grounding.
    """
    t = (user_text or "").strip()
    if not t:
        return {"reply": "", "intent": "other"}

    msgs = [{"role": "system", "content": grounding}]
    if history:
        msgs += history[-10:]
    msgs.append({"role": "user", "content": t})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        temperature=0.55,
        max_tokens=220,
        frequency_penalty=0.35,
    )

    reply = (resp.choices[0].message.content or "").strip()
    reply = _clean_output(reply)
    return {"reply": reply, "intent": "other"}


def ai_rewrite(
    user_text: str,
    deterministic_reply: str,
    grounding: str,
    history: Optional[List[Dict[str, str]]] = None,
    lang: str = "ar",
    last_bot_reply: str = "",
) -> str:
    """
    Rewrites a factual deterministic reply into warm Smorti style without changing facts.
    Includes anti-repeat logic.
    """
    if not deterministic_reply:
        return ""

    variety_tag = f"VAR{secrets.randbelow(10000)}"
    last = (last_bot_reply or "").strip()

    if lang == "en":
        prompt = f"""
Rewrite this reply to sound warm and human (1-3 lines).
Rules:
- Keep same facts/links/prices. Do NOT add new links or claims.
- Avoid repeating the previous bot wording.
- Do NOT include: {variety_tag}

Previous bot reply (avoid repeating):
{last}

Reply to rewrite:
{deterministic_reply}
""".strip()
    else:
        prompt = f"""
أعد صياغة الرد بشكل ودود وطبيعي (1-3 أسطر).
القواعد:
- نفس الحقائق والروابط والأسعار فقط. لا تضف روابط/ادعاءات جديدة.
- لا تكرر نفس صياغة الرد السابق.
- لا تكتب: {variety_tag}

الرد السابق (تجنب تكراره):
{last}

الرد المراد إعادة صياغته:
{deterministic_reply}
""".strip()

    msgs = [{"role": "system", "content": grounding}]
    if history:
        msgs += history[-6:]
    msgs.append({"role": "user", "content": prompt})

    def call(temp: float, freq_pen: float) -> str:
        r = client.chat.completions.create(
            model=MODEL,
            messages=msgs,
            temperature=temp,
            max_tokens=160,
            frequency_penalty=freq_pen,
        )
        out = (r.choices[0].message.content or "").strip()
        out = out.replace(variety_tag, "").strip()
        out = _clean_output(out)
        return out

    out1 = call(temp=0.75, freq_pen=0.55)

    # If repeated, try once again
    if out1 and last and out1.strip().lower() == last.strip().lower():
        msgs.append({"role": "user", "content": "مهم: غير الصياغة تماماً وخله طبيعي."})
        out2 = call(temp=0.95, freq_pen=0.75)
        return out2 or out1

    return out1 or deterministic_reply
