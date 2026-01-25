from __future__ import annotations

import re
from typing import Iterable, Optional, Set

# --- Basic normalize (Arabic-friendly) ---
def normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def detect_lang(user_text: str, prev_lang: str = "ar") -> str:
    """
    Stable language detection:
    - Switch to English only if message is clearly English.
    - Do NOT switch because a device name is English.
    """
    t = (user_text or "").strip()
    if not t:
        return prev_lang

    ar = len(re.findall(r"[\u0600-\u06FF]", t))
    en = len(re.findall(r"[A-Za-z]", t))

    if en >= 8 and en > ar * 2:
        return "en"
    if ar > 0:
        return "ar"
    return prev_lang


# --- Link stripping (no hallucinated links) ---
URL_RE = re.compile(r"https?://[^\s\)\]\}\>,،؛!؟\"']+", re.I)

def strip_disallowed_links(
    text: str,
    allowed_exact: Optional[Set[str]] = None,
    allowed_prefixes: Iterable[str] = (),
) -> str:
    if not text:
        return ""

    allowed_exact = allowed_exact or set()
    prefixes = tuple(allowed_prefixes or ())

    def is_allowed(u: str) -> bool:
        u = u.strip().rstrip(").,،؛;!؟?\"'")
        if u in allowed_exact:
            return True
        return any(u.startswith(p) for p in prefixes)

    def repl(m: re.Match) -> str:
        u = m.group(0)
        return u if is_allowed(u) else ""

    out = URL_RE.sub(repl, text)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    # don't return literal None
    if out.strip().lower() == "none":
        return ""
    return out


# --- Optional: if you need bidi fix in CLI, keep it simple ---
def bidi_fix(s: str) -> str:
    return s or ""
