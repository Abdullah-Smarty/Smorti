from __future__ import annotations
from typing import Optional
from core.state import ChatState
from core.config import SHOP_URL  # ✅ مهم


def try_answer(text: str, state: ChatState) -> Optional[str]:
    t = (text or "").strip().lower()
    if "المتجر" in t or "رابط" in t or "shop" in t:
        return f"هذا رابط متجرنا 🛒 {SHOP_URL}"
    return None
