# faq_engine.py
import re
import pandas as pd
from rapidfuzz import fuzz

from text_utils import normalize_arabic
from intent import is_price_question

FAQ_FILE = "faqs.csv"
SIMILARITY_THRESHOLD = 85  # raise to reduce wrong matches

PRICE_A_PATTERNS = [
    r"\bريال\b",
    r"\bرس\b",
    r"\bSAR\b",
    r"\d",
    r"\bبعد الخصم\b",
]

CLARIFY_PATTERNS = [
    r"\bاي\b.*\bموديل\b",
    r"\bاي\b.*\bجهاز\b",
    r"\bوش\b.*\bالموديل\b",
    r"\bحدد\b.*\bالموديل\b",
    r"\bارسل\b.*\bاسم\b",
    r"\bارسل\b.*\bصوره\b",
]

def is_safe_price_answer(answer: str) -> bool:
    a = normalize_arabic(answer)
    if any(re.search(p, a) for p in PRICE_A_PATTERNS):
        return True
    if any(re.search(p, a) for p in CLARIFY_PATTERNS):
        return True
    return False

faq_df = pd.read_csv(FAQ_FILE)
faq_df["q_norm"] = faq_df["question"].apply(normalize_arabic)

def get_faq_answer(user_text: str):
    user_norm = normalize_arabic(user_text)
    price_q = is_price_question(user_text)

    best_score = 0
    best_answer = None

    for _, row in faq_df.iterrows():
        score = fuzz.partial_ratio(user_norm, row["q_norm"])
        if score > best_score:
            if price_q and not is_safe_price_answer(str(row["answer"])):
                continue
            best_score = score
            best_answer = row["answer"]

    if best_score >= SIMILARITY_THRESHOLD:
        print(f"📌 FAQ matched with score: {best_score}")
        return best_answer

    return None
