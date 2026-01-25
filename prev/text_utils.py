# text_utils.py
from __future__ import annotations
import re
from typing import List

_AR_NUM_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def normalize_arabic(s: str) -> str:
    """
    Normalizes Arabic text for matching:
    - unify Alef/Ya/Ta marbuta, remove tatweel/diacritics
    - normalize Arabic digits to Latin
    - collapse whitespace
    """
    if s is None:
        return ""
    s = str(s)

    # Arabic-Indic digits -> Latin
    s = s.translate(_AR_NUM_MAP)

    # Remove tatweel + harakat
    s = re.sub(r"[\u0640\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", s)

    # Normalize common letters
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ئ", "ي")
    s = s.replace("ة", "ه")

    # Collapse spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s

def low(s: str) -> str:
    return normalize_arabic(s).lower().strip()

def tokens(text: str) -> List[str]:
    """
    Tokenize Arabic/English/numbers/dots (good for model names and SKUs).
    """
    t = low(text)
    return re.findall(r"[a-z\u0600-\u06FF0-9.]+", t)
