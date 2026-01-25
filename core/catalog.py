from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Iterable
import csv
import os

from core.text import normalize
from core.config import SHOP_URL

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "products_enriched.csv")


@dataclass
class Product:
    product_id: str
    name_en: str = ""
    name_ar: str = ""
    name_raw: str = ""
    brand: str = ""
    category: str = ""
    category_name_ar: str = ""
    category_link: str = ""
    series: str = ""
    price_sar: Optional[float] = None
    old_price_sar: Optional[float] = None
    availability: str = ""  # may be empty
    screen_size_in: str = ""
    display_type: str = ""
    ram_gb: str = ""
    storage_gb: str = ""
    short_desc: str = ""
    keywords: str = ""
    product_url: str = ""
    connectivity: str = ""
    item_type: str = ""


def _to_float(x: str) -> Optional[float]:
    try:
        x = (x or "").strip()
        if not x:
            return None
        return float(x)
    except Exception:
        return None


def load_products(path: str = DATA_PATH) -> List[Product]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Products CSV not found: {path}")

    out: List[Product] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = Product(
                product_id=str(row.get("product_id") or "").strip(),
                name_en=(row.get("name_en") or "").strip(),
                name_ar=(row.get("name_ar") or "").strip(),
                name_raw=(row.get("name_raw") or row.get("name") or "").strip(),
                brand=(row.get("brand") or "").strip().lower(),
                category=(row.get("category") or "").strip().lower(),
                category_name_ar=(row.get("category_name_ar") or "").strip(),
                category_link=(row.get("category_link") or "").strip(),
                series=(row.get("series") or "").strip(),
                price_sar=_to_float(row.get("price_sar") or ""),
                old_price_sar=_to_float(row.get("old_price_sar") or ""),
                availability=(row.get("availability") or "").strip(),
                screen_size_in=(row.get("screen_size_in") or "").strip(),
                display_type=(row.get("display_type") or "").strip(),
                ram_gb=(row.get("ram_gb") or "").strip(),
                storage_gb=(row.get("storage_gb") or "").strip(),
                short_desc=(row.get("short_desc") or "").strip(),
                keywords=(row.get("keywords") or "").strip(),
                product_url=(row.get("product_url") or "").strip(),
                connectivity=(row.get("connectivity") or "").strip(),
                item_type=(row.get("item_type") or "").strip(),
            )
            # fallback link
            if not p.product_url:
                p.product_url = ""
            if not p.category_link:
                p.category_link = SHOP_URL
            out.append(p)
    return out


def _haystack(p: Product) -> str:
    # Strong match fields: Arabic + English + keywords + desc
    parts = [
        p.name_en, p.name_ar, p.name_raw,
        p.series, p.brand, p.category_name_ar,
        p.keywords, p.short_desc,
    ]
    return normalize(" ".join([x for x in parts if x]))


def search_products(
    query: str,
    products: List[Product],
    limit: int = 10,
    brand_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    series_hint: Optional[str] = None,
) -> List[Product]:
    qn = normalize(query)
    if len(qn) < 2:
        return []

    # avoid matching greetings/smalltalk
    if qn in {"سلام", "السلام", "هلا", "مرحبا", "اهلا", "هاي", "hello", "hi"}:
        return []

    scored: List[tuple[int, Product]] = []
    for p in products:
        if brand_filter and p.brand and brand_filter != p.brand:
            continue
        if category_filter and p.category and category_filter != p.category:
            continue
        if series_hint and p.series and series_hint.lower() not in p.series.lower():
            # still allow if name matches strongly
            pass

        h = _haystack(p)

        # simple scoring (no difflib here to keep it fast/steady)
        score = 0
        if qn in h:
            score += 6
        # split tokens match
        toks = [t for t in qn.split() if len(t) >= 2]
        hit = sum(1 for t in toks if t in h)
        score += hit

        # series boost
        if series_hint and p.series and series_hint.lower() in p.series.lower():
            score += 2

        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


def group_products(hits: List[Product], lang: str = "ar") -> Dict[str, List[Product]]:
    groups: Dict[str, List[Product]] = {}
    for p in hits:
        key = (p.series or "").strip()
        if not key:
            # fallback grouping by name prefix
            nm = p.name_ar if (lang == "ar" and p.name_ar) else (p.name_en or p.name_raw)
            nm = (nm or "").strip()
            key = nm.split("|")[0].strip() if nm else "Other"
        groups.setdefault(key, []).append(p)
    return groups
