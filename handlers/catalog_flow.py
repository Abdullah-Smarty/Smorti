from __future__ import annotations
import re
from typing import List, Dict, Optional

from core.state import ChatState
from core.menu import category_label, category_link, categories_menu
from core.fuzzy import normalize, guess_product
from core.catalog import all_products

PRICE_NUM_RE = re.compile(r"(\d[\d,]*\.?\d*)")


def _parse_price_to_float(price_text: str) -> Optional[float]:
    if not price_text:
        return None
    m = PRICE_NUM_RE.search(price_text.replace("٫", "."))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def _cat_text(item: dict) -> str:
    return normalize(
        (item.get("category_norm") or "") + " "
        + (item.get("type_norm") or "") + " "
        + (item.get("name_en") or "") + " "
        + (item.get("base_model") or "")
    )


def _match_category(cat: str, it: dict) -> bool:
    hay = _cat_text(it)

    if cat == "tablets_reading":
        return any(k in hay for k in ["boox", "ereader", "e ink", "eink", "tablet", "قارئ", "قراءة", "بووكس", "بوكس"])

    if cat == "interactive_screens":
        include = any(k in hay for k in [
            "maxhub", "ideahub", "viewpro", "transcend", "classic series",
            "interactive flat panel", "interactive screen",
            "شاشة تفاعلية", "شاشات تفاعلية", "سبورة تفاعلية",
            "smart interactive", "sparq smart", "education interactive",
        ])
        exclude = any(k in hay for k in [
            "monitor", "monitors", "thinkvision", "lenovo thinkvision",
            "s27", "fhd", "ips", "screen replacement",
            "مونيتور", "مونيتورات", "thinkvision",
            "حافظة", "case", "cover"
        ])
        return include and not exclude

    if cat == "computer_accessories":
        return any(k in hay for k in ["keyboard", "mouse", "dock", "hub", "power bank", "مفاتيح", "كيبورد", "ماوس", "دوك", "هاب", "باور"])

    if cat == "software":
        return any(k in hay for k in ["license", "software", "subscription", "windows", "office", "ترخيص", "تراخيص", "برمجيات", "اشتراك"])

    return False


def _base_name(it: dict) -> str:
    return (it.get("base_model") or it.get("name_en") or it.get("name") or "").strip()


def _group_key(base: str) -> str:
    b = base.strip()
    tl = normalize(b)

    # BOOX series grouping
    if "boox go" in tl:
        return "BOOX Go"
    if "note air" in tl or "boox note air" in tl:
        return "BOOX Note Air"
    if "palma" in tl:
        return "BOOX Palma"
    if "note max" in tl:
        return "BOOX Note Max"
    if "boox page" in tl or "page" in tl:
        return "BOOX Page"
    if "mira" in tl:
        return "BOOX Mira"
    if "pok" in tl or "poke" in tl:
        return "BOOX Poke"

    # Screens
    if "ideahub" in tl:
        return "IdeaHub"
    if "maxhub" in tl:
        return "MAXHUB"

    return b.split(" ")[0].upper() if b else "Other"


def build_groups(state: ChatState) -> None:
    base_list = state.last_base_list or []
    group_map: Dict[str, List[str]] = {}

    for base in base_list:
        g = _group_key(base)
        group_map.setdefault(g, []).append(base)

    # sort & store
    groups = sorted(group_map.keys(), key=lambda x: x.lower())
    state.group_list = groups
    state.group_map = group_map
    state.selected_group = None


def list_category(cat: str, state: ChatState) -> str:
    items = [it for it in all_products() if _match_category(cat, it)]

    base_map: Dict[str, List[dict]] = {}
    for it in items:
        base = _base_name(it)
        if not base:
            continue
        base_map.setdefault(base, []).append(it)

    base_list = sorted(base_map.keys(), key=lambda x: x.lower())

    state.last_category = cat
    state.last_base_list = base_list
    state.last_base_map = base_map
    state.list_offset = 0
    state.catalog_level = "groups"
    state.selected_base = None

    if not base_list:
        return "ما لقينا منتجات في هذا القسم حالياً 🙂"

    build_groups(state)
    return render_groups_page(state)


def render_groups_page(state: ChatState) -> str:
    cat = state.last_category or ""
    label = category_label(cat)
    link = category_link(cat)

    groups = state.group_list or []
    if not groups:
        state.catalog_level = "models"
        return render_models_page(state)

    lines = [
        f"أكيد 😊 اختر مجموعة من: {label} 👇",
        f"وللتفاصيل الكاملة تقدر تشوف القسم بالموقع: {link}",
        "",
    ]
    for i, g in enumerate(groups, start=1):
        lines.append(f"{i}) {g}")

    lines.append("\nاكتب رقم المجموعة 👇 (للرجوع: 'رجوع' | للقائمة: 'القائمة')")
    return "\n".join(lines)


