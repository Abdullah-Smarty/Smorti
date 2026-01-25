from __future__ import annotations
from typing import Optional
from core.state import ChatState
from core.fuzzy import normalize, guess_from_choices

SHOP_LINK = "https://shop.smart.sa/ar"

KSA_KEYS = ["السعوديه", "السعودية", "داخل السعوديه", "داخل السعودية", "ksa", "saudi"]
OUTSIDE_KEYS = ["خارج", "دولي", "international", "outside"]

SHIP_KEYS = ["شحن", "توصيل", "delivery", "shipping", "ship"]

GCC_COUNTRIES = ["قطر", "الكويت", "الامارات", "الإمارات", "البحرين", "عمان", "uae", "qatar", "kuwait", "bahrain", "oman"]
KSA_CITIES_SAMPLE = ["جدة", "الرياض", "الدمام", "جازان", "جيزان", "مكة", "المدينة", "الخبر"]  # sample for fuzzy


def _looks_like_shipping(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in SHIP_KEYS)


def _contains_place(text: str) -> bool:
    t = normalize(text)
    # very loose: if message contains "الى/إلى/to" or a known country/city
    if any(x in t for x in ["الى", "إلى", "to"]):
        return True
    if any(c in t for c in GCC_COUNTRIES):
        return True
    # quick city fuzzy guess
    g = guess_from_choices(text, KSA_CITIES_SAMPLE, cutoff=0.75)
    return g is not None


def try_answer(text: str, state: ChatState) -> Optional[str]:
    t_norm = normalize(text)

    # follow-up: scope
    if state.awaiting_ship_scope:
        state.awaiting_ship_scope = False
        if any(k in t_norm for k in KSA_KEYS) or "داخل" in t_norm:
            state.awaiting_ship_place = True
            return "تمام 😊 داخل السعودية ولا يهم المدينة—بس اكتب اسم المدينة وبأكد لك."
        if any(k in t_norm for k in OUTSIDE_KEYS) or "خارج" in t_norm:
            state.awaiting_ship_place = True
            return "تمام 😊 خارج السعودية—اكتب الدولة وبأعطيك التفاصيل."
        # unclear
        state.awaiting_ship_scope = True
        return "عشان أفيدك بسرعة 😊 التوصيل داخل السعودية ولا خارج السعودية؟"

    # follow-up: place
    if state.awaiting_ship_place:
        state.awaiting_ship_place = False
        # if user gave a GCC / outside country name -> DHL
        if any(c in t_norm for c in GCC_COUNTRIES) or "دوله" in t_norm or "دولة" in t_norm:
            return (
                "نعم ✅ التوصيل خارج السعودية متوفر عبر DHL.\n"
                f"أسعار ومدة الشحن تظهر عند إنهاء الطلب في الموقع: {SHOP_LINK}"
            )
        # otherwise treat as KSA city
        guess_city = guess_from_choices(text, KSA_CITIES_SAMPLE, cutoff=0.75)
        city = guess_city or text.strip()
        return (
            f"نعم ✅ التوصيل داخل السعودية متوفر (يشمل {city}).\n"
            "نشحن عبر: RedBox / SMSA / Aramex.\n"
            f"أسعار الشحن تظهر عند إنهاء الطلب في الموقع: {SHOP_LINK}"
        )

    # main shipping intent
    if _looks_like_shipping(text):
        # if they already included a city/country, answer immediately
        if _contains_place(text):
            if any(c in t_norm for c in GCC_COUNTRIES):
                return (
                    "نعم ✅ التوصيل خارج السعودية متوفر عبر DHL.\n"
                    f"أسعار ومدة الشحن تظهر عند إنهاء الطلب في الموقع: {SHOP_LINK}"
                )
            # else KSA
            return (
                "نعم ✅ التوصيل داخل السعودية متوفر.\n"
                "نشحن عبر: RedBox / SMSA / Aramex.\n"
                f"أسعار الشحن تظهر عند إنهاء الطلب في الموقع: {SHOP_LINK}"
            )

        # otherwise ask scope
        state.awaiting_ship_scope = True
        return "أكيد 😊 التوصيل داخل السعودية ولا خارج السعودية؟"

    return None
