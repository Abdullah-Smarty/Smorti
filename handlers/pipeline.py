from __future__ import annotations

from core.state import ChatState
from core.menu import categories_menu, category_from_choice, looks_like_device_request
from core.formatting import smart_style, looks_like_salam, looks_like_greeting, _low, is_number_choice

from handlers.shipping import try_answer as shipping_try
from handlers.location import try_answer as location_try
from handlers.store import try_answer as store_try
from handlers.policies import try_answer as policies_try

from handlers.catalog_flow import (
    list_category,
    select_group,
    select_model,
    page_more,
    page_back,
)

SHOP_URL = "https://shop.smart.sa/ar"


def greet_salam() -> str:
    return smart_style(
        "و عليكم السلام و رحمة الله و بركاته 🤍\n"
        "حياك الله في متجر سمارت!\n"
        "أنا سمورتي مساعدك 😊\n"
        f"متجرنا 🛒 {SHOP_URL}\n"
        "كيف أقدر أخدمك اليوم؟"
    )


def greet_normal() -> str:
    return smart_style(
        "ياهلا 😊 حياك في متجر سمارت!\n"
        "أنا سمورتي مساعدك 🤍\n"
        "وش تحب تسوي؟ (تقدر تكتب: 'القائمة' لعرض الأقسام)"
    )


def reset_catalog(state: ChatState) -> None:
    state.catalog_level = "categories"
    state.last_category = None
    state.last_base_list = None
    state.last_base_map = None
    state.group_list = None
    state.group_map = None
    state.selected_group = None
    state.selected_base = None
    state.list_offset = 0


def pipeline_reply(user_text: str, state: ChatState) -> str:
    t = (user_text or "").strip()
    if not t:
        return smart_style("حياك 😊 اكتب رسالتك وأنا حاضر.")

    tl = _low(t)

    # Commands
    if tl in {"القائمة", "menu", "categories"}:
        reset_catalog(state)
        return smart_style(categories_menu("أكيد 😊 تفضل أقسامنا:"))

    if tl in {"رجوع", "back"}:
        return smart_style(page_back(state))

    if tl in {"المزيد", "more", "التالي", "next"}:
        return smart_style(page_more(state))

    # Greetings
    if looks_like_salam(t):
        return greet_salam()
    if looks_like_greeting(t):
        return greet_normal()

    # ✅ Policies priority (fix warranty/returns)
    p = policies_try(t)
    if p:
        return smart_style(p)

    # ✅ Shipping/Location/Store priority (so they don't get stuck in catalog)
    resp = shipping_try(t, state)
    if resp:
        return smart_style(resp)

    resp = location_try(t, state)
    if resp:
        return smart_style(resp)

    resp = store_try(t, state)
    if resp:
        return smart_style(resp)

    # Device request intent -> show categories
    if looks_like_device_request(t):
        reset_catalog(state)
        return smart_style(categories_menu("أكيد 😊 تفضل الأقسام المتوفرة عندنا:"))

    # ✅ IMPORTANT: If we are already inside catalog, numbers should NOT be treated as category selection
    if state.catalog_level == "groups" and is_number_choice(t):
        return smart_style(select_group(t, state))

    if state.catalog_level in {"models", "detail"} and is_number_choice(t):
        return smart_style(select_model(t, state))

    # Category selection ONLY when at categories level
    if state.catalog_level == "categories":
        cat_choice = category_from_choice(t)
        if cat_choice:
            return smart_style(list_category(cat_choice, state))

    # inside catalog but text isn't a number
    if state.catalog_level in {"groups", "models", "detail"}:
        return smart_style("اكتب رقم من القائمة 👇 (أو 'رجوع' / 'القائمة')")

    # fallback
    return smart_style(f"ما فهمت عليك تمام 😅\nتقدر تكتب 'القائمة' أو تزور المتجر: {SHOP_URL}")
