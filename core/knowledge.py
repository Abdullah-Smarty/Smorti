from __future__ import annotations
from core.config import (
    SHOP_URL, CATEGORY_LINKS, RETURN_POLICY_URL, WARRANTY_POLICY_URL, CONTACT
)

def brand_facts() -> str:
    return f"""
- Official shop link: {SHOP_URL}
- Categories:
  - Tablets & eReaders: {CATEGORY_LINKS["tablets_readers"]}
  - Interactive Screens: {CATEGORY_LINKS["interactive_screens"]}
  - Computers & Accessories: {CATEGORY_LINKS["computers_accessories"]}
  - Software: {CATEGORY_LINKS["software"]}
- Return policy link: {RETURN_POLICY_URL}
- Warranty policy link: {WARRANTY_POLICY_URL}
- Contact:
  - WhatsApp: {CONTACT["whatsapp"]}
  - Email: {CONTACT["email"]}
""".strip()

def shipping_policy() -> str:
    return """
Shipping rules (must follow exactly):
- Inside Saudi Arabia: shipping is available to all cities/areas via RedBox / SMSA / Aramex.
- GCC countries: shipping is available.
- Outside Saudi Arabia: DHL.
- Prices and delivery time vary and are shown at checkout on the website.
If user asks for exact shipping price/time: direct them to the shop checkout link.
""".strip()

def returns_summary_ar() -> str:
    return """
ملخص سياسة الاسترجاع والاستبدال (مختصر):
- الاسترجاع/الاستبدال خلال 7 أيام من الاستلام بشرط المنتج غير مفتوح وبحالته الأصلية.
- إذا تم فتح المنتج: يُعامل كمستعمل ويقل السعر 20-30% حسب الحالة.
- المنتجات المستعملة: مسموح استبدالها خلال 30 يوم.
- الشحن على العميل، ويلزم تغليف آمن.
- بعد الفحص والموافقة: استرجاع المبلغ خلال 7 أيام عمل أو إرسال البديل حسب التوفر.
""".strip()

def warranty_summary_ar() -> str:
    return """
ملخص سياسة الضمان (مختصر):
- المنتجات الجديدة: ضمان سنتين على العيوب المصنعية.
- المنتجات المستعملة: ضمان 30 يوم على العيوب المصنعية.
- لا يشمل: سوء الاستخدام/الحوادث/الصيانة غير المعتمدة.
""".strip()
