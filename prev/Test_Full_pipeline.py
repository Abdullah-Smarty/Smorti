# Test_Full_pipeline.py
from rules import rule_based_reply
from intent import is_price_question
from core.catalog import find_products
from faq_engine import get_faq_answer
from ai_fallback import ai_reply, ai_clarify

import re


# ----------------------------
# Helpers
# ----------------------------
def _low(s: str) -> str:
    return (s or "").lower()

def _tokenize(t: str) -> list[str]:
    # عربي/إنجليزي/أرقام/نقطة للأحجام مثل 10.3
    return re.findall(r"[a-z\u0600-\u06FF0-9.]+", (t or "").lower())

def _has_product_hint(t: str) -> bool:
    """
    True if message looks like it contains a product/model hint.
    We use this to avoid random catalog suggestions for ultra-generic price questions.
    """
    tl = _low(t)
    toks = _tokenize(tl)

    # any clear brand mention
    if _mentions_boox(t) or _mentions_lenovo(t) or _mentions_logitech(t):
        return True

    # any numeric token (models/sizes) like 24, 65, 10.3, 86, 13.3, gen2...
    if any(re.fullmatch(r"\d+(\.\d+)?", tok) for tok in toks):
        return True

    # common model-ish keywords (expand as you like)
    modelish = {
        "go", "tab", "note", "air", "palma", "page",
        "thinkvision", "mk345", "k580", "h390",
        "magsafe", "gen2", "gen", "pro", "ultra", "mini", "max",
        "boox", "logitech", "lenovo",
    }
    if any(tok in modelish for tok in toks):
        return True

    # two meaningful words (len>=3) is usually enough to try catalog
    meaningful = [tok for tok in toks if len(tok) >= 3]
    return len(meaningful) >= 2

def _mentions_boox(t: str) -> bool:
    tl = _low(t)
    return ("بووكس" in t) or ("بوكس" in t) or ("boox" in tl)

def _mentions_lenovo(t: str) -> bool:
    tl = _low(t)
    return ("لينوفو" in t) or ("lenovo" in tl) or ("thinkvision" in tl)

def _mentions_logitech(t: str) -> bool:
    tl = _low(t)
    return ("لوجيتك" in t) or ("logitech" in tl)

def _is_case_query(t: str) -> bool:
    tl = _low(t)
    return any(w in t for w in ["كفر", "حافظه", "حافظة", "جراب"]) or any(w in tl for w in ["case", "cover"])

def _is_keyboard_query(t: str) -> bool:
    tl = _low(t)
    return any(w in t for w in ["كيبورد", "لوحة مفاتيح", "لوحه مفاتيح"]) or "keyboard" in tl

def _is_screen_query(t: str) -> bool:
    tl = _low(t)
    return any(w in t for w in ["شاشة", "شاشه", "مونيتور"]) or any(w in tl for w in ["screen", "monitor", "interactive"])

def _is_headset_query(t: str) -> bool:
    tl = _low(t)
    return any(w in t for w in ["سماعة", "سماعه", "هيدسيت"]) or "headset" in tl

def _is_dock_query(t: str) -> bool:
    tl = _low(t)
    return ("dock" in tl) or ("docking" in tl) or ("دوكينق" in t) or ("هاب" in t) or ("hub" in tl)

def _is_powerbank_query(t: str) -> bool:
    tl = _low(t)
    return ("باور" in t) or ("power bank" in tl) or ("باوربانك" in t) or ("شاحن متنقل" in t) or ("magsafe" in tl) or ("mag safe" in tl)

def _is_tips_query(t: str) -> bool:
    tl = _low(t)
    return any(w in t for w in ["رؤوس", "سنون", "سنون القلم", "رؤوس القلم"]) or any(w in tl for w in ["tips", "nibs"])

def _format_options(hits: list[dict], n: int = 3, ask: str = "اختر رقم أو اكتب الاسم.") -> str:
    top = hits[:n]
    lines = [f"{i+1}) {h['name']} — {h['price_raw']}" for i, h in enumerate(top)]
    return "\n".join(lines) + f"\n\n{ask}"

def _keep_brand_consistent(user_text: str, hits: list[dict]) -> list[dict]:
    if _mentions_boox(user_text):
        filtered = [h for h in hits if "boox" in _low(h["name"])]
        return filtered or hits
    if _mentions_lenovo(user_text):
        filtered = [h for h in hits if "lenovo" in _low(h["name"]) or "thinkvision" in _low(h["name"])]
        return filtered or hits
    if _mentions_logitech(user_text):
        filtered = [h for h in hits if "logitech" in _low(h["name"])]
        return filtered or hits
    return hits

