import re
import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
TATWEEL = "\u0640"

def _norm_text(s: str) -> str:
    """Light normalization: casefold, trim, remove tatweel/diacritics, unify whitespace."""
    if s is None:
        return ""
    s = str(s).strip().casefold()
    s = s.replace(TATWEEL, "")
    s = ARABIC_DIACRITICS.sub("", s)
    # unify common Arabic letter variants (minimal, safe)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    # remove extra punctuation that breaks matching (keep + and . and - for models)
    s = re.sub(r"[^\w\s\.\+\-\/]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

@dataclass
class CatalogItem:
    name: str
    price: str
    url: str
    sku: str

class CatalogNormalizer:
    """
    Expects a CSV like:
    name,price,url,sku,aliases

    aliases can be:
    - empty
    - a single alias
    - multiple aliases separated by | or , or ; (we handle all)
    """
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.alias_to_sku: Dict[str, str] = {}
        self.sku_to_item: Dict[str, CatalogItem] = {}
        self.sku_to_aliases: Dict[str, List[str]] = {}

        self._load_csv()

    def _split_aliases(self, raw: str) -> List[str]:
        if not raw:
            return []
        # allow multiple separators
        parts = re.split(r"[|,;]+", raw)
        return [p.strip() for p in parts if p and p.strip()]

    def _load_csv(self) -> None:
        with open(self.csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {"name", "price", "url", "sku", "aliases"}
            missing = required - set((reader.fieldnames or []))
            if missing:
                raise ValueError(f"Catalog CSV missing columns: {sorted(missing)}")

            for row in reader:
                name = (row.get("name") or "").strip()
                price = (row.get("price") or "").strip()
                url = (row.get("url") or "").strip()
                sku = (row.get("sku") or "").strip()
                aliases_raw = row.get("aliases") or ""

                if not sku or not name:
                    continue

                item = CatalogItem(name=name, price=price, url=url, sku=sku)
                self.sku_to_item[sku] = item

                aliases = self._split_aliases(aliases_raw)
                # Always include the main name as an alias
                aliases = [name, *aliases]

                norm_aliases = []
                for a in aliases:
                    na = _norm_text(a)
                    if na:
                        norm_aliases.append(na)

                # store
                self.sku_to_aliases[sku] = sorted(set(norm_aliases), key=len, reverse=True)
                for na in self.sku_to_aliases[sku]:
                    # first win keeps the mapping (prevents random overrides)
                    self.alias_to_sku.setdefault(na, sku)

    def normalize_message(self, user_text: str) -> str:
        """Return normalized user text (safe to feed matching)."""
        return _norm_text(user_text)

    def match_sku(self, user_text: str) -> Optional[Tuple[str, CatalogItem]]:
        """
        Best-effort match:
        - normalize message
        - exact alias match OR alias substring hit (longer alias wins)
        """
        t = self.normalize_message(user_text)
        if not t:
            return None

        # Exact alias match
        if t in self.alias_to_sku:
            sku = self.alias_to_sku[t]
            return sku, self.sku_to_item[sku]

        # Substring hit (choose longest alias that appears)
        best_sku = None
        best_alias_len = 0
        for alias, sku in self.alias_to_sku.items():
            if alias and alias in t:
                if len(alias) > best_alias_len:
                    best_alias_len = len(alias)
                    best_sku = sku

        if best_sku:
            return best_sku, self.sku_to_item[best_sku]

        return None