def select_group(choice: str, state: ChatState) -> str:
    groups = state.group_list or []
    if not groups:
        state.catalog_level = "models"
        return render_models_page(state)

    if not choice.isdigit():
        return "اكتب رقم صحيح من القائمة 🙂"

    idx = int(choice) - 1
    if idx < 0 or idx >= len(groups):
        return "اكتب رقم صحيح من القائمة 🙂"

    g = groups[idx]
    state.selected_group = g
    state.catalog_level = "models"
    state.list_offset = 0
    return render_models_page(state)


def render_models_page(state: ChatState) -> str:
    cat = state.last_category or ""
    label = category_label(cat)
    link = category_link(cat)

    base_map = state.last_base_map or {}
    base_list = state.last_base_list or []

    # apply group filter if selected
    if state.selected_group and state.group_map:
        base_list = state.group_map.get(state.selected_group, [])

    off = int(state.list_offset or 0)
    size = int(state.page_size or 20)
    page = base_list[off: off + size]

    title = label
    if state.selected_group:
        title = f"{label} — {state.selected_group}"

    lines = [
        f"تفضل 😊 هذا المتوفر عندنا في: {title} 👇",
        f"للمواصفات والألوان وخيارات الشحن: {link}",
        "",
    ]

    for i, base in enumerate(page, start=off + 1):
        prices = []
        for it in base_map.get(base, []):
            p = _parse_price_to_float((it.get("price") or it.get("price_raw") or "").strip())
            if p is not None:
                prices.append(p)

        if prices:
            lo, hi = min(prices), max(prices)
            price_txt = f"{lo:,.2f} - {hi:,.2f} ر.س" if lo != hi else f"{lo:,.2f} ر.س"
            lines.append(f"{i}) {base} — {price_txt}")
        else:
            lines.append(f"{i}) {base}")

    if off + size < len(base_list):
        lines.append("\nاكتب: المزيد / more")

    lines.append("اكتب رقم المنتج 👇 (للرجوع: 'رجوع' | للقائمة: 'القائمة')")
    return "\n".join(lines)


def select_model(choice: str, state: ChatState) -> str:
    base_map = state.last_base_map or {}
    base_list = state.last_base_list or []

    if state.selected_group and state.group_map:
        base_list = state.group_map.get(state.selected_group, [])

    if not base_list:
        state.catalog_level = "categories"
        return categories_menu()

    if not choice.isdigit():
        return "اكتب رقم صحيح من القائمة 🙂"

    idx = int(choice) - 1
    if idx < 0 or idx >= len(base_list):
        return "اكتب رقم صحيح من القائمة 🙂"

    base = base_list[idx]
    items = base_map.get(base, [])
    state.selected_base = base
    state.catalog_level = "detail"

    prices = []
    for it in items:
        p = _parse_price_to_float((it.get("price") or it.get("price_raw") or "").strip())
        if p is not None:
            prices.append(p)

    link = category_link(state.last_category or "")

    if prices:
        lo, hi = min(prices), max(prices)
        price_txt = f"{lo:,.2f} - {hi:,.2f} ر.س" if lo != hi else f"{lo:,.2f} ر.س"
        return (
            f"أكيد 😊 هذا المنتج اللي اخترته:\n{base}\n"
            f"السعر: {price_txt} 💰\n"
            f"للتفاصيل والمواصفات والألوان: {link}"
        )

    return (
        f"أكيد 😊 هذا المنتج اللي اخترته:\n{base}\n"
        "السعر غير متوفر حالياً 🙂\n"
        f"للتفاصيل والمواصفات والألوان: {link}"
    )


def page_more(state: ChatState) -> str:
    state.list_offset = int(state.list_offset or 0) + int(state.page_size or 20)
    return render_models_page(state)


def page_back(state: ChatState) -> str:
    # detail -> models
    if state.catalog_level == "detail":
        state.catalog_level = "models"
        state.selected_base = None
        return render_models_page(state)

    # models -> groups
    if state.catalog_level == "models":
        state.catalog_level = "groups"
        state.selected_group = None
        state.list_offset = 0
        return render_groups_page(state)

    # groups -> categories
    state.catalog_level = "categories"
    state.last_category = None
    state.last_base_list = None
    state.last_base_map = None
    state.group_list = None
    state.group_map = None
    state.selected_group = None
    state.selected_base = None
    state.list_offset = 0
    return categories_menu()
