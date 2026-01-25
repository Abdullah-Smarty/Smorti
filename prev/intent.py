# intent.py
from __future__ import annotations

import re
from text_utils import normalize_arabic

# Robust Arabic/English price intent (handles punctuation مثل ؟)
PRICE_PATTERNS = [
    r"(^|[\s\W])سعر(ه)?([\s\W]|$)",
    r"(^|[\s\W])السعر([\s\W]|$)",
    r"(^|[\s\W])بكم([\s\W]|$)",
    r"(^|[\s\W])كم([\s\W]|$)",          # كم؟ alone
    r"كم.*سعر",
    r"كم.*يكلف",
    r"كم.*ثمن",
    r"\bprice\b",
    r"\bcost\b",
    r"how\s*much",
]

def is_price_question(text: str) -> bool:
    t = normalize_arabic(text)
    return any(re.search(p, t, flags=re.IGNORECASE) for p in PRICE_PATTERNS)
