from __future__ import annotations
from typing import Optional
from core.state import ChatState
from core.fuzzy import normalize, guess_from_choices

JEDDAH_MAP = "https://maps.app.goo.gl/PhENEtgDbGsace158"
RIYADH_MAP = "https://maps.app.goo.gl/Hq7wrDydx3jQN2bE9n"

BRANCH_CITIES = ["جدة", "الرياض"]


def try_answer(text: str, state: ChatState) -> Optional[str]:
    t = normalize(text)

    wants_location = any(k in t for k in ["موقع", "لوكيشن", "location", "وين موقعكم", "فين موقعكم", "عنوان", "address"])

    # If user is answering the follow-up city question
    if state.awaiting_location_city and not wants_location:
        guessed = guess_from_choices(t, BRANCH_CITIES, cutoff=0.75)
        if guessed:
            return _branch_reply(guessed, state)
        # If unknown city while awaiting, keep it simple
        return (
            "حاليًا عندنا فرعين: جدة والرياض.\n"
            "اكتب (جدة) أو (الرياض) وبعطيك الرابط والعنوان 😊"
        )

    # Direct city mention (with or without 'location' words)
    if "جده" in t or "جدة" in t:
        return _branch_reply("جدة", state)
    if "الرياض" in t or "رياض" in t:
        return _branch_reply("الرياض", state)

    # Asked for location but didn’t specify a branch
    if wants_location:
        state.awaiting_location_city = True
        return "أكيد 😊 أي فرع تقصد؟ جدة ولا الرياض؟ اكتب المدينة وبعطيك الرابط والعنوان."

    return None


def _branch_reply(city: str, state: ChatState) -> str:
    state.awaiting_location_city = False
    if city == "جدة":
        return (
            "تنورنا 🤍 هذا موقع فرع جدة:\n"
            f"{JEDDAH_MAP}\n"
            "Albassam Business Center, Office #43, Fourth Floor, Jeddah 22234"
        )
    return (
        "حياك 🤍 هذا موقع فرع الرياض:\n"
        f"{RIYADH_MAP}\n"
        "7236، 4435 2nd Floor, Alyasmin, Office 25, Riyadh 13326"
    )
