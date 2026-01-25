from pathlib import Path
import re

FILE = Path("chat_cli.py")
if not FILE.exists():
    print("❌ chat_cli.py غير موجود")
    raise SystemExit(1)

src = FILE.read_text(encoding="utf-8")

# 1) Add helper if missing (safe, injected near Shipping helpers header)
if "_looks_like_country" not in src:
    anchor = "# Shipping helpers"
    if anchor not in src:
        print("❌ ما لقيت عنوان Shipping helpers في الملف")
        raise SystemExit(1)

    helper = """
def _looks_like_country(t: str) -> bool:
    tl = _low(t)
    # مؤشرات أن المستخدم يقصد دولة/جهة خارج المدن
    return any(k in tl for k in [
        "الى", "إلى", "لـ", "له", "لل",
        "to", "country"
    ])
"""
    src = src.replace(anchor, anchor + "\n" + helper.strip() + "\n")

# 2) Inject guard inside pipeline_reply shipping section
# Find the shipping block start
m = re.search(r"\n\s*if\s+_is_shipping_question\(t\)\s*:\s*\n", src)
if not m:
    print("❌ ما لقيت if _is_shipping_question(t): داخل pipeline_reply")
    raise SystemExit(1)

inject_guard = """
        # لو المستخدم يذكر دولة/وجهة غير الخليج -> رفض مباشر
        country = _extract_country(t)
        if country:
            return smart_style(_shipping_reply(country))

        # إذا فيه "إلى/الى/to" ومعها كلمة (يعني غالبًا دولة) بس مو ضمن الخليج
        if _looks_like_country(t):
            return smart_style(
                "حالياً 🚫 التوصيل متوفر داخل السعودية ودول الخليج فقط.\\n"
                "ما عندنا توصيل خارجهم 🙏"
            )
"""

# We will inject AFTER the city checks (jeddah/riyadh) if they exist
# Find the first occurrence of "country = _extract_country(t)" and if exists, we won't duplicate.
if "if _looks_like_country(t):" in src:
    print("✅ التعديل موجود مسبقًا (ما فيه شي جديد)")
    raise SystemExit(0)

# Try to place it right before the first "country = _extract_country(t)" if exists
m2 = re.search(r"\n(\s*)country\s*=\s*_extract_country\(t\)\s*\n", src)
if m2:
    indent = m2.group(1)
    block = "\n".join(indent + line if line.strip() else line for line in inject_guard.strip("\n").split("\n"))
    src = src[:m2.start()] + "\n" + block + "\n" + src[m2.start():]
else:
    # fallback: inject right after the shipping if-block line
    indent = re.search(r"\n(\s*)if\s+_is_shipping_question\(t\)\s*:\s*\n", src).group(1) + "    "
    block = "\n".join(indent + line if line.strip() else line for line in inject_guard.strip("\n").split("\n"))
    insert_pos = m.end()
    src = src[:insert_pos] + block + "\n" + src[insert_pos:]

FILE.write_text(src, encoding="utf-8")

print("✅ Refactor v2 applied successfully!")
print("• Shipping: خارج السعودية/الخليج = رفض واضح")
print("• منع اعتبار الدول كمدن")