def _split_devices_and_accessories(hits: list[dict]) -> tuple[list[dict], list[dict]]:
    accessories_kw = ["case", "cover", "keyboard cover", "stylus", "tips", "warranty"]
    devices, acc = [], []
    for h in hits:
        nm = _low(h["name"])
        if any(k in nm for k in accessories_kw):
            acc.append(h)
        else:
            devices.append(h)
    return devices, acc

def _pick_best(hits: list[dict]) -> dict | None:
    return hits[0] if hits else None


# ----------------------------
# Catalog reply
# ----------------------------
def catalog_reply(user_text: str) -> str | None:
    hits = find_products(user_text, limit=12)
    if not hits:
        return None

    hits = _keep_brand_consistent(user_text, hits)

    # Tips (pen nibs)
    if _is_tips_query(user_text):
        tips = [h for h in hits if "tips" in _low(h["name"]) or h.get("type") == "tips"]
        if tips:
            best = _pick_best(tips)
            return f"{best['name']}\nالسعر: {best['price_raw']}"
        return None

    # Powerbank
    if _is_powerbank_query(user_text):
        pb = [h for h in hits if "power bank" in _low(h["name"]) or "magsafe" in _low(h["name"])]
        if pb:
            best = _pick_best(pb)
            return f"{best['name']}\nالسعر: {best['price_raw']}"
        return "حالياً ما لقيت باور بنك MagSafe في القائمة. تقدر ترسل اسم المنتج أو رابط/صورة لو متوفر عندك."

    # Screen category
    if _is_screen_query(user_text):
        screens = [h for h in hits if any(x in _low(h["name"]) for x in ["screen", "monitor", "interactive"]) or h.get("type") == "screen"]
        screens = _keep_brand_consistent(user_text, screens)
        if not screens:
            return None
        if len(screens) == 1:
            h = screens[0]
            return f"{h['name']}\nالسعر: {h['price_raw']}"
        return "هذي الشاشات/المونيتورات المتوفرة عندنا 👇\n" + _format_options(
            screens, n=min(5, len(screens)), ask="أي موديل/مقاس تقصد؟ اختر رقم أو اكتب الاسم."
        )

    # Headset category
    if _is_headset_query(user_text):
        hs = [h for h in hits if ("headset" in _low(h["name"])) or h.get("type") == "headset"]
        hs = _keep_brand_consistent(user_text, hs)
        if not hs:
            return None
        if len(hs) == 1:
            h = hs[0]
            return f"{h['name']}\nالسعر: {h['price_raw']}"
        return "هذي السماعات المتوفرة عندنا 👇\n" + _format_options(hs, n=min(3, len(hs)))

    # Keyboard category
    if _is_keyboard_query(user_text):
        kb = [h for h in hits if ("keyboard" in _low(h["name"])) or h.get("type") == "keyboard"]
        kb = _keep_brand_consistent(user_text, kb)
        if not kb:
            return "عندنا كيبوردات، بس عطِني اسم الموديل اللي تقصده (مثل K580 / MK345 / Tab Ultra Keyboard Cover)."
        if len(kb) == 1:
            h = kb[0]
            return f"{h['name']}\nالسعر: {h['price_raw']}"
        return "هذي الكيبوردات المتوفرة عندنا 👇\n" + _format_options(
            kb, n=min(5, len(kb)), ask="لأي جهاز/موديل تحتاجه؟ اختر رقم أو اكتب الاسم."
        )

    # Case category
    if _is_case_query(user_text):
        cases = [h for h in hits if any(x in _low(h["name"]) for x in ["case", "cover"]) or h.get("type") == "case"]
        cases = _keep_brand_consistent(user_text, cases)
        if not cases:
            return "أكيد 👍 كفر لأي جهاز/موديل؟ اكتب الموديل (مثل Go 7 / Note Air5) وبعطيك سعر الكفر المناسب."
        if len(cases) == 1:
            h = cases[0]
            return f"{h['name']}\nالسعر: {h['price_raw']}"
        return "أكيد 👍 كفر لأي جهاز/موديل؟ هذي بعض الكفرات المتوفرة عندنا:\n" + _format_options(
            cases, n=min(5, len(cases)), ask="اذكر موديل جهازك (مثلاً Go 7 / Note Air5) أو اختر رقم."
        )

    # Normal device-first answering
    devices, acc = _split_devices_and_accessories(hits)
    primary_pool = devices if devices else hits
    best = _pick_best(primary_pool)
    if not best:
        return None

    if best.get("score", 0) >= 86 and best.get("price_raw"):
        msg = f"{best['name']}\nالسعر: {best['price_raw']}"

        sugg = [h for h in devices if h["name"] != best["name"]][:2]
        if sugg:
            msg += "\n\nممكن أيضاً يعجبك:\n" + "\n".join([f"- {h['name']} — {h['price_raw']}" for h in sugg])

        rel_acc = []
        bn = _low(best["name"])
        for h in acc:
            hn = _low(h["name"])
            if ("boox" in bn and "boox" in hn) and any(k in hn for k in ["case", "cover", "keyboard", "tips", "stylus"]):
                rel_acc.append(h)
        rel_acc = rel_acc[:2]
        if rel_acc:
            msg += "\n\nاكسسوارات متوفرة:\n" + "\n".join([f"- {h['name']} — {h['price_raw']}" for h in rel_acc])

        return msg

    pool = primary_pool[:5]
    if len(pool) == 1:
        h = pool[0]
        return f"{h['name']}\nالسعر: {h['price_raw']}"
    return "لقيت أكثر من خيار قريب 👇\n" + _format_options(pool, n=min(3, len(pool)))


