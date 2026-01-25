# rules.py
from __future__ import annotations

from intent import is_price_question
from text_utils import tokens

# كلمات عامة ما تعتبر "منتج"
_GENERIC_WORDS = {
    "منتج", "المنتج", "جهاز", "الجهاز", "موديل", "الموديل",
    "نوع", "النوع", "شي", "شيء", "هذا", "هاذا",
}

# كلمات فئات نسمح لها تعتبر “تلميح منتج”
_CATEGORY_HINTS = {
    "كفر", "حافظة", "حافظه", "جراب", "case", "cover",
    "كيبورد", "لوحة", "لوحه", "مفاتيح", "keyboard",
    "شاشة", "شاشه", "مونيتور", "screen", "monitor", "interactive",
    "سماعة", "سماعه", "هيدسيت", "headset",
    "باور", "باوربانك", "شاحن", "magsafe", "power", "bank",
    "dock", "docking", "هاب", "hub",
}

def _generic_price_welcome() -> str:
    # سمورتي ستايل (خفيف ومباشر)
    return (
        "تمام 👌 عشان أعطيك سعر دقيق:\n"
        "اكتب اسم الجهاز/الموديل (أو ارسل صورة) وبعطيك السعر والتوفر 👍"
    )

def _has_category_hint(toks: list[str]) -> bool:
    return any(t in _CATEGORY_HINTS for t in toks)

def _has_product_hint(toks: list[str]) -> bool:
    """
    أي كلمة “مفيدة” غير كلمات عامة تعتبر تلميح منتج/موديل.
    """
    meaningful = [
        t for t in toks
        if t not in _GENERIC_WORDS and len(t) >= 2
    ]
    return len(meaningful) > 0

def rule_based_reply(user_text: str) -> str | None:
    toks = tokens(user_text)

    # سؤال سعر عام بدون موديل/فئة
    if is_price_question(user_text) and not _has_product_hint(toks) and not _has_category_hint(toks):
        return _generic_price_welcome()

    return None
