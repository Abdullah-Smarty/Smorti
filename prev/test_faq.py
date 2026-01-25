from faq_engine import get_faq_answer

tests = [
    "كم سعر المنتج؟",
    "بكم المنتج",
    "سعره كم",
    "كم سعرر المنتج",
    "المنتج سعره كام"
]

for t in tests:
    print(t, "→", get_faq_answer(t))