# ----------------------------
# Pipeline (FINAL: block only ultra-generic)
# ----------------------------
def pipeline_reply(user_text: str) -> str:
    # 0) RULE
    r = rule_based_reply(user_text)
    if r is not None and str(r).strip() and str(r).strip().lower() != "none":
        return f"[RULE]\n{r}"

    # 1) PRICE FLOW
    if is_price_question(user_text):
        is_category = any([
            _is_case_query(user_text),
            _is_keyboard_query(user_text),
            _is_screen_query(user_text),
            _is_headset_query(user_text),
            _is_dock_query(user_text),
            _is_powerbank_query(user_text),
            _is_tips_query(user_text),
        ])

        # If it's ultra-generic AND not a category AND no product hint -> don't search catalog
        if (not is_category) and (not _has_product_hint(user_text)):
            return (
                "[RULE]\n"
                "حياك في متجر سمارت 👋\n"
                "اكتب اسم الجهاز/الموديل اللي تقصده (أو ارسل صورة) وبعطيك السعر والتوفر فورًا 👍"
            )

        cr = catalog_reply(user_text)
        if cr:
            return f"[CATALOG]\n{cr}"

        topic = (
            "case" if _is_case_query(user_text)
            else "keyboard" if _is_keyboard_query(user_text)
            else "screen" if _is_screen_query(user_text)
            else "headset" if _is_headset_query(user_text)
            else "dock" if _is_dock_query(user_text)
            else "powerbank" if _is_powerbank_query(user_text)
            else "tips" if _is_tips_query(user_text)
            else "product"
        )
        return f"[AI]\n{ai_clarify(user_text, topic_hint=topic)}"

    # 2) FAQ (non-price)
    a = get_faq_answer(user_text)
    if a:
        a = a.strip().splitlines()[0].strip()
        return f"[FAQ]\n{a}"

    # 3) AI
    return f"[AI]\n{ai_reply(user_text)}"


def main():
    tests = [
        # ultra-generic
        "بكم؟", "السعر؟", "سعره؟", "كم؟", "كم سعر المنتج؟",

        # boox devices
        "سعر بووكس نوت اير 4 سي",
        "سعر بووكس نوت اير5 سي",
        "كم سعر نوت ماكس",
        "سعر تاب اكس سي",
        "سعر tab mini c",
        "بكم go 10.3",
        "بكم go 6",
        "سعر جو 7 ملون",
        "سعر جو 7 ابيض واسود",

        # accessories & categories
        "بكم الكفر؟",
        "سعر الكفر",
        "سعر كفر جو 7",
        "سعر رؤوس القلم",
        "بكم سنون القلم",
        "سعر كيبورد بووكس",
        "سعر الكيبورد بوكس",

        # non-boox items
        "سعر باور بنك magsafe",
        "سعر docking station 15 in 1",
        "سعر logitech k580",
        "بكم mk345",
        "سعر سماعة h390",
        "كم سعر شاشة لينوفو 24",
        "سعر thinkvision 24",
    ]

    print("=== Pipeline Test (RULE → CATALOG → FAQ → AI) ===\n")
    for q in tests:
        print("User:", q)
        print("Bot :", pipeline_reply(q))
        print("-" * 60)
    print("\n✅ Finished pipeline test.")


if __name__ == "__main__":
    main()
